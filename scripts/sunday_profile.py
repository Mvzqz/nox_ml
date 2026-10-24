"""Perfil de verosimilitud del cociente domingo/hábil: se fija α_domingo,r = c·α_hábil,r en las 9 regiones
(c = 0.42 … 1.0, restricción casi exacta) y se mide el ajuste en muestra y la validación LOO.
Si el ajuste casi no cambia con c, los datos no determinan el cociente y el 0.42 lo decide el fondo por hora.

Uso: .venv/bin/python scripts/sunday_profile.py
"""
import json
from pathlib import Path

import numpy as np

import improve_real as ir
import real_check_linear as rcl

ROOT = Path(__file__).resolve().parents[1]


def main():
    ir.configure(sigma30=True)
    m = rcl.build(ir.START, ir.END, "domain", no_industry=True, extras=True)
    N0, b0 = rcl.solve(m)
    x0 = np.linalg.solve(N0, b0)
    obs = np.array([r[4] for r in m["st_rows"]])
    n_src, H = m["n_pt"] + 27, len(m["hours"])
    dts = np.array([rcl.day_type(h) for h in m["hours"]])
    out = []
    for c in (None, 0.42, 0.55, 0.65, 0.80, 1.0):
        E = None
        if c is not None:
            ir.RATIO_PRIOR, ir.RATIO_SD = {2: c}, 1e-3
            E = ir.ratio_constraint(m, x0)
        N, b = rcl.solve(m)
        x = np.linalg.solve(N + E if E is not None else N, b)
        pred = np.array([kr @ x[idx] for _, _, idx, kr, _ in m["st_rows"]])
        chi2 = float(((obs - pred) ** 2).sum() / rcl.SIG_ST ** 2)
        tot = rcl.road_totals(m, x)
        bg = x[n_src:n_src + H]
        r = ir.evaluate(m, E)
        row = dict(c=c, sun=float(tot[2] / tot[0]), rmse=float(np.sqrt(np.mean((obs - pred) ** 2))), chi2=chi2,
                   bg_habil=float(bg[dts == 0].mean()), bg_dom=float(bg[dts == 2].mean()),
                   rm=float(r["rm"]), rh=float(r["rh"]), um=float(r["um"]), win=int(r["win"]))
        out.append(row)
        print(row, flush=True)
    ir.RATIO_PRIOR, ir.RATIO_SD = {1: 0.95, 2: 0.80}, 0.15
    ir.configure()
    (ROOT / "data/interim/sunday_profile.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
