"""Hipótesis de pluma fresca para las centrales (reports/centrales_generacion.md).

La inversión deja a Valle de México (Acolman) en ~300 t/año frente a un a priori de 1,600 ± 650 (Climate TRACE).
Hipótesis: el jacobiano de TEMPO convierte NOₓ → NO₂ con un solo cociente urbano (NO₂/NOₓ de la tarde en
estaciones, ~0.82) también para la pluma fresca de la central, que sale casi toda como NO. Si cerca de la chimenea
el NO₂ real es menor, el modelo necesita menos emisión para explicar la columna y subestima la central.

Cociente NO₂/NOₓ de la pluma de cada central en cada píxel TEMPO (solo columnas de las centrales; las estaciones
miden NOₓ y no cambian; vial, aeropuertos y fondo conservan el cociente urbano):
  - r0 = 0.10: NO₂/NOₓ en chimenea de un ciclo combinado de gas (típico 0.05–0.15; el 0.5 de EPA es conservador
    para normativa, no realista).
  - req = cociente urbano de la tarde (equilibrio fotoestacionario al que tiende la pluma).
  - OLM (método de ozono limitante de EPA): NO₂ = r0·NOₓ + min((req − r0)·NOₓ, O₃). La pluma solo puede convertir
    tanto NO como O₃ de fondo le entra. NOₓ es la concentración de la pluma instantánea (sin meandro del viento;
    Briggs urbano B, mezcla vertical limitada por la capa límite) en el punto del eje a la distancia del píxel, con
    la emisión a priori de la central: es una cota superior de la concentración, así que el efecto es máximo.
    O₃ = mediana horaria de las estaciones SIMAT. La cinética NO + O₃ (τ ≈ 1 min con 50 ppb) se ignora.
  - "lenta": además, conversión limitada por la entrada de aire ambiente, req − (req − r0)·exp(−t/20 min),
    con t = distancia / viento. Cota alta de la literatura para plumas de centrales de día.
  - "extrema": 0.25 en todo el dominio. No es física: dice cuánto podría subir la central si todo el efecto fuera real.

Corridas: nov–dic 2023, viento del dominio, σθ = 30°, industria agrupada en el fondo + estaciones extra (la mejor
configuración de base_sigma30.md), a priori corregidos (Valle 1,600 ± 650, Nonoalco 100 ± 100) y débiles.
Gemelo: emisiones "verdaderas" = a posteriori real con Valle 1,600 y Nonoalco 100, generadas con la pluma fresca,
invertidas con el cociente uniforme y con el de pluma fresca.

Uso: .venv/bin/python scripts/centrales_pluma_fresca.py
Salida: reports/centrales_pluma_fresca_2023-11-01_2023-12-31.md (tablas; el análisis va en centrales_generacion.md)
"""
from pathlib import Path

import numpy as np
import pandas as pd

import feasibility_linear as fl
import improve_real as ir
import puff
import real_check_linear as rcl
from centrales_prior_real import PRIORS, set_priors

ROOT = Path(__file__).resolve().parents[1]
START, END = "2023-11-01", "2023-12-31"
R0 = 0.10
TAU_SLOW = 20 * 60.0   # s
CENTRALES = ("Valle de México", "Nonoalco")
VARIANTS = {
    "uniforme": "cociente urbano también para las centrales (actual)",
    "olm": "ozono limitante, pluma instantánea",
    "lenta": "ozono limitante + conversión lenta (τ = 20 min)",
    "extrema": "0.25 fijo (cota no física)",
}
ORIG_JAC = rcl.jacobian_hour
rng = np.random.default_rng(11)


def load_o3():
    df = pd.read_csv(ROOT / "data/raw/simat/contaminantes_2023.csv.gz", skiprows=9, compression="zip")
    o = df[df.id_parameter == "O3"].copy()
    o["utc"] = pd.to_datetime(o.date, format="mixed") + pd.Timedelta(hours=6)
    o["h"] = o.utc - pd.Timedelta(hours=1)  # SIMAT etiqueta al final de la hora
    return o.groupby("h").value.median()


O3 = load_o3()
STATE = {"variant": "uniforme", "q": {}}  # q: emisión (t/año) de cada central usada para la concentración OLM
DIAG = []                                  # (variante, central, cociente medio ponderado por K)


def fresh_ratio(variant, along, cross, sp, pbl_h, q_tpy, o3, req):
    if variant == "extrema":
        return np.full(along.shape, 0.25)
    a = np.maximum(along, 300.0)
    sy = 0.32 * a / np.sqrt(1 + 0.0004 * a)          # sin meandro: pluma instantánea
    sz = 0.24 * a * np.sqrt(1 + 0.001 * a)
    zeff = np.minimum(np.sqrt(np.pi / 2) * sz, pbl_h)
    c = q_tpy * fl.T_PER_YR_TO_GS / (np.sqrt(2 * np.pi) * sy * sp * zeff) * fl.PPB_PER_GM3  # ppb en el eje
    r = np.minimum(req, R0 + o3 / np.maximum(c, 1e-9))
    if variant == "lenta":
        r = np.minimum(r, req - (req - R0) * np.exp(-along / sp / TAU_SLOW))
    return r


def jac(h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    blocks = ORIG_JAC(h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio)
    STATE["ratio"] = ratio
    v = STATE["variant"]
    if v == "uniforme" or callable(uv):
        return blocks
    u, w = uv
    mag = np.hypot(u, w)
    sp, ex, ey = max(mag, fl.U_MIN), u / max(mag, 1e-6), w / max(mag, 1e-6)
    o3 = O3.get(h, O3.median())
    out = []
    for kind, K in blocks:
        if kind == "tp":
            K = K.copy()
            for key in CENTRALES:
                j = int(np.flatnonzero(cand.nombre.str.contains(key).values)[0])
                s = cand.geometry.iloc[j]
                dx, dy = px_h.x.values - s.x, px_h.y.values - s.y
                along, cross = dx * ex + dy * ey, -dx * ey + dy * ex
                r = fresh_ratio(v, along, cross, sp, pbl_h, STATE["q"][key], o3, ratio)
                if K[:, j].sum() > 0:
                    DIAG.append((v, key, (K[:, j] * r).sum() / K[:, j].sum()))
                K[:, j] *= r / ratio
        out.append((kind, K))
    return out


def solve_rows(m, y_st, y_tp, xa, sa):
    """Inversión con observaciones sintéticas usando las filas (sin bloques precalculados)."""
    N = np.diag(1 / sa ** 2)
    b = xa / sa ** 2
    for (sid, h, idx, kr, _), y in zip(m["st_rows"], y_st):
        s2 = (rcl.SIG_ST * (rcl.EST_FACTOR if sid in m["est_ids"] else 1.0)) ** 2
        N[np.ix_(idx, idx)] += np.outer(kr, kr) / s2
        b[idx] += kr * y / s2
    for (idx, Kf, _), y in zip(m["tp_rows"], y_tp):
        N[np.ix_(idx, idx)] += Kf.T @ Kf / rcl.SIG_TP ** 2
        b[idx] += Kf.T @ y / rcl.SIG_TP ** 2
    x = np.linalg.solve(N, b)
    return x, np.sqrt(np.diag(np.linalg.inv(N)))


def main():
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.jacobian_hour = jac
    STATE["q"] = {"Valle de México": 1600.0, "Nonoalco": 100.0}
    models = {}
    for v in VARIANTS:
        STATE["variant"] = v
        models[v] = rcl.build(START, END, "domain", no_industry=True, extras=True)
        print("construido", v, flush=True)
    names = list(models["uniforme"]["cand"].nombre)
    ix = {k: next(i for i, nm in enumerate(names) if k in nm) for k in ("Valle de México", "Nonoalco", "AICM", "AIFA")}

    diag = pd.DataFrame(DIAG, columns=["v", "c", "r"]).groupby(["v", "c"]).r.mean()
    lines = ["# Centrales: hipótesis de pluma fresca (nov–dic 2023, σθ = 30°)\n",
             f"Cociente urbano NO₂/NOₓ de la tarde: {STATE['ratio']:.2f}; O₃ mediano 12–17 h: "
             f"{O3.reindex(models['uniforme']['hours']).median():.0f} ppb; r0 = {R0}.\n",
             "## Cociente NO₂/NOₓ efectivo de la pluma en los píxeles TEMPO (promedio ponderado por sensibilidad)\n",
             "| Variante | Valle de México | Nonoalco |", "|---|---|---|", f"| uniforme | {STATE['ratio']:.2f} | {STATE['ratio']:.2f} |"]
    for v in ("olm", "lenta", "extrema"):
        lines.append(f"| {v} | {diag.get((v, 'Valle de México'), np.nan):.2f} | {diag.get((v, 'Nonoalco'), np.nan):.2f} |")

    lines += ["\n## Datos reales\n",
              "| Variante | A priori | Valle de México | Nonoalco | AICM | AIFA | Vial / inventario | "
              "RMSE LOO modelo / híbrido (ppb) | TEMPO r | Domingo/hábil |", "|---|---|---|---|---|---|---|---|---|---|"]
    post = {}
    for v, label in VARIANTS.items():
        m = models[v]
        for pname in ("corregido", "débil (solo datos)"):
            set_priors(m, PRIORS[pname])
            N, b = rcl.solve(m)
            x = np.linalg.solve(N, b)
            sd = np.sqrt(np.diag(np.linalg.inv(N)))
            if pname == "corregido":
                post[v] = x
            f = lambda k: f"{x[ix[k]]:,.0f} ± {sd[ix[k]]:,.0f}"
            r = ir.evaluate(m)
            line = (f"| {label} | {pname} | {f('Valle de México')} | {f('Nonoalco')} | {f('AICM')} | {f('AIFA')} | "
                    f"{r['inv']:.0%} | {r['rm']:.1f} / {r['rh']:.1f} | {r['tempo']:.2f} | "
                    f"{r['sun']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) |")
            lines.append(line)
            print(line, flush=True)

    # Gemelo: verdad con pluma fresca, inversión con cociente uniforme o con pluma fresca
    lines += ["\n## Gemelo (verdad: a posteriori real con Valle 1,600 y Nonoalco 100 t/año; 20 realizaciones de ruido)\n",
              "| Verdad generada con | Invertida con | A priori | Valle de México (mediana, P5–P95) | σ posterior | "
              "Nonoalco | Vial / verdad |", "|---|---|---|---|---|---|---|"]
    base = models["uniforme"]
    for truth in ("olm", "lenta", "extrema"):
        mt = models[truth]
        xt = post["uniforme"].copy()
        xt[ix["Valle de México"]], xt[ix["Nonoalco"]] = 1600.0, 100.0
        tot_true = rcl.road_totals(base, xt).sum()
        for inv in ("uniforme", truth):
            mi = models[inv]
            for pname in ("corregido", "débil (solo datos)"):
                set_priors(mi, PRIORS[pname])
                res = []
                for _ in range(20):
                    y_st = [kr @ xt[idx] + rng.normal(0, rcl.SIG_ST * (rcl.EST_FACTOR if s in mi["est_ids"] else 1))
                            for s, h, idx, kr, _ in mt["st_rows"]]
                    y_tp = [Kf @ xt[idx] + rng.normal(0, rcl.SIG_TP, len(Kf)) for idx, Kf, _ in mt["tp_rows"]]
                    x, sd = solve_rows(mi, y_st, y_tp, mi["xa"], mi["sa"])
                    res.append((x[ix["Valle de México"]], sd[ix["Valle de México"]], x[ix["Nonoalco"]],
                                rcl.road_totals(mi, x).sum() / tot_true))
                res = np.array(res)
                p5, p50, p95 = np.percentile(res[:, 0], [5, 50, 95])
                line = (f"| {truth} | {inv} | {pname} | {p50:,.0f} ({p5:,.0f}–{p95:,.0f}) | {np.median(res[:, 1]):,.0f} | "
                        f"{np.median(res[:, 2]):,.0f} | {np.median(res[:, 3]):.2f} |")
                lines.append(line)
                print(line, flush=True)

    out = ROOT / f"reports/centrales_pluma_fresca_{START}_{END}.md"
    out.write_text("\n".join(lines) + "\n\nValores en t/año (a posteriori ± σ). Ver reports/centrales_generacion.md.\n")
    print("escrito", out)


if __name__ == "__main__":
    main()
