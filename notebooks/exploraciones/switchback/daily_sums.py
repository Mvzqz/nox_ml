"""Per-day sums of the E7 (normalized_ratio) terms on the normal business days of six seasons.

E7's ratio of a group of days over another is (sum obs / sum model) of one over the other, with hourly
rows ``obs`` = mean station NOx - point sources - background and ``model`` = mean modeled road NOx
(`nox_ml.models.normalized_ratio`). Both are sums, so any design is a ratio of per-day sums. The injection
of the sheets (`events.inject_drop`) lowers station NOx above the background by d, which turns ``obs``
into ``(1 - d) obs - d point``: linear too, so the per-day point term is kept as well.

Usage (from the repo root): uv run python notebooks/exploraciones/switchback/daily_sums.py OUT_DIR
Writes OUT_DIR/<season>.csv with columns day, obs, model, point, hours.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import BACKGROUND_STATION
from nox_ml.time import local_day
from nox_ml.validation import events, products

SEASONS = {
    "nd2023": ("2023-11-01", "2023-12-31"),
    "fm2024": ("2024-02-15", "2024-05-31"),
    "nd2024": ("2024-11-01", "2024-12-31"),
    "fm2025": ("2025-02-15", "2025-05-31"),
    "nd2025": ("2025-11-01", "2025-12-31"),
    "fm2026": ("2026-02-15", "2026-05-31"),
}
DATA = Path("data")


def season_table(start: str, end: str) -> pd.DataFrame:
    inputs = products.season_inputs(DATA, start, end, products.sources_for(start, end))
    excluded = products.reference_exclusions(DATA, start, end, pd.DatetimeIndex([]))
    normal = events.split_days(inputs, pd.DatetimeIndex([]), excluded).normal
    data = inputs.on_days(normal)
    key, transport = plume_transport(np.deg2rad(15.0), 1.0)  # the transport of E7
    n_points = len(data.points)
    prior = data.points["prior"].to_numpy(float)
    rows = []
    for hour, jac in zip(data.hours, data.jacobians(key, transport), strict=True):
        if len(hour.nox) == 0:
            continue
        point = jac.stations[:, :n_points] @ prior
        rows.append(
            {
                "day": local_day(hour.hour),
                "obs": float((hour.nox - point - BACKGROUND_STATION[0]).mean()),
                "model": float(jac.stations[:, n_points:].sum(axis=1).mean()),
                "point": float(point.mean()),
                "hours": 1,
            }
        )
    return pd.DataFrame(pd.DataFrame(rows).groupby("day", as_index=False).sum())


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, (start, end) in SEASONS.items():
        table = season_table(start, end)
        table.to_csv(out / f"{name}.csv", index=False)
        print(name, len(table), "normal business days", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
