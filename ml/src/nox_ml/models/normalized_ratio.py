
"""Meteorology-normalized relative NOx emission estimator (E7)."""

from collections.abc import Sequence
from typing import Self

from nox_ml.data.inputs import Inputs
from nox_ml.models.base import ModelParams, EmissionEstimate

import numpy as np
import pandas as pd

from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import (
    BACKGROUND_STATION,
    DAY_TYPE_NAMES,
    HOLIDAYS,
)
from nox_ml.inversion.normalized import (
    WEEKDAY,
    bootstrap_ratio,
    day_type,
    interval,
    ratio,
)

from nox_ml.time import local_day

from nox_ml.inversion.linear import background_mean, SIGMA_STATION
from nox_ml.models.base import PREDICTION_COLUMNS
class NormalizedRatio:
    """Estimate relative road-emission changes after weather normalization."""

    name = "normalized_ratio"
    role = "model"
    Params = ModelParams

    def __init__(self, params: ModelParams | None = None):
        self.params = params if params is not None else self.Params()
        self._fitted: Inputs | None = None
        self._excluded_stations: frozenset[str] = frozenset()


    @property
    def n_params(self) -> int:
        """Number of fitted relative emission factors."""
        if self._fitted is None:
            raise RuntimeError("fit the model first")
        return len(DAY_TYPE_NAMES) - 1


    def fit(
        self,
        data: Inputs,
        *,
        exclude_stations: Sequence[str] = (),
    ) -> Self:
        self._fitted = data
        self._excluded_stations = frozenset(exclude_stations)
        return self


    def estimate_emissions(self) -> EmissionEstimate:
        """Estimate relative NOx indices by day type."""
        if self._fitted is None:
            raise RuntimeError("fit the model first")

        data = self._fitted
        key, transport = plume_transport(np.deg2rad(15.0), 1.0)
        jacobians = data.jacobians_without_stations(
            self._excluded_stations, key, transport
        )

        n_points = len(data.points)
        point_prior = data.points["prior"].to_numpy(float)

        rows = []
        training_hours = data.without_stations(self._excluded_stations)
        for hour, jac in zip(training_hours, jacobians, strict=True):
            if len(hour.nox) == 0:
                continue

            point_contribution = jac.stations[:, :n_points] @ point_prior
            road_contribution = jac.stations[:, n_points:].sum(axis=1)

            observed_road = (
                hour.nox
                - point_contribution
                - BACKGROUND_STATION[0]
            )

            day = local_day(hour.hour)
            kind = (data.day_kinds or {}).get(
                day,
                int(day_type(pd.DatetimeIndex([day]), HOLIDAYS)[0]),
            )

            rows.append({
                "day": day,
                "group": kind,
                "obs": float(observed_road.mean()),
                "model": float(road_contribution.mean()),
            })

        frame = pd.DataFrame(rows)

        if frame.empty:
            raise ValueError("No station observations available")

        estimates = []
        rng = np.random.default_rng(self.params.seed)

        for kind, name in enumerate(DAY_TYPE_NAMES):
            if kind == WEEKDAY:
                value, lo, hi = 1.0, 1.0, 1.0
            else:
                value = ratio(frame, WEEKDAY, kind)

                samples = bootstrap_ratio(
                    frame, WEEKDAY, kind, 200, rng
                )
                valid_samples = samples[np.isfinite(samples)]

                if valid_samples.size:
                    lo, hi = interval(valid_samples)
                else:
                    lo, hi = np.nan, np.nan


            estimates.append({
                "zone": None,
                "day_type": name,
                "mean": value,
                "lo": lo,
                "hi": hi,
            })

        return EmissionEstimate(
            kind="relative",
            table=pd.DataFrame(
                estimates,
                columns=["zone", "day_type", "mean", "lo", "hi"],
            ),
        )


    def predict_stations(
        self,
        data: Inputs,
        stations: Sequence[str],
    ) -> pd.DataFrame:
        """Predict NOx at requested stations using fitted relative factors."""
        if self._fitted is None:
            raise RuntimeError("fit the model first")

        estimate = self.estimate_emissions()
        factors = estimate.table.set_index("day_type")["mean"]

        key, transport = plume_transport(np.deg2rad(15.0), 1.0)
        jacobians = data.jacobians(key, transport)

        n_points = len(data.points)
        point_prior = data.points["prior"].to_numpy(float)

        rows = []
        for hour, jac, ids in zip(
            data.hours, jacobians, data.station_ids, strict=True
        ):
            wanted = np.isin(ids, list(stations))
            if not wanted.any():
                continue

            day = local_day(hour.hour)
            kind = (data.day_kinds or {}).get(
                day,
                int(day_type(pd.DatetimeIndex([day]), HOLIDAYS)[0]),
            )
            factor = float(factors[DAY_TYPE_NAMES[kind]])

            point = jac.stations[:, :n_points] @ point_prior
            road = jac.stations[:, n_points:].sum(axis=1) * factor
            base = point + road

            seen = ~np.isin(ids, list(self._excluded_stations))
            background = background_mean(
                (hour.nox - base)[seen],
                SIGMA_STATION,
                BACKGROUND_STATION,
            )

            rows.append(
                pd.DataFrame({
                    "station": ids[wanted],
                    "utc": hour.hour,
                    "nox_ppb_pred": (base + background)[wanted],
                })
            )

        return (
            pd.concat(rows, ignore_index=True)
            if rows
            else pd.DataFrame(columns=PREDICTION_COLUMNS)
        )
