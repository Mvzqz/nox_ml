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
from nox_ml.inversion.jacobian import HourJacobianFn, plume_transport
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


class PlumeInversionParams(ModelParams):
    """What every model that inverts with this machinery shares: the bootstrap of the day-type ratios."""

    bootstrap_n: int = Field(default=200, ge=1, description="replicates of the bootstrap over days")
    bootstrap_level: float = Field(default=0.90, gt=0, lt=1, description="central level of its intervals")


class InversionPlumeParams(PlumeInversionParams):
    sigma_theta_deg: float = Field(15.0, gt=0, le=90, description="wind-direction uncertainty, degrees")
    u_min_ms: float = Field(1.0, gt=0, description="floor of the transport speed, m/s")


def ratio_intervals(
    systems: list[HourSystem],
    points: pd.DataFrame,
    n_regions: int,
    prior: np.ndarray,
    n: int,
    level: float,
    seed: int,
) -> pd.DataFrame:
    """Interval of each day type's road total over the weekday's (columns ``day_type``, ``lo``, ``hi``,
    ``level``): `n` replicates that solve the systems again on whole days drawn with replacement."""
    days, day_index = np.unique([s.day for s in systems], return_inverse=True)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n):
        pick = rng.choice(len(days), len(days))
        weights = np.bincount(pick, minlength=len(days))[day_index]
        boot.append(solve(systems, points, n_regions, weights).road_factors() @ prior)
    totals = np.array(boot)
    return pd.DataFrame(
        [
            {
                "day_type": DAY_TYPE_NAMES[kind],
                **dict(zip(("lo", "hi"), interval(totals[:, kind] / totals[:, WEEKDAY], level), strict=True)),
                "level": level,
            }
            for kind in (WEEKDAY, SATURDAY, SUNDAY_HOLIDAY)
        ]
    )


class InversionPlume:
    """The inversion with the stationary plume. A model with another transport subclasses it and overrides
    `transport` (and `name`, `Params`): fit, prediction and emissions are the same."""

    name: ClassVar[str] = "inversion_plume"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = InversionPlumeParams

    def __init__(self, params: PlumeInversionParams | None = None) -> None:
        self.params: ModelParams = params or self.Params()
        self._fitted: tuple[Inputs, list[HourSystem], Posterior, frozenset[str]] | None = None

    @property
    def _state(self) -> tuple[Inputs, list[HourSystem], Posterior, frozenset[str]]:
        if self._fitted is None:
            raise RuntimeError("fit the model first")
        return self._fitted

    def transport(self) -> HourJacobianFn:
        """The source-receptor matrix of one hour (`nox_ml.inversion.jacobian.HourJacobianFn`): the forward
        model the inversion assumes, which the contract tests also use to simulate data."""
        p = self.params
        assert isinstance(p, InversionPlumeParams)
        return plume_transport(np.deg2rad(p.sigma_theta_deg), p.u_min_ms)[1]

    def transport_key(self) -> tuple:
        """What identifies the transport in the Jacobian cache (`Inputs.jacobians`): the kernel and every
        param it is evaluated with. Models with another kernel put its identity first."""
        p = self.params
        assert isinstance(p, InversionPlumeParams)
        return plume_transport(np.deg2rad(p.sigma_theta_deg), p.u_min_ms)[0]

    @property
    def n_params(self) -> int:
        return len(self._state[2].mean)

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        key, transport = self.transport_key(), self.transport()
        systems = hour_systems(
            data.without_stations(exclude_stations),
            data.zones,
            data.points,
            data.no2_nox_ratio,
            data.n_regions,
            HOLIDAYS,
            day_kinds=data.day_kinds,
            jacobians=data.jacobians_without_stations(exclude_stations, key, transport),
        )
        post = solve(systems, data.points, data.n_regions)
        self._fitted = (data, systems, post, frozenset(exclude_stations))
        return self

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        """Jacobian with the fitted sources plus the background of each hour, estimated from the rows of the
        stations the model was fitted with (never the excluded ones)."""
        _, _, post, excluded = self._state
        jacobians = data.jacobians(self.transport_key(), self.transport())
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
        p = self.params
        assert isinstance(p, PlumeInversionParams)
        ci = ratio_intervals(
            systems, data.points, data.n_regions, prior, p.bootstrap_n, p.bootstrap_level, p.seed
        )
        return EmissionEstimate("absolute", table, ci)

    def tempo_correlation(self, data: Inputs) -> float:
        """Correlation of the fitted model with the TEMPO NO2 columns."""
        _, systems, post, _ = self._state
        model, observed = loo.predict_pixels(data, systems, post)
        return float(np.corrcoef(model, observed)[0, 1])
