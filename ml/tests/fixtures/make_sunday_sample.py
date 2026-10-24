"""Rebuilds ``sunday_sample.csv`` from the research output (needs `dvc pull`).

Usage: uv run python ml/tests/fixtures/make_sunday_sample.py

The source is ``data/interim/sunday_diag_days.csv``: for each local day of Nov-Dec 2023 (61 days), the mean
afternoon (12-17 h) NOx observed at the stations (``obs``, ppb) and the NOx that the transport model predicts
with fixed road emission (``model``, ppb), with ``dt`` the day type (0 weekday, 1 Saturday, 2 Sunday/holiday).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("sunday_sample.csv")

if __name__ == "__main__":
    src = pd.read_csv(ROOT / "data/interim/sunday_diag_days.csv", usecols=["day", "dt", "obs", "model"])
    src = src.rename(columns={"dt": "group"}).round(4)
    src.to_csv(OUT, index=False)
    print(f"{len(src)} days -> {OUT.relative_to(ROOT)}")
