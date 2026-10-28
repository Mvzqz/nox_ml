"""X3: the PINN puff model (E5b) averaged over several trainings of the network.

Each member is the same model with another ``seed``, which retrains the kernel (a network trained with
physics only, never with data): the members differ only in the network. Their predictions are averaged with
equal weights and the spread between networks enters the standard deviation of the emissions, so the point
of the ensemble is the uncertainty of the network, not a lower error (eight networks of the avance 4 differed
by 0.016 ppb).

**Emission level.** The members have different `transport_key()` (the key holds the network's training hash),
so the contract rule of `ConvexEnsemble` would give a relative estimate. Here the physics is the same and
only the network changes, so their tonnes are comparable and `PinnSeeds.shares_absolute_level` says so: the
estimate is absolute, the mean of the members' means, and its sd is that of the mixture (`combine_absolute`):
the variance between networks adds to the variance within each.

**Cache.** An `Inputs` keeps the Jacobians of at most `MAX_CACHED_TRANSPORTS` transports, evicting the oldest.
Every member is one transport used in every fold, so with more members than slots each fold would evict the
Jacobians the next one needs and rebuild all of them (~11 min per member in nov-dec 2023). The decision is to
refuse such a configuration (`seeds` is validated against that constant) rather than grow the cache or work
around it, since 16 networks are already far more than the spread between them needs. The trained networks
are cached on disk in `kernel_dir` (the first seeds run trains their network, ~3 min; seed 0 is bundled).
"""

from collections.abc import Sequence
from typing import Annotated, ClassVar, Self

import numpy as np
from pydantic import Field, field_validator, model_validator

from nox_ml.data.inputs import MAX_CACHED_TRANSPORTS
from nox_ml.inversion.linear import HourTransport
from nox_ml.models.base import EmissionEstimate, ModelParams
from nox_ml.models.ensemble import ConvexEnsemble, MemberConfig
from nox_ml.models.pinn.model import PinnInversion, PinnPuff


def default_base() -> MemberConfig:
    """E5b as configured in ``configs/experiments/pinn_puff.yaml`` (the other parameters are the defaults)."""
    return MemberConfig(
        name=PinnPuff.name,
        params={"lifetime": "oh", "u_min": 2.0, "bootstrap_n": 200, "kernel_dir": ".cache/pinn"},
    )


class PinnSeedsParams(ModelParams):
    base: MemberConfig = Field(
        default_factory=default_base,
        description="the PINN model every member runs, as an experiment config; its own `seed` is replaced "
        "by each of `seeds`",
    )
    seeds: Annotated[list[int], Field(min_length=1)] = Field(
        default_factory=lambda: [0, 1, 2, 3],
        description="one network per seed (0 is the one bundled with the package)",
    )

    @field_validator("seeds")
    @classmethod
    def distinct_and_cacheable(cls, seeds: list[int]) -> list[int]:
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"seeds must be distinct, got {seeds}")
        if len(seeds) > MAX_CACHED_TRANSPORTS:
            raise ValueError(
                f"{len(seeds)} seeds, but the Jacobian cache of `Inputs` holds {MAX_CACHED_TRANSPORTS} "
                "transports: with more, every fold would evict and rebuild the matrices of the members "
                f"(use at most {MAX_CACHED_TRANSPORTS} seeds)"
            )
        return seeds

    @model_validator(mode="after")
    def base_is_a_pinn(self) -> Self:
        from nox_ml.models import REGISTRY

        if not issubclass(REGISTRY[self.base.name], PinnInversion):
            raise ValueError(f"base must be a PINN model (pinn_plume or pinn_puff), got {self.base.name!r}")
        return self

    def members(self) -> list[MemberConfig]:
        return [
            MemberConfig(name=self.base.name, params={**self.base.params, "seed": seed})
            for seed in self.seeds
        ]


class PinnSeeds(ConvexEnsemble):
    """Equal-weight average of `params.base` over the networks of `params.seeds`."""

    name: ClassVar[str] = "pinn_seeds"
    Params: ClassVar[type[ModelParams]] = PinnSeedsParams

    def __init__(self, params: PinnSeedsParams | None = None) -> None:
        # not `super().__init__`: a single seed is one member, which `EnsembleParams` refuses as an ensemble
        self.params: ModelParams = params or self.Params()
        assert isinstance(self.params, PinnSeedsParams)
        self._members = [member.build() for member in self.params.members()]
        self._fitted = False

    @property
    def _pinn_members(self) -> list[PinnInversion]:
        return [member for member in self._members if isinstance(member, PinnInversion)]

    @property
    def weights(self) -> np.ndarray:
        return np.full(len(self._members), 1 / len(self._members))

    def transport(self) -> HourTransport:
        """The forward model of the members (the same physics for every seed, up to the network): the first
        one's, which the contract tests use to simulate data."""
        return self._pinn_members[0].transport()

    def shares_absolute_level(self, estimates: Sequence[EmissionEstimate]) -> bool:
        """True when every estimate is absolute and the members differ only in the seed of the network.

        The contract compares `transport_key()`, which includes the network, so seeds never match. Another
        network is the same physics with another approximation of its kernel, so the tonnes are comparable
        and the difference between them is exactly the dispersion this ensemble reports."""
        if any(estimate.kind != "absolute" for estimate in estimates):
            return False
        same_but_seed = {
            member.params.model_copy(update={"seed": 0}).model_dump_json() for member in self._pinn_members
        }
        return len(same_but_seed) == 1
