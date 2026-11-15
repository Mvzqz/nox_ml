"""Weekly drift of each city, its correlation with the ZMVM and the drift of the ZMVM - control difference.

Anomaly: log of the daily emission on normal business days (weekday, not atypical; for the ZMVM also not a
contingency day), minus its season mean. Weekly means over ISO weeks with at least `MIN_DAYS` days. The drift
is the spread of the weekly means beyond what the daily noise puts in it, as in
`context/knowledge/deriva.md`: sqrt(var(weekly means) - mean(within-week variance / n)). For the difference,
the weekly means of each city are subtracted and the noise of both is removed.

The detection limit of a measure lasting a whole season (k business days), with level 90 % and power 80 %
(`divergence.placebo`): 1 - exp(-z * sqrt(drift^2 + cv^2 * 2 / k)), cv the day-to-day spread.

Usage: .venv/bin/python notebooks/exploraciones/control_city/compare.py 2024-11-01 2024-12-31 monterrey puebla
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from nox_ml.validation import divergence, products

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / "out"
OFFICIAL = ROOT / "results/runs/flux_divergence"
MIN_DAYS = 3
BLOCK = 9
COLUMN = "tau_2h"
Z = float(norm.ppf(0.95) + norm.ppf(0.80))


def load(city: str, start: str, end: str) -> pd.DataFrame:
    path = (
        OFFICIAL / f"{start}_{end}.csv"
        if city == "zmvm_official"
        else OUT / f"daily_{city}_{start}_{end}.csv"
    )
    return pd.read_csv(path, index_col=0, parse_dates=True)


def normal_log(d: pd.DataFrame, exclude: pd.DatetimeIndex, column: str = COLUMN) -> pd.Series:
    keep = (d["kind"] == 0) & ~d["atypical"] & ~d.index.isin(exclude) & (d[column] > 0)
    x = np.log(d.loc[keep, column])
    return x - x.mean()


def weekly(x: pd.Series) -> pd.DataFrame:
    week = x.index.to_period("W")
    g = x.groupby(week)
    w = pd.DataFrame({"mean": g.mean(), "var": g.var(ddof=1), "n": g.size()})
    return w[w["n"] >= MIN_DAYS]


def drift(w: pd.DataFrame) -> float:
    excess = w["mean"].var(ddof=1) - (w["var"] / w["n"]).mean()
    return float(np.sqrt(max(excess, 0.0)))


def diff_drift(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, int]:
    j = a.join(b, how="inner", suffixes=("_a", "_b"))
    d = j["mean_a"] - j["mean_b"]
    excess = d.var(ddof=1) - (j["var_a"] / j["n_a"] + j["var_b"] / j["n_b"]).mean()
    return float(np.sqrt(max(excess, 0.0))), len(j)


def daily_cv(x: pd.Series) -> float:
    """Day-to-day spread inside the weeks (pooled)."""
    week = x.index.to_period("W")
    resid = x - x.groupby(week).transform("mean")
    n_weeks = week.nunique()
    return float(np.sqrt((resid**2).sum() / max(len(x) - n_weeks, 1)))


def block_drift(x: pd.Series, k: int = BLOCK, draws: int = 2000, seed: int = 0) -> float:
    """Drift with runs of `k` consecutive normal days, as the later `deriva.md`: the spread of the log mean of
    each run against the rest of the season, minus that of `k` days drawn at random."""
    v = x.sort_index().to_numpy()
    n = len(v)
    if n < 2 * k:
        return float("nan")
    runs = np.array([v[i : i + k].mean() - np.delete(v, range(i, i + k)).mean() for i in range(n - k + 1)])
    rng = np.random.default_rng(seed)
    rand = np.empty(draws)
    for j in range(draws):
        fake = rng.permutation(n) < k
        rand[j] = v[fake].mean() - v[~fake].mean()
    return float(np.sqrt(max(runs.var(ddof=1) - rand.var(ddof=1), 0.0)))


def mdc(drift_: float, cv: float, k: int) -> float:
    return float(1 - np.exp(-Z * np.sqrt(drift_**2 + cv**2 * 2 / k)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("cities", nargs="*")
    ap.add_argument("--column", default=COLUMN)
    a = ap.parse_args()
    zmvm_exclude = products.reference_exclusions(ROOT / "data", a.start, a.end, pd.DatetimeIndex([]))
    none = pd.DatetimeIndex([])
    series = {
        "zmvm_official": normal_log(load("zmvm_official", a.start, a.end), zmvm_exclude, a.column),
        "zmvm": normal_log(load("zmvm", a.start, a.end), zmvm_exclude, a.column),
    }
    for c in a.cities:
        series[c] = normal_log(load(c, a.start, a.end), none, a.column)
    weeks = {k: weekly(v) for k, v in series.items()}
    k_season = len(series["zmvm"])
    report: dict = {"start": a.start, "end": a.end, "column": a.column, "cities": {}}
    for name, x in series.items():
        d = load(name, a.start, a.end)
        ratios = divergence.day_type_ratios(pd.DataFrame(d[~d["atypical"]]).drop(columns="atypical"))
        normal = pd.DatetimeIndex(x.index)
        pl = divergence.placebo(pd.Series(d[a.column]), normal)
        row = {
            "n_days": len(x),
            "n_weeks": len(weeks[name]),
            "drift": drift(weeks[name]),
            "block_drift": block_drift(x),
            "cv": daily_cv(x),
            "sunday": ratios[a.column].get("sunday", {}).get("ratio"),
            "saturday": ratios[a.column].get("saturday", {}).get("ratio"),
            "placebo_9d": next((r["center"] for r in pl["rows"] if r["days"] == 9), None),
            "placebo_9d_mdc": next((r["mdc"] for r in pl["rows"] if r["days"] == 9), None),
        }
        if name not in ("zmvm", "zmvm_official"):
            for ref in ("zmvm", "zmvm_official"):
                j = weeks[ref].join(weeks[name], how="inner", suffixes=("_a", "_b"))
                row[f"r_weekly_{ref}"] = (
                    float(np.corrcoef(j["mean_a"], j["mean_b"])[0, 1]) if len(j) > 2 else None
                )
                dd, nw = diff_drift(weeks[ref], weeks[name])
                both = series[ref].index.intersection(x.index)
                r_daily = np.corrcoef(series[ref][both], x[both])[0, 1] if len(both) > 2 else np.nan
                diff_cv = daily_cv(series[ref][both] - x[both]) if len(both) > 5 else np.nan
                row[f"diff_{ref}"] = {
                    "drift": dd,
                    "block_drift": block_drift(series[ref][both] - x[both]),
                    "n_paired_days": len(both),
                    "ref_block_drift_paired": block_drift(series[ref][both]),
                    "ref_weekly_drift_paired": drift(weekly(series[ref][both])),
                    "weekly_drift_paired": drift(weekly(series[ref][both] - x[both])),
                    "n_weeks": nw,
                    "r_daily": float(r_daily),
                    "cv_paired": float(diff_cv),
                    "mdc_season": mdc(dd, float(diff_cv), k_season),
                }
        row["mdc_season"] = mdc(row["drift"], row["cv"], k_season)
        report["cities"][name] = row
    OUT.mkdir(exist_ok=True)
    path = OUT / f"compare_{a.start}_{a.end}_{a.column}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
