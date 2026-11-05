# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""X1: bagging of an inversion. The base model (E5b by default) is fitted once; each bag solves the same
inversion again with whole days drawn with replacement (blocks of `block_days` consecutive days, as the
bootstrap of the intervals does, `block_draw`).

The transport does not depend on which days are used, so the Jacobians are built once and every bag only
solves the normal equations again (`solve` with per-hour weights: a day drawn twice counts twice). Each bag
is a shallow copy of the fitted base with its own posterior, so predictions and emissions are those of the
ordinary inversion. Days are drawn within each day type (stratified), because the target of the inversion is
the ratio between day types: a plain draw can leave a bag without any Sunday, and a Sunday level fitted
from a few days becomes unstable. The members share one `transport_key()`, so the contract rule gives absolute
emissions: the mean of the bags' means, and the sd of their mixture (the spread between bags adds to the sd).

The bags describe how much the data decide the estimate, not a lower error: for a linear Gaussian inversion
the average of the bags is close to the full posterior.
"""

import copy
from collections.abc import Sequence
from typing import ClassVar, Self

import numpy as np
from pydantic import Field, model_validator

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import solve
from nox_ml.models.base import ModelParams
from nox_ml.models.ensemble import ConvexEnsemble, MemberConfig
from nox_ml.models.inversion_plume import InversionPlume, block_draw


def default_base() -> MemberConfig:
    """E2 (`inversion_puff`) with the parameters of `configs/experiments/inversion_puff.yaml`; the experiment
    config of X1 names E5b (`pinn_puff`) instead."""
    return MemberConfig(
        name="inversion_puff",
        params={"max_age_h": 24, "lifetime": "oh", "bootstrap_n": 200, "bootstrap_level": 0.90, "seed": 7},
    )


class BaggedInversionParams(ModelParams):
    base: MemberConfig = Field(
        default_factory=default_base,
        description="the inversion every bag solves again, as an experiment config (a model of the registry "
        "that inverts with `InversionPlume`, not an ensemble)",
    )
    n_bags: int = Field(default=20, ge=2, description="number of bags (resamplings of the days)")
    block_days: int = Field(
        default=1,
        ge=1,
        description="consecutive days of a day type drawn together (1: whole days, as the bootstrap of days)",
    )
    seed: int = Field(default=0, description="seed of the resampling")

    @model_validator(mode="after")
    def base_must_invert(self) -> Self:
        from nox_ml.models import REGISTRY

        model = REGISTRY[self.base.name]
        if not issubclass(model, InversionPlume) or issubclass(model, ConvexEnsemble):
            raise ValueError(
                f"base must be an inversion (inversion_plume, inversion_puff, pinn_*), got {self.base.name!r}"
            )
        return self


class BaggedInversion(ConvexEnsemble):
    """Equal-weight average of `n_bags` solves of `params.base` on resampled days."""

    name: ClassVar[str] = "bagged_inversion"
    Params: ClassVar[type[ModelParams]] = BaggedInversionParams

    def __init__(self, params: BaggedInversionParams | None = None) -> None:
        # not `super().__init__`: the members exist only after `fit` (one per bag, built from the fitted base)
        self.params: ModelParams = params or self.Params()
        assert isinstance(self.params, BaggedInversionParams)
        self._base = self.params.base.build()
        self._members: list = []
        self._fitted = False

    @property
    def weights(self) -> np.ndarray:
        assert isinstance(self.params, BaggedInversionParams)
        return np.full(self.params.n_bags, 1 / self.params.n_bags)

    def transport(self):
        """The forward model of the base (the bags share it): what the contract tests use to simulate data."""
        return self._base.transport()

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        assert isinstance(self.params, BaggedInversionParams)
        self._base.fit(data, exclude_stations=exclude_stations)
        _, systems, _, excluded = self._base._state  # the base's hour systems, built once
        days, day_index = np.unique([s.day for s in systems], return_inverse=True)
        kind_of = {s.day: s.kind for s in systems}
        kind_of_day = np.array([kind_of[day] for day in days])
        constraints = self._base.constraints(data)
        rng = np.random.default_rng(self.params.seed)
        members = []
        for _ in range(self.params.n_bags):
            day_weights = np.zeros(len(days), dtype=int)
            for kind in np.unique(kind_of_day):  # within each day type, so every bag keeps its Sundays
                in_kind = np.flatnonzero(kind_of_day == kind)
                day_weights[in_kind] = block_draw(len(in_kind), self.params.block_days, rng)
            posterior = solve(systems, data.points, data.n_regions, day_weights[day_index], constraints)
            bag = copy.copy(self._base)  # same transport and Jacobians; only the posterior differs
            bag._fitted = (data, systems, posterior, excluded)
            members.append(bag)
        self._members = members
        self._fitted = True
        return self
