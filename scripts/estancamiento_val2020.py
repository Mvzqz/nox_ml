"""Estancamiento: validación 2020 (confinamiento) con otro piso de viento U_MIN en el modelo de pluma.

Reconstruye las series horarias (observado y modelo con emisión vial fija) de val2020_linear.py sin invertir y calcula los
mismos cocientes de val2020_ratio.py (fase / base, año 2020 y placebo 2019). No sobrescribe los archivos originales.

Uso: .venv/bin/python scripts/estancamiento_val2020.py [--sigma15] 1.0 1.5 2.0 2.5 3.0 2.0:1500   (piso[:tope de capa límite en m])
Salida: data/interim/estancamiento_val2020.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feasibility_linear as fl  # noqa: E402
import val2020_linear as vl  # noqa: E402
import val2020_ratio as vr  # noqa: E402

INT = vl.INT


def hourly(year, umin, cap=None):
    fl.U_MIN = umin
    cand, prior_pt, sd_pt, cells, prior_rd, st = vl.static_inputs()
    nox, wind, pbl, _ = vl.dynamic_inputs(st)
    if cap:
        pbl = pbl.clip(upper=cap)
    n_pt = len(cand)
    px_empty = pd.DataFrame({"x": [], "y": []})
    rows = []
    for gi, (name, a, b) in enumerate(vl.PERIODS[year]):
        for h in sorted(set(nox[nox.local.between(a, f"{b} 23:59")].h) & set(wind.index)):
            nh = nox[nox.h == h]
            K = fl.jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, px_empty, 0.8)[0][1]
            rows.append({"h": h, "day": (h - pd.Timedelta(hours=6)).normalize(), "g": gi * 2 + vl.day_type(h),
                         "obs": nh.NOX.mean(), "modelo": K[:, n_pt:n_pt + 9].sum(1).mean()})
    return pd.DataFrame(rows)


def main():
    out = {}
    legacy = "--sigma15" in sys.argv
    fl.SIGMA_THETA = fl.SIGMA_THETA_LEGACY if legacy else fl.SIGMA_THETA        # 15° reproduce val2020_ratio.json original
    tag = "sigma15" if legacy else "sigma30"
    for arg in [a for a in sys.argv[1:] if not a.startswith("--")]:
        umin, cap = float(arg.split(":")[0]), (float(arg.split(":")[1]) if ":" in arg else None)   # "2.0:1500" = piso 2.0 y capa límite ≤ 1500 m
        etq = f"U_MIN={umin}" + (f"|cap={cap:g}" if cap else "")
        for y in (2020, 2019):
            df = hourly(y, umin, cap)
            for p in (1, 2):
                for dt in (0, 1):
                    out[f"{tag}|{etq}|{y}|{vr.NAMES[p]}|{vr.DAY[dt]}"] = float(vr.ratio(df, dt, 2 * p + dt))
        print(etq, {k.split("|", 1)[1]: round(v, 2) for k, v in out.items() if k.startswith(f"{tag}|{etq}|")}, flush=True)
    f = INT / "estancamiento_val2020.json"
    old = json.loads(f.read_text()) if f.exists() else {}
    old.update(out)
    f.write_text(json.dumps(old, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
