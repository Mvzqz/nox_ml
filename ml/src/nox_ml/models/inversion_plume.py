# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""The baseline: Bayesian linear inversion with the stationary plume (`nox_ml.inversion.linear`).

Road emission by region and day type is the posterior factor alpha times the region prior; its uncertainty
for ratios between day types comes from a bootstrap over whole days that solves the systems again.
"""

from collections.abc import Sequence
from typing import ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import (
    BACKGROUND_STATION,
    DAY_TYPE_NAMES,
    HOLIDAYS,
    SIGMA_STATION,
    HourSystem,
    Posterior,
    background_mean,
    hour_systems,
    solve,
)
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.models.base import PREDICTION_COLUMNS, EmissionEstimate, ModelParams
from nox_ml.time import local_day
from nox_ml.validation import loo


class InversionPlumeParams(ModelParams):
    sigma_theta_deg: float = Field(15.0, gt=0, le=90, description="wind-direction uncertainty, degrees")
    u_min_ms: float = Field(1.0, gt=0, description="floor of the transport speed, m/s")
    bootstrap_n: int = Field(200, ge=1, description="replicates of the bootstrap over days")
    bootstrap_level: float = Field(0.90, gt=0, lt=1, description="central level of its intervals")


def bootstrap_day_types(
    systems: list[HourSystem], points: pd.DataFrame, n_regions: int, prior: np.ndarray, params: ModelParams
) -> np.ndarray:
    """Road totals by day type, shaped (replicate, day type), solving again on days drawn with replacement."""
    assert isinstance(params, InversionPlumeParams)
    days, day_index = np.unique([s.day for s in systems], return_inverse=True)
    rng = np.random.default_rng(params.seed)
    out = []
    for _ in range(params.bootstrap_n):
        pick = rng.choice(len(days), len(days))
        weights = np.bincount(pick, minlength=len(days))[day_index]
        out.append(solve(systems, points, n_regions, weights).road_factors() @ prior)
    return np.array(out)


class InversionPlume:
    name: ClassVar[str] = "inversion_plume"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = InversionPlumeParams

    def __init__(self, params: InversionPlumeParams | None = None) -> None:
        self.params = params or InversionPlumeParams()
        self._fitted: tuple[Inputs, list[HourSystem], Posterior, frozenset[str]] | None = None

    @property
    def _state(self) -> tuple[Inputs, list[HourSystem], Posterior, frozenset[str]]:
        if self._fitted is None:
            raise RuntimeError("fit the model first")
        return self._fitted

    @property
    def n_params(self) -> int:
        return len(self._state[2].mean)

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        p = self.params
        sigma_theta = np.deg2rad(p.sigma_theta_deg)
        systems = hour_systems(
            data.without_stations(exclude_stations),
            data.zones,
            data.points,
            data.no2_nox_ratio,
            data.n_regions,
            HOLIDAYS,
            sigma_theta,
            p.u_min_ms,
            data.day_kinds,
            data.jacobians_without_stations(exclude_stations, sigma_theta, p.u_min_ms),
        )
        post = solve(systems, data.points, data.n_regions)
        self._fitted = (data, systems, post, frozenset(exclude_stations))
        return self

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        """Jacobian with the fitted sources plus the background of each hour, estimated from the rows of the
        stations the model was fitted with (never the excluded ones)."""
        p = self.params
        _, _, post, excluded = self._state
        jacobians = data.jacobians(np.deg2rad(p.sigma_theta_deg), p.u_min_ms)
        days = pd.DatetimeIndex([local_day(h.hour) for h in data.hours])
        kinds = day_type(days, HOLIDAYS)
        rows = []
        for hour, jac, ids, day, kind in zip(
            data.hours, jacobians, data.station_ids, days, kinds, strict=True
        ):
            wanted = np.isin(ids, list(stations))
            if not wanted.any():
                continue
            base = jac.stations @ post.state((data.day_kinds or {}).get(day, int(kind)))
            seen = ~np.isin(ids, list(excluded))
            background = background_mean((hour.nox - base)[seen], SIGMA_STATION, BACKGROUND_STATION)
            rows.append(
                pd.DataFrame(
                    {"station": ids[wanted], "utc": hour.hour, "nox_ppb_pred": (base + background)[wanted]}
                )
            )
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=PREDICTION_COLUMNS)

    def estimate_emissions(self) -> EmissionEstimate:
        data, systems, post, _ = self._state
        prior = (
            data.zones.groupby("region")["weight"]
            .sum()
            .reindex(range(data.n_regions), fill_value=0)
            .to_numpy()
        )
        table = pd.DataFrame(
            [
                {
                    "zone": region,
                    "day_type": name,
                    "mean": post.road_factors()[kind, region] * prior[region],
                    "sd": post.sd[post.n_points + kind * post.n_regions + region] * prior[region],
                }
                for kind, name in enumerate(DAY_TYPE_NAMES)
                for region in range(data.n_regions)
            ]
        )
        boot = bootstrap_day_types(systems, data.points, data.n_regions, prior, self.params)
        level = self.params.bootstrap_level
        ci = pd.DataFrame(
            [
                {
                    "day_type": DAY_TYPE_NAMES[kind],
                    **dict(zip(("lo", "hi"), interval(boot[:, kind] / boot[:, WEEKDAY], level), strict=True)),
                    "level": level,
                }
                for kind in (WEEKDAY, SATURDAY, SUNDAY_HOLIDAY)
            ]
        )
        return EmissionEstimate("absolute", table, ci)

    def tempo_correlation(self, data: Inputs) -> float:
        """Correlation of the fitted model with the TEMPO NO2 columns."""
        _, systems, post, _ = self._state
        model, observed = loo.predict_pixels(data, systems, post)
        return float(np.corrcoef(model, observed)[0, 1])
