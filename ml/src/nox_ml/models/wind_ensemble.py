# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""X2: an ensemble of puff inversions (E2) over perturbed winds.

The wind is the main source of error of the transport. Each member perturbs, with its own seed, the direction
and speed of the wind of every hour and the boundary layer height (`WindPerturbation`), builds its own
transport matrices and solves the inversion. The prediction and the emissions are the mean of the members.

The perturbation is one draw per hour (UTC start), the same for the hours of the fit and for the whole-period
wind the puffs are followed with, so the two stay coherent. It is applied inside the transport
(`WindPerturbedTransport`): every member keeps the observations and the period of the data it is given, and
its Jacobians are cached under its own key, so a placebo refit or a leave-one-station-out fold reuses them.

All members are the same model with another draw of the wind, so their tonnes are comparable and the
emissions are absolute (the members' transports differ, but not the physics; see
`WindEnsemble.shares_absolute_level`).
"""

import dataclasses
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nox_ml.data.inputs import MAX_CACHED_TRANSPORTS
from nox_ml.inversion.jacobian import HourJacobian, Sources
from nox_ml.inversion.linear import History, HistoryTransport, HourData
from nox_ml.models.base import EmissionEstimate, ModelParams
from nox_ml.models.ensemble import ConvexEnsemble, MemberConfig
from nox_ml.models.inversion_puff import InversionPuff, InversionPuffParams, PuffTransport


class WindPerturbation(BaseModel):
    """The noise of one member: the direction in degrees (normal), and the speed and the boundary layer height
    as multiplicative factors (log-normal, median 1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    sigma_dir_deg: float = Field(ge=0, description="standard deviation of the wind direction, degrees")
    sigma_speed: float = Field(ge=0, description="log standard deviation of the wind speed")
    sigma_pbl: float = Field(ge=0, description="log standard deviation of the boundary layer height")


def perturbation_draws(stamps: pd.DatetimeIndex, p: WindPerturbation) -> pd.DataFrame:
    """One draw per timestamp (direction in rad, log speed factor, log height factor), reproducible from the
    seed. Indexed by `stamps`, which the caller passes sorted and complete (the whole period), so a subset of
    the hours gets the same draws."""
    rng = np.random.default_rng(p.seed)
    z = rng.standard_normal((len(stamps), 3))
    return pd.DataFrame(
        {
            "dir": np.deg2rad(p.sigma_dir_deg) * z[:, 0],
            "log_speed": p.sigma_speed * z[:, 1],
            "log_pbl": p.sigma_pbl * z[:, 2],
        },
        index=stamps,
    )


def perturbed_wind(wind: pd.DataFrame, draws: pd.DataFrame) -> pd.DataFrame:
    """The wind table (columns ``u``, ``v``) with each row turned and scaled by its draw."""
    d = draws.reindex(wind.index)
    speed = np.hypot(wind["u"], wind["v"]) * np.exp(d["log_speed"])
    angle = np.arctan2(wind["v"], wind["u"]) + d["dir"]
    return pd.DataFrame({"u": speed * np.cos(angle), "v": speed * np.sin(angle)}, index=wind.index)


def perturbed_hour(hour: HourData, draws: pd.DataFrame) -> HourData:
    """The hour with the wind and the boundary layer height of its draw; the observations are unchanged."""
    d = draws.loc[hour.hour]
    u, v = hour.wind
    speed = np.hypot(u, v) * np.exp(d["log_speed"])
    angle = np.arctan2(v, u) + d["dir"]
    return dataclasses.replace(
        hour,
        wind=(float(speed * np.cos(angle)), float(speed * np.sin(angle))),
        pbl=float(hour.pbl * np.exp(d["log_pbl"])),
    )


@dataclass(frozen=True)
class WindPerturbedTransport:
    """A puff transport (`PuffTransport`) fed with the perturbed winds: the hours and the whole-period wind
    of `History` are drawn with the same perturbation, then the inner transport builds the matrices."""

    inner: PuffTransport
    perturbation: WindPerturbation

    def for_hours(
        self, hours: Sequence[HourData], history: History
    ) -> Callable[[HourData, Sources, float], HourJacobian]:
        # without the period's wind, the puffs are followed with the winds of the hours (`PuffTransport`)
        wind = history.wind
        if wind is None:
            wind = pd.DataFrame(
                [h.wind for h in hours], columns=["u", "v"], index=pd.DatetimeIndex([h.hour for h in hours])
            ).sort_index()
        stamps = wind.index.union(pd.DatetimeIndex([h.hour for h in hours]))
        draws = perturbation_draws(stamps, self.perturbation)
        perturbed = [perturbed_hour(h, draws) for h in hours]
        at = self.inner.for_hours(perturbed, dataclasses.replace(history, wind=perturbed_wind(wind, draws)))
        by_hour = {h.hour: p for h, p in zip(hours, perturbed, strict=True)}
        return lambda data, sources, no2_nox_ratio: at(by_hour[data.hour], sources, no2_nox_ratio)


class WindMemberParams(InversionPuffParams):
    perturbation: WindPerturbation | None = Field(
        default=None, description="the draw of the wind of this member; None: the unperturbed E2"
    )

    @model_validator(mode="after")
    def perturbation_needs_the_period_wind(self) -> Self:
        if self.perturbation is not None and self.wind_field:
            raise ValueError("a wind perturbation is not defined with wind_field (the stations' winds)")
        return self


class WindMember(InversionPuff):
    """E2 whose transport sees a perturbed wind. Not registered: `WindEnsemble` builds its members."""

    name: ClassVar[str] = "wind_member"
    Params: ClassVar[type[ModelParams]] = WindMemberParams

    def transport(self) -> HistoryTransport:
        p = self.params
        assert isinstance(p, WindMemberParams)
        inner = super().transport()
        return inner if p.perturbation is None else WindPerturbedTransport(inner, p.perturbation)

    def transport_key(self) -> tuple:
        p = self.params
        assert isinstance(p, WindMemberParams)
        base = super().transport_key()
        return base if p.perturbation is None else ("wind_member", base, p.perturbation.model_dump_json())


def default_base() -> MemberConfig:
    """E2 with the parameters of `configs/experiments/inversion_puff.yaml`."""
    return MemberConfig(
        name=InversionPuff.name,
        params={"max_age_h": 24, "lifetime": "oh", "bootstrap_n": 200, "bootstrap_level": 0.90, "seed": 7},
    )


class WindEnsembleParams(ModelParams):
    base: MemberConfig = Field(
        default_factory=default_base,
        description="the puff inversion every member runs, as an experiment config (E2)",
    )
    n_members: int = Field(
        default=8,
        ge=2,
        le=MAX_CACHED_TRANSPORTS,
        description="number of perturbed winds; each member takes one slot of the Jacobian cache of `Inputs`",
    )
    sigma_dir_deg: float = Field(
        default=30.0, ge=0, description="direction uncertainty, degrees (measured 28-32)"
    )
    sigma_speed: float = Field(default=0.2, ge=0, description="log uncertainty of the wind speed")
    sigma_pbl: float = Field(default=0.2, ge=0, description="log uncertainty of the boundary layer height")
    seed: int = Field(default=0, description="seed of the draws; member k uses seed + k")

    @model_validator(mode="after")
    def base_is_a_puff_inversion(self) -> Self:
        from nox_ml.models import REGISTRY

        if not issubclass(REGISTRY[self.base.name], InversionPuff):
            raise ValueError(f"base must be a puff inversion (inversion_puff), got {self.base.name!r}")
        if self.base.params.get("wind_field"):
            raise ValueError("the base must not use wind_field: the perturbation is of the period's wind")
        return self


class WindEnsemble(ConvexEnsemble):
    """Equal-weight average of E2 over `n_members` perturbed winds."""

    name: ClassVar[str] = "wind_ensemble"
    Params: ClassVar[type[ModelParams]] = WindEnsembleParams

    def __init__(self, params: WindEnsembleParams | None = None) -> None:
        # not `super().__init__`: the members are built here, one per perturbation (`ConvexEnsemble` expects
        # `EnsembleParams`)
        self.params: ModelParams = params or self.Params()
        assert isinstance(self.params, WindEnsembleParams)
        p = self.params
        self._base = p.base.build()  # the unperturbed E2: the physics the members are perturbations of
        self._members = [
            WindMember(
                WindMemberParams.model_validate(
                    {
                        **p.base.params,
                        "perturbation": WindPerturbation(
                            seed=p.seed + k,
                            sigma_dir_deg=p.sigma_dir_deg,
                            sigma_speed=p.sigma_speed,
                            sigma_pbl=p.sigma_pbl,
                        ),
                    }
                )
            )
            for k in range(p.n_members)
        ]
        self._fitted = False

    @property
    def weights(self) -> np.ndarray:
        return np.full(len(self._members), 1 / len(self._members))

    def transport(self):
        """The forward model of E2 without perturbation: what the contract tests use to simulate data."""
        return self._base.transport()

    def shares_absolute_level(self, estimates: Sequence[EmissionEstimate]) -> bool:
        """True when every member is absolute: they are the same inversion over another draw of the wind, so
        their tonnes are comparable (the transport keys differ only in the draw, by construction)."""
        return all(estimate.kind == "absolute" for estimate in estimates)
