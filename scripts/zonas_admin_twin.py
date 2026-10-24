"""Gemelo de identificabilidad de las zonas viales (reports/zonas_admin.md).

Misma configuración que puffs_cdmx.py (puffs con el viento del dominio, σθ = 30° en el ensamble, TEMPO ×1/3,
restricción de cociente de Infovial, a priori de centrales de Climate TRACE, sin clústeres industriales, estaciones
extra), nov–dic 2023:
  - "verdad": factores viales α por región ~ LN(0, 0.3) (hábil), sábado y domingo = α · 0.87 / 0.69 · LN(0, 0.03),
    puntuales = a priori · LN(0, 0.3), fondos por hora ~ N(5, 3) ppb y N(5, 1)·10¹⁵ molec/cm²;
  - observaciones sintéticas con un Jacobiano construido con el viento ROTADO (error de dirección AR(1) por hora,
    σ = 30°, correlación de 0.8 entre horas) más ruido (15 ppb en estaciones, ×1.5 en las estimadas de NO₂; 5·10¹⁵ en
    TEMPO);
  - inversión con el Jacobiano nominal (viento sin rotar), como con datos reales.
Se repite con N_DRAWS verdades sobre el mismo par de Jacobianos (el error de viento es una sola realización).

Métricas por región: error mediano |α̂/α − 1| del día hábil, σ a posteriori relativa al a priori (0.5) y
correlaciones a posteriori entre regiones. Referencia sin información: con el a priori (α̂ = 1) el error mediano
sería ~20 % para esta verdad.

Variante --hetero: la verdad varía por MUNICIPIO (capa admin_mun) y se invierte con cada esquema; mide el error de
agregación por municipio, por zona y por entidad (run_hetero).

Uso: .venv/bin/python scripts/zonas_admin_twin.py --schemes admin_grupos 3x3_ecatepec [--hetero]
Salida: data/interim/zonas_admin/twin_<esquema>.json, twin_hetero_<esquema>.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import feasibility_linear as fl
import puff
import puffs_cdmx as pc
import real_check_linear as rcl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/zonas_admin"
N_DRAWS = 40
ROT_SIG_DEG, ROT_RHO = 30.0, 0.8


def setup(period, scheme):
    """Entradas como en puffs_cdmx.run (a priori nuevos de centrales)."""
    start, end = pc.PERIODS[period]
    fl.REGION_SCHEME = scheme
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    puff.TAU_CHEM_H = 4.0
    rcl.set_tempo_weight(3, 0)
    inp = list(fl.load_inputs(start, end, extras=True))
    cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
    for nm, (p, s) in pc.NEW_PRIORS.items():
        i = next(i for i, c in enumerate(cand.nombre) if nm in c)
        prior_pt[i], sd_pt[i] = p, s
    inp[1], inp[2] = prior_pt, sd_pt
    return start, end, inp


def rotated(wind, rng):
    e = np.zeros(len(wind))
    e[0] = rng.normal(0, ROT_SIG_DEG)
    for k in range(1, len(e)):
        e[k] = ROT_RHO * e[k - 1] + rng.normal(0, ROT_SIG_DEG * np.sqrt(1 - ROT_RHO ** 2))
    th = np.deg2rad(e)
    w = wind.copy()
    w["u"] = wind.u * np.cos(th) - wind.v * np.sin(th)
    w["v"] = wind.u * np.sin(th) + wind.v * np.cos(th)
    w.attrs = wind.attrs
    return w


def build(start, end, inp, wind):
    inp = list(inp)
    inp[9] = wind
    rcl.load_inputs = lambda *_a, **_k: tuple(inp)
    tr = pc.Transport("domain", pc.profile_fn("supuesto"), traj=puff.Trajectories(wind))
    rcl.Trajectories = lambda *_a, _tr=tr: _tr
    rcl.jacobian_hour_puff = pc.jacobian_puff_mx
    return rcl.build(start, end, "puff", no_industry=True, extras=True)


def synth(m_true, x_true, rng):
    """Observaciones sintéticas fila por fila (mismo orden que m_nom)."""
    ys = []
    for s, h, idx, kr, _ in m_true["st_rows"]:
        sig = rcl.SIG_ST * (rcl.EST_FACTOR if s in m_true["est_ids"] else 1.0)
        ys.append(kr @ x_true[idx] + rng.normal(0, sig))
    yt = [Kf @ x_true[idx] + rng.normal(0, rcl.SIG_TP_BASE, len(Kf)) for idx, Kf, _ in m_true["tp_rows"]]
    return np.array(ys), yt


def rhs(m, ys, yt):
    b = m["xa"] / m["sa"] ** 2
    for (s, h, idx, kr, _), y in zip(m["st_rows"], ys):
        wr = rcl.EST_FACTOR ** -2 if s in m["est_ids"] else 1.0
        b[idx] += kr * wr * y / rcl.SIG_ST ** 2
    for (idx, Kf, _), y in zip(m["tp_rows"], yt):
        b[idx] += Kf.T @ y / rcl.SIG_TP ** 2
    return b


def run(period, scheme, seed=7):
    t0 = time.time()
    rng = np.random.default_rng(seed)
    start, end, inp = setup(period, scheme)
    m = build(start, end, inp, inp[9])
    m_true = build(start, end, inp, rotated(inp[9], rng))
    assert len(m["st_rows"]) == len(m_true["st_rows"]) and len(m["tp_rows"]) == len(m_true["tp_rows"])
    print(f"[{scheme}] Jacobianos en {time.time() - t0:.0f} s", flush=True)
    n_pt, nr, H = m["n_pt"], m["n_reg"], len(m["hours"])
    N, _ = rcl.solve(m)
    N = N + pc.ratio_constraint(m, m["xa"])
    Ninv = np.linalg.inv(N)
    sl = slice(n_pt, n_pt + nr)
    S = Ninv[sl, sl]
    sd = np.sqrt(np.diag(S))
    C = S / np.outer(sd, sd)
    err, tot_err, sun_err = [], [], []
    for _ in range(N_DRAWS):
        a = np.exp(rng.normal(0, 0.3, nr))
        x = np.r_[m["prior_pt"] * np.exp(rng.normal(0, 0.3, n_pt)), a,
                  a * 0.87 * np.exp(rng.normal(0, 0.03, nr)), a * 0.69 * np.exp(rng.normal(0, 0.03, nr)),
                  np.maximum(rng.normal(5, 3, H), 0), rng.normal(5e15, 1e15, H)]
        ys, yt = synth(m_true, x, rng)
        xh = Ninv @ rhs(m, ys, yt)
        err.append(xh[sl] / a - 1)
        t_true, t_hat = rcl.road_totals(m, x), rcl.road_totals(m, xh)
        tot_err.append(t_hat[0] / t_true[0] - 1)
        sun_err.append((t_hat[2] / t_hat[0]) / (t_true[2] / t_true[0]) - 1)
    err = np.array(err)
    out = {"esquema": scheme, "regiones": fl.region_names(), "prior_rd": m["prior_rd"].tolist(),
           "error_mediano": np.median(np.abs(err), 0).tolist(), "sesgo_mediano": np.median(err, 0).tolist(),
           "sd_post_rel": (sd / 0.5).tolist(), "corr": C.tolist(),
           "error_total_vial_mediano": float(np.median(np.abs(tot_err))), "sesgo_total_vial": float(np.median(tot_err)),
           "error_domingo_mediano": float(np.median(np.abs(sun_err))),
           "n_draws": N_DRAWS, "rot_sigma_deg": ROT_SIG_DEG, "segundos": time.time() - t0}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"twin_{scheme}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    iu = np.triu_indices(nr, 1)
    worst = sorted(zip(np.abs(C[iu]), iu[0], iu[1]), reverse=True)[:4]
    print(f"[{scheme}] total vial {out['error_total_vial_mediano']:.0%}, domingo {out['error_domingo_mediano']:.0%}", flush=True)
    for nm, e, s in zip(out["regiones"], out["error_mediano"], out["sd_post_rel"]):
        print(f"   {nm:28s} error {e:5.0%}  σ post/prior {s:.2f}", flush=True)
    print("   pares más correlacionados:", [(out["regiones"][i], out["regiones"][j], round(float(C[i, j]), 2)) for _, i, j in worst], flush=True)


def cells_of(scheme):
    fl.REGION_SCHEME = scheme
    return fl.load_inputs("2023-11-01", "2023-12-31", extras=False)[3]


def run_hetero(period, schemes, seed=11):
    """Verdad heterogénea: α distinto por MUNICIPIO (LN(0, 0.3)); se invierte con cada esquema de zonas.

    Mide el error de agregación (una zona con municipios distintos, como Ecatepec dentro del "Centro"): error del
    total vial hábil por municipio (repartiendo α̂ de la zona a sus celdas), por zona del esquema y por entidad.
    """
    import geopandas as gpd
    from config import UTM
    rng = np.random.default_rng(seed)
    t0 = time.time()
    start, end, inp_mun = setup(period, "admin_mun")
    wind_rot = rotated(inp_mun[9], rng)
    m_true = build(start, end, inp_mun, wind_rot)
    c_mun = inp_mun[3]
    mun = gpd.read_file(fl.ADMIN_GPKG, layer="admin_mun")
    ent = gpd.read_file(fl.INT / "municipios.gpkg").set_index("NOMGEO").NOM_ENT
    c_ent = mun.grupo.map(ent).values[c_mun.region.values]
    n_pt, nm, H = m_true["n_pt"], m_true["n_reg"], len(m_true["hours"])
    draws = []
    for _ in range(N_DRAWS):
        a = np.exp(rng.normal(0, 0.3, nm))
        x = np.r_[m_true["prior_pt"] * np.exp(rng.normal(0, 0.3, n_pt)), a,
                  a * 0.87 * np.exp(rng.normal(0, 0.03, nm)), a * 0.69 * np.exp(rng.normal(0, 0.03, nm)),
                  np.maximum(rng.normal(5, 3, H), 0), rng.normal(5e15, 1e15, H)]
        draws.append((a, synth(m_true, x, rng)))
    print(f"[hetero] verdad por municipio ({nm}) en {time.time() - t0:.0f} s", flush=True)
    w = c_mun.w.values
    big = pd.Series(w).groupby(c_mun.region.values).sum()
    big = big[big > 0.01 * w.sum()].index  # municipios con ≥ 1 % del peso vial (los demás son ruido de borde)
    for scheme in schemes:
        _, _, inp = setup(period, scheme)
        m = build(start, end, inp, inp[9])
        assert len(m["st_rows"]) == len(m_true["st_rows"])
        c_s = inp[3]
        assert np.allclose(c_s.w.values, w)
        N, _ = rcl.solve(m)
        Ninv = np.linalg.inv(N + pc.ratio_constraint(m, m["xa"]))
        nr = m["n_reg"]
        e_mun, e_zone, e_ent, e_tot, e_sun = [], [], [], [], []
        for a, (ys, yt) in draws:
            xh = Ninv @ rhs(m, ys, yt)
            ah = xh[n_pt:n_pt + nr][c_s.region.values]
            at = a[c_mun.region.values]
            ah_sun = xh[n_pt + 2 * nr:n_pt + 3 * nr][c_s.region.values]
            g = lambda key, v: pd.Series(w * v).groupby(key).sum()
            e_mun.append((g(c_mun.region.values, ah) / g(c_mun.region.values, at) - 1)[big].values)
            e_zone.append((g(c_s.region.values, ah) / g(c_s.region.values, at) - 1).values)
            e_ent.append((g(c_ent, ah) / g(c_ent, at) - 1).values)
            e_tot.append((w * ah).sum() / (w * at).sum() - 1)
            e_sun.append(((w * ah_sun).sum() / (w * ah).sum()) / 0.69 - 1)
        out = {"esquema": scheme, "regiones": fl.region_names(),
               "error_municipio_mediano": float(np.median(np.abs(e_mun))),
               "error_zona_por_zona": np.median(np.abs(e_zone), 0).tolist(),
               "error_zona_mediano": float(np.median(np.abs(e_zone))),
               "entidades": sorted(set(c_ent)), "error_entidad": np.median(np.abs(e_ent), 0).tolist(),
               "error_total_vial": float(np.median(np.abs(e_tot))), "error_domingo": float(np.median(np.abs(e_sun))),
               "municipios_evaluados": int(len(big))}
        (OUT / f"twin_hetero_{scheme}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"[hetero {scheme}] municipio {out['error_municipio_mediano']:.0%}, zona {out['error_zona_mediano']:.0%}, "
              f"entidad {dict(zip(out['entidades'], np.round(out['error_entidad'], 3)))}, total {out['error_total_vial']:.0%}, "
              f"domingo {out['error_domingo']:.0%}", flush=True)
        for nmz, e in zip(out["regiones"], out["error_zona_por_zona"]):
            print(f"   {nmz:28s} {e:5.0%}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="nov23", choices=list(pc.PERIODS))
    ap.add_argument("--schemes", nargs="+", default=["admin_grupos", "3x3_ecatepec"])
    ap.add_argument("--hetero", action="store_true", help="verdad por municipio (error de agregación)")
    a = ap.parse_args()
    if a.hetero:
        run_hetero(a.period, a.schemes)
        return
    for s in a.schemes:
        run(a.period, s)


if __name__ == "__main__":
    main()
