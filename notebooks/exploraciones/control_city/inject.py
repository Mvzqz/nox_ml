# ruff: noqa: E501
"""Injected drops in the ZMVM, read with the ZMVM alone and with the difference ZMVM - control.

On the business days where both series have a value (normal days, `compare.normal_log`), a measure is a run
of `k` consecutive days. Its estimate is the log mean of the run minus that of the rest of the season: for
the ZMVM alone on the ZMVM series, for the difference in differences on ZMVM - control. A drop `d` is
injected in the ZMVM only (log(1 - d) added to the run).

The range comes from the placebo of the same estimator: the estimates of the other runs of the season
without injection that do not overlap the tested one (all of them if fewer than `MIN_NULL`), so it carries
the drift of consecutive days. Per drop and run length: detection (the estimate below the 5 % quantile of
the placebo), coverage (the true log change inside the 90 % range: estimate minus the 5-95 % quantiles of
the placebo) and, for a drop of 0, the false alarms (outside the 5-95 % quantiles). The minimum detectable
change is the smallest drop of a 1 % grid detected in 80 % of the runs; ``mdc_sd`` the one from the spread of
the runs, 1 - exp(-2.49 sd), the rule of `products`.

Usage: .venv/bin/python notebooks/exploraciones/control_city/inject.py puebla 2024-11-01:2024-12-31 2025-02-15:2025-05-31
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from compare import OUT, ROOT, load, normal_log

from nox_ml.validation import products

DROPS = (0.0, 0.10, 0.15, 0.20)
RUNS = (9, 20)
MIN_NULL = 5
POWER = 0.80
Z = 2.49  # one-sided 5 % plus 80 % power, as `products`


def run_estimates(x: np.ndarray, k: int) -> np.ndarray:
    """Log mean of each run of `k` consecutive days minus that of the rest."""
    total, n = x.sum(), len(x)
    return np.array([x[i : i + k].mean() - (total - x[i : i + k].sum()) / (n - k) for i in range(n - k + 1)])


def evaluate(x: np.ndarray, k: int, drops: np.ndarray) -> dict[str, np.ndarray]:
    """Detection, coverage and false alarms of runs of `k` days for each drop (one row per run)."""
    base = run_estimates(x, k)
    m = len(base)
    shift = np.log(1 - drops)  # the run moves by log(1 - d), the rest is untouched
    detect = np.zeros((m, len(drops)), bool)
    cover = np.zeros((m, len(drops)), bool)
    alarm = np.zeros(m, bool)
    for i in range(m):
        others = np.array([j for j in range(m) if abs(j - i) >= k])
        null = base[others] if len(others) >= MIN_NULL else np.delete(base, i)
        lo, hi = np.quantile(null, [0.05, 0.95])
        est = base[i] + shift
        detect[i] = est < lo
        cover[i] = (est - hi <= shift) & (shift <= est - lo)
        alarm[i] = not (lo <= base[i] <= hi)
    return {"detect": detect, "cover": cover, "alarm": alarm}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("city")
    ap.add_argument("seasons", nargs="+")
    ap.add_argument("--column", default="tau_2h")
    ap.add_argument("--zmvm", default="zmvm", help="zmvm (same method) or zmvm_official")
    a = ap.parse_args()
    grid = np.round(np.arange(0, 0.61, 0.01), 2)
    report = {"city": a.city, "zmvm": a.zmvm, "column": a.column, "seasons": {}}
    pooled: dict = {}
    for season in a.seasons:
        start, end = season.split(":")
        exclude = products.reference_exclusions(ROOT / "data", start, end, pd.DatetimeIndex([]))
        z = normal_log(load(a.zmvm, start, end), exclude, a.column)
        c = normal_log(load(a.city, start, end), pd.DatetimeIndex([]), a.column)
        both = z.index.intersection(c.index).sort_values()
        series = {"zmvm": z[both].to_numpy(), "did": (z[both] - c[both]).to_numpy()}
        out: dict = {"n_days": len(both)}
        for name, x in series.items():
            x = x - x.mean()
            for k in RUNS:
                if len(x) < 2 * k:
                    continue
                r = evaluate(x, k, grid)
                key = f"{name}_{k}"
                pooled.setdefault(key, []).append(r)
                rate = r["detect"].mean(0)
                hit = np.where(rate >= POWER)[0]
                out[key] = {
                    "runs": len(r["alarm"]),
                    "false_alarm": float(r["alarm"].mean()),
                    "detect": {f"{d:.2f}": float(rate[grid == d][0]) for d in DROPS[1:]},
                    "cover": {f"{d:.2f}": float(r["cover"].mean(0)[grid == d][0]) for d in DROPS},
                    "mdc": float(grid[hit[0]]) if len(hit) else None,
                    "sd_runs": float(np.std(run_estimates(x, k), ddof=1)),
                    "mdc_sd": float(1 - np.exp(-Z * np.std(run_estimates(x, k), ddof=1))),
                }
        report["seasons"][season] = out
    report["pooled"] = {}
    for key, rs in pooled.items():
        detect = np.vstack([r["detect"] for r in rs])
        cover = np.vstack([r["cover"] for r in rs])
        rate = detect.mean(0)
        hit = np.where(rate >= POWER)[0]
        report["pooled"][key] = {
            "runs": len(detect),
            "false_alarm": float(np.concatenate([r["alarm"] for r in rs]).mean()),
            "detect": {f"{d:.2f}": float(rate[grid == d][0]) for d in DROPS[1:]},
            "cover": {f"{d:.2f}": float(cover.mean(0)[grid == d][0]) for d in DROPS},
            "mdc": float(grid[hit[0]]) if len(hit) else None,
        }
    path = OUT / f"inject_{a.city}_{a.zmvm}_{a.column}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
