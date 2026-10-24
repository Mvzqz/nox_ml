"""Inversión con el núcleo PINN y comparación con la inversión lineal (pluma gaussiana).

Configuración común (la base de las pruebas de mejoras, opción B): industria agrupada en las regiones
viales, estaciones extra (solo NO₂) y viento METAR, viento uniforme del dominio, σθ = 30° en la
pluma (en la PINN el serpenteo va en K = κ|u|). Estado: 4 fuentes grandes | α vial por región (3×3)
× tipo de día | fondo por hora (estaciones y TEMPO).

Pasos:
  1. Gemelo: se plantan emisiones conocidas, se simulan observaciones con un modelo y se invierte con
     cada modelo (incluye el cruce lineal ↔ PINN, que mide el efecto de equivocarse de física).
  2. Datos reales, red congelada: jacobiano PINN + misma estadística bayesiana que la lineal
     (bootstrap de días, estación retenida).
  3. Datos reales, entrenamiento conjunto (solo estaciones): pérdida = residuo de la ecuación +
     ajuste a estaciones + a priori; la red y las emisiones se ajustan juntas.
  4. Estimador normalizado por meteorología (observado ÷ modelo con emisión fija) por tipo de día.

Restricción de cociente por tipo de día (por defecto, reports/sesgo_domingos.md): los datos no fijan el
cociente domingo/hábil (el fondo por hora absorbe la diferencia), así que se ata α_dt,r ≈ r_dt · α_hábil,r
con el tráfico de Infovial del día completo ponderado por emisión: sábado 0.87 y domingo/festivo 0.69 (rango
0.84–0.89 y 0.65–0.73 según el peso de los pesados). La σ por región es 0.02, casi fija: con σ = 0.08 la
verosimilitud (errores supuestos independientes, demasiado confiada) apenas la movía (domingo 0.42 → 0.45),
aunque el error con estación retenida no distingue entre cocientes (sunday_profile.py). La incertidumbre real
del cociente es el rango de Infovial y se reporta aparte.
--sin-restriccion reproduce la inversión anterior. El entrenamiento conjunto (paso 3) no la usa.

Transporte del modelo lineal (por defecto puffs, reports/puffs_cdmx.md y reports/config_final.md): puffs con el
vector medio del dominio (scripts/puff.py vía puffs_cdmx.jacobian_puff_mx: perfil horario supuesto). Vida química
(reports/vida_quimica.md): por defecto dependiente de mes y hora (pérdida por OH, scripts/vida_quimica.py) con puffs
de hasta 24 h; --vida-quimica fija4 reproduce la vida constante de 4 h con puffs de 6 h. --transporte pluma
reproduce la pluma estacionaria. La PINN aprendió solo la pluma estacionaria (kernel.py),
así que su núcleo sigue siendo pluma: en las comparaciones, la referencia de transporte es el lineal con puffs.

Regiones viales: feasibility_linear.REGION_SCHEME (estándar: 13 grupos de alcaldías y municipios "admin_grupos",
reports/zonas_admin.md); --regiones 3x3_ecatepec o 3x3 reproducen los esquemas anteriores.

A priori de centrales (reports/centrales_generacion.md, Climate TRACE 2023): Valle de México 1,600 ± 650 t/año y
Nonoalco 100 ± 100 (antes 2,615 y 277 del inventario de capacidad).

Peso de TEMPO (por defecto σ por píxel ×3, reports/peso_tempo.md): --tempo-sigma-mult 1 reproduce los
resultados anteriores; --superobs-km 8 promedia TEMPO en celdas de 8 km por escaneo (sin gemelo). Las
variantes distintas del estándar se escriben con sufijo (_tp1, _so8km) para no pisar lo que lee la app.

Piso de viento (reports/estancamiento.md): U_MIN = 2.0 m/s por defecto; --u-min 1.0 (o la variable U_MIN) reproduce el anterior.

Uso: .venv/bin/python scripts/pinn/invert.py 2023-11-01 2023-12-31 [--full] [--u-min 2.0] [--sin-restriccion]
     [--tempo-sigma-mult 3] [--superobs-km 0] [--transporte puff|pluma] [--vida-quimica oh|fija4] [--regiones admin_grupos]
Salida: data/processed/pinn/resultados_<inicio>_<fin>.json y normalizado_<inicio>_<fin>.parquet
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feasibility_linear as fl  # noqa: E402

fl.SIGMA_THETA = np.deg2rad(30)  # error de dirección medido (reports/viento.md); no se edita el script base
import kernel as kn  # noqa: E402
import model as pm  # noqa: E402
import real_check_linear as rcl  # noqa: E402
import puff  # noqa: E402
import puffs_cdmx as pc  # noqa: E402
import vida_quimica as vq  # noqa: E402

OUT = kn.OUT
rng = np.random.default_rng(11)
RATIO_PRIOR = {1: (0.87, 0.02), 2: (0.69, 0.02)}  # tipo de día: (cociente respecto al hábil, σ); Infovial día completo
TRANSPORT = "puff"  # transporte del modelo lineal: "puff" (estándar) o "pluma"
CHEM = "oh"  # vida química de los puffs: "oh" (por mes y hora, estándar) o "fija4" (4 h constante)
_CACHE = {}
_orig_load = fl.load_inputs


def cached_load(start, end, extras=False):
    k = (start, end, extras, fl.REGION_SCHEME)
    if k not in _CACHE:
        inp = list(_orig_load(start, end, extras))
        cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
        for nm, (p, sd) in pc.NEW_PRIORS.items():
            i = next(i for i, c in enumerate(cand.nombre) if nm in c)
            prior_pt[i], sd_pt[i] = p, sd
        inp[1], inp[2] = prior_pt, sd_pt
        _CACHE[k] = tuple(inp)
    return _CACHE[k]


def build(start, end, kind):
    rcl.load_inputs = cached_load  # puffs_cdmx.run también parchea rcl.load_inputs; se restablece aquí
    t0 = time.time()
    if kind == "lineal" and TRANSPORT == "puff":
        puff.SIGMA_THETA = fl.SIGMA_THETA
        if CHEM == "oh":
            if not vq.covered(start, end):
                raise SystemExit(f"la serie de vida química no cubre {start}–{end}; usa --vida-quimica fija4")
            vq.apply_variant(vq.STANDARD)
            prof = vq.extended_profile()
        else:
            vq.apply_variant("fija4_6h")
            prof = pc.profile_fn("supuesto")
        rcl.Trajectories = lambda w: pc.Transport("domain", prof, traj=puff.Trajectories(w))
        rcl.jacobian_hour_puff = pc.jacobian_puff_mx
        m = rcl.build(start, end, "puff", no_industry=True, extras=True)
    else:
        rcl.jacobian_hour = fl.jacobian_hour if kind == "lineal" else pm.jacobian_hour_pinn
        m = rcl.build(start, end, "domain", no_industry=True, extras=True)
    m["secs"] = time.time() - t0
    m["n_src"] = m["n_pt"] + 3 * m["n_reg"]
    m["H"] = len(m["hours"])
    m["sig_row"] = np.array([rcl.SIG_ST * (rcl.EST_FACTOR if s in m["est_ids"] else 1.0) for s, *_ in m["st_rows"]])
    return m


def ratio_constraint(m, x_ref, prior=RATIO_PRIOR):
    """Término de a priori α_dt,r − r_dt · α_hábil,r ≈ 0 con σ = σ_r · α_hábil,r (x_ref: solución sin restricción)."""
    n_pt, n, nr = m["n_pt"], m["n"], m["n_reg"]
    E = np.zeros((n, n))
    for dt, (r, sd) in prior.items():
        for i in range(nr):
            g = np.zeros(n)
            g[n_pt + nr * dt + i] = 1.0
            g[n_pt + i] = -r
            E += np.outer(g, g) / (sd * max(x_ref[n_pt + i], 0.1)) ** 2
    return E


def add_ratio_constraint(m):
    m.pop("E", None)
    N, b = normal(m)
    m["E"] = ratio_constraint(m, np.linalg.solve(N, b))


def is_tp(m, idx):
    return idx[-1] >= m["n_src"] + m["H"]


def normal(m, weights=None, drop_station=None, tempo=True, y_st=None, y_tp=None):
    """Ecuaciones normales. y_st / y_tp reemplazan las observaciones (gemelo)."""
    n = m["n"]
    N = np.diag(1 / m["sa"] ** 2)
    b = m["xa"] / m["sa"] ** 2
    if y_st is None:
        for d, idx, A, g in m["blocks"]:
            if not tempo and is_tp(m, idx):
                continue
            w = 1.0 if weights is None else weights.get(d, 0)
            if w:
                N[np.ix_(idx, idx)] += w * A
                b[idx] += w * g
    else:  # gemelo: se recalcula b con las y sintéticas (N no depende de y)
        for d, idx, A, g in m["blocks"]:
            if tempo or not is_tp(m, idx):
                N[np.ix_(idx, idx)] += A
        for (s, h, idx, kr, _), sig, yy in zip(m["st_rows"], m["sig_row"], y_st):
            b[idx] += kr * yy / sig ** 2
        if tempo:
            for (idx, Kf, _), yy in zip(m["tp_rows"], y_tp):
                b[idx] += Kf.T @ yy / rcl.SIG_TP ** 2
    if m.get("E") is not None:
        N = N + m["E"]
    if drop_station:
        for (s, h, idx, kr, yy), sig in zip(m["st_rows"], m["sig_row"]):
            if s == drop_station:
                N[np.ix_(idx, idx)] -= np.outer(kr, kr) / sig ** 2
                b[idx] -= kr * yy / sig ** 2
    return N, b


def summary(m, x, S=None):
    n_pt, nr = m["n_pt"], m["n_reg"]
    tot = rcl.road_totals(m, x)
    out = {"total_vial": tot.tolist(), "cociente_sabado": float(tot[1] / tot[0]), "cociente_domingo": float(tot[2] / tot[0]),
           "alfa": [[float(x[n_pt + nr * d + i]) for i in range(nr)] for d in range(3)],
           "puntos": [float(v) for v in x[:n_pt]]}
    if S is not None:
        sd = np.sqrt(np.diag(S))
        out["alfa_sd"] = [[float(sd[n_pt + nr * d + i]) for i in range(nr)] for d in range(3)]
        out["puntos_sd"] = [float(v) for v in sd[:n_pt]]
    return out


def predict_st(m, x):
    return np.array([kr @ x[idx] for _, _, idx, kr, _ in m["st_rows"]])


def real(m, boot, loo, tempo=True):
    N, b = normal(m, tempo=tempo)
    S = np.linalg.inv(N)
    x = S @ b
    res = summary(m, x, S)
    obs = np.array([r[4] for r in m["st_rows"]])
    pred = predict_st(m, x)
    res["ajuste_estaciones"] = {"r": float(np.corrcoef(pred, obs)[0, 1]), "rmse": float(np.sqrt(np.mean((pred - obs) ** 2)))}
    if tempo and m["tp_rows"]:
        to = np.concatenate([y for *_, y in m["tp_rows"]])
        tp = np.concatenate([Kf @ x[idx] for idx, Kf, _ in m["tp_rows"]])
        res["ajuste_tempo_r"] = float(np.corrcoef(tp, to)[0, 1])
    days = sorted({d for d, *_ in m["blocks"]})
    bs = []
    for _ in range(boot):
        pick = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick]).groupby(level=0).sum().to_dict()
        Nb, bb = normal(m, weights=wts, tempo=tempo)
        xb = np.linalg.solve(Nb, bb)
        bs.append(np.r_[rcl.road_totals(m, xb), xb[m["n_pt"]:m["n_pt"] + 3 * m["n_reg"]]])
    bs = np.array(bs)
    if boot:
        res["boot"] = {"total_vial_ic90": np.percentile(bs[:, :3], [5, 95], 0).T.tolist(),
                       "cociente_sabado_ic90": np.percentile(bs[:, 1] / bs[:, 0], [5, 95]).tolist(),
                       "cociente_domingo_ic90": np.percentile(bs[:, 2] / bs[:, 0], [5, 95]).tolist(),
                       "alfa_ic90": np.percentile(bs[:, 3:], [5, 95], 0).T.reshape(3, m["n_reg"], 2).tolist(),
                       "n": boot, "dias": len(days)}
    if loo:
        rows = pd.DataFrame([(s, o) for s, _, _, _, o in m["st_rows"]], columns=["sid", "obs"])
        per = {}
        for sid in sorted(set(rows.sid) - m["est_ids"]):
            Nl, bl = normal(m, drop_station=sid, tempo=tempo)
            xl = np.linalg.solve(Nl, bl)
            mask = (rows.sid == sid).values
            p = predict_st(m, xl)[mask]
            o = rows.obs.values[mask]
            per[sid] = {"n": int(mask.sum()), "rmse": float(np.sqrt(np.mean((p - o) ** 2))), "sesgo": float(np.mean(p - o)),
                        "r": float(np.corrcoef(p, o)[0, 1])}
        nn = np.array([v["n"] for v in per.values()])
        rm = np.array([v["rmse"] for v in per.values()])
        res["loo"] = {"por_estacion": per, "rmse_ponderado": float(np.sqrt((nn * rm ** 2).sum() / nn.sum()))}
    return res, x


def twin(models, x_ref, n_rep):
    """Gemelos: generador × inversor. x_ref = solución real lineal (de ahí salen los fondos)."""
    m0 = models["lineal"]
    n_pt, n_src = m0["n_pt"], m0["n_src"]
    dt_factor = np.array([1.0, 0.9, 0.7])
    out = {f"{g}→{i}": {"err_total": [], "err_sab": [], "err_dom": [], "err_alfa": [], "err_puntos": []}
           for g in models for i in models}
    for _ in range(n_rep):
        xt = x_ref.copy()
        xt[:n_pt] = m0["prior_pt"] * rng.lognormal(0, 0.5, n_pt)
        nr = m0["n_reg"]
        reg = rng.lognormal(0, 0.4, nr)
        for d in range(3):
            xt[n_pt + nr * d: n_pt + nr * d + nr] = reg * dt_factor[d] * rng.lognormal(0, 0.1, nr)
        t_tot = rcl.road_totals(m0, xt)
        for g, mg in models.items():
            y_st = predict_st(mg, xt) + rng.normal(0, 10.0, len(mg["st_rows"]))
            y_tp = [Kf @ xt[idx] + rng.normal(0, 3e15, len(Kf)) for idx, Kf, _ in mg["tp_rows"]]
            for i, mi in models.items():
                N, b = normal(mi, y_st=y_st, y_tp=y_tp)
                x = np.linalg.solve(N, b)
                tot = rcl.road_totals(mi, x)
                o = out[f"{g}→{i}"]
                o["err_total"].append(np.abs(tot / t_tot - 1).tolist())
                o["err_sab"].append(abs((tot[1] / tot[0]) / (t_tot[1] / t_tot[0]) - 1))
                o["err_dom"].append(abs((tot[2] / tot[0]) / (t_tot[2] / t_tot[0]) - 1))
                o["err_alfa"].append(float(np.median(np.abs(x[n_pt:n_src] / xt[n_pt:n_src] - 1))))
                o["err_puntos"].append(np.abs(x[:n_pt] / xt[:n_pt] - 1).tolist())
    res = {}
    for k, o in out.items():
        res[k] = {"err_total_mediano_por_tipo": np.median(o["err_total"], 0).tolist(),
                  "err_cociente_sabado_mediano": float(np.median(o["err_sab"])),
                  "err_cociente_domingo_mediano": float(np.median(o["err_dom"])),
                  "err_alfa_mediano": float(np.median(o["err_alfa"])),
                  "err_puntos_mediano": np.median(o["err_puntos"], 0).tolist()}
    return res


def normalized(m, boot=1000):
    """Observado ÷ modelo con emisión vial del a priori (α = 1), por día; cocientes por tipo de día."""
    n_pt = m["n_pt"]
    rows = [(h, yy, kr[n_pt:n_pt + m["n_reg"]].sum()) for (s, h, idx, kr, yy) in m["st_rows"] if s not in m["est_ids"]]
    df = pd.DataFrame(rows, columns=["h", "obs", "modelo"])
    df["dia"] = (df.h - pd.Timedelta(hours=6)).dt.normalize()
    df["tipo"] = df.h.map(rcl.day_type)
    daily = df.groupby("dia").agg(obs=("obs", "sum"), modelo=("modelo", "sum"), tipo=("tipo", "first"),
                                  n=("obs", "size")).reset_index()
    daily["indice"] = daily.obs / daily.modelo

    def ratio(d):
        g = d.groupby("tipo")[["obs", "modelo"]].sum()
        r = g.obs / g.modelo
        return [r.get(1, np.nan) / r.get(0, np.nan), r.get(2, np.nan) / r.get(0, np.nan)]

    est = ratio(daily)
    bs = np.array([ratio(daily.iloc[rng.integers(0, len(daily), len(daily))]) for _ in range(boot)])
    conc = daily.groupby("tipo").obs.sum() / daily.groupby("tipo").n.sum()
    met = daily.groupby("tipo").modelo.sum() / daily.groupby("tipo").n.sum()
    res = {"sabado_habil": est[0], "domingo_habil": est[1],
           "sabado_habil_ic90": np.nanpercentile(bs[:, 0], [5, 95]).tolist(),
           "domingo_habil_ic90": np.nanpercentile(bs[:, 1], [5, 95]).tolist(),
           "concentracion_sabado_habil": float(conc.get(1) / conc.get(0)),
           "concentracion_domingo_habil": float(conc.get(2) / conc.get(0)),
           "meteorologia_sabado_habil": float(met.get(1) / met.get(0)),
           "meteorologia_domingo_habil": float(met.get(2) / met.get(0))}
    daily["obs_ppb"] = daily.obs / daily.n
    daily["modelo_ppb"] = daily.modelo / daily.n
    return res, daily[["dia", "tipo", "obs_ppb", "modelo_ppb", "indice"]]


def joint(m_pinn, x0, lam, steps, batch=6, seed=0):
    """Entrenamiento conjunto (solo estaciones): red + emisiones + fondos, a partir de la solución congelada."""
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = _CACHE[m_pinn["key"]]
    keep = (cand.tipo != "industria").values
    cand = cand[keep].reset_index(drop=True)
    model = kn.load()
    n_pt, n_src, H, nr = m_pinn["n_pt"], m_pinn["n_src"], m_pinn["H"], m_pinn["n_reg"]
    xa = torch.tensor(m_pinn["xa"][:n_src + H], dtype=torch.float32)
    sa = torch.tensor(m_pinn["sa"][:n_src + H], dtype=torch.float32)
    z = torch.tensor((x0[:n_src + H] - m_pinn["xa"][:n_src + H]) / m_pinn["sa"][:n_src + H], dtype=torch.float32,
                     requires_grad=True)
    opt = torch.optim.Adam([{"params": [z], "lr": 2e-2}, {"params": model.parameters(), "lr": 5e-5}])
    hours = m_pinn["hours"]
    data = []
    for k, h in enumerate(hours):
        nh = nox[nox.h == h]
        sig = np.where(nh.id_station.isin(m_pinn["est_ids"]), rcl.SIG_ST * rcl.EST_FACTOR, rcl.SIG_ST)
        data.append((k, rcl.day_type(h), h, nh, torch.tensor(nh.NOX.values, dtype=torch.float32),
                     torch.tensor(sig, dtype=torch.float32)))
    n_obs = sum(len(d[4]) for d in data)
    t0 = time.time()
    log = []

    def pred(k, dt, h, nh, x):
        # los pares se recalculan cada vez: guardarlos todos ocuparía ~0.6 GB
        K = pm.JointPairs(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, n_pt).jac(model)
        coef = torch.cat([x[:n_pt], x[n_pt + nr * dt: n_pt + nr * dt + nr]])
        return K @ coef + x[n_src + k]

    for step in range(steps):
        opt.zero_grad()
        x = xa + sa * z
        pick = rng.choice(len(data), batch, replace=False)
        chi = sum((((d[4] - pred(d[0], d[1], d[2], d[3], x)) / d[5]) ** 2).sum() for d in (data[i] for i in pick))
        chi = chi * len(data) / batch
        prior = (z ** 2).sum()
        pde = kn.pde_loss(model, gen, n=1024)
        loss = (chi + prior) / n_obs + lam * pde
        loss.backward()
        opt.step()
        if step % 25 == 0 or step == steps - 1:
            log.append((step, chi.item() / n_obs, pde.item(), time.time() - t0))
            print(f"  conjunto λ={lam} paso {step}: χ²/n {chi.item() / n_obs:.2f}  EDP {pde.item():.2e}  "
                  f"{time.time() - t0:.0f} s", flush=True)
    with torch.no_grad():
        x = (xa + sa * z).numpy().astype(float)
        P, O = [], []
        for d in data:
            P.append(pred(d[0], d[1], d[2], d[3], torch.tensor(x, dtype=torch.float32)).numpy())
            O.append(d[4].numpy())
    P, O = np.concatenate(P), np.concatenate(O)
    xf = np.r_[x, m_pinn["xa"][n_src + H:]]
    res = summary(m_pinn, xf)
    res.update({"lambda_edp": lam, "pasos": steps, "segundos": time.time() - t0, "log": log,
                "ajuste_estaciones": {"r": float(np.corrcoef(P, O)[0, 1]), "rmse": float(np.sqrt(np.mean((P - O) ** 2)))},
                "validacion_nucleo_despues": kn.validate(model)})
    return res


def main():
    global TRANSPORT, CHEM
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--full", action="store_true", help="gemelo, estación retenida y entrenamiento conjunto")
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--twin", type=int, default=20)
    ap.add_argument("--joint-steps", type=int, default=150)
    ap.add_argument("--sin-restriccion", action="store_true", help="sin la restricción de cociente de Infovial")
    ap.add_argument("--tempo-sigma-mult", type=float, default=rcl.TEMPO_SIGMA_MULT,
                    help="multiplicador de σ por píxel de TEMPO (estándar 3; anterior 1)")
    ap.add_argument("--superobs-km", type=float, default=rcl.SUPEROBS_KM,
                    help="promediar TEMPO en celdas de este tamaño por escaneo (0 = píxel a píxel)")
    ap.add_argument("--transporte", choices=["puff", "pluma"], default=TRANSPORT,
                    help="transporte del modelo lineal (estándar puff; la PINN es siempre pluma)")
    ap.add_argument("--vida-quimica", choices=["oh", "fija4"], default=CHEM,
                    help="vida química de los puffs del lineal (estándar oh: por mes y hora)")
    ap.add_argument("--regiones", choices=list(fl.REGION_SCHEMES) + ["admin_grupos", "admin_mun"], default=fl.REGION_SCHEME,
                    help="esquema de regiones viales (estándar admin_grupos)")
    ap.add_argument("--u-min", type=float, default=None,
                    help="piso de la rapidez de transporte en m/s (estándar 2.0; 1.0 reproduce lo anterior)")
    a = ap.parse_args()
    if a.u_min is not None:
        fl.U_MIN = a.u_min
    TRANSPORT = a.transporte
    CHEM = a.vida_quimica
    std_scheme = fl.REGION_SCHEME
    fl.REGION_SCHEME = a.regiones
    rcl.set_tempo_weight(a.tempo_sigma_mult, a.superobs_km)
    if a.full and rcl.SUPEROBS_KM > 0:
        ap.error("el gemelo (--full) no está implementado con superobservaciones")
    sfx = "" if (rcl.TEMPO_SIGMA_MULT == 3 and rcl.SUPEROBS_KM == 0) else (
        f"_so{rcl.SUPEROBS_KM:g}km" if rcl.SUPEROBS_KM > 0 else f"_tp{rcl.TEMPO_SIGMA_MULT:g}")
    sfx += ("" if TRANSPORT == "puff" else "_pluma") + ("" if CHEM == "oh" or TRANSPORT != "puff" else "_vq4") + ("" if fl.REGION_SCHEME == std_scheme else f"_{fl.REGION_SCHEME}")
    res = {"periodo": [a.start, a.end], "tau_h": pm.TAU_H, "sigma_theta_lineal_grados": 30,
           "tempo_sigma_mult": rcl.TEMPO_SIGMA_MULT, "superobs_km": rcl.SUPEROBS_KM,
           "transporte_lineal": "puffs" if TRANSPORT == "puff" else "pluma", "transporte_pinn": "pluma",
           "vida_quimica_lineal": ("por mes y hora (OH), puffs de 24 h" if CHEM == "oh" else "4 h constante, puffs de 6 h")
           if TRANSPORT == "puff" else None,
           "regiones": fl.region_names(), "esquema_regiones": fl.REGION_SCHEME,
           "prior_centrales": {k: list(v) for k, v in pc.NEW_PRIORS.items()},
           "restriccion_cociente": None if a.sin_restriccion else
           {"sabado": list(RATIO_PRIOR[1]), "domingo": list(RATIO_PRIOR[2]), "rango_sabado": [0.84, 0.89],
            "rango_domingo": [0.65, 0.73], "fuente": "Infovial ene-2017, día completo ponderado por emisión"}}
    models = {}
    for kind in ("lineal", "pinn"):
        models[kind] = build(a.start, a.end, kind)
        models[kind]["key"] = (a.start, a.end, True, fl.REGION_SCHEME)  # misma clave que cached_load
        print(f"{kind}: jacobianos en {models[kind]['secs']:.0f} s", flush=True)
    m0 = models["lineal"]
    res["horas"] = m0["H"]
    res["obs_estaciones"] = len(m0["st_rows"])
    res["pixeles_tempo"] = int(sum(len(y) for *_, y in m0["tp_rows"]))
    res["fuentes"] = list(m0["cand"].nombre)
    res["prior_puntos"] = m0["prior_pt"].tolist()
    res["prior_regiones"] = m0["prior_rd"].tolist()
    res["tiempos_s"] = {f"jacobiano_{k}": v["secs"] for k, v in models.items()}

    xs = {}
    for kind, m in models.items():
        t0 = time.time()
        if not a.sin_restriccion:
            sr, _ = real(m, 0, a.full)  # referencia sin restricción (antes de añadirla)
            res[kind + "_sin_restriccion"] = sr
            add_ratio_constraint(m)
        res[kind], xs[kind] = real(m, a.boot, a.full)
        res[kind + "_solo_estaciones"], xs[kind + "_st"] = real(m, 0, False, tempo=False)
        res["tiempos_s"][f"inversion_{kind}"] = time.time() - t0
        nres, daily = normalized(m)
        res[kind]["normalizado"] = nres
        daily.to_parquet(OUT / f"normalizado_{kind}_{a.start}_{a.end}{sfx}.parquet")
        print(f"{kind}: total vial {res[kind]['total_vial']}, dom/háb {res[kind]['cociente_domingo']:.2f}", flush=True)

    if a.full:
        t0 = time.time()
        res["gemelo"] = twin(models, xs["lineal"], a.twin)
        res["tiempos_s"]["gemelo"] = time.time() - t0
        res["conjunto"] = []
        for lam in (10.0, 0.1):
            t0 = time.time()
            res["conjunto"].append(joint(models["pinn"], xs["pinn_st"], lam, a.joint_steps))
            res["tiempos_s"][f"conjunto_{lam}"] = time.time() - t0
    out = OUT / f"resultados_{a.start}_{a.end}{sfx}.json"
    json.dump(res, open(out, "w"), indent=1, ensure_ascii=False, default=float)
    print("escrito", out)


if __name__ == "__main__":
    main()
