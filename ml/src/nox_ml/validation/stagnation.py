"""Diagnosis of the estimator on stagnant days: does a null result drift with the modeled ventilation?

With no emission change, the single-day index of :func:`relative_index` should be 1 whatever the weather. A
slope of ``log(index)`` on the log of the modeled ventilation different from 0 means the model over- or
under-states the effect of weather.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

import numpy as np
import pandas as pd

from nox_ml.validation.placebo import reference_days


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
