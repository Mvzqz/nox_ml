"""The data term of the baseline inversion as a quadratic in the unknowns, for estimators that are not the
linear-Gaussian posterior (`solve`) but need the same physics.

Each `HourSystem` holds the information matrix ``K^T R K`` and gradient ``K^T R (y - m)`` of one hour, with
the regional background of the stations and of TEMPO already integrated out (`marginalized_block`). Summed
over hours they give the misfit ``1/2 x^T H x - g^T x`` (up to a constant) of the whole period: any estimator
that minimises that, plus its own penalty, works with the background in the same way as the baseline and
its results are comparable with it. The sums are kept per local day so a bootstrap over days only draws
weights.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from nox_ml.inversion.linear import DAY_TYPE_NAMES, HourSystem, Posterior

Array = NDArray[np.float64]


@dataclass(frozen=True)
class DayEquations:
    """Information ``(n_days, n, n)`` and gradient ``(n_days, n)`` of every local day, over the unknowns."""

    days: pd.DatetimeIndex
    info: Array
    gradient: Array

    def total(self, counts: ArrayLike | None = None) -> tuple[Array, Array]:
        """``(H, g)`` with day ``d`` repeated ``counts[d]`` times (default: once each)."""
        w = np.ones(len(self.days)) if counts is None else np.asarray(counts, float)
        return np.tensordot(w, self.info, 1), w @ self.gradient

    def resample(self, rng: np.random.Generator) -> Array:
        """Counts of a draw of the days with replacement: a bootstrap replicate for `total`."""
        return np.bincount(rng.choice(len(self.days), len(self.days)), minlength=len(self.days)).astype(float)


def day_equations(systems: Sequence[HourSystem], n_unknowns: int) -> DayEquations:
    """Sum the `systems` by local day, placing each hour's block at its columns."""
    days = pd.DatetimeIndex(sorted({s.day for s in systems}))
    position = {day: i for i, day in enumerate(days)}
    info = np.zeros((len(days), n_unknowns, n_unknowns))
    gradient = np.zeros((len(days), n_unknowns))
    for system in systems:
        d = position[system.day]
        info[d][np.ix_(system.columns, system.columns)] += system.info
        gradient[d][system.columns] += system.gradient
    return DayEquations(days, info, gradient)


def constraint_terms(
    constraints: Sequence[tuple[Array, float, float]], n_unknowns: int
) -> tuple[Array, Array]:
    """``(H, g)`` of the pseudo-observations ``(row, target, sd)`` (`traffic_constraints`), added once."""
    info, gradient = np.zeros((n_unknowns, n_unknowns)), np.zeros(n_unknowns)
    for row, target, sd in constraints:
        info += np.outer(row, row) / sd**2
        gradient += row * target / sd**2
    return info, gradient


def road_table(post: Posterior, prior: Array) -> pd.DataFrame:
    """Road emission of every region and day type (t/yr) as the absolute `EmissionEstimate` table: the
    factor in `post` times the prior of the region, with the standard deviation `post.sd`."""
    factors = post.road_factors()
    return pd.DataFrame(
        [
            {
                "zone": region,
                "day_type": name,
                "mean": factors[kind, region] * prior[region],
                "sd": post.sd[post.n_points + kind * post.n_regions + region] * prior[region],
            }
            for kind, name in enumerate(DAY_TYPE_NAMES)
            for region in range(post.n_regions)
        ]
    )
