# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""The contract every model and reference plugs into (see ``docs/models.md``)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol, Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import DAY_TYPE_NAMES

Dataset = Inputs  # what the harness builds once per period; models treat it as read-only

PREDICTION_COLUMNS = ["station", "utc", "nox_ppb_pred"]
ABSOLUTE_COLUMNS = ["zone", "day_type", "mean", "sd"]
RELATIVE_COLUMNS = ["zone", "day_type", "mean", "lo", "hi"]
WEEKDAY = "weekday"


class ModelParams(BaseModel):
    """Base of the hyperparameters of a model: validated, immutable, no unknown fields, round-trips YAML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int = 7  # seed of everything random in the model


@dataclass(frozen=True)
class EmissionEstimate:
    """Emissions by day type, in the units of its `kind`.

    ``absolute``: `table` has ``zone``, ``day_type``, ``mean`` and ``sd`` in t/yr.
    ``relative``: `table` has ``day_type``, ``zone`` (null when not resolved), ``mean`` (index; the weekday
    is 1) and its interval ``lo``, ``hi``.
    `ratio_ci` optionally gives the interval of each day type over the weekday for absolute models
    (columns ``day_type``, ``lo``, ``hi``, ``level``).
    """

    kind: Literal["absolute", "relative"]
    table: pd.DataFrame
    ratio_ci: pd.DataFrame | None = None

    def validate(self) -> Self:
        """Raise ValueError unless the table follows the schema of its kind."""
        columns = ABSOLUTE_COLUMNS if self.kind == "absolute" else RELATIVE_COLUMNS
        if list(self.table.columns) != columns:
            raise ValueError(f"{self.kind} estimate needs columns {columns}, got {list(self.table.columns)}")
        if not set(self.table["day_type"]) <= set(DAY_TYPE_NAMES):
            raise ValueError(f"day_type must be in {DAY_TYPE_NAMES}")
        if not np.isfinite(self.table["mean"]).all():
            raise ValueError("means must be finite")
        if self.kind == "absolute" and not (self.table["sd"] > 0).all():
            raise ValueError("sd must be positive")
        if self.kind == "relative" and not (self.table["lo"] <= self.table["hi"]).all():
            raise ValueError("lo must not exceed hi")
        return self

    def to_frame(self) -> pd.DataFrame:
        """The table with its `kind`, as ``emissions.parquet`` stores it."""
        return self.table.assign(kind=self.kind, zone=self.table["zone"].astype("Int64"))

    def day_type_ratio(self, day_type: str) -> float:
        """Emission of `day_type` over the weekday, all zones together."""
        if self.kind == "relative":
            pooled = self.table[self.table["zone"].isna()].set_index("day_type")["mean"]
            return float(pooled[day_type] / pooled[WEEKDAY])
        total = self.table.groupby("day_type")["mean"].sum()
        return float(total[day_type] / total[WEEKDAY])

    def day_type_interval(self, day_type: str) -> tuple[float, float] | None:
        """Interval of `day_type_ratio`, when the model gives one."""
        if self.kind == "relative":
            row = self.table[self.table["zone"].isna() & (self.table["day_type"] == day_type)]
            return float(row["lo"].iloc[0]), float(row["hi"].iloc[0])
        if self.ratio_ci is None:
            return None
        row = self.ratio_ci[self.ratio_ci["day_type"] == day_type]
        return float(row["lo"].iloc[0]), float(row["hi"].iloc[0])


class Model(Protocol):
    """A model (``role == "model"``, estimates emissions) or a reference (concentration floor only).

    `fit` must not read the rows of `exclude_stations`. `predict_stations` returns ``PREDICTION_COLUMNS`` for
    the rows of `stations` in `data`. `Params` is the pydantic class of `params`, used to validate configs.
    Optional: ``tempo_correlation(data) -> float``, the in-sample agreement with TEMPO.
    """

    name: ClassVar[str]
    role: ClassVar[Literal["model", "reference"]]
    Params: ClassVar[type[ModelParams]]

    def __init__(self, params: Any = None) -> None: ...

    @property
    def params(self) -> ModelParams: ...

    @property
    def n_params(self) -> int: ...

    def fit(self, data: Dataset, *, exclude_stations: Sequence[str] = ()) -> Self: ...

    def predict_stations(self, data: Dataset, stations: Sequence[str]) -> pd.DataFrame: ...

    def estimate_emissions(self) -> EmissionEstimate: ...
