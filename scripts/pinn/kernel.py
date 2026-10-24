"""PINN del núcleo de transporte (función de Green) de la ecuación de advección–difusión 2D.

Por qué un núcleo: con un viento uniforme por hora (el mismo supuesto de la inversión lineal en modo
"domain"), la ecuación es lineal e invariante ante traslaciones y rotaciones. La columna que deja una
fuente en un receptor solo depende de la posición relativa en el marco del viento (a = a lo largo,
c = transversal) y de la rapidez. Basta entonces con que la red aprenda UNA pluma, y el campo de
cualquier inventario se obtiene sumando plumas. La red se entrena solo con física (residuo de la
ecuación + condiciones de frontera); los datos entran después, en invert.py.

Ecuación (columna G en g/m² por 1 g/s, marco del viento):
    |u| ∂G/∂a − K (∂²G/∂a² + ∂²G/∂c²) + G/τ = δσ(a, c)
con K = κ|u| (la difusión representa el serpenteo del viento: κ = 1,500 m reproduce el ancho de la
pluma con σθ = 30° a ~10 km) y τ la vida media de NOₓ (pérdida química + ventilación).
Adimensional con L = 10 km, G = F / (|u| L):
    ∂F/∂A − ε ∇²F + γ F = δ̂(A, C),  ε = κ/L = 0.15,  γ = L / (|u| τ)
γ es la única entrada física de la red: así τ y la rapidez se cambian sin reentrenar.
δ̂ es una gaussiana de masa 1 con σ = 1.5 km (fuente suavizada; el modelo no resuelve < 1.5 km).

Validación: para ε, γ constantes hay solución exacta (núcleo de Bessel K₀), convolucionada con la
gaussiana por FFT. Se compara la red contra ella en varios γ.

Uso: .venv/bin/python scripts/pinn/kernel.py [--steps 6000]
Salidas: data/processed/pinn/kernel.pt, kernel_table.npz, kernel_validation.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from scipy.signal import fftconvolve
from scipy.special import k0

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/pinn"
L = 10_000.0          # m
KAPPA = 1_500.0       # m, K = κ|u|
EPS = KAPPA / L
SIG = 0.15            # σ de la fuente suavizada (1.5 km)
A_RANGE = (-1.0, 5.0)  # −10 a 50 km a lo largo del viento
C_MAX = 4.0           # ±40 km transversal
G_RANGE = (0.03, 0.75)  # γ: τ = 4–12 h con |u| = 1–6 m/s
torch.set_num_threads(1)


class Kernel(torch.nn.Module):
    """F(A, C, γ) = exp(red(A, C², log γ)); simétrica en C y positiva."""

    def __init__(self, width=64, depth=4):
        super().__init__()
        layers, d = [], 3
        for _ in range(depth):
            layers += [torch.nn.Linear(d, width), torch.nn.Tanh()]
            d = width
        layers.append(torch.nn.Linear(d, 1))
        self.net = torch.nn.Sequential(*layers)

    def forward(self, A, C, g):
        lg = (torch.log(g) - np.log(0.15)) / 1.0
        z = torch.stack([(A - 2) / 3, C ** 2 / 4 - 1, lg], -1)
        return torch.exp(self.net(z).squeeze(-1))


def source(A, C):
    return torch.exp(-(A ** 2 + C ** 2) / (2 * SIG ** 2)) / (2 * np.pi * SIG ** 2)


def residual(model, A, C, g):
    A = A.requires_grad_(True)
    C = C.requires_grad_(True)
    F = model(A, C, g)
    FA, FC = torch.autograd.grad(F.sum(), (A, C), create_graph=True)
    FAA = torch.autograd.grad(FA.sum(), A, create_graph=True)[0]
    FCC = torch.autograd.grad(FC.sum(), C, create_graph=True)[0]
    return FA - EPS * (FAA + FCC) + g * F - source(A, C), F


def sample(n, gen):
    """Puntos de colocación: 40 % cerca de la fuente, 30 % en la pluma, 30 % uniformes."""
    n1, n2 = int(0.4 * n), int(0.3 * n)
    n3 = n - n1 - n2
    A = torch.cat([torch.randn(n1, generator=gen) * 0.35,
                   torch.rand(n2, generator=gen) * 5.0,
                   A_RANGE[0] + torch.rand(n3, generator=gen) * (A_RANGE[1] - A_RANGE[0])])
    C = torch.cat([torch.randn(n1, generator=gen) * 0.35,
                   torch.randn(n2, generator=gen) * (0.2 + 0.5 * torch.sqrt(A[n1:n1 + n2].clamp(min=0) + 0.1)),
                   (torch.rand(n3, generator=gen) * 2 - 1) * C_MAX])
    A, C = A.clamp(*A_RANGE), C.clamp(-C_MAX, C_MAX)
    g = torch.exp(np.log(G_RANGE[0]) + torch.rand(n, generator=gen) * np.log(G_RANGE[1] / G_RANGE[0]))
    return A, C, g


def boundary(n, gen):
    """F ≈ 0 a 10 km contra el viento y a 40 km de lado (la salida a 50 km queda libre)."""
    t = torch.rand(n, generator=gen)
    side = torch.rand(n, generator=gen) < 0.5
    A = torch.where(side, torch.full_like(t, A_RANGE[0]), A_RANGE[0] + t * (A_RANGE[1] - A_RANGE[0]))
    C = torch.where(side, (t * 2 - 1) * C_MAX, torch.sign(torch.rand(n, generator=gen) - 0.5) * C_MAX)
    g = torch.exp(np.log(G_RANGE[0]) + torch.rand(n, generator=gen) * np.log(G_RANGE[1] / G_RANGE[0]))
    return A, C, g


def pde_loss(model, gen, n=2048):
    A, C, g = sample(n, gen)
    R, F = residual(model, A, C, g)
    # escala relativa: el error importa en proporción al valor (la cola lejana suma muchas celdas)
    w = 1.0 / (F.detach() + 0.05)
    Ab, Cb, gb = boundary(512, gen)
    return (w * R).pow(2).mean() + 10 * model(Ab, Cb, gb).pow(2).mean()


def exact(gamma, h=0.02):
    """Solución exacta (K₀) convolucionada con la fuente gaussiana, en una malla con paso h."""
    a = np.arange(A_RANGE[0] - 1, A_RANGE[1] + 1 + h / 2, h)
    c = np.arange(-C_MAX - 1, C_MAX + 1 + h / 2, h)
    AA, CC = np.meshgrid(a, c, indexing="ij")
    r = np.maximum(np.hypot(AA, CC), h / 4)
    lam = np.sqrt(1 / (4 * EPS ** 2) + gamma / EPS)
    G0 = np.exp(AA / (2 * EPS)) * k0(lam * r) / (2 * np.pi * EPS)
    # celda del origen: integral de la singularidad logarítmica (aprox.) para conservar masa
    ka = np.arange(-4 * SIG, 4 * SIG + h / 2, h)
    KA, KC = np.meshgrid(ka, ka, indexing="ij")
    src = np.exp(-(KA ** 2 + KC ** 2) / (2 * SIG ** 2))
    src /= src.sum()
    F = fftconvolve(G0, src, mode="same")
    return a, c, F


def validate(model):
    res = {}
    for gamma in (0.04, 0.1, 0.25, 0.6):
        a, c, F = exact(gamma)
        m = (a >= -0.5) & (a <= 4.0)
        n = np.abs(c) <= 2.5
        AA, CC = np.meshgrid(a[m][::5], c[n][::5], indexing="ij")
        Fe = F[np.ix_(m, n)][::5, ::5]
        with torch.no_grad():
            Fp = model(torch.tensor(AA.ravel(), dtype=torch.float32), torch.tensor(CC.ravel(), dtype=torch.float32),
                       torch.full((AA.size,), gamma)).numpy().reshape(AA.shape)
        big = Fe > 0.05 * Fe.max()
        rel = np.abs(Fp - Fe)[big] / Fe[big]
        # error integrado sobre la pluma (lo que pesa al sumar celdas): masa en la ventana
        res[f"{gamma}"] = {"err_rel_mediano": float(np.median(rel)), "err_rel_p90": float(np.percentile(rel, 90)),
                           "err_masa": float(Fp.sum() / Fe.sum() - 1),
                           "centro_a_5km": float(Fp[np.argmin(np.abs(AA[:, 0] - 0.5)), np.argmin(np.abs(CC[0]))]),
                           "exacto_a_5km": float(Fe[np.argmin(np.abs(AA[:, 0] - 0.5)), np.argmin(np.abs(CC[0]))]),
                           "centro_a_20km": float(Fp[np.argmin(np.abs(AA[:, 0] - 2.0)), np.argmin(np.abs(CC[0]))]),
                           "exacto_a_20km": float(Fe[np.argmin(np.abs(AA[:, 0] - 2.0)), np.argmin(np.abs(CC[0]))])}
    return res


def table(model):
    """Tabla F(A, C, γ) para evaluación rápida (interpolación bilineal en A, C y lineal en log γ)."""
    a = np.arange(A_RANGE[0], A_RANGE[1] + 1e-9, 0.02)
    c = np.arange(0, C_MAX + 1e-9, 0.02)
    gs = np.exp(np.linspace(np.log(G_RANGE[0]), np.log(G_RANGE[1]), 16))
    AA, CC = np.meshgrid(a, c, indexing="ij")
    T = np.empty((len(gs), len(a), len(c)), dtype=np.float32)
    with torch.no_grad():
        for i, g in enumerate(gs):
            T[i] = model(torch.tensor(AA.ravel(), dtype=torch.float32), torch.tensor(CC.ravel(), dtype=torch.float32),
                         torch.full((AA.size,), float(g))).numpy().reshape(AA.shape)
    np.savez_compressed(OUT / "kernel_table.npz", a=a, c=c, g=gs, T=T)


def train(steps, seed=0):
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    model = Kernel()
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps, eta_min=2e-5)
    log = []
    t0 = time.time()
    for k in range(steps):
        opt.zero_grad()
        loss = pde_loss(model, gen)
        loss.backward()
        opt.step()
        sched.step()
        if k % 100 == 0 or k == steps - 1:
            log.append((k, loss.item(), time.time() - t0))
            print(f"paso {k:5d}  pérdida {loss.item():.3e}  {time.time() - t0:.0f} s", flush=True)
    return model, log, time.time() - t0


def refine(model, rounds, iters=60, n=6000, seed=1):
    """L-BFGS sobre puntos fijos, renovados en cada ronda (Adam se estanca en ~1e-2)."""
    gen = torch.Generator().manual_seed(seed)
    log, t0 = [], time.time()
    for r in range(rounds):
        A, C, g = sample(n, gen)
        Ab, Cb, gb = boundary(1024, gen)
        opt = torch.optim.LBFGS(model.parameters(), lr=1.0, max_iter=iters, history_size=50,
                                line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            R, F = residual(model, A.clone(), C.clone(), g)
            loss = ((R / (F.detach() + 0.05)) ** 2).mean() + 10 * model(Ab, Cb, gb).pow(2).mean()
            loss.backward()
            return loss

        loss = opt.step(closure)
        log.append((r, loss.item(), time.time() - t0))
        print(f"L-BFGS ronda {r:3d}  pérdida {loss.item():.3e}  {time.time() - t0:.0f} s", flush=True)
    return log, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--lbfgs", type=int, default=0, help="rondas de L-BFGS después de Adam")
    ap.add_argument("--resume", help="punto de partida (.pt); omite Adam")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.resume:
        model = Kernel()
        model.load_state_dict(torch.load(a.resume))
        prev = json.load(open(OUT / "kernel_validation_adam3000.json"))
        log, secs = prev["log"], prev["segundos"]
    else:
        model, log, secs = train(a.steps)
    if a.lbfgs:
        lb, s2 = refine(model, a.lbfgs)
        log, secs = log + [("lbfgs",) + t for t in lb], secs + s2
    torch.save(model.state_dict(), OUT / "kernel.pt")
    val = validate(model)
    table(model)
    json.dump({"pasos_adam": a.steps, "rondas_lbfgs": a.lbfgs, "segundos": secs, "log": log, "validacion": val,
               "parametros": {"L_m": L, "kappa_m": KAPPA, "sigma_fuente_km": SIG * L / 1000}},
              open(OUT / "kernel_validation.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(val, indent=1))


def load():
    model = Kernel()
    model.load_state_dict(torch.load(OUT / "kernel.pt"))
    model.eval()
    return model


if __name__ == "__main__":
    main()
