"""Meteorology-normalized estimator of emission change.

The index of a period is ``sum(observed NOx) / sum(modeled NOx with fixed emission)``. The model carries the
effect of the weather (ventilation) and the emission is held at its prior, so the ratio of the index between
two periods estimates the change in emission once the weather is discounted. Unlike the full inversion it has
no free background term to trade off against the emission.

Tables are long-format DataFrames with columns ``obs`` and ``model`` (one row per hour or per day), a ``day``
column when bootstrapping, and a ``group`` column labelling the period or day type.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable

import numpy as np
import pandas as pd

WEEKDAY, SATURDAY, SUNDAY_HOLIDAY = 0, 1, 2
CDMX_UTC_OFFSET_H = 6  # Mexico City local time is UTC-6 (no daylight saving since 2022)


def local_day(utc: pd.Series | pd.DatetimeIndex, utc_offset_h: int = CDMX_UTC_OFFSET_H):
    """Local calendar day (midnight) of naive UTC timestamps."""
    shifted = utc - pd.Timedelta(hours=utc_offset_h)
    return shifted.dt.normalize() if isinstance(shifted, pd.Series) else shifted.normalize()


def day_type(days: pd.DatetimeIndex, holidays: Collection[str] = ()) -> np.ndarray:
    """0 weekday, 1 Saturday, 2 Sunday or holiday (holidays are 'YYYY-MM-DD' strings)."""
    holiday = days.strftime("%Y-%m-%d").isin(list(holidays))
    return np.select(
        [(days.day_of_week == 6) | holiday, days.day_of_week == 5], [SUNDAY_HOLIDAY, SATURDAY], WEEKDAY
    )


def index(df: pd.DataFrame) -> float:
    """Observed over modeled NOx of a set of rows."""
    return float(df["obs"].to_numpy().sum() / df["model"].to_numpy().sum())


def ratio(df: pd.DataFrame, g0: Hashable, g1: Hashable, group_col: str = "group") -> float:
    """Index of group ``g1`` over index of group ``g0``; NaN if either group is absent."""
    a, b = df.loc[df[group_col] == g0], df.loc[df[group_col] == g1]
    if a.empty or b.empty:
        return np.nan
    return index(b) / index(a)


def bootstrap_ratio(
    df: pd.DataFrame,
    g0: Hashable,
    g1: Hashable,
    n_boot: int,
    rng: np.random.Generator,
    group_col: str = "group",
    day_col: str = "day",
) -> np.ndarray:
    """Ratio of ``g1`` over ``g0`` on ``n_boot`` resamples of whole days (with replacement).

    Resampling days, not hours, keeps the within-day correlation. Replicates that lose a group are NaN.
    """
    day = pd.factorize(df[day_col])[0]
    group, obs, model = df[group_col].to_numpy(), df.obs.to_numpy(), df.model.to_numpy()
    table = np.zeros((day.max() + 1, 4))  # per day: obs and model of g0, obs and model of g1
    for k, g in enumerate((g0, g1)):
        sel = group == g
        np.add.at(table[:, 2 * k], day[sel], obs[sel])
        np.add.at(table[:, 2 * k + 1], day[sel], model[sel])
    pick = rng.integers(len(table), size=(n_boot, len(table)))
    o0, m0, o1, m1 = table[pick].sum(axis=1).T
    out = np.full(n_boot, np.nan)
    ok = (m0 > 0) & (m1 > 0) & (o0 > 0)
    out[ok] = (o1[ok] / m1[ok]) / (o0[ok] / m0[ok])
    return out


def interval(samples: np.ndarray, level: float = 0.90) -> tuple[float, float]:
    """Central percentile interval of bootstrap or placebo samples, ignoring NaN."""
    tail = 50 * (1 - level)
    lo, hi = np.nanpercentile(samples, [tail, 100 - tail])
    return float(lo), float(hi)


def difference_in_differences(
    target: np.ndarray, control: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Target over control ratio samples; the two bootstraps are independent, so they pair at random."""
    return target / rng.permutation(control)
