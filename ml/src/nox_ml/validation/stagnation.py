"""Diagnosis of the estimator on stagnant days: does a null result drift with the modeled ventilation?

With no emission change, the single-day index of :func:`relative_index` should be 1 whatever the weather. A
slope of ``log(index)`` on the log of the modeled ventilation different from 0 means the model over- or
under-states the effect of weather.

It also groups days by how well they are ventilated: quartiles of wind speed times boundary layer height
(independent of the transport model), and the "poorly ventilated days" pool of the event placebos.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

import numpy as np
import pandas as pd

from nox_ml.inversion.normalized import interval
from nox_ml.validation.placebo import reference_days

N_QUARTILES = 4
POORLY_VENTILATED_Q = 0.25  # share of the event days that is allowed to be more stagnant than the pool


def relative_index(d: pd.DataFrame, days: Sequence, excluded: Collection) -> pd.Series:
    """Index of each day over the index of its reference days (same weekday, +-4 weeks): a one-day placebo."""
    out = {}
    for day in days:
        refs = reference_days(d, day, excluded)
        if refs:
            x, y = d.loc[day], d.loc[refs]
            out[day] = (x.obs / x.model) / (y.obs.sum() / y.model.sum())
    return pd.Series(out, dtype=float)


def ols(y: pd.Series, x: pd.DataFrame) -> tuple[dict, dict, float]:
    """Least squares with intercept: returns (coefficients, t statistics, R^2), keyed by column name."""
    a = np.column_stack([np.ones(len(x)), x.to_numpy()])
    beta, *_ = np.linalg.lstsq(a, y.to_numpy(), rcond=None)
    res = y.to_numpy() - a @ beta
    s2 = res @ res / (len(y) - a.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(a.T @ a)))
    names = ["const", *x.columns]
    with np.errstate(invalid="ignore", divide="ignore"):  # a perfect or constant fit gives NaN, not an error
        r2 = 1 - res @ res / ((y.to_numpy() - y.mean()) ** 2).sum()
        t = beta / se
    return dict(zip(names, beta, strict=True)), dict(zip(names, t, strict=True)), float(r2)


def ventilation_slope(d: pd.DataFrame, days: Sequence, excluded: Collection) -> tuple[float, float, int]:
    """Slope of log(relative index) on log(relative modeled ventilation): slope, t, day count."""
    rel = relative_index(d, days, excluded)
    refs = {x: reference_days(d, x, excluded) for x in rel.index.to_list()}
    met = pd.Series(
        {
            x: np.log(d.loc[x].stagnation / (d.loc[r].model.sum() / d.loc[r].hours.sum()))
            for x, r in refs.items()
        }
    )
    beta, t, _ = ols(pd.Series(np.log(rel)), pd.DataFrame({"lmet": met}))
    return float(beta["lmet"]), float(t["lmet"]), len(rel)


def ventilation_quartile(ventilation: pd.Series) -> pd.Series:
    """Quartile of each day by ventilation (``pd.qcut``): 0 is the most stagnant, 3 the best ventilated.

    ``ventilation`` is the daily mean wind speed times boundary layer height, which does not depend on the
    transport model (the modeled `stagnation` of the daily table does).
    """
    return pd.Series(pd.qcut(ventilation, N_QUARTILES, labels=False), index=ventilation.index)


def geometric_mean(values: Sequence[float] | np.ndarray | pd.Series) -> float:
    return float(np.exp(np.nanmean(np.log(np.asarray(values, float)))))


def index_by_quartile(rel: pd.Series, quartile: pd.Series) -> list[float]:
    """Geometric mean of the relative index in each ventilation quartile, most stagnant first.

    With no emission change every value should be near 1; a trend from stagnant to ventilated days means the
    model mishandles the weather. ``quartile`` is indexed by day and covers ``rel``'s days.
    """
    q = quartile.reindex(rel.index)
    return [geometric_mean(rel[q == k]) for k in range(N_QUARTILES)]


def stagnant_index(
    rel: pd.Series, quartile: pd.Series, n_boot: int = 1000, level: float = 0.90, seed: int = 5
) -> tuple[float, tuple[float, float], int]:
    """Index of the most stagnant quartile, its bootstrap interval (resampling days) and its day count.

    To read it on weekdays only, pass the ``rel`` of those days.
    """
    values = np.asarray(rel[quartile.reindex(rel.index) == 0], float)
    rng = np.random.default_rng(seed)
    boot = [geometric_mean(values[rng.integers(len(values), size=len(values))]) for _ in range(n_boot)]
    return geometric_mean(values), interval(np.array(boot), level), len(values)


def poorly_ventilated_mask(
    d: pd.DataFrame, event_days: Sequence, q: float = POORLY_VENTILATED_Q
) -> np.ndarray:
    """Pool of "poorly ventilated days" for ``placebo.placebo``'s ``pool_mask``, aligned with ``d``.

    A day is eligible when its modeled `stagnation` is at least the ``q`` quantile of the event days', so fake
    events are as stagnant as the real ones (which are poorly ventilated, being ozone episodes). Combine it
    with the season and non-event masks of the caller.
    """
    threshold = d.loc[list(event_days), "stagnation"].quantile(q)
    return (d["stagnation"] >= threshold).to_numpy()
