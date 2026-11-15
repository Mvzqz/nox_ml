# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
# (pandas stubs do not type pivot tables)
"""Tables of the note from the output of `simulate.py`.

Usage: uv run python notebooks/exploraciones/switchback/summarize.py OUT_DIR
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

Z = norm.ppf(0.95) + norm.ppf(0.80)  # one-sided 5 % (lower bound of a 90 % range) and 80 % power
WIDENING = 1.05


def md(table: pd.DataFrame | pd.Series, digits: int = 2) -> str:
    return table.round(digits).to_markdown()


def drift(spread: pd.Series, reference: str) -> pd.DataFrame:
    """Drift left by each design as in deriva.md: its spread around no change minus, in quadrature, the
    spread of random days (`reference`) of the same season."""
    out = {}
    for key, value in spread.items():
        design, season = key  # pyright: ignore[reportGeneralTypeIssues]
        base = spread[(reference, season)]
        out[(design, season)] = np.sqrt(max(value**2 - base**2, 0.0))
    return pd.DataFrame(pd.Series(out).unstack())


def main(out: Path) -> None:
    frame = pd.read_csv(out / "switchback.csv")
    zero_all = frame[frame["drop"] == 0.0]
    for estimator in ("e7", "e7_satellite"):
        zero = zero_all[zero_all["estimator"] == estimator]
        for carry in ("none", "carry50"):
            table = zero[zero["carryover"] == carry].pivot_table(
                index="design", columns="season", values="mdd"
            )
            print(f"\n[{estimator}] Minimum detectable drop, carryover={carry}\n{md(table)}")
        base = zero[zero["carryover"] == "none"].set_index(["design", "season"])
        # Six seasons combined by inverse variance of the log ratio (normal approximation).
        sd = base["sd_log"].groupby("design").apply(lambda s: float(np.sum(s**-2) ** -0.5))
        print(f"\n[{estimator}] Six seasons combined (no carryover)\n{md(1 - np.exp(-Z * WIDENING * sd), 3)}")
        spread = base["rms_log"]
        print(f"\n[{estimator}] Spread of the log ratio around 1 (rms)\n{md(spread.unstack(), 3)}")
        nine = drift(spread[spread.index.get_level_values(0).str.startswith("ref_")], "ref_random9")
        half = drift(spread[~spread.index.get_level_values(0).str.startswith("ref_")], "e_random_days")
        print(f"\n[{estimator}] Drift, runs of 9 days over 9 random\n{md(nine, 3)}")
        print(f"\n[{estimator}] Drift left by each design over random days\n{md(half, 3)}")
        print(f"means: 9-day runs {nine.loc['ref_contiguous9'].mean():.3f}; designs")
        print(md(half.mean(axis=1), 3))
    e7 = frame[frame["estimator"] == "e7"]
    zero = e7[e7["drop"] == 0.0]
    sizes = zero.groupby("design")[["k_mean", "n_days", "sd_log"]].mean()
    print(f"\nPer design, mean over seasons\n{md(sizes, 3)}")
    false_alarm = zero.pivot_table(index="design", columns="carryover", values="detected", aggfunc="mean")
    print(f"\nFalse alarms (drop 0), mean over seasons\n{md(false_alarm, 3)}")
    boot = zero.dropna(subset=["boot_coverage0"]).pivot_table(
        index="design", columns="season", values="boot_coverage0"
    )
    print(f"\nCoverage of 1 by the day bootstrap (nominal 0.90)\n{md(boot)}")
    by_drop = {"index": ["design", "carryover"], "columns": "drop", "aggfunc": "mean"}
    coverage = e7.pivot_table(values="coverage", **by_drop)
    print(f"\nRange coverage of the true drop, mean over seasons\n{md(coverage)}")
    print(f"\nShare detected, mean over seasons\n{md(e7.pivot_table(values='detected', **by_drop))}")
    center = zero[zero["carryover"] == "none"].pivot_table(
        index="design", columns="season", values="placebo_center"
    )
    print(f"\nPlacebo center\n{md(center)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
