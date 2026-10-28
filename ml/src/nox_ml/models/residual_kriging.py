# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Regression-kriging: a base model plus the kriging of its residuals between the stations.

The base model (any model of the registry that estimates emissions, declared like an ensemble member) gives
the part of the NOx the physics explains. Its residuals at the training stations are spatially correlated
(local sources, the real wind against the uniform one), so a Gaussian process of the residuals of each hour,
added to the base prediction, corrects the station it has not seen with the errors of its neighbours.

The shape of the variogram (range and nugget, relative to the variance of the hour) is one for the whole
period: by default it is the one that best predicts each training residual from the others of its hour,
pooled over every hour, on the training stations only (the marginal likelihood chose a range of 12 km that
smooths too much: 10.9 ppb on E5b against 10.4 of the IDW of its residuals). Each hour keeps its own mean
and scale (the residuals are standardized per hour), so the correction follows the hours of large and small
errors without fitting ~20 points alone.

The emissions are the base model's: kriging changes the concentration, not the inversion.
"""

from collections.abc import Sequence
from typing import Any, ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field

from nox_ml.data.inputs import Inputs
from nox_ml.models.base import PREDICTION_COLUMNS, EmissionEstimate, Model, ModelParams
from nox_ml.models.ensemble import MemberConfig

KM = 1000.0
RANGES_KM = (2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0)  # candidate ranges of the pooled fit
NUGGETS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2)  # candidate nuggets, relative to the variance of the hour
MIN_STATIONS = 3  # an hour with fewer training residuals gets no correction


class ResidualKrigingParams(ModelParams):
    base: MemberConfig = Field(
        default_factory=lambda: MemberConfig(name="inversion_plume"),
        description="the model whose residuals are kriged, as an experiment config",
    )
    length_scale_km: float | None = Field(
        default=None,
        gt=0,
        description="range of the squared-exponential kernel, km; null: pooled leave-one-out",
    )
    nugget: float | None = Field(
        default=None,
        gt=0,
        description="noise variance relative to the hour's; null: pooled leave-one-out",
    )


def _kernel(a: np.ndarray, b: np.ndarray, length_scale_km: float) -> np.ndarray:
    distance = np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])
    return np.exp(-0.5 * (distance / length_scale_km) ** 2)


def _standardized(residuals: np.ndarray) -> tuple[np.ndarray, float, float]:
    mean, scale = float(residuals.mean()), float(residuals.std())
    scale = scale if scale > 0 else 1.0
    return (residuals - mean) / scale, mean, scale


def pooled_loo_error(
    hours: Sequence[tuple[np.ndarray, np.ndarray]], length_scale_km: float, nugget: float
) -> float:
    """Mean squared error (ppb²) of kriging each training residual from the others of its hour, pooled over
    hours (``(xy_km, residuals)`` per hour). Closed form of the Gaussian process, ``e_i = (K⁻¹y)_i /
    (K⁻¹)_ii``, on the residuals standardized once per hour (the mean is not re-estimated without the
    station)."""
    total, n = 0.0, 0
    for xy, residuals in hours:
        y, _, scale = _standardized(residuals)
        inverse = np.linalg.inv(_kernel(xy, xy, length_scale_km) + nugget * np.eye(len(y)))
        errors = scale * (inverse @ y) / np.diag(inverse)
        total, n = total + float(errors @ errors), n + len(y)
    return total / n if n else float("inf")  # no hour to krige: any shape will do


def fit_shape(hours: Sequence[tuple[np.ndarray, np.ndarray]]) -> tuple[float, float]:
    """Range (km) and relative nugget of the grid that predict the training residuals best when each is left
    out: the criterion the model is judged by, without the held-out station."""
    scores = {
        (scale, nugget): pooled_loo_error(hours, scale, nugget) for scale in RANGES_KM for nugget in NUGGETS
    }
    return min(scores, key=scores.__getitem__)


def krige(
    xy: np.ndarray, residuals: np.ndarray, at: np.ndarray, length_scale_km: float, nugget: float
) -> np.ndarray:
    """Kriged residual at `at` (km) from the residuals of one hour: the hour's mean plus the Gaussian process
    of the standardized residuals, back to ppb. Far from every station it goes back to the hour's mean."""
    y, mean, scale = _standardized(residuals)
    k = _kernel(xy, xy, length_scale_km) + nugget * np.eye(len(y))
    return mean + scale * _kernel(at, xy, length_scale_km) @ np.linalg.solve(k, y)


class ResidualKriging:
    """The base model plus the kriging of its residuals at the training stations, hour by hour."""

    name: ClassVar[str] = "residual_kriging"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = ResidualKrigingParams

    def __init__(self, params: ResidualKrigingParams | None = None) -> None:
        self.params: ModelParams = params or self.Params()
        assert isinstance(self.params, ResidualKrigingParams)
        self._base: Model = self.params.base.build()
        self._residuals: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray]] | None = None
        self.shape: tuple[float, float] | None = None  # range (km) and relative nugget in use

    @property
    def n_params(self) -> int:
        return self._base.n_params + 2

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        p = self.params
        assert isinstance(p, ResidualKrigingParams)
        self._base.fit(data, exclude_stations=exclude_stations)
        excluded = set(exclude_stations)
        train = [s for s in data.station_xy.index if s not in excluded]
        predicted = self._base.predict_stations(data, train).set_index(["station", "utc"])["nox_ppb_pred"]
        self._residuals = {}
        for hour, ids in zip(data.hours, data.station_ids, strict=True):
            keep = ~np.isin(ids, list(excluded))
            model = predicted.reindex(list(zip(ids[keep], [hour.hour] * keep.sum(), strict=True))).to_numpy()
            ok = np.isfinite(model)
            if ok.sum() < MIN_STATIONS:
                continue
            xy = np.c_[hour.stations.x[keep][ok], hour.stations.y[keep][ok]] / KM
            self._residuals[hour.hour] = (xy, hour.nox[keep][ok] - model[ok])
        hours = list(self._residuals.values())
        fitted = fit_shape(hours) if p.length_scale_km is None or p.nugget is None else (0.0, 0.0)
        self.shape = (p.length_scale_km or fitted[0], p.nugget or fitted[1])
        return self

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        """The base prediction plus the kriged residual of its hour (none in hours with fewer than
        `MIN_STATIONS` training residuals)."""
        if self._residuals is None or self.shape is None:
            raise RuntimeError("fit the model first")
        base = self._base.predict_stations(data, stations)
        xy = data.station_xy.loc[base["station"]].to_numpy(float) / KM
        correction = np.zeros(len(base))
        for utc, rows in base.groupby("utc").indices.items():
            if utc in self._residuals:
                train_xy, residuals = self._residuals[utc]
                correction[rows] = krige(train_xy, residuals, xy[rows], *self.shape)
        return base.assign(nox_ppb_pred=base["nox_ppb_pred"].to_numpy(float) + correction)[PREDICTION_COLUMNS]

    def estimate_emissions(self) -> EmissionEstimate:
        return self._base.estimate_emissions()

    def tempo_correlation(self, data: Inputs) -> float | None:
        """The base model's: kriging only corrects the stations."""
        correlation: Any = getattr(self._base, "tempo_correlation", None)
        return None if correlation is None else correlation(data)
