"""Placebo calibration of the meteorology-normalized estimator on event days (e.g. pollution contingencies).

An event day is compared with reference days of the same weekday within ``WINDOW`` days that are not events.
The estimator is run on fake event days drawn from non-event days, where no emission change exists, to see how
far from 1 a null result lands. Days are Timestamps indexing a *daily table* from :func:`daily_table`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from datetime import datetime

import numpy as np
import pandas as pd

from nox_ml.inversion.normalized import interval
from nox_ml.time import local_day, local_hour

WINDOW = 28  # days searched on each side for reference days
MIN_HOURS = 4  # a day needs this many valid hours to enter the daily table


def daily_table(
    hourly: pd.DataFrame,
    holidays: Collection[str] = (),
    min_hours: int = MIN_HOURS,
    extras: Sequence[str] = (),
) -> pd.DataFrame:
    """Daily sums of hourly ``obs`` and ``model`` (``day`` column = local day), indexed by day.

    Adds ``hours``, the daily mean of each column in ``extras``, ``weekday`` (holidays count as Sunday, 6) and
    ``stagnation``: modeled NOx per hour with fixed emission, high when ventilation is poor.
    """
    g = hourly.groupby("day")
    d = g.agg(obs=("obs", "sum"), model=("model", "sum"), hours=("obs", "size"))
    for c in extras:
        d[c] = g[c].mean()
    d = d.loc[d.hours >= min_hours].copy()
    days = pd.DatetimeIndex(d.index)
    d["weekday"] = np.where(days.strftime("%Y-%m-%d").isin(list(holidays)), 6, days.day_of_week)
    d["stagnation"] = d.model / d.hours
    return d


def hourly_to_daily(
    hourly: pd.DataFrame, hours: tuple[int, int], holidays: Collection[str] = (), min_hours: int = MIN_HOURS
) -> pd.DataFrame:
    """Daily table of the local start hours in ``hours`` (inclusive) from a table with a UTC column ``h``."""
    sel = hourly[local_hour(hourly.h).between(*hours)].assign(day=lambda x: local_day(x.h))
    return daily_table(sel, holidays, min_hours)


def reference_days(d: pd.DataFrame, day: datetime, excluded: Collection, window: int = WINDOW) -> list:
    """Days of the same weekday as ``day`` (holidays are Sundays) within ``window`` days, not in ``excluded``.

    ``day`` itself is a candidate unless it is in ``excluded``, so callers pass the event days there.
    """
    apart = (d.index.to_numpy() - np.datetime64(day)) / np.timedelta64(1, "D")
    near = d[(abs(apart) <= window) & ~d.index.isin(list(excluded))]
    return list(near.index[near.weekday == d.loc[day, "weekday"]])


def estimate(d: pd.DataFrame, days: Sequence, excluded: Collection) -> dict | None:
    """Ratios event days over their reference days: concentration, meteorology (modeled) and emission.

    ``emission = concentration / meteorology``. None if no event day has references.
    """
    refs = [r for day in days for r in reference_days(d, day, excluded)]
    if not refs:
        return None
    c, r = d.loc[list(days)], d.loc[refs]
    conc = (c.obs.sum() / c.hours.sum()) / (r.obs.sum() / r.hours.sum())
    met = (c.model.sum() / c.hours.sum()) / (r.model.sum() / r.hours.sum())
    return {"concentration": conc, "meteorology": met, "emission": conc / met, "n_ref": len(set(refs))}


def bootstrap_interval(
    d: pd.DataFrame,
    days: Sequence,
    excluded: Collection,
    n_boot: int,
    rng: np.random.Generator,
    level: float = 0.90,
) -> tuple[float, float]:
    """Stratified bootstrap of the emission ratio: resample event days and, for each, its reference days."""
    pairs = [(day, reference_days(d, day, excluded)) for day in days]
    pairs = [(day, refs) for day, refs in pairs if refs]
    if not pairs:
        return np.nan, np.nan
    out = []
    for _ in range(n_boot):
        pick = [pairs[i] for i in rng.integers(len(pairs), size=len(pairs))]
        event = d.loc[[day for day, _ in pick]]
        ref = d.loc[[x for _, refs in pick for x in rng.choice(refs, len(refs))]]
        out.append((event.obs.sum() / event.model.sum()) / (ref.obs.sum() / ref.model.sum()))
    return interval(np.array(out), level)


def placebo(
    d: pd.DataFrame, event_days: Sequence, pool_mask: np.ndarray, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Emission ratios of ``n`` fake event sets with the weekday pattern of the real ones, from the pool.

    ``pool_mask`` is a boolean array aligned with ``d`` selecting eligible days; real event days are removed.
    With no emission change the samples are centered on 1; their spread is the noise of a null result.
    """
    samples = []
    for fake, excluded in fake_event_sets(d, event_days, pool_mask, n, rng):
        est = estimate(d, fake, excluded)
        if est:
            samples.append(est["emission"])
    return np.array(samples)


def fake_event_sets(
    d: pd.DataFrame,
    event_days: Sequence,
    pool_mask: np.ndarray,
    n: int,
    rng: np.random.Generator,
    real: Collection | None = None,
) -> Iterator[tuple[list, set]]:
    """``n`` fake event sets with the weekday pattern of ``event_days``, drawn from the pool (``pool_mask``
    aligned with ``d``, without the ``real`` days, by default the event days), each with the days its
    references must avoid (the real and the fake ones). Sets that find no day are skipped."""
    real = set(event_days) if real is None else set(real)
    weekdays = [d.loc[x, "weekday"] for x in event_days]
    pool = d[pool_mask & ~d.index.isin(list(real))]
    by_weekday = {k: list(pool.index[pool.weekday == k]) for k in range(7)}
    for _ in range(n):
        fake = []
        for k in weekdays:
            options = [x for x in by_weekday[k] if x not in fake]
            if options:
                fake.append(options[rng.integers(len(options))])
        if fake:
            yield fake, real | set(fake)


def split_placebo(d: pd.DataFrame, n_fake: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """Index ratios of ``n`` random splits of the days of ``d`` (columns ``obs``, ``model``): ``n_fake`` days
    over the rest, where the index is observed over modeled NOx. Given days of one type, the splits have no
    emission change, so their spread is the width of a null result (e.g. fake Sundays among weekdays)."""
    out = np.empty(n)
    for i in range(n):
        fake = np.zeros(len(d), bool)
        fake[rng.choice(len(d), n_fake, replace=False)] = True
        a, b = d[~fake], d[fake]
        out[i] = (b.obs.sum() / b.model.sum()) / (a.obs.sum() / a.model.sum())
    return out


def episodes(days: Sequence[pd.Timestamp]) -> list[list[pd.Timestamp]]:
    """Groups sorted days into runs of consecutive days."""
    runs, current = [], [days[0]]
    for day in days[1:]:
        if (day - current[-1]).days <= 1:
            current.append(day)
        else:
            runs.append(current)
            current = [day]
    runs.append(current)
    return runs
