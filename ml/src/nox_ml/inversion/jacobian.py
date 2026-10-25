"""Source-receptor matrix of one hour: what each source adds at each station and TEMPO pixel.

Migrated from `jacobian_hour_puff` (`scripts/puff.py`) as used by the standard configuration of
`scripts/pinn/invert.py` (research-archive, `jacobian_puff_mx` in `scripts/puffs_cdmx.py`). The concentration
is linear in the emissions, so the matrix turns the unknowns (point sources and one emission factor per road
zone) into modeled observations. Each entry is the sum of the plume of the last hour (truncated to what was
emitted since the hour began) and the puffs released in the previous hours, `MAX_AGE_H` of them.

Columns: the point sources, then the road zones. A point source column is the response to 1 t/yr; a zone
column is the response to the zone at its prior emission (the unknown is a factor of that prior, 1 at the
prior). Stations respond in ppb of NOx, pixels in molecules/cm2 of NO2 (the NO2/NOx `no2_nox_ratio` of the
afternoon).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.inversion.normalized import day_type
from nox_ml.physics.plume import (
    MOLEC_CM2_PER_GM2,
    PPB_PER_GM3,
    SIGMA_THETA,
    T_PER_YR_TO_GS,
    U_MIN,
    plume,
    speed,
)
from nox_ml.physics.puff import (
    MAX_AGE_H,
    TRAFFIC_PROFILE,
    HourProfile,
    Survival,
    Trajectories,
    Weights,
    cumulative_loss,
    puffs,
    road_weights,
    variable_lifetime,
)
from nox_ml.time import local_day, local_hour

Array = NDArray[np.float64]

PIXEL_SIGMA_Y = 1300.0  # extra lateral spread (m) of a TEMPO pixel of about 2 x 4.5 km


@dataclass(frozen=True)
class Sources:
    """Point sources and road cells (positions in m, projected). `cell_prior` is the prior emission of each
    cell in t/yr and `cell_zone` its zone index in `range(n_zones)`; a zone without cells has zero columns."""

    point_x: Array
    point_y: Array
    cell_x: Array
    cell_y: Array
    cell_prior: Array
    cell_zone: NDArray[np.int_]
    n_zones: int

    @property
    def n_columns(self) -> int:
        return len(self.point_x) + self.n_zones


@dataclass(frozen=True)
class Receptors:
    """Positions (m, projected) where the model is evaluated."""

    x: Array
    y: Array


@dataclass(frozen=True)
class Transport:
    """What moves and removes the mass: the wind sequence, the survival of NOx and the emission profile of
    roads over the day. `max_age_h` is how far back puffs are followed."""

    traj: Trajectories
    survival: Survival
    road_profile: HourProfile
    max_age_h: int = MAX_AGE_H


@dataclass(frozen=True)
class HourJacobian:
    """Rows are receptors, columns `Sources` (points, then zones)."""

    stations: Array  # ppb
    pixels: Array  # molecules/cm2

    def without_stations(self, keep: NDArray[np.bool_]) -> "HourJacobian":
        """Only the station rows where `keep` is true: each row depends on its own receptor alone, so this is
        the matrix that would be built without the other stations."""
        return HourJacobian(self.stations[keep], self.pixels)


def standard_transport(wind: pd.DataFrame, loss_rate: pd.Series, road_profile: HourProfile) -> Transport:
    """Standard configuration: puffs of 24 h with the NOx lifetime of the OH-based loss (`loss_rate`, 1/s,
    UTC hourly series; see `nox_ml.physics.chemistry`) and the wind at 2 m/s minimum (`wind`: see
    `Trajectories.from_wind`)."""
    traj = Trajectories.from_wind(wind)
    return Transport(traj, variable_lifetime(cumulative_loss(loss_rate, traj)), road_profile)


def road_emission_profile(infovial: Mapping[int, Mapping[int, float]], holidays=()) -> HourProfile:
    """Emission factor of roads for a UTC hour: the typical urban profile at local 6-17 h and, outside those
    hours (puffs of more than 6 h were released at night), the Infovial profile of the local day type
    (0 weekday, 1 Saturday, 2 Sunday or the dates in `holidays`, 'YYYY-MM-DD')."""

    @cache
    def profile(h: pd.Timestamp) -> float:
        hour = int(local_hour(h))
        if hour in TRAFFIC_PROFILE:
            return TRAFFIC_PROFILE[hour]
        kind = int(day_type(pd.DatetimeIndex([local_day(h)]), holidays)[0])
        return infovial[kind][hour]

    return profile


def jacobian_hour_puff(
    h: pd.Timestamp,
    wind_h: tuple[float, float],
    pbl_h: float,
    transport: Transport,
    sources: Sources,
    stations: Receptors,
    pixels: Receptors,
    no2_nox_ratio: float,
) -> HourJacobian:
    """Matrix of the hour that starts at `h` (UTC), with the wind `wind_h` = (u, v) (m/s) and the boundary
    layer height `pbl_h` (m) of that hour. Receptors that are absent that hour are empty arrays."""
    to_ppb = T_PER_YR_TO_GS * PPB_PER_GM3
    to_molec = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * no2_nox_ratio
    return HourJacobian(
        stations=_block(h, wind_h, pbl_h, transport, sources, stations, 0.0, ground=True, scale=to_ppb),
        pixels=_block(
            h, wind_h, pbl_h, transport, sources, pixels, PIXEL_SIGMA_Y, ground=False, scale=to_molec
        ),
    )


def _block(
    h: pd.Timestamp,
    wind_h: tuple[float, float],
    pbl_h: float,
    transport: Transport,
    sources: Sources,
    receptors: Receptors,
    extra_sy: float,
    ground: bool,
    scale: float,
) -> Array:
    """Stations see the ground level concentration, pixels the column."""
    if not len(receptors.x):
        return np.zeros((0, sources.n_columns))
    u, v = wind_h
    reach = float(speed(np.hypot(u, v))) * 3600  # the last hour's plume only extends as far as the wind went
    t_target = transport.traj.t(h) + 0.5
    pick = 0 if ground else 1
    roads_now = transport.road_profile(h)
    roads_before = road_weights(transport.traj, transport.road_profile)

    def response(xs: Array, ys: Array, weights: Weights) -> tuple[Array, Array]:
        steady = plume(xs, ys, receptors.x, receptors.y, u, v, pbl_h, extra_sy=extra_sy, x_max=reach)
        aged = puffs(
            xs,
            ys,
            receptors.x,
            receptors.y,
            transport.traj,
            t_target,
            pbl_h,
            weights,
            extra_sy,
            transport.survival,
            transport.max_age_h,
        )
        return steady[pick], aged[pick]

    points_steady, points_aged = response(sources.point_x, sources.point_y, lambda _t: 1.0)
    cells_steady, cells_aged = response(sources.cell_x, sources.cell_y, roads_before)
    cells = (cells_steady * roads_now + cells_aged) * sources.cell_prior
    zones = np.stack([cells[:, sources.cell_zone == z].sum(axis=1) for z in range(sources.n_zones)], axis=1)
    return np.hstack([(points_steady + points_aged) * scale, zones * scale])


def jacobian_hour_plume(
    wind_h: tuple[float, float],
    pbl_h: float,
    sources: Sources,
    stations: Receptors,
    pixels: Receptors,
    no2_nox_ratio: float,
    sigma_theta: float = SIGMA_THETA,
    u_min: float = U_MIN,
) -> HourJacobian:
    """Matrix of one hour with the stationary plume: the wind `wind_h` = (u, v) (m/s) of the whole domain
    blows forever, with no memory of earlier hours and a constant emission through the day. Migrated from
    `jacobian_hour` (`scripts/feasibility_linear.py`, research-archive). `sigma_theta` (rad) and `u_min`
    (m/s) are the wind-direction uncertainty and the transport-speed floor. Same columns and units as
    `jacobian_hour_puff`."""
    to_ppb = T_PER_YR_TO_GS * PPB_PER_GM3
    to_molec = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * no2_nox_ratio

    def block(receptors: Receptors, extra_sy: float, ground: bool, scale: float) -> Array:
        if not len(receptors.x):
            return np.zeros((0, sources.n_columns))
        pick = 0 if ground else 1

        def response(xs: Array, ys: Array) -> Array:
            u, v = wind_h
            return plume(
                xs, ys, receptors.x, receptors.y, u, v, pbl_h, extra_sy, sigma_theta=sigma_theta, u_min=u_min
            )[pick]

        cells = response(sources.cell_x, sources.cell_y) * sources.cell_prior
        zones = np.stack(
            [cells[:, sources.cell_zone == z].sum(axis=1) for z in range(sources.n_zones)], axis=1
        )
        return np.hstack([response(sources.point_x, sources.point_y) * scale, zones * scale])

    return HourJacobian(
        stations=block(stations, 0.0, ground=True, scale=to_ppb),
        pixels=block(pixels, PIXEL_SIGMA_Y, ground=False, scale=to_molec),
    )
