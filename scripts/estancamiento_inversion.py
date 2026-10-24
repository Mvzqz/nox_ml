"""Estancamiento: inversión completa estándar (lineal, puffs, admin_grupos, vida química OH de 24 h) con una variante de
la rapidez de transporte (estancamiento_invierno.config). Igual que vida_quimica.completo para un periodo, más el total vial
hábil por zona. Salida: data/interim/estancamiento_inversion_<variante>_<periodo>.json
Uso: .venv/bin/python scripts/estancamiento_inversion.py <variante> nov23|prim24 [--boot 200]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estancamiento_invierno as ei  # noqa: E402
import feasibility_linear as fl  # noqa: E402
import la_real as lr  # noqa: E402
import puff  # noqa: E402
import puffs_cdmx as pc  # noqa: E402
import real_check_linear as rcl  # noqa: E402
import vida_quimica as vq  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variante")
    ap.add_argument("periodo", choices=list(vq.PERIODS))
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    cap, pe = ei.config(a.variante)
    vq.apply_variant(vq.STANDARD)
    start, end = vq.PERIODS[a.periodo]
    t0 = time.time()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.set_tempo_weight(3, 0)
    inp = list(fl.load_inputs(start, end, extras=True))
    cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
    for nm, (p, s) in pc.NEW_PRIORS.items():
        i = next(i for i, c in enumerate(cand.nombre) if nm in c)
        prior_pt[i], sd_pt[i] = p, s
    inp[1], inp[2] = prior_pt, sd_pt
    if cap:
        inp[10] = inp[10].clip(upper=cap)
    if pe:
        inp[10] = 1000.0 ** (1 - pe) * inp[10] ** pe
    wind = inp[9]
    rcl.load_inputs = lambda *_a, **_k: tuple(inp)
    tr = pc.Transport("domain", vq.extended_profile(), traj=puff.Trajectories(wind))
    rcl.Trajectories = lambda *_a, _tr=tr: _tr
    rcl.jacobian_hour_puff = pc.jacobian_puff_mx
    m = rcl.build(start, end, "puff", no_industry=True, extras=True)
    tb = time.time() - t0
    m.pop("E", None)
    x0, free = pc.free_sunday(m, a.boot)
    m["E"] = pc.ratio_constraint(m, x0)
    r = lr.metrics(m, a.boot)
    r.update(free)
    r["sub"] = vq.subperiods(m)
    N, b = rcl.solve(m)
    x = np.linalg.solve(N, b)
    n_pt, nr = m["n_pt"], m["n_reg"]
    r["regiones"] = fl.region_names()
    r["alfa_habil"] = x[n_pt:n_pt + nr].tolist()
    r["total_zona_habil"] = (x[n_pt:n_pt + nr] * np.asarray(m["prior_rd"])).tolist()
    r["variante"] = a.variante
    r["segundos_jacobiano"], r["segundos_total"] = tb, time.time() - t0
    out = vq.INT / f"estancamiento_inversion_{a.variante}_{a.periodo}.json"
    out.write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
    print(a.variante, a.periodo, f"LOO {r['loo_model']:.1f}/{r['loo_idw']:.1f}/{r['loo_hybrid']:.1f}",
          f"vial {r['vial_habil']:.0f}", f"dom {r['domingo']:.2f} libre {r['domingo_libre']:.2f} norm {r['norm_domingo']:.2f}",
          f"rTEMPO {r['muestra_r_tempo']:.2f}", f"{r['segundos_total']:.0f}s", flush=True)


if __name__ == "__main__":
    main()
