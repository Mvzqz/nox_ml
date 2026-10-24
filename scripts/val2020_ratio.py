"""Estimador simple normalizado por meteorología: (NOₓ observado ÷ NOₓ modelado con emisión fija),
cociente entre periodos, con IC 90 % por bootstrap de días. Lee las salidas horarias de val2020_linear.py.

Uso: .venv/bin/python scripts/val2020_ratio.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
rng = np.random.default_rng(7)
NAMES = ["base", "fase2", "fase3"]
DAY = ["hábil", "fin de semana/festivo"]


def ratio(df, g0, g1):
    if not ((df.g == g0).any() and (df.g == g1).any()):
        return np.nan
    a, b = df[df.g == g0], df[df.g == g1]
    return (b.obs.sum() / b.modelo.sum()) / (a.obs.sum() / a.modelo.sum())


def main(boot=1000):
    out, samples = {}, {}
    for y in (2020, 2019):
        df = pd.read_parquet(INT / f"val2020_hourly_{y}.parquet")
        days = df.day.unique()
        for p in (1, 2):
            for dt in (0, 1):
                key = f"{NAMES[p]}/base|{DAY[dt]}"
                est = ratio(df, dt, 2 * p + dt)
                bs = []
                for _ in range(boot):
                    pick = rng.choice(days, len(days))
                    d = pd.concat([df[df.day == q] for q in pick])
                    bs.append(ratio(d, dt, 2 * p + dt))
                samples[(y, key)] = np.array(bs)
                out.setdefault(str(y), {})[key] = {"estimado": est, "ic90": [float(np.nanpercentile(bs, 5)), float(np.nanpercentile(bs, 95))]}
    for key in out["2020"]:
        a, b = samples[(2020, key)], samples[(2019, key)]
        smp = a / rng.permutation(b)
        out.setdefault("did", {})[key] = {"estimado": out["2020"][key]["estimado"] / out["2019"][key]["estimado"],
                                          "ic90": [float(np.nanpercentile(smp, 5)), float(np.nanpercentile(smp, 95))]}
    (INT / "val2020_ratio.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k, v in out.items():
        print(f"== {k}")
        for kk, vv in v.items():
            print(f"  {kk:32s} {vv['estimado']:.2f} (IC90 {vv['ic90'][0]:.2f}–{vv['ic90'][1]:.2f})")


if __name__ == "__main__":
    main()
