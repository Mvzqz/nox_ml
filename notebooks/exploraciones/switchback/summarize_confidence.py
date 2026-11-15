# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
# (pandas stubs do not type pivot tables)
"""Tables of the note from the output of `confidence.py`.

Usage: uv run python notebooks/exploraciones/switchback/summarize_confidence.py OUT_DIR
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

Z = norm.ppf(0.95) + norm.ppf(0.80)
WIDENING = 1.05


def md(table: pd.DataFrame | pd.Series, digits: int = 2) -> str:
    return table.round(digits).to_markdown()


def combined(sd_log: pd.Series) -> float:
    """Minimum detectable drop of seasons combined by inverse variance (normal approximation)."""
    return float(1 - np.exp(-Z * WIDENING * np.sum(sd_log**-2) ** -0.5))


def calibration(out: Path) -> None:
    frame = pd.read_csv(out / "calibration.csv")
    index = ["estimator", "design"]
    clean = frame[frame["scenario"] == "none"]
    print("\nFalse alarms (drop 0), mean and max over seasons")
    print(
        md(clean[clean["drop"] == 0].pivot_table(index=index, values="detected", aggfunc=["mean", "max"]), 3)
    )
    inside = clean[clean["drop"] > 0]
    print("\nCoverage of the true drop, 5-20 %, mean and min over seasons and drops")
    print(md(inside.pivot_table(index=index, values="coverage", aggfunc=["mean", "min"]), 3))
    print("\nCoverage by season, drop 10 %")
    print(md(clean[clean["drop"] == 0.10].pivot_table(index=index, columns="season", values="coverage")))
    print("\nFalse alarms by season")
    print(md(clean[clean["drop"] == 0].pivot_table(index=index, columns="season", values="detected"), 3))
    print("\nMinimum detectable drop")
    print(md(clean[clean["drop"] == 0].pivot_table(index=index, columns="season", values="mdd")))
    carried = frame[(frame["scenario"] == "carry50") & (frame["drop"] == 0.20)]
    print("\nCoverage with carryover 50 %, drop 20 %")
    print(md(carried.pivot_table(index=index, columns="season", values="coverage")))


def carry(out: Path) -> None:
    frame = pd.read_csv(out / "carry.csv")
    zero = frame[frame["drop"] == 0.0]
    for estimator in ("e7", "e7_satellite"):
        part = zero[zero["estimator"] == estimator]
        table = part.pivot_table(index=["design", "scenario"], columns="season", values="mdd")
        print(f"\n[{estimator}] Minimum detectable drop")
        print(md(table))
        sd = part.pivot_table(index=["design", "scenario"], columns="season", values="sd_log")
        print(f"\n[{estimator}] Six seasons combined")
        print(md(sd.apply(combined, axis=1), 3))
        days = part.pivot_table(index=["design", "scenario"], columns="season", values="c_mean")
        print(f"\n[{estimator}] Mean control days used")
        print(md(days, 1))
    rate = frame[(frame["drop"] == 0.2) & (frame["estimator"] == "e7_satellite")]
    print("\n[e7_satellite] Coverage at drop 20 %, mean over seasons")
    print(md(rate.pivot_table(index=["design", "scenario"], values="coverage"), 3))


def fewer(out: Path) -> None:
    frame = pd.read_csv(out / "fewer.csv")
    frame["k"] = (frame["n"] / 2).astype(int)
    for estimator in ("e7", "e7_satellite"):
        part = frame[frame["estimator"] == estimator]
        for scenario in ("none", "carry50"):
            sub = part[part["scenario"] == scenario]
            print(f"\n[{estimator}] Minimum detectable by N days: median, min, max ({scenario})")
            table = sub.pivot_table(index="design", columns="n", values="mdd", aggfunc="median")
            print(md(table))
            best = sub.pivot_table(index="design", columns="n", values="mdd", aggfunc="min")
            print(md(best))
            worst = sub.pivot_table(index="design", columns="n", values="mdd", aggfunc="max")
            print(md(worst))
        print(
            md(
                part[part["scenario"] == "none"].pivot_table(
                    index="season", columns=["design", "n"], values="mdd", aggfunc="median"
                )
            )
        )


def years(out: Path) -> None:
    frame = pd.read_csv(out / "years.csv")
    print(md(frame.pivot_table(index=["estimator", "design"], columns="pair", values="value"), 3))


if __name__ == "__main__":
    for step in (calibration, carry, fewer, years):
        if (Path(sys.argv[1]) / f"{step.__name__}.csv").exists():
            print(f"\n=== {step.__name__} ===")
            step(Path(sys.argv[1]))
