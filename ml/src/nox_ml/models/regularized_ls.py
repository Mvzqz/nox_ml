# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""E3: non-negative regularized least squares on the hour systems of the baseline, no Bayesian reading.

Same physics and the same data term as the baseline (`hour_systems`: the regional background of every hour is
integrated out, so it does not leak into the emissions). The unknowns are normalised by their prior
assumption and estimated by ridge with non-negativity (NNLS), see `nox_ml.inversion.regularized`. It has no
posterior: the uncertainty is a bootstrap over whole days that solves the problem again on each replicate
(`bootstrap_n`), from which come the standard deviations and the intervals of the day-type ratios.
"""

from collections.abc import Sequence
from typing import ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import DAY_TYPE_NAMES, Posterior, prior_state
from nox_ml.inversion.normal_equations import constraint_terms, day_equations, road_table
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, interval
from nox_ml.inversion.regularized import Penalty, bootstrap_regularized, solve_regularized
from nox_ml.models.base import EmissionEstimate, ModelParams
from nox_ml.models.inversion_plume import InversionPlume, InversionPlumeParams

MIN_SD = 1e-6  # t/yr; a parameter held at zero in every replicate still has a positive uncertainty


class RegularizedLsParams(InversionPlumeParams):
    alpha: float = Field(
        0.01,
        ge=0,
        description="penalty weight relative to the median information of a normalised parameter (0: none)",
    )
    penalty: Penalty = Field(
        "prior", description="shrink towards the prior assumption (prior) or towards zero (zero)"
    )


class RegularizedLs(InversionPlume):
    name: ClassVar[str] = "regularized_ls"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = RegularizedLsParams

    def _problem(self, data: Inputs):
        """Day equations, constraint terms and the prior scale of the unknowns."""
        _, systems, post, _ = self._state
        n = len(post.mean)
        return (
            day_equations(systems, n),
            constraint_terms(self.constraints(data), n),
            post.prior_mean,
        )

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        super().fit(data, exclude_stations=exclude_stations)
        p = self.params
        assert isinstance(p, RegularizedLsParams)
        _, systems, base, excluded = self._state
        days, (c_info, c_gradient), scale = self._problem(data)
        info, gradient = days.total()
        x = solve_regularized(info + c_info, gradient + c_gradient, scale, p.alpha, p.penalty)
        n_points, n_regions = base.n_points, base.n_regions
        mean, sd, labels = prior_state(data.points, n_regions)
        # no covariance without the bootstrap, which `estimate_emissions` runs
        post = Posterior(labels, x, np.zeros((len(x), len(x))), mean, sd, n_points, n_regions)
        self._fitted = (data, systems, post, excluded)
        return self

    def estimate_emissions(self) -> EmissionEstimate:
        data, _, post, _ = self._state
        p = self.params
        assert isinstance(p, RegularizedLsParams)
        days, constraint, scale = self._problem(data)
        replicates = bootstrap_regularized(days, constraint, scale, p.alpha, p.penalty, p.bootstrap_n, p.seed)
        prior = self.road_prior(data)
        sd = np.maximum(replicates.std(axis=0, ddof=1) if len(replicates) > 1 else 0 * post.mean, MIN_SD)
        with_sd = Posterior(
            post.labels,
            post.mean,
            np.diag(sd**2),
            post.prior_mean,
            post.prior_sd,
            post.n_points,
            post.n_regions,
        )
        table = road_table(with_sd, prior)
        totals = np.array([r[post.n_points :].reshape(len(DAY_TYPE_NAMES), -1) @ prior for r in replicates])
        ci = pd.DataFrame(
            [
                {
                    "day_type": DAY_TYPE_NAMES[kind],
                    **dict(
                        zip(
                            ("lo", "hi"),
                            interval(totals[:, kind] / totals[:, WEEKDAY], p.bootstrap_level),
                            strict=True,
                        )
                    ),
                    "level": p.bootstrap_level,
                }
                for kind in (WEEKDAY, SATURDAY, SUNDAY_HOLIDAY)
            ]
        )
        return EmissionEstimate("absolute", table, ci)
