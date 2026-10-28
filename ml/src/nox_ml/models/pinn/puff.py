"""Puff transport with the learned kernel: E5b, the PINN applied to every segment of every puff.

The trajectories, the speed floor and the emission profile of the roads are the ones of `nox_ml.physics.puff`
and the matrix is assembled as in `nox_ml.inversion.jacobian.jacobian_hour_puff` (the plume of the last hour,
truncated to what was emitted since the hour began, plus the sub-puffs released in the previous hours). What
changes is the shape of each piece, which now comes from the network instead of the Gaussian:

- **The last hour** is the column of the kernel (`nox_ml.models.pinn.transport.column`), cut where the wind
  has not yet carried the emission. With no puffs older than that (``max_age_h = 0``) it is the matrix of
  `jacobian_hour_pinn` wherever the receptor is within reach.
- **A puff of age a** has travelled the distance ``d`` of its trajectory. Its mass spreads around its centre
  with the cross-wind profile the kernel has at ``d`` (the plume is the integral of the puffs of every age, so
  its section at ``d`` is their spread): ``P(r) = F(d, r) / (2 pi int r F(d, r) dr)``, isotropic and with unit
  mass, the exact Gaussian when ``F`` is one. The speed ``d / a`` sets the kernel's ``gamma``. Beyond the
  50 km of the table the profile widens as ``sqrt(d)``, the diffusive law the kernel follows.
- The mass of a puff decays with the lifetime ``tau_h`` (the kernel already includes it in the last hour; a
  puff applies it as the survival fraction, so there is no double counting). With ``lifetime="oh"`` the
  survival fraction of the puffs comes instead from the NOx loss rate of the inputs
  (`nox_ml.physics.puff.variable_lifetime`); the kernel of the last hour keeps ``tau_h``.

Like `jacobian_hour_pinn`, the kernel has its own horizontal resolution: the pixel's spread is not added.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.inversion.jacobian import (
    HourJacobian,
    Receptors,
    Sources,
    Transport,
    road_emission_profile,
)
from nox_ml.inversion.linear import HOLIDAYS, History, HourData
from nox_ml.models.pinn.equation import L_M
from nox_ml.models.pinn.transport import KernelTable, column
from nox_ml.physics.plume import (
    MOLEC_CM2_PER_GM2,
    PPB_PER_GM3,
    T_PER_YR_TO_GS,
    effective_height,
    speed,
)
from nox_ml.physics.puff import (
    SUB_PER_H,
    Survival,
    Trajectories,
    Weights,
    cumulative_loss,
    fixed_lifetime,
    local_hour_profile,
    road_weights,
    variable_lifetime,
)

Array = NDArray[np.float64]


def radial_profile(table: KernelTable, dist: float, age_h: float, tau_h: float) -> Callable[[Array], Array]:
    """Unit-mass isotropic profile ``P(r)`` (1/m2) of a puff that has travelled `dist` m in `age_h` hours,
    from the kernel's cross-wind section at that distance."""
    a_max = float(table.a[-1])
    a = dist / L_M
    widen = max(a / a_max, 1.0) ** 0.5  # beyond the table the section grows as sqrt(distance)
    gamma = L_M / (dist / (age_h * 3600) * tau_h * 3600)
    r = table.c
    f = table(np.full_like(r, min(a, a_max)), r, gamma)
    norm = 2 * np.pi * np.trapezoid(r * f, r)
    if norm <= 0:
        return lambda radius: np.zeros_like(radius)
    return lambda radius: np.interp(radius / (L_M * widen), r, f, right=0.0) / (norm * (L_M * widen) ** 2)


def pinn_puffs(
    xs: Array,
    ys: Array,
    xr: Array,
    yr: Array,
    traj: Trajectories,
    t_target: float,
    pbl_h: float,
    weights: Weights,
    survival: Survival,
    max_age_h: int,
    table: KernelTable,
    tau_h: float,
    sub_per_h: int = SUB_PER_H,
) -> tuple[Array, Array]:
    """Sum of sub-puffs of ages 1 to `max_age_h` h released at (xs, ys) and seen at (xr, yr): the same sum as
    `nox_ml.physics.puff.puffs` with the kernel's profile instead of the Gaussian. Returns (ground level in
    g/m3, column in g/m2), shaped (receptors, sources), per 1 g/s."""
    ground = np.zeros((len(xr), len(xs)))
    col = np.zeros((len(xr), len(xs)))
    dt = 3600 / sub_per_h
    for age in 1 + (np.arange(max_age_h * sub_per_h) + 0.5) / sub_per_h:
        t_rel = t_target - age
        dx, dy, dist = traj.between(t_rel, t_target)
        mass = weights(t_rel) * dt * survival(t_rel, t_target, age)
        radius = np.hypot(xr[:, None] - (xs[None, :] + dx), yr[:, None] - (ys[None, :] + dy))
        piece = mass * radial_profile(table, float(dist), age, tau_h)(radius)  # one domain wind: one distance
        col += piece
        ground += piece / effective_height(dist, pbl_h)
    return ground, col


def jacobian_hour_pinn_puff(
    h: pd.Timestamp,
    wind_h: tuple[float, float],
    pbl_h: float,
    transport: Transport,
    sources: Sources,
    stations: Receptors,
    pixels: Receptors,
    no2_nox_ratio: float,
    table: KernelTable,
    tau_h: float,
    u_min: float,
) -> HourJacobian:
    """Matrix of the hour that starts at `h` (UTC), in the format and units of `jacobian_hour_puff`, with the
    kernel `table` as the shape of every plume. `transport` carries the trajectories, the survival of the
    puffs, their age limit and the emission profile of the roads."""
    to_ppb = T_PER_YR_TO_GS * PPB_PER_GM3
    to_molec = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * no2_nox_ratio
    args = (h, wind_h, pbl_h, transport, sources, table, tau_h, u_min)
    return HourJacobian(
        stations=_block(*args, receptors=stations, ground=True, scale=to_ppb),
        pixels=_block(*args, receptors=pixels, ground=False, scale=to_molec),
    )


def _block(
    h: pd.Timestamp,
    wind_h: tuple[float, float],
    pbl_h: float,
    transport: Transport,
    sources: Sources,
    table: KernelTable,
    tau_h: float,
    u_min: float,
    receptors: Receptors,
    ground: bool,
    scale: float,
) -> Array:
    """Stations see the ground level concentration, pixels the column."""
    if not len(receptors.x):
        return np.zeros((0, sources.n_columns))
    u, v = wind_h
    reach = (
        float(speed(np.hypot(u, v), u_min)) * 3600
    )  # the last hour's plume only extends as far as the wind went
    t_target = transport.traj.t(h) + 0.5
    roads_now = transport.road_profile(h)
    roads_before = road_weights(transport.traj, transport.road_profile)

    def response(xs: Array, ys: Array, weights: Weights) -> tuple[Array, Array]:
        col, along = column(
            receptors.x[:, None] - xs[None, :], receptors.y[:, None] - ys[None, :], u, v, table, tau_h, u_min
        )
        col = np.where(along < reach, col, 0.0)
        steady = col / effective_height(along, pbl_h) if ground else col
        aged_ground, aged_col = pinn_puffs(
            xs, ys, receptors.x, receptors.y, transport.traj, t_target, pbl_h, weights,
            transport.survival, transport.max_age_h, table, tau_h,
        )  # fmt: skip
        return steady, aged_ground if ground else aged_col

    points_steady, points_aged = response(sources.point_x, sources.point_y, lambda _t: 1.0)
    cells_steady, cells_aged = response(sources.cell_x, sources.cell_y, roads_before)
    cells = (cells_steady * roads_now + cells_aged) * sources.cell_prior
    zones = np.stack([cells[:, sources.cell_zone == z].sum(axis=1) for z in range(sources.n_zones)], axis=1)
    return np.hstack([(points_steady + points_aged) * scale, zones * scale])


@dataclass(frozen=True)
class PinnPuffTransport:
    """The puff transport of E5b as a `HistoryTransport`: bound to the hours being fitted, it builds the
    trajectories from the hourly wind of the whole period (`History.wind`, or the winds of the hours
    themselves) and the road profile from the Infovial counts (or the typical traffic profile). With
    ``lifetime="oh"`` the puffs survive by the NOx loss rate of `History.loss_rate` (required then)."""

    table: KernelTable
    tau_h: float
    u_min: float
    max_age_h: int
    lifetime: Literal["fixed", "oh"] = "fixed"

    def for_hours(
        self, hours: Sequence[HourData], history: History
    ) -> Callable[[HourData, Sources, float], HourJacobian]:
        wind = history.wind
        if wind is None:
            wind = pd.DataFrame(
                [h.wind for h in hours], columns=["u", "v"], index=pd.DatetimeIndex([h.hour for h in hours])
            ).sort_index()
        profile = (
            road_emission_profile(history.infovial, HOLIDAYS)
            if history.infovial is not None
            else local_hour_profile()
        )
        traj = Trajectories.from_wind(wind, self.u_min)
        if self.lifetime == "oh":
            if history.loss_rate is None:
                raise ValueError("lifetime='oh' needs the NOx loss rate: the inputs have no `loss_rate`")
            survival = variable_lifetime(cumulative_loss(history.loss_rate, traj))
        else:
            survival = fixed_lifetime(self.tau_h)
        transport = Transport(traj, survival, profile, self.max_age_h)

        def at(data: HourData, sources: Sources, no2_nox_ratio: float) -> HourJacobian:
            return jacobian_hour_pinn_puff(
                data.hour, data.wind, data.pbl, transport, sources, data.stations, data.pixels,
                no2_nox_ratio, self.table, self.tau_h, self.u_min,
            )  # fmt: skip

        return at
