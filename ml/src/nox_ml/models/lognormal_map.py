# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""E4: log-normal emissions, MAP with L-BFGS-B and Laplace uncertainty, on the hour systems of the baseline.

The data term is the baseline's (`hour_systems`, regional background integrated out), but the unknowns are
``x = exp(eta)``: emissions can never be negative and their uncertainty is multiplicative. The MAP and the
covariance of its Laplace approximation come from `nox_ml.inversion.lognormal`. The interval of a day-type
ratio is log-normal around the ratio of the MAP, with the log-variance from the delta method on that
covariance (``bootstrap_level`` is its level; ``bootstrap_n`` is not used).
"""

from collections.abc import Sequence
from typing import ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field
from scipy import stats

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import DAY_TYPE_NAMES, Posterior, prior_state
from nox_ml.inversion.lognormal import map_estimate
from nox_ml.inversion.normal_equations import constraint_terms, day_equations, road_table
from nox_ml.models.base import EmissionEstimate, ModelParams
from nox_ml.models.inversion_plume import InversionPlume, InversionPlumeParams


class LognormalMapParams(InversionPlumeParams):
    bootstrap_n: int = Field(
        1, ge=1, description="not used: the uncertainty comes from the Laplace approximation"
    )
    prior_sd_mult: float = Field(
        1.0,
        gt=0,
        description="multiplies the log-scale standard deviation of every prior (small: pin to the prior)",
    )
    max_iter: int = Field(1000, ge=1, description="iterations of L-BFGS-B")


class LognormalMap(InversionPlume):
    _cov_eta: np.ndarray  # Laplace covariance of the log emissions, set by `fit`

    name: ClassVar[str] = "lognormal_map"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = LognormalMapParams

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        super().fit(data, exclude_stations=exclude_stations)
        p = self.params
        assert isinstance(p, LognormalMapParams)
        _, systems, base, excluded = self._state
        n = len(base.mean)
        info, gradient = day_equations(systems, n).total()
        c_info, c_gradient = constraint_terms(self.constraints(data), n)
        mean, sd, labels = prior_state(data.points, base.n_regions)
        fit = map_estimate(info + c_info, gradient + c_gradient, mean, sd, p.prior_sd_mult, p.max_iter)
        post = Posterior(labels, fit.x, fit.cov_x, mean, sd, base.n_points, base.n_regions)
        self._fitted = (data, systems, post, excluded)
        self._cov_eta = fit.cov_eta
        return self

    def estimate_emissions(self) -> EmissionEstimate:
        data, _, post, _ = self._state
        p = self.params
        assert isinstance(p, LognormalMapParams)
        prior = self.road_prior(data)
        # weight of each unknown in the road total of its day type: x * prior of its region
        weight = np.zeros((len(DAY_TYPE_NAMES), len(post.mean)))
        for kind in range(len(DAY_TYPE_NAMES)):
            start = post.n_points + kind * post.n_regions
            weight[kind, start : start + post.n_regions] = post.mean[start : start + post.n_regions] * prior
        totals = weight.sum(axis=1)
        z = stats.norm.ppf(0.5 + p.bootstrap_level / 2)
        rows = []
        for kind, name in enumerate(DAY_TYPE_NAMES):
            # d log(ratio) / d eta, where the ratio is the road total of the day type over the weekday's
            slope = weight[kind] / totals[kind] - weight[0] / totals[0]
            half = z * np.sqrt(slope @ self._cov_eta @ slope)
            ratio = totals[kind] / totals[0]
            rows.append(
                {
                    "day_type": name,
                    "lo": ratio * np.exp(-half),
                    "hi": ratio * np.exp(half),
                    "level": p.bootstrap_level,
                }
            )
        return EmissionEstimate("absolute", road_table(post, prior), pd.DataFrame(rows))
