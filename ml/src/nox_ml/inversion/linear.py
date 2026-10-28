"""Baseline inversion: Bayesian linear estimate of point sources and road factors with the stationary plume.

Migrated from `scripts/real_check_linear.py` (`build` and `solve`) and `scripts/feasibility_linear.py`
(research-archive), in the baseline configuration: one domain-mean wind per hour, wind-direction uncertainty
of 15 degrees, transport-speed floor of 1 m/s, the 4 point sources outside the industry clusters with their
research priors, TEMPO at its nominal weight (x1), no traffic-ratio constraint.

Unknowns: the point sources (t/yr), then one factor alpha per road region and day type (weekday, Saturday,
Sunday or holiday), that multiplies the prior emission of the region; the three day types share the same
prior, so any difference between them comes from the data. The background of each hour (one for the
stations, one for TEMPO) is a nuisance with a Gaussian prior; it is integrated out analytically, so the
system keeps only the source unknowns: the errors of a block of observations of one hour have covariance
``sigma^2 I + s_b^2 1 1^T`` and its inverse comes from Sherman-Morrison. The result equals solving with one
extra unknown per hour and kind, which is what the research code did.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Protocol, runtime_checkable

import geopandas as gpd
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.data.roads import UTM
from nox_ml.data.traffic import Infovial
from nox_ml.inversion.jacobian import (
    HourJacobian,
    HourJacobianFn,
    Receptors,
    Sources,
    jacobian_hour_plume,
)
from nox_ml.inversion.normalized import day_type
from nox_ml.time import local_day

Array = NDArray[np.float64]

SIGMA_THETA = np.deg2rad(15.0)  # wind-direction uncertainty
U_MIN = 1.0  # floor of the transport speed (m/s)

SIGMA_STATION = 15.0  # ppb, observation plus representation error of a station
SIGMA_PIXEL = 5e15  # molecules/cm2 of a TEMPO pixel, weight x1
BACKGROUND_STATION = (5.0, 10.0)  # ppb, prior mean and standard deviation of the hourly background
BACKGROUND_PIXEL = (5e15, 5e15)  # molecules/cm2
ROAD_FACTOR = (1.0, 0.5)  # prior mean and standard deviation of every alpha

N_DAY_TYPES = 3
DAY_TYPE_NAMES = ("weekday", "saturday", "sunday_holiday")
# Road total of a day type over the weekday's, from the Infovial traffic, by day type index (1, 2). Its
# standard deviation is an assumption: the Sunday range of the traffic counts is 0.65-0.73.
TRAFFIC_RATIOS = {1: 0.87, 2: 0.69}
TRAFFIC_RATIO_SD = 0.04
HOLIDAYS = (
    "2019-02-04",  # 2019-2020: the lockdown validation (`validation.lockdown`)
    "2019-03-18",
    "2019-04-18",
    "2019-04-19",
    "2019-05-01",
    "2020-02-03",
    "2020-03-16",
    "2020-04-09",
    "2020-04-10",
    "2020-05-01",
    "2023-11-20",
    "2023-12-25",
    "2024-01-01",
    "2024-02-05",
    "2024-03-18",
    "2024-03-28",
    "2024-03-29",
    "2024-05-01",
)

AIRPORT_PRIOR = 500.0  # t/yr, assumption (the inventory has no value per airport)

# name, kind, latitude, longitude, prior (t/yr; None: the airport assumption). The standard deviation of the
# prior is the prior itself, twice for airports. The prior of the power plants is the original one of
# `scripts/point_candidates.py`, as in the research baseline.
_POINT_SOURCES = (
    ("Nonoalco", "power plant", 19.4503, -99.15, 277.0),
    ("Valle de México (CC) + Valle de México (Vapor)", "power plant", 19.6183, -98.9764, 2615.0),
    ("AIFA (NLU)", "airport", 19.74158756011259, -99.0106819753855, None),
    ("AICM (MEX)", "airport", 19.43540722513049, -99.07122509381499, None),
)


def baseline_point_sources() -> pd.DataFrame:
    """The 4 point sources: columns ``name``, ``x``, ``y`` (UTM 14N, m), ``prior`` and ``sd`` (t/yr)."""
    rows = pd.DataFrame(_POINT_SOURCES, columns=["name", "kind", "lat", "lon", "prior"])
    xy = gpd.GeoSeries.from_xy(rows["lon"], rows["lat"], crs=4326).to_crs(UTM)
    airport = rows["kind"] == "airport"
    prior = rows["prior"].fillna(AIRPORT_PRIOR).astype(float)
    return pd.DataFrame(
        {
            "name": rows["name"],
            "x": xy.x,
            "y": xy.y,
            "prior": prior,
            "sd": prior * np.where(airport, 2.0, 1.0),
        }
    )


@dataclass(frozen=True)
class HourData:
    """What one hour contributes: the wind (u, v) in m/s of the domain, the boundary layer height in m and the
    observations at the stations (NOx, ppb) and TEMPO pixels (NO2 column, molecules/cm2). `hour` is the
    start of the hour, UTC. Absent receptors are empty arrays."""

    hour: pd.Timestamp
    wind: tuple[float, float]
    pbl: float
    stations: Receptors
    nox: Array
    pixels: Receptors
    no2: Array


@dataclass(frozen=True)
class History:
    """What a transport with memory (puffs) needs beyond the hours it is asked for: the hourly wind of the
    whole domain (columns ``u``, ``v``, indexed by the UTC start of the hour; the fitted hours are only the
    afternoons), the Infovial profile of the roads and, for a transport with OH chemistry, the NOx loss rate
    (1/s, same index). Without wind and Infovial the transport falls back to the winds of the hours
    themselves and to the typical traffic profile."""

    wind: pd.DataFrame | None = None
    infovial: Infovial | None = None
    loss_rate: pd.Series | None = None


@runtime_checkable
class HistoryTransport(Protocol):
    """A transport whose matrix of an hour depends on earlier hours, so it cannot be a function of that hour
    alone (`HourJacobianFn`). `for_hours` binds it to the hours being fitted and returns the function that
    builds the matrix of one of them from its `HourData`, the sources and the NO2/NOx ratio."""

    def for_hours(
        self, hours: Sequence[HourData], history: History
    ) -> Callable[[HourData, Sources, float], HourJacobian]: ...


# Anything `hour_jacobians` accepts as the forward model.
HourTransport = HourJacobianFn | HistoryTransport


@dataclass(frozen=True)
class Posterior:
    """Gaussian posterior of the source unknowns, in the order points, weekday regions, Saturday regions,
    Sunday or holiday regions."""

    labels: list[str]
    mean: Array
    cov: Array
    prior_mean: Array
    prior_sd: Array
    n_points: int
    n_regions: int

    @property
    def sd(self) -> Array:
        return np.sqrt(np.diag(self.cov))

    def road_factors(self) -> Array:
        """Posterior mean of alpha, shaped (day type, region)."""
        return self.mean[self.n_points :].reshape(N_DAY_TYPES, self.n_regions)

    def state(self, kind: int) -> Array:
        """Posterior mean of the unknowns that act on a day of type `kind`: the points, then its road factors;
        the columns of a Jacobian row."""
        start = self.n_points + self.n_regions * kind
        return np.r_[self.mean[: self.n_points], self.mean[start : start + self.n_regions]]


def road_sources(zones: pd.DataFrame, points: pd.DataFrame, n_regions: int) -> Sources:
    """`Sources` from the road cells (columns ``x``, ``y``, ``weight`` in t/yr and ``region``, as
    `nox_ml.data.roads.road_emission_cells`) and the point sources; the zones are the regions."""
    return Sources(
        point_x=points["x"].to_numpy(float),
        point_y=points["y"].to_numpy(float),
        cell_x=zones["x"].to_numpy(float),
        cell_y=zones["y"].to_numpy(float),
        cell_prior=zones["weight"].to_numpy(float),
        cell_zone=zones["region"].to_numpy(int),
        n_zones=n_regions,
    )


def marginalized_block(
    k: Array, y: Array, sigma: float, background: tuple[float, float]
) -> tuple[Array, Array]:
    """Contribution ``(K^T R K, K^T R (y - m))`` of one block of observations that share a background with
    prior mean ``m`` and standard deviation ``s``, where ``R = (sigma^2 I + s^2 1 1^T)^-1``. By
    Sherman-Morrison ``R = D^-1 - c D^-1 1 1^T D^-1`` with ``D = sigma^2 I`` and
    ``c = s^2 / (1 + s^2 1^T D^-1 1)``."""
    mean, sd = background
    d_inv = 1 / sigma**2
    c = sd**2 / (1 + sd**2 * d_inv * len(y))
    r = y - mean
    col_sum = k.sum(axis=0)
    info = d_inv * k.T @ k - c * d_inv**2 * np.outer(col_sum, col_sum)
    gradient = d_inv * k.T @ r - c * d_inv**2 * col_sum * r.sum()
    return info, gradient


def prior_state(points: pd.DataFrame, n_regions: int) -> tuple[Array, Array, list[str]]:
    """Prior mean, prior standard deviation and label of every unknown."""
    n_roads = N_DAY_TYPES * n_regions
    mean = np.r_[points["prior"].to_numpy(float), np.full(n_roads, ROAD_FACTOR[0])]
    sd = np.r_[points["sd"].to_numpy(float), np.full(n_roads, ROAD_FACTOR[1])]
    labels = [str(n) for n in points["name"]] + [
        f"road {kind} region {r}" for kind in DAY_TYPE_NAMES for r in range(n_regions)
    ]
    return mean, sd, labels


@dataclass(frozen=True)
class HourSystem:
    """What one hour adds to the normal equations: its local `day`, the day type `kind`, the `columns` of the
    unknowns it touches (points, then the road regions of its day type), its Jacobian, and the information
    matrix and gradient of its station and TEMPO blocks, with the background integrated out."""

    day: pd.Timestamp
    kind: int
    columns: NDArray[np.int_]
    jacobian: HourJacobian
    info: Array
    gradient: Array


def hour_jacobians(
    hours: Sequence[HourData],
    zones: pd.DataFrame,
    points: pd.DataFrame,
    no2_nox_ratio: float,
    n_regions: int,
    sigma_theta: float = SIGMA_THETA,
    u_min: float = U_MIN,
    jacobian: HourTransport | None = None,
    history: History | None = None,
) -> list[HourJacobian]:
    """The Jacobian of every hour, all its receptors, with the transport `jacobian` (default: the stationary
    plume with `sigma_theta` and `u_min`; a `HistoryTransport` also gets the `history` of the hours). Rows do
    not depend on one another, so a subset of the rows is the Jacobian of the subset of receptors
    (`HourJacobian.without_stations`)."""
    jacobian = jacobian or partial(jacobian_hour_plume, sigma_theta=sigma_theta, u_min=u_min)
    sources = road_sources(zones, points, n_regions)
    if isinstance(jacobian, HistoryTransport):
        at = jacobian.for_hours(hours, history or History())
        return [at(data, sources, no2_nox_ratio) for data in hours]
    return [
        jacobian(data.wind, data.pbl, sources, data.stations, data.pixels, no2_nox_ratio) for data in hours
    ]


def hour_systems(
    hours: Sequence[HourData],
    zones: pd.DataFrame,
    points: pd.DataFrame,
    no2_nox_ratio: float,
    n_regions: int,
    holidays: Collection[str] = HOLIDAYS,
    sigma_theta: float = SIGMA_THETA,
    u_min: float = U_MIN,
    day_kinds: Mapping[pd.Timestamp, int] | None = None,
    jacobians: Sequence[HourJacobian] | None = None,
    jacobian: HourTransport | None = None,
    tempo_sigma_mult: float = 1.0,
) -> list[HourSystem]:
    """The `HourSystem` of every hour. The Jacobians dominate the cost of an inversion; the systems can be
    solved again with other weights by `solve`. `sigma_theta` (rad) and `u_min` (m/s) are the plume
    parameters; `day_kinds` maps local days to a day type, overriding the calendar (placebos). `jacobians`
    are the ones of `hours` already computed with the transport (row for row), to skip building them;
    otherwise `jacobian` (a `HourJacobianFn` or `HistoryTransport`, default: the stationary plume with
    `sigma_theta` and `u_min`) builds them. `tempo_sigma_mult` multiplies the error of every TEMPO pixel
    (1 is the nominal weight); it does not touch the Jacobians."""
    n_points = len(points)
    sigma_pixel = SIGMA_PIXEL * tempo_sigma_mult
    days = pd.DatetimeIndex([local_day(h.hour) for h in hours])
    kinds = day_type(days, holidays)
    if day_kinds:
        kinds = np.array([day_kinds.get(d, k) for d, k in zip(days, kinds, strict=True)])
    if jacobians is None:
        jacobians = hour_jacobians(
            hours, zones, points, no2_nox_ratio, n_regions, sigma_theta, u_min, jacobian
        )
    systems = []
    for data, jac, day, kind in zip(hours, jacobians, days, kinds, strict=True):
        # the columns of the road regions go to the ones of this day type
        columns = np.r_[np.arange(n_points), n_points + n_regions * kind + np.arange(n_regions)]
        info = np.zeros((len(columns), len(columns)))
        gradient = np.zeros(len(columns))
        for k, y, sigma, background in (
            (jac.stations, data.nox, SIGMA_STATION, BACKGROUND_STATION),
            (jac.pixels, data.no2, sigma_pixel, BACKGROUND_PIXEL),
        ):
            if len(y):
                block_info, block_gradient = marginalized_block(k, y, sigma, background)
                info += block_info
                gradient += block_gradient
        systems.append(HourSystem(day, int(kind), columns, jac, info, gradient))
    return systems


def traffic_constraints(
    prior: Array, n_points: int, sd: float = TRAFFIC_RATIO_SD
) -> list[tuple[Array, float, float]]:
    """Pseudo-observations ``(row, target, sd)`` that hold the road total of Saturday and of Sunday or holiday
    at its traffic ratio over the weekday's: ``sum_r prior_r alpha[k, r] - ratio_k sum_r prior_r alpha[0, r]``
    is 0 with noise ``sd T0``, where ``T0`` is the weekday's prior total. Linear in the unknowns, so `solve`
    takes them as they are; `prior` is the prior emission of each region."""
    total = float(prior.sum())
    constraints = []
    for kind, ratio in TRAFFIC_RATIOS.items():
        row = np.zeros(n_points + N_DAY_TYPES * len(prior))
        row[n_points : n_points + len(prior)] = -ratio * prior
        start = n_points + kind * len(prior)
        row[start : start + len(prior)] = prior
        constraints.append((row, 0.0, sd * total))
    return constraints


def solve(
    systems: Sequence[HourSystem],
    points: pd.DataFrame,
    n_regions: int,
    weights: Sequence[float] | None = None,
    constraints: Sequence[tuple[Array, float, float]] = (),
) -> Posterior:
    """Posterior from the hour systems. `weights` (one per hour, default 1) multiply the information of
    each hour: an hour with weight 2 counts as if it were repeated, as a bootstrap over days needs. The
    `constraints` (``(row, target, sd)``, `traffic_constraints`) are added once, whatever the weights."""
    mean, sd, labels = prior_state(points, n_regions)
    precision = np.diag(1 / sd**2)
    rhs = mean / sd**2
    for k, system in enumerate(systems):
        w = 1.0 if weights is None else weights[k]
        if w:
            precision[np.ix_(system.columns, system.columns)] += w * system.info
            rhs[system.columns] += w * system.gradient
    for row, target, noise in constraints:
        precision += np.outer(row, row) / noise**2
        rhs += row * target / noise**2
    cov = np.linalg.inv(precision)
    return Posterior(labels, cov @ rhs, cov, mean, sd, len(points), n_regions)


def invert(
    hours: Sequence[HourData],
    zones: pd.DataFrame,
    points: pd.DataFrame,
    no2_nox_ratio: float,
    n_regions: int | None = None,
    holidays: Collection[str] = HOLIDAYS,
) -> Posterior:
    """Posterior of the point sources and the road factors given the hours of data.

    `zones` has one row per road cell (``x``, ``y``, ``weight``, ``region``); `points` is
    `baseline_point_sources()`; `no2_nox_ratio` converts NOx to the NO2 that TEMPO sees. `n_regions`
    defaults to one more than the largest region. With no hours the posterior is the prior.
    """
    n_regions = n_regions if n_regions is not None else int(zones["region"].to_numpy().max()) + 1
    systems = hour_systems(hours, zones, points, no2_nox_ratio, n_regions, holidays)
    return solve(systems, points, n_regions)


def background_mean(residual: Array, sigma: float, background: tuple[float, float]) -> float:
    """Posterior mean of the background of one hour and kind given the sources: `residual` is the
    observations minus the modeled ones without background, for the rows of the block (possibly none, then
    the prior mean). It is the mean the research code got from the background unknown it solved for."""
    mean, sd = background
    return float((mean / sd**2 + residual.sum() / sigma**2) / (1 / sd**2 + len(residual) / sigma**2))
