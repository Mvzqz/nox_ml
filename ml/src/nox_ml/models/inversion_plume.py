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
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import (
    BACKGROUND_STATION,
    DAY_TYPE_NAMES,
    HOLIDAYS,
    SIGMA_STATION,
    TRAFFIC_RATIO_SD,
    HourSystem,
    HourTransport,
    Posterior,
    background_mean,
    hour_systems,
    solve,
    traffic_constraints,
)
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.models.base import PREDICTION_COLUMNS, EmissionEstimate, ModelParams
from nox_ml.time import local_day
from nox_ml.validation import loo


class PlumeInversionParams(ModelParams):
    """What every model that inverts with this machinery shares: the bootstrap of the day-type ratios, the
    weight of the TEMPO pixels and the optional traffic ratio of the day types. The defaults are the
    baseline (nominal TEMPO weight, no traffic constraint)."""

    bootstrap_n: int = Field(default=200, ge=1, description="replicates of the bootstrap over days")
    bootstrap_level: float = Field(default=0.90, gt=0, lt=1, description="central level of its intervals")
    # 7: whole weeks. On twins with a background that persists for days (`validation.twins`, 20 seeds) the
    # 90 % interval of the Sunday ratio held the truth 17 times with 7-day blocks, 6 in 10 with single days
    # and 14-15 with 14- and 21-day blocks (too few blocks)
    bootstrap_block_days: int = Field(
        default=7,
        ge=1,
        description="consecutive days drawn together; > 1 keeps the days a persistent background ties",
    )
    tempo_sigma_mult: float = Field(
        default=1.0, gt=0, description="multiplies the error of every TEMPO pixel; 1 is the nominal weight"
    )
    traffic_constraint: bool = Field(
        default=False, description="hold the Saturday and Sunday road totals at their traffic ratios"
    )
    traffic_sd: float = Field(
        default=TRAFFIC_RATIO_SD, gt=0, description="standard deviation of those ratios (traffic constraint)"
    )


class InversionPlumeParams(PlumeInversionParams):
    sigma_theta_deg: float = Field(15.0, gt=0, le=90, description="wind-direction uncertainty, degrees")
    u_min_ms: float = Field(1.0, gt=0, description="floor of the transport speed, m/s")


def block_draw(n_days: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """How many times each of `n_days` (in time order) enters a moving-block bootstrap replicate: blocks of
    `block` consecutive days with random starts until `n_days` are drawn (the last block is cut). With
    ``block = 1`` it is the plain bootstrap of days. Days tied by a background that persists for several days
    stay together, so the spread of the replicates is not understated."""
    block = min(block, n_days)
    starts = rng.integers(0, n_days - block + 1, size=-(-n_days // block))
    picked = (starts[:, None] + np.arange(block)).ravel()[:n_days]
    return np.bincount(picked, minlength=n_days)


def ratio_intervals(
    systems: list[HourSystem],
    points: pd.DataFrame,
    n_regions: int,
    prior: np.ndarray,
    n: int,
    level: float,
    seed: int,
    constraints: Sequence[tuple[np.ndarray, float, float]] = (),
    block: int = 1,
) -> pd.DataFrame:
    """Interval of each day type's road total over the weekday's (columns ``day_type``, ``lo``, ``hi``,
    ``level``): `n` replicates that solve the systems again on whole days drawn with replacement, in blocks
    of `block` consecutive days (`block_draw`), with the same `constraints` as the fit."""
    days, day_index = np.unique([s.day for s in systems], return_inverse=True)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n):
        weights = block_draw(len(days), block, rng)[day_index]
        boot.append(solve(systems, points, n_regions, weights, constraints).road_factors() @ prior)
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

    def transport(self) -> HourTransport:
        """The source-receptor matrix of one hour (`HourJacobianFn`, or a `HistoryTransport` when it depends
        on earlier hours): the forward model the inversion assumes, which the contract tests also use to
        simulate data."""
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

    def road_prior(self, data: Inputs) -> np.ndarray:
        """Prior emission of each road region (t/yr): the sum of its cells."""
        return (
            data.zones.groupby("region")["weight"]
            .sum()
            .reindex(range(data.n_regions), fill_value=0)
            .to_numpy()
        )

    def constraints(self, data: Inputs) -> list[tuple[np.ndarray, float, float]]:
        """The pseudo-observations of the fit: none by default (the baseline), the traffic ratios when on."""
        p = self.params
        assert isinstance(p, PlumeInversionParams)
        # A placebo refit relabels weekdays as Sundays (`Inputs.with_day_kinds`). The traffic ratios describe
        # the real calendar, so they are not imposed on those fake Sundays: otherwise the placebo finds a drop
        # that is not there. The refit has no constraint, as in the baseline.
        if not p.traffic_constraint or data.day_kinds:
            return []
        return traffic_constraints(self.road_prior(data), len(data.points), p.traffic_sd)

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        key, transport = self.transport_key(), self.transport()
        p = self.params
        assert isinstance(p, PlumeInversionParams)
        systems = hour_systems(
            data.without_stations(exclude_stations),
            data.zones,
            data.points,
            data.no2_nox_ratio,
            data.n_regions,
            HOLIDAYS,
            day_kinds=data.day_kinds,
            jacobians=data.jacobians_without_stations(exclude_stations, key, transport),
            tempo_sigma_mult=p.tempo_sigma_mult,
        )
        post = solve(systems, data.points, data.n_regions, constraints=self.constraints(data))
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
        prior = self.road_prior(data)
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
            systems,
            data.points,
            data.n_regions,
            prior,
            p.bootstrap_n,
            p.bootstrap_level,
            p.seed,
            self.constraints(data),
            p.bootstrap_block_days,
        )
        return EmissionEstimate("absolute", table, ci)

    def tempo_correlation(self, data: Inputs) -> float:
        """Correlation of the fitted model with the TEMPO NO2 columns."""
        _, systems, post, _ = self._state
        model, observed = loo.predict_pixels(data, systems, post)
        return float(np.corrcoef(model, observed)[0, 1])
