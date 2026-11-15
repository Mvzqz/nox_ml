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


def main(out: Path) -> None:
    frame = pd.read_csv(out / "switchback.csv")
    zero = frame[frame["drop"] == 0.0]
    for carry in ("none", "carry50"):
        table = zero[zero["carryover"] == carry].pivot_table(index="design", columns="season", values="mdd")
        print(f"\nMinimum detectable drop, carryover={carry}\n{table.round(2).to_markdown()}")
    # Six seasons combined by inverse variance of the log ratio (normal approximation).
    base = zero[zero["carryover"] == "none"].set_index(["design", "season"])
    sd = base["sd_log"].groupby("design").apply(lambda s: float(np.sum(s**-2) ** -0.5))
    print("\nSix seasons combined (normal approximation, no carryover):")
    print((1 - np.exp(-Z * WIDENING * sd)).rename("mdd").round(3).to_markdown())
    print("\nPer design, mean over seasons:")
    cols = ["k_mean", "n_days", "sd_log"]
    print(base[cols].groupby("design").mean().round(3).to_markdown())
    false_alarm = zero.pivot_table(index="design", columns="carryover", values="detected", aggfunc="mean")
    print(f"\nFalse alarms (drop 0), mean over seasons\n{false_alarm.round(3).to_markdown()}")
    boot = zero.dropna(subset=["boot_coverage0"]).pivot_table(
        index="design", columns="season", values="boot_coverage0"
    )
    print(f"\nCoverage of 1 by the day bootstrap (nominal 0.90)\n{boot.round(2).to_markdown()}")
    coverage = frame.pivot_table(
        index=["design", "carryover"], columns="drop", values="coverage", aggfunc="mean"
    )
    print(f"\nRange coverage of the true drop, mean over seasons\n{coverage.round(2).to_markdown()}")
    power = frame.pivot_table(
        index=["design", "carryover"], columns="drop", values="detected", aggfunc="mean"
    )
    print(f"\nShare detected, mean over seasons\n{power.round(2).to_markdown()}")
    recovered = frame[frame["drop"] == 0.2].pivot_table(
        index="design", columns="carryover", values="mean_recovered"
    )
    print(f"\nMedian recovered drop at 20 %\n{recovered.round(3).to_markdown()}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
