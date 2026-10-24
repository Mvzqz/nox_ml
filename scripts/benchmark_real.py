"""Banco datos-vs-desempeño, parte 2: degradar los datos reales de la CDMX (reports/banco_datos.md).

Configuración estándar (la vigente al correr; se registra en la salida): puffs con el viento del dominio, zonas
admin_grupos, σθ = 30°, TEMPO ×1/3, restricción de cociente de Infovial, a priori de centrales de Climate TRACE, sin
clústeres industriales, estaciones extra; vida química según --variante (vida_quimica.VARIANTS).

Degradaciones (nov–dic 2023):
  base                 todo
  sin_tempo            sin el satélite en la inversión (el estimador normalizado no cambia: usa solo estaciones)
  sin_restriccion      sin la restricción de cociente de tráfico
  viento+20 / +30      el viento real rotado con un error adicional AR(1) (ρ = 0.8) de 20° o 30°
                       (error total ≈ √(30² + σ²): ~36° y ~42°)
  est15 / est9         15 o 9 estaciones de NOₓ al azar (sin las extras de NO₂; 5 subconjuntos), con y sin TEMPO
  caja                 sin modelo de transporte: el estimador normalizado divide entre 1/(viento · capa límite)
Métricas: error fuera de muestra (LOO con la red completa; estaciones no usadas con los subconjuntos) del modelo,
IDW e híbrido; estimador normalizado domingo/hábil, ancho del placebo (= cambio mínimo detectable) y CV de los
hábiles; domingo de la inversión libre y con restricción; total vial / a priori; Spearman por zona con EDGAR total.

Uso: .venv/bin/python scripts/benchmark_real.py --variante oh_24h       Salida: data/interim/benchmark/real.json
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import benchmark_common as bc
import feasibility_linear as fl
import puff
import puffs_cdmx as pc
import real_check_linear as rcl
import vida_quimica as vq

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/benchmark"
INFOVIAL = (0.65, 0.73)


def setup(start, end, variant):
    fl.REGION_SCHEME = "admin_grupos"
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.set_tempo_weight(3, 0)
    inp = list(fl.load_inputs(start, end, extras=True))
    cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
    for nm, (p, s) in pc.NEW_PRIORS.items():
        i = next(i for i, c in enumerate(cand.nombre) if nm in c)
        prior_pt[i], sd_pt[i] = p, s
    inp[1], inp[2] = prior_pt, sd_pt
    vq.apply_variant(variant)
    return inp


def build(start, end, inp, wind):
    inp = list(inp)
    inp[9] = wind
    rcl.load_inputs = lambda *_a, **_k: tuple(inp)
    prof = vq.extended_profile() if puff.MAX_AGE_H > 6 else pc.profile_fn("supuesto")
    tr = pc.Transport("domain", prof, traj=puff.Trajectories(wind))
    rcl.Trajectories = lambda *_a, _tr=tr: _tr
    rcl.jacobian_hour_puff = pc.jacobian_puff_mx
    puff._loss_cache.clear()
    return rcl.build(start, end, "puff", no_industry=True, extras=True)


def edgar_zone_totals():
    d = json.loads((ROOT / "data/interim/edgar/edgar_compare.json").read_text())
    return {r["zona"]: r["edgar_total"] for r in d["tabla_zonas"]}


def evaluate(m, R, fixed, keep, tempo, restr, eval_ids, loo, edgar, names):
    """Métricas de una configuración."""
    N0 = bc.normal_matrix(m, R, keep, tempo, None)
    b = bc.rhs(m, R, R["ys"], R["yt"], keep, tempo)
    x0 = np.linalg.solve(N0, b)
    Z0 = bc.zone_totals(m, x0)
    out = {"domingo_libre": float(Z0[2].sum() / Z0[0].sum())}
    E = pc.ratio_constraint(m, x0) if restr else None
    N = N0 + E if restr else N0
    x = np.linalg.solve(N, b)
    Z = bc.zone_totals(m, x)
    out["domingo_inversion"] = float(Z[2].sum() / Z[0].sum())
    out["vial_habil_sobre_apriori"] = float(Z[0].sum() / m["prior_rd"].sum())
    ed = np.array([edgar[n] for n in names])
    out["spearman_edgar_total"] = float(spearmanr(Z[0], ed).statistic)
    if loo:
        base_keep = set(R["sid"]) if keep is None else set(keep)

        def x_of(s):
            Nl = bc.normal_matrix(m, R, base_keep - {s}, tempo, E)
            return np.linalg.solve(Nl, bc.rhs(m, R, R["ys"], R["yt"], base_keep - {s}, tempo))
        out["fuera_de_muestra"] = bc.heldout(m, R, x_of, eval_ids, keep)
    else:
        out["fuera_de_muestra"] = bc.heldout(m, R, lambda s: x, eval_ids, keep)
    out.update(bc.normalized(R, fixed, keep))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variante", default="fija4_6h", choices=list(vq.VARIANTS))
    ap.add_argument("--seeds", type=int, default=5)
    a = ap.parse_args()
    start, end = "2023-11-01", "2023-12-31"
    t00 = time.time()
    inp = setup(start, end, a.variante)
    m = build(start, end, inp, inp[9])
    R = bc.sparse_rows(m)
    fixed = bc.fixed_model(m, R)
    names = fl.region_names()
    edgar = edgar_zone_totals()
    nox_ids = sorted(set(R["sid"][~R["est"]]))
    all_ids = sorted(set(R["sid"]))
    print(f"Jacobiano base en {time.time() - t00:.0f} s; {len(nox_ids)} estaciones NOₓ, {len(all_ids)} en total", flush=True)
    res = {}
    res["base"] = evaluate(m, R, fixed, None, True, True, nox_ids, True, edgar, names)
    print("base", {k: v for k, v in res["base"].items() if k != "fuera_de_muestra"}, res["base"]["fuera_de_muestra"], flush=True)
    res["sin_tempo"] = evaluate(m, R, fixed, None, False, True, nox_ids, True, edgar, names)
    res["sin_restriccion"] = evaluate(m, R, fixed, None, True, False, nox_ids, True, edgar, names)
    print(f"base/sin_tempo/sin_restriccion listos ({time.time() - t00:.0f} s)", flush=True)

    # sin modelo de transporte: normalizado con 1/(u·h)
    wind, pbl = inp[9], inp[10]
    sp_ = np.hypot(wind.u, wind.v).clip(lower=fl.U_MIN)
    box = np.array([1.0 / (sp_.loc[h] * max(pbl.loc[h], 200.0)) for h in R["h"]])
    res["caja"] = bc.normalized(R, box, None)

    # estaciones: subconjuntos
    srng = np.random.default_rng(99)
    for n_st in (15, 9):
        for s in range(a.seeds):
            keep = sorted(srng.choice(nox_ids, n_st, replace=False))
            ev = [e for e in nox_ids if e not in keep]
            for tempo in (True, False):
                k = f"est{n_st}{'' if tempo else '_sin_tempo'}_s{s}"
                res[k] = evaluate(m, R, fixed, set(keep), tempo, True, ev, False, edgar, names)
                res[k]["estaciones"] = keep
            # referencia: la red completa (LOO) evaluada en las mismas estaciones no usadas
            res[f"est{n_st}_s{s}"]["referencia_red_completa_mismas_estaciones"] = bc.aggregate(
                res["base"]["fuera_de_muestra"]["por_estacion"], ev)
            res[f"caja_est{n_st}_s{s}"] = bc.normalized(R, box, set(keep))
            print(f"est{n_st} s{s} listo ({time.time() - t00:.0f} s)", flush=True)

    # viento degradado
    zr = np.random.default_rng(2026)
    z = pd.Series(bc.ar1(len(inp[9]), 0.8, zr), index=inp[9].index)
    for sig in (20, 30):
        t1 = time.time()
        mw = build(start, end, inp, bc.rotate_wind(inp[9], z, sig))
        Rw = bc.sparse_rows(mw)
        res[f"viento+{sig}"] = evaluate(mw, Rw, bc.fixed_model(mw, Rw), None, True, True, nox_ids, True, edgar, names)
        print(f"viento+{sig} listo ({time.time() - t1:.0f} s)", flush=True)

    cfg = {"REGION_SCHEME": fl.REGION_SCHEME, "transporte": f"puffs, viento del dominio, {puff.MAX_AGE_H} h",
           "vida_quimica": a.variante, "sigma_theta_deg": 30, "tempo_sigma_mult": rcl.TEMPO_SIGMA_MULT,
           "restriccion": "Infovial 0.87/0.69 ± 0.02", "periodo": f"{start} a {end}", "estaciones_nox": nox_ids,
           "referencia_infovial_domingo": INFOVIAL}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "real.json").write_text(json.dumps({"configuracion": cfg, "resultados": res}, ensure_ascii=False, indent=1, default=float))
    print(f"listo en {time.time() - t00:.0f} s", flush=True)


if __name__ == "__main__":
    main()
