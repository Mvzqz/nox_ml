"""Test 1: the east share of the TEMPO flux divergence, aggregated by the report's six zones.

Same scans, grid and formula as `nox_ml.validation.divergence.scan_emission`, but the interior cells are
summed by zone (the 3x3 regions of `data.roads`) instead of over the whole city. Weekdays only, without the
atypical periods and the contingency days. Usage: flux_zones.py [wind_scale]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import calendar, roads
from nox_ml.inversion.normalized import WEEKDAY
from nox_ml.time import local_day
from nox_ml.validation import divergence as dv
from nox_ml.validation import products
from nox_ml.validation.report_final import ZONES

DATA = Path("data")
SEASONS = [
    ("2023-11-01", "2023-12-31"),
    ("2024-02-15", "2024-05-31"),
    ("2024-11-01", "2024-12-31"),
    ("2025-02-15", "2025-05-31"),
    ("2025-11-01", "2025-12-31"),
    ("2026-02-15", "2026-05-31"),
]
TAUS = (2.0, 4.0)
OUT = Path(__file__).parent / "out"


def region_of_cells(grid: dv.Grid) -> np.ndarray:
    """Region (0-8) of each interior cell of `grid` by its centre, as `roads.road_emission_cells` does."""
    x0, y0, x1, y1 = roads.domain_bounds_utm()
    nx, ny = int((x1 - x0) // roads.CELL_M) + 1, int((y1 - y0) // roads.CELL_M) + 1
    ix = np.arange(1, grid.nx - 1)
    iy = np.arange(1, grid.ny - 1)
    cx = np.clip(((grid.x0 + (ix + 0.5) * grid.cell - x0) // roads.CELL_M).astype(int), 0, nx - 1)
    cy = np.clip(((grid.y0 + (iy + 0.5) * grid.cell - y0) // roads.CELL_M).astype(int), 0, ny - 1)
    return cx[None, :] * roads.N_SPLIT // nx + roads.N_SPLIT * (cy[:, None] * roads.N_SPLIT // ny)


def zone_sums(values: np.ndarray, region: np.ndarray) -> dict[str, float]:
    """Sum of `values` over the cells of each zone, the missing cells taking the mean of their zone."""
    out = {}
    for name, members in ZONES.items():
        v = values[np.isin(region, members)]
        out[name] = float(np.nanmean(v)) * v.size if np.isfinite(v).any() else np.nan
    return out


def season_zones(start: str, end: str, wind_scale: float) -> pd.DataFrame:
    """One row per scan and zone: day and the zone's divergence, excess and emissions for each lifetime."""
    inputs = products.load_inputs(DATA, start, end, (12, 17), products.sources_for(start, end))
    hours = [h for h in inputs.hours if len(h.no2)]
    grid = dv.Grid.over(hours)
    region = region_of_cells(grid)
    rows = []
    for hour in hours:
        v = grid.mean(hour.pixels.x, hour.pixels.y, hour.no2) / (hour.no2_nox or inputs.no2_nox_ratio)
        u, w = (wind_scale * c for c in hour.wind)
        fx, fy = v * u, v * w
        div = (fx[1:-1, 2:] - fx[1:-1, :-2] + fy[2:, 1:-1] - fy[:-2, 1:-1]) / (2 * grid.cell)
        if np.isfinite(div).mean() < dv.MIN_COVER:
            continue
        excess = v[1:-1, 1:-1] - np.nanpercentile(v, dv.BACKGROUND_PERCENTILE)
        day = local_day(pd.Series([hour.hour]))[0]
        layers = {"div": div, "excess": excess} | {f"tau{t:g}": div + excess / (t * 3600) for t in TAUS}
        sums = {k: zone_sums(a, region) for k, a in layers.items()}
        for zone in ZONES:
            rows.append({"day": day, "zone": zone} | {k: s[zone] for k, s in sums.items()})
    return pd.DataFrame(rows)


def east_share(table: pd.DataFrame) -> float:
    return table["Oriente"].mean() / table.sum(axis=1).mean()


def main(wind_scale: float = 1.0) -> None:
    OUT.mkdir(exist_ok=True)
    result = []
    rng = np.random.default_rng(0)
    for start, end in SEASONS:
        scans = season_zones(start, end, wind_scale)
        days = pd.DatetimeIndex(scans["day"].unique())
        kind = dv.day_type(days, dv.HOLIDAYS)
        left_out = products.reference_exclusions(DATA, start, end, pd.DatetimeIndex([]))
        keep = days[(kind == WEEKDAY) & ~days.isin(calendar.atypical_days(start, end)) & ~days.isin(left_out)]
        scans = scans[pd.DatetimeIndex(scans["day"]).isin(keep)]
        daily = scans.groupby(["day", "zone"]).mean().reset_index()
        for col in ("div", "excess", *(f"tau{t:g}" for t in TAUS)):
            table = daily.pivot(index="day", columns="zone", values=col)[list(ZONES)].clip(lower=0)
            boot = [east_share(table.iloc[rng.integers(0, len(table), len(table))]) for _ in range(500)]
            row = {
                "season": start,
                "layer": col,
                "n_days": len(table),
                "east": east_share(table),
                "lo": np.percentile(boot, 5),
                "hi": np.percentile(boot, 95),
            }
            result.append(row | {z: table[z].mean() / table.sum(axis=1).mean() for z in ZONES})
        print(pd.DataFrame(result).tail(4).round(3).to_string(), flush=True)
    frame = pd.DataFrame(result)
    frame.to_csv(OUT / f"flux_zones_w{wind_scale:g}.csv", index=False)
    print(frame.pivot(index="season", columns="layer", values="east").round(3))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0)
