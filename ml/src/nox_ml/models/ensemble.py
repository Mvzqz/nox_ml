# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Ensembles: a `Model` that wraps base models and combines them with convex weights (``docs/models.md``,
section 10).

Concentration is linear in emission, so a convex combination of the predictions of the base models is the
same combination of their emissions. The base models are declared in `params.members` as experiment configs
(``{name, params}``), so an ensemble is one more config of the registry and runs, tunes and compares like
any model.

Emission rule of `Ensemble.estimate_emissions`:

- **absolute** (t/yr) when every member is absolute *and* shares the transport (same `transport_key()`):
  their levels mean the same thing, so the estimate is the weighted mean of the means and the weighted
  mixture of the variances (the disagreement between members adds to the sd);
- **relative** otherwise: members with different transports differ by 25-40 % in absolute level (one is not
  an error of the other), and relative members have no tonnes at all. Each member is reduced to its index
  over the weekday and the indices are averaged. The index is pooled over zones, as in ADR 0006, because
  zones are not comparable across methods.

Intervals are the weighted means of the members' bounds, so their level is the members' (a member without
an interval gets a normal one from its sd, 90 %). The weights are the same for predictions and emissions.
"""

from collections.abc import Sequence
from typing import Any, ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from nox_ml.data.inputs import Inputs
from nox_ml.models.base import (
    PREDICTION_COLUMNS,
    WEEKDAY,
    EmissionEstimate,
    Model,
    ModelParams,
)

WEIGHT_TOLERANCE = 1e-6  # allowed distance of the weights' sum to 1
Z_90 = 1.645  # normal quantile of a central 90 % interval


class MemberConfig(BaseModel):
    """A base model of an ensemble: the ``model: {name, params}`` block of an experiment config. `params`
    is stored with every default filled in, so a run's `config.yaml` records exactly what was combined."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    params: dict[str, Any] = Field(default_factory=dict, validate_default=True)

    @model_validator(mode="after")
    def registered(self) -> Self:
        from nox_ml.models import REGISTRY  # the registry contains the ensembles that import this module

        if self.name not in REGISTRY:
            raise ValueError(f"unknown member {self.name!r}; registered: {sorted(REGISTRY)}")
        cls = REGISTRY[self.name]
        if cls.role != "model" or issubclass(cls, ConvexEnsemble):
            raise ValueError(f"member {self.name!r} must be a base model (an ensemble cannot contain one)")
        resolved = cls.Params.model_validate(self.params).model_dump(mode="json")
        object.__setattr__(self, "params", resolved)
        return self

    def build(self) -> Model:
        from nox_ml.models import REGISTRY

        cls = REGISTRY[self.name]
        return cls(cls.Params.model_validate(self.params))


class EnsembleParams(ModelParams):
    members: list[MemberConfig] = Field(
        default_factory=lambda: [
            MemberConfig(name="inversion_plume", params={"bootstrap_n": 50}),
            MemberConfig(name="regularized_ls", params={"bootstrap_n": 50}),
        ],
        min_length=2,
        description="base models, as experiment configs (default: the simple average of two inversions)",
    )
    weights: list[float] | None = Field(
        None, description="convex weights of the members, in order (>= 0, sum 1); null: equal weights"
    )

    @field_validator("weights")
    @classmethod
    def convex(cls, weights: list[float] | None) -> list[float] | None:
        if weights is None:
            return None
        if min(weights) < 0 or abs(sum(weights) - 1) > WEIGHT_TOLERANCE:
            raise ValueError(f"weights must be >= 0 and sum to 1, got {weights}")
        return weights

    @model_validator(mode="after")
    def one_weight_per_member(self) -> Self:
        if self.weights is not None and len(self.weights) != len(self.members):
            raise ValueError(f"{len(self.weights)} weights for {len(self.members)} members")
        return self


class ConvexEnsemble:
    """Wraps the base models of `params.members` and combines them with convex weights. Equal weights (the
    default) are the simple average; learned ones (`nox_ml.validation.stacking`) are frozen in the config."""

    name: ClassVar[str] = "convex_ensemble"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = EnsembleParams

    def __init__(self, params: EnsembleParams | None = None) -> None:
        self.params: ModelParams = params or self.Params()
        assert isinstance(self.params, EnsembleParams)
        self._members: list[Model] = [member.build() for member in self.params.members]
        self._fitted = False

    @property
    def weights(self) -> np.ndarray:
        p = self.params
        assert isinstance(p, EnsembleParams)
        return (
            np.full(len(self._members), 1 / len(self._members)) if p.weights is None else np.array(p.weights)
        )

    @property
    def n_params(self) -> int:
        return sum(member.n_params for member in self._members)

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        for member in self._members:
            member.fit(data, exclude_stations=exclude_stations)
        self._fitted = True
        return self

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        """Weighted mean of the members' predictions, row by row (``station``, ``utc``)."""
        if not self._fitted:
            raise RuntimeError("fit the model first")
        frames = [
            member.predict_stations(data, stations).set_index(["station", "utc"])["nox_ppb_pred"]
            for member in self._members
        ]
        table = pd.concat(frames, axis=1, keys=range(len(frames)), join="inner")
        combined = pd.Series(table.to_numpy() @ self.weights, index=table.index, name="nox_ppb_pred")
        return combined.reset_index()[PREDICTION_COLUMNS]

    def shares_absolute_level(self, estimates: Sequence[EmissionEstimate]) -> bool:
        """True when the members' tonnes are comparable: all absolute and with the same transport."""
        if any(estimate.kind != "absolute" for estimate in estimates):
            return False
        keys = [getattr(member, "transport_key", lambda: None)() for member in self._members]
        return keys[0] is not None and all(key == keys[0] for key in keys)

    def estimate_emissions(self) -> EmissionEstimate:
        if not self._fitted:
            raise RuntimeError("fit the model first")
        estimates = [member.estimate_emissions() for member in self._members]
        if self.shares_absolute_level(estimates):
            return combine_absolute(estimates, self.weights)
        return combine_relative(estimates, self.weights)


def combine_absolute(estimates: Sequence[EmissionEstimate], weights: np.ndarray) -> EmissionEstimate:
    """Weighted mean of absolute estimates (same zones and day types); the sd is that of the mixture."""
    keyed = [e.table.set_index(["zone", "day_type"]) for e in estimates]
    mean = sum(w * t["mean"] for w, t in zip(weights, keyed, strict=True))
    variance = sum(w * (t["sd"] ** 2 + (t["mean"] - mean) ** 2) for w, t in zip(weights, keyed, strict=True))
    table = pd.DataFrame({"mean": mean, "sd": np.sqrt(variance)}).reset_index()
    combined = EmissionEstimate("absolute", table[["zone", "day_type", "mean", "sd"]])
    return EmissionEstimate("absolute", combined.table, _ratio_ci(estimates, weights, combined))


def _ratio_ci(
    estimates: Sequence[EmissionEstimate], weights: np.ndarray, combined: EmissionEstimate
) -> pd.DataFrame | None:
    """Weighted mean of the members' day-type intervals, widened to hold the combined ratio (the ratio of
    sums is not the mean of the ratios). None unless every member has an interval at the same level."""
    cis = [e.ratio_ci.set_index("day_type") for e in estimates if e.ratio_ci is not None]
    if len(cis) < len(estimates):
        return None
    levels = {float(ci["level"].iloc[0]) for ci in cis}
    if len(levels) != 1:
        return None
    rows = []
    for day_type in cis[0].index:
        lo = sum(w * ci.loc[day_type, "lo"] for w, ci in zip(weights, cis, strict=True))
        hi = sum(w * ci.loc[day_type, "hi"] for w, ci in zip(weights, cis, strict=True))
        ratio = combined.day_type_ratio(day_type)
        rows.append(
            {"day_type": day_type, "lo": min(lo, ratio), "hi": max(hi, ratio), "level": levels.copy().pop()}
        )
    return pd.DataFrame(rows)


def pooled_index(estimate: EmissionEstimate) -> pd.DataFrame:
    """The index of each day type over the weekday, pooled over zones (``day_type``, ``mean``, ``lo``,
    ``hi``). For an absolute estimate the interval is its own when it has one, else a normal 90 % one from
    the sd of the totals (independent errors between day types)."""
    if estimate.kind == "relative":
        pooled = estimate.table[estimate.table["zone"].isna()]
        if pooled.empty:
            raise ValueError("a relative member needs zone-pooled rows to enter an ensemble")
        return pooled.loc[:, ["day_type", "mean", "lo", "hi"]]
    total = estimate.table.groupby("day_type")["mean"].sum()
    sd = np.sqrt(estimate.table.groupby("day_type")["sd"].apply(lambda s: (s**2).sum()))
    rows = []
    for day_type in total.index:
        ratio = estimate.day_type_ratio(day_type)
        bounds = estimate.day_type_interval(day_type)
        if bounds is None:
            spread = ratio * np.hypot(sd[day_type] / total[day_type], sd[WEEKDAY] / total[WEEKDAY])
            bounds = (ratio - Z_90 * spread, ratio + Z_90 * spread)
        rows.append({"day_type": day_type, "mean": ratio, "lo": bounds[0], "hi": bounds[1]})
    return pd.DataFrame(rows)


def combine_relative(estimates: Sequence[EmissionEstimate], weights: np.ndarray) -> EmissionEstimate:
    """Weighted mean of the members' indices over the weekday, pooled over zones (``zone`` null)."""
    indices = [pooled_index(e).set_index("day_type") for e in estimates]
    table = sum(w * index for w, index in zip(weights, indices, strict=True)).dropna().reset_index()
    table.insert(0, "zone", np.nan)
    return EmissionEstimate("relative", table[["zone", "day_type", "mean", "lo", "hi"]])
