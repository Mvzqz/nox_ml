# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""NOx emission of the city from TEMPO alone: the flux divergence method (Beirle et al. 2019, 2021).

Each afternoon scan is binned on a regular grid over the stored pixels (the model's domain). With the wind of
its hour, the emission of a cell is ``div(V u) + (V - V_bg) / tau``: what leaves the cell plus what the
chemistry removes, ``V`` the NO2 column converted to NOx with the ratio the stations measured that hour
(`HourData.no2_nox`, else the period's). The city emission of a scan is the sum over the interior cells; a day
is the mean of its scans.

It uses no station NOx, no traffic counts and no transport model, so its day-type ratios are a reference for
every estimator. The absolute level depends on the wind height and on ``tau``; the ratios barely do: in
2023-2026 the Sunday/weekday ratio moved by less than 0.05 between ``tau`` of 2 and 4 h and between the
surface wind and 2.5 times it (`context/knowledge/sesgo_domingo.md`).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import HOLIDAYS, HourData
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.time import local_day

CELL_M = 5000.0  # grid cell (m): 3-4 TEMPO pixels of ~2 x 4.5 km
MIN_COVER = 0.7  # share of the interior cells a scan needs with a column
BACKGROUND_PERCENTILE = 10  # of the scan's columns, the background of the chemistry term
TAUS_H = (2.0, 4.0, np.inf)  # afternoon NOx lifetimes (h) the ratios are reported with; inf: divergence alone
PLACEBO_DAYS = (5, 9, 15)  # fake event lengths of the placebo, as `events.detection_curve`
PLACEBO_DRAWS = 2000  # cheap: no refit, only means of the daily series
EXTRAPOLATED_DAYS = (20, 60)  # a month of business days, a season


@dataclass(frozen=True)
class Grid:
    """A regular grid of `cell` metres from (`x0`, `y0`), `nx` by `ny` cells."""

    x0: float
    y0: float
    nx: int
    ny: int
    cell: float = CELL_M

    @classmethod
    def over(cls, hours: list[HourData], cell: float = CELL_M) -> "Grid":
        """The grid over the pixels of `hours` (0.5-99.5 percentiles of their positions)."""
        x = np.concatenate([h.pixels.x for h in hours if len(h.no2)])
        y = np.concatenate([h.pixels.y for h in hours if len(h.no2)])
        x0, y0 = float(np.percentile(x, 0.5)), float(np.percentile(y, 0.5))
        nx = int((np.percentile(x, 99.5) - x0) // cell) + 1
        ny = int((np.percentile(y, 99.5) - y0) // cell) + 1
        return cls(x0, y0, nx, ny, cell)

    def mean(self, x: np.ndarray, y: np.ndarray, values: np.ndarray) -> np.ndarray:
        """Mean of `values` in each cell (rows: y), NaN where no point falls."""
        ix, iy = ((x - self.x0) // self.cell).astype(int), ((y - self.y0) // self.cell).astype(int)
        inside = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        total, count = np.zeros((self.ny, self.nx)), np.zeros((self.ny, self.nx))
        np.add.at(total, (iy[inside], ix[inside]), values[inside])
        np.add.at(count, (iy[inside], ix[inside]), 1)
        with np.errstate(invalid="ignore"):
            return total / count


def scan_emission(
    hour: HourData, grid: Grid, ratio: float, taus: tuple[float, ...] = TAUS_H, wind_scale: float = 1.0
) -> dict[str, float] | None:
    """Emission of the interior cells in one scan (molecules/cm2/s summed over cells), one per lifetime in
    `taus` (h; ``inf``: no chemistry), or None when the scan covers less than `MIN_COVER` of them. `ratio`
    converts NO2 to NOx; `wind_scale` turns the hour's surface wind into the wind that carries the plume."""
    if len(hour.no2) == 0:
        return None
    v = grid.mean(hour.pixels.x, hour.pixels.y, hour.no2) / ratio
    u, w = (wind_scale * c for c in hour.wind)
    fx, fy = v * u, v * w
    div = (fx[1:-1, 2:] - fx[1:-1, :-2] + fy[2:, 1:-1] - fy[:-2, 1:-1]) / (
        2 * grid.cell
    )  # m/s and m: molecules/cm2/s
    cover = float(np.isfinite(div).mean())
    if cover < MIN_COVER:
        return None
    excess = v[1:-1, 1:-1] - np.nanpercentile(v, BACKGROUND_PERCENTILE)
    out = {"cover": cover, "excess": float(np.nanmean(excess)), "wind": float(np.hypot(u, w))}
    for tau in taus:
        emission = div + (excess / (tau * 3600) if np.isfinite(tau) else 0.0)
        out[f"tau_{tau:g}h"] = float(np.nanmean(emission)) * div.size  # gaps filled with the mean
    return out


def daily_emission(inputs: Inputs, taus: tuple[float, ...] = TAUS_H, wind_scale: float = 1.0) -> pd.DataFrame:
    """Mean city emission of the scans of each local day (rows indexed by ``day``, one column per lifetime,
    ``scans``) with its ``kind`` (0 weekday, 1 Saturday, 2 Sunday or holiday, as `day_type`), and the
    weather of the scans: the mean NOx column over the background (``excess``), ``wind`` and ``pbl``. With
    the chemistry term dominant, the emission ratios are close to the ``excess`` ratios, which do not account
    for the weather."""
    hours = [h for h in inputs.hours if len(h.no2)]
    grid = Grid.over(hours)
    rows = []
    for hour in hours:
        scan = scan_emission(hour, grid, hour.no2_nox or inputs.no2_nox_ratio, taus, wind_scale)
        if scan is not None:
            rows.append({"day": local_day(pd.Series([hour.hour]))[0], "pbl": hour.pbl, **scan})
    scans = pd.DataFrame(rows)
    daily = scans.groupby("day").mean().drop(columns="cover")
    daily["scans"] = scans.groupby("day").size()
    daily["kind"] = day_type(pd.DatetimeIndex(daily.index), HOLIDAYS)
    return daily


def day_type_ratios(
    daily: pd.DataFrame, level: float = 0.90, n_boot: int = 1000, seed: int = 0
) -> dict[str, dict[str, Any]]:
    """Saturday and Sunday over weekday of each lifetime column of `daily`, with a bootstrap interval over the
    days of each type."""
    rng = np.random.default_rng(seed)
    q = [50 * (1 - level), 50 * (1 + level)]
    out: dict[str, dict[str, Any]] = {}
    weekday = daily[daily["kind"] == WEEKDAY]
    for column in [c for c in daily.columns if c.startswith("tau_")]:
        out[column] = {}
        for name, kind in (("saturday", SATURDAY), ("sunday", SUNDAY_HOLIDAY)):
            days = daily[daily["kind"] == kind][column].to_numpy()
            base = weekday[column].to_numpy()
            if len(days) == 0 or len(base) == 0:
                continue
            boot = [
                rng.choice(days, len(days)).mean() / rng.choice(base, len(base)).mean() for _ in range(n_boot)
            ]
            lo, hi = np.percentile(boot, q)
            out[column][name] = {
                "ratio": float(days.mean() / base.mean()),
                "lo": float(lo),
                "hi": float(hi),
                "n_days": len(days),
            }
        out[column]["n_weekdays"] = len(base)
    return out


def placebo(
    daily: pd.Series,
    normal: pd.DatetimeIndex,
    counts: tuple[int, ...] = PLACEBO_DAYS,
    level: float = 0.90,
    power: float = 0.80,
    draws: int = PLACEBO_DRAWS,
    seed: int = 0,
) -> dict[str, Any]:
    """The placebo of the daily emission `daily` on the `normal` days (business days where nothing changed):
    k fake event days drawn from them over the rest, for each k of `counts`, with the keys and the detection
    rule of `events.detection_curve` (``mdc`` the drop detected with probability `power`)."""
    rng = np.random.default_rng(seed)
    values = daily[daily.index.isin(normal)].dropna().to_numpy()
    n = len(values)
    rows = []
    for k in [k for k in counts if k < n]:
        ratios = np.empty(draws)
        for i in range(draws):
            fake = rng.permutation(n) < k
            ratios[i] = values[fake].mean() / values[~fake].mean()
        lo, hi = interval(ratios, level)
        center = float(np.median(ratios))
        rows.append(
            {
                "days": k,
                "center": center,
                "lo": lo,
                "hi": hi,
                "mdc_half": 1 - lo / center,
                "mdc": 1 - lo / float(np.quantile(ratios, power)),
                "sd_log": float(np.std(np.log(ratios), ddof=1)),
            }
        )
    scale = np.array([np.sqrt(1 / r["days"] + 1 / (n - r["days"])) for r in rows])
    cv = float(scale @ np.array([r["sd_log"] for r in rows]) / (scale @ scale))
    z = float(norm.ppf(0.5 + level / 2) + norm.ppf(power))
    extrapolated = [
        {"days": k, "mdc": float(1 - np.exp(-z * cv * np.sqrt(2 / k)))} for k in EXTRAPOLATED_DAYS
    ]
    return {"n_normal": n, "power": power, "cv": cv, "rows": rows, "extrapolated": extrapolated}
