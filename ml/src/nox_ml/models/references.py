# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Concentration references: the floor a model must match or beat at stations it has not seen.

They only predict NOx at stations, hour by hour from the other stations of the same hour, and estimate no
emissions (``role = "reference"``). `fit` just records which stations may not be read. `predict_stations`
uses the training stations of each hour (the requested station itself too, when it is among them): an
hour in which no training station reports gets no prediction.

- ``idw``: inverse-distance weighting, the IDW of `nox_ml.validation.loo` (R1).
- ``kriging``: a spatial-only Gaussian process per hour (R2).
"""

from collections.abc import Sequence
from typing import Any, ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel

from nox_ml.data.inputs import Inputs
from nox_ml.models.base import PREDICTION_COLUMNS, EmissionEstimate, ModelParams
from nox_ml.validation import loo

KM = 1000.0


class IdwParams(ModelParams):
    power: float = Field(default=loo.IDW_POWER, gt=0, description="exponent of the distance in the weights")
    min_distance_km: float = Field(
        default=loo.MIN_DISTANCE_KM, gt=0, description="floor of the distance in the weights, km"
    )


class KrigingParams(ModelParams):
    length_scale_km: float = Field(
        default=12.0, gt=0, description="range of the squared-exponential kernel, km"
    )
    nugget: float = Field(
        default=0.3, gt=0, description="noise variance relative to the variance of the stations of the hour"
    )


class _Reference:
    """What the references share: no fitted state beyond the excluded stations, no emissions."""

    name: ClassVar[str]
    role: ClassVar[Literal["model", "reference"]] = "reference"
    Params: ClassVar[type[ModelParams]]

    def __init__(self, params: Any = None) -> None:
        self.params: ModelParams = params or self.Params()
        self._excluded: frozenset[str] | None = None

    @property
    def n_params(self) -> int:
        return 0  # nothing is learned: the hyperparameters are chosen, not fitted

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        self._excluded = frozenset(exclude_stations)
        return self

    def estimate_emissions(self) -> EmissionEstimate:
        raise NotImplementedError(f"{self.name} is a reference: it does not estimate emissions")

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        if self._excluded is None:
            raise RuntimeError("fit the model first")
        frames = [
            self._hour(hour.hour, ids, hour.stations.x, hour.stations.y, hour.nox, stations)
            for hour, ids in zip(data.hours, data.station_ids, strict=True)
        ]
        frames = [f for f in frames if f is not None]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PREDICTION_COLUMNS)

    def _hour(
        self,
        utc: pd.Timestamp,
        ids: np.ndarray,
        x: np.ndarray,
        y: np.ndarray,
        nox: np.ndarray,
        stations: Sequence[str],
    ) -> pd.DataFrame | None:
        """Predictions of the requested stations of one hour from the training ones, or None if either is
        missing."""
        train = ~np.isin(ids, list(self._excluded or ()))
        want = np.isin(ids, list(stations))
        if not train.any() or not want.any():
            return None
        pred = self._interpolate(x[train], y[train], nox[train], x[want], y[want])
        return pd.DataFrame({"station": ids[want], "utc": utc, "nox_ppb_pred": pred})

    def _interpolate(
        self,
        x: np.ndarray,
        y: np.ndarray,
        nox: np.ndarray,
        at_x: np.ndarray,
        at_y: np.ndarray,
    ) -> np.ndarray:
        raise NotImplementedError


class Idw(_Reference):
    """R1: inverse-distance weighting of the NOx of the training stations of the hour."""

    name: ClassVar[str] = "idw"
    Params: ClassVar[type[ModelParams]] = IdwParams

    def _interpolate(
        self, x: np.ndarray, y: np.ndarray, nox: np.ndarray, at_x: np.ndarray, at_y: np.ndarray
    ) -> np.ndarray:
        p = self.params
        assert isinstance(p, IdwParams)
        distance = np.hypot(x[None, :] - at_x[:, None], y[None, :] - at_y[:, None])
        w = loo.idw_weights(distance, p.power, p.min_distance_km)
        return w @ nox / w.sum(axis=1)


class Kriging(_Reference):
    """R2: Gaussian process on the position of the stations of each hour (no time, no weather). The NOx of
    the hour is standardised, so the process has unit variance, a constant mean and the `nugget` as noise;
    far from every station the prediction goes back to the mean of the hour."""

    name: ClassVar[str] = "kriging"
    Params: ClassVar[type[ModelParams]] = KrigingParams

    def _interpolate(
        self, x: np.ndarray, y: np.ndarray, nox: np.ndarray, at_x: np.ndarray, at_y: np.ndarray
    ) -> np.ndarray:
        p = self.params
        assert isinstance(p, KrigingParams)
        process = GaussianProcessRegressor(
            ConstantKernel(1.0, "fixed") * RBF(p.length_scale_km, "fixed"),
            alpha=p.nugget,
            normalize_y=True,
            optimizer=None,
        )
        process.fit(np.c_[x, y] / KM, nox)
        return process.predict(np.c_[at_x, at_y] / KM)
