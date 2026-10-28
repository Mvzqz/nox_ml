"""Non-stationary transport: puffs released in previous hours, advected by the real hourly wind sequence.

Migrated from `scripts/puff.py` (research-archive). Sub-puffs every 15 min travel with the hourly wind of
the domain, spread with the distance travelled, mix in the boundary layer of the target hour and decay
chemically. Standard configuration: 24 h of history and NOx loss from OH (`chemistry.nox_loss_rate`).

The inversion matrices built from these puffs are in `nox_ml.inversion.jacobian`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.physics.plume import SIGMA_THETA, U_MIN, speed
from nox_ml.time import local_hour

Array = NDArray[np.float64]
Survival = Callable[[float, float, float], float]  # (t_rel, t_target, age_h) -> surviving fraction
Weights = Callable[[float], float | Array]  # emission factor at release time t_rel (hours since t0)
HourProfile = Callable[[pd.Timestamp], float]  # UTC start of an hour -> emission factor of roads

MAX_AGE_H = 24
SUB_PER_H = 4
TAU_CHEM_H = 4.0  # constant lifetime, used when there is no OH-based loss series
NS_PER_HOUR = 3_600_000_000_000
SIGMA0 = 500.0  # initial puff size (m)
# Typical urban traffic profile (local hour -> factor relative to the daily mean). Assumption.
TRAFFIC_PROFILE = {
    6: 0.9,
    7: 1.5,
    8: 1.6,
    9: 1.4,
    10: 1.2,
    11: 1.2,
    12: 1.2,
    13: 1.25,
    14: 1.3,
    15: 1.3,
    16: 1.35,
    17: 1.45,
}


@dataclass(frozen=True)
class WindField:
    """The hourly wind of each station (`u`, `v`: (hours, stations), m/s, NaN where a station has no data)
    from `t0` on, and where the stations are (`x`, `y`, m). `at` interpolates it to any point."""

    t0: pd.Timestamp
    u: Array
    v: Array
    x: Array
    y: Array

    @classmethod
    def from_stations(cls, wind: pd.DataFrame, xy: pd.DataFrame) -> "WindField":
        """`wind`: hourly frame indexed by UTC hour with columns ``(u, station)`` and ``(v, station)``;
        `xy`: ``x``, ``y`` of the stations. Gaps of up to 3 h of a station are interpolated."""
        idx = pd.date_range(wind.index.min(), wind.index.max(), freq="h")
        full = wind.reindex(idx).interpolate(limit=3, limit_area="inside")
        stations = list(full["u"].columns)
        position = xy.loc[stations]
        return cls(
            cast(pd.Timestamp, idx[0]),
            full["u"].to_numpy(float),
            full["v"].to_numpy(float),
            position["x"].to_numpy(float),
            position["y"].to_numpy(float),
        )

    def at(
        self, xs: Array, ys: Array, power: float = 2.0, min_distance: float = 500.0
    ) -> tuple[Array, Array]:
        """Wind (hours, points) at the points: inverse-distance weighting (``1 / d^power``, `d` floored at
        `min_distance` m) of the stations that report each hour; calm where none does."""
        d = np.maximum(np.hypot(self.x[:, None] - xs[None, :], self.y[:, None] - ys[None, :]), min_distance)
        w = d**-power
        has = ~np.isnan(self.u)
        norm = has.astype(float) @ w
        with np.errstate(invalid="ignore"):
            u = np.where(norm > 0, np.nan_to_num(self.u) @ w / norm, 0.0)
            v = np.where(norm > 0, np.nan_to_num(self.v) @ w / norm, 0.0)
        return u, v


@dataclass(frozen=True)
class Trajectories:
    """Displacement and distance travelled, integrating the hourly wind.

    `cx`, `cy` accumulate the vector wind (m); `cs` accumulates the floored speed (m). Index k is the start
    of hour k after `t0`. With the wind of the domain they are vectors (one trajectory for every source);
    with a `WindField` they are (hours, sources): each source moves with the wind at its location.
    """

    t0: pd.Timestamp
    cx: Array
    cy: Array
    cs: Array

    @classmethod
    def from_wind(cls, wind: pd.DataFrame, u_min: float = U_MIN) -> "Trajectories":
        """`wind`: hourly frame indexed by UTC hour with columns `u`, `v` (m/s). Gaps of up to 3 h are
        interpolated; longer ones are calm."""
        idx = pd.date_range(wind.index.min(), wind.index.max(), freq="h")
        full = wind.reindex(idx).interpolate(limit=3).fillna(0.0)
        u, v = full["u"].to_numpy(), full["v"].to_numpy()
        return cls.from_arrays(cast(pd.Timestamp, idx[0]), u, v, u_min)

    @classmethod
    def from_field(cls, field: WindField, xs: Array, ys: Array, u_min: float = U_MIN) -> "Trajectories":
        """One trajectory per source (xs, ys), with the wind of `field` at the source."""
        u, v = field.at(xs, ys)
        return cls.from_arrays(field.t0, u, v, u_min)

    @classmethod
    def from_arrays(cls, t0: pd.Timestamp, u: Array, v: Array, u_min: float = U_MIN) -> "Trajectories":
        start = np.zeros((1, *u.shape[1:]))
        return cls(
            t0=t0,
            cx=np.concatenate([start, np.cumsum(u * 3600, axis=0)]),
            cy=np.concatenate([start, np.cumsum(v * 3600, axis=0)]),
            cs=np.concatenate([start, np.cumsum(speed(np.hypot(u, v), u_min) * 3600, axis=0)]),
        )

    @property
    def k(self) -> Array:
        return np.arange(len(self.cx), dtype=float)

    def t(self, h: pd.Timestamp) -> float:
        """Hours from `t0` to the timestamp `h`."""
        return (h.value - self.t0.value) / NS_PER_HOUR

    def between(self, t_from: float, t_to: float) -> tuple[Array, Array, Array]:
        """Displacement (dx, dy) and distance travelled L between two times (hours from `t0`): scalars, or
        one per source with a wind field."""

        def at(c: Array, t: float) -> Array:
            t = min(max(t, 0.0), len(c) - 1.0)
            i = min(int(np.floor(t)), len(c) - 2)
            f = t - i
            return c[i] * (1 - f) + c[i + 1] * f

        return (
            at(self.cx, t_to) - at(self.cx, t_from),
            at(self.cy, t_to) - at(self.cy, t_from),
            at(self.cs, t_to) - at(self.cs, t_from),
        )


def fixed_lifetime(tau_h: float = TAU_CHEM_H) -> Survival:
    """Survival fraction for a constant NOx lifetime."""
    return lambda t_rel, t_target, age_h: float(np.exp(-age_h / tau_h))


def cumulative_loss(loss_rate: pd.Series, traj: Trajectories) -> Array:
    """Integral of the NOx loss rate (1/s, UTC hourly series) in hours -1, 0, 1, ... after `traj.t0`."""
    idx = pd.date_range(traj.t0 - pd.Timedelta(hours=1), periods=len(traj.k) + 2, freq="h")
    k = loss_rate.reindex(idx).interpolate(limit_direction="both").fillna(0.0).to_numpy()
    return np.r_[0, np.cumsum(k * 3600)]


def variable_lifetime(lam: Array) -> Survival:
    """Survival fraction for a time-varying loss, given its cumulative integral `lam` (`cumulative_loss`)."""
    grid = np.arange(len(lam))

    def survival(t_rel: float, t_target: float, age_h: float) -> float:
        return float(np.exp(-(np.interp(t_target + 1, grid, lam) - np.interp(t_rel + 1, grid, lam))))

    return survival


def local_hour_profile(table: Mapping[int, float] = TRAFFIC_PROFILE) -> HourProfile:
    """Emission factor of roads from a local-hour table (1.0 outside it)."""
    return lambda h: table.get(int(local_hour(h)), 1.0)


def road_weights(traj: Trajectories, profile: HourProfile) -> Weights:
    """Emission factor at release time `t_rel` (hours since `traj.t0`) from a profile of UTC hours."""
    return lambda t_rel: profile(cast(pd.Timestamp, traj.t0 + pd.Timedelta(hours=float(np.floor(t_rel)))))


def road_profile(traj: Trajectories, profile: Mapping[int, float] | None = None) -> Weights:
    """Emission factor of roads at release time `t_rel`, from a local-hour profile (1.0 outside it)."""
    return road_weights(traj, local_hour_profile(TRAFFIC_PROFILE if profile is None else profile))


def puffs(
    xs: Array,
    ys: Array,
    xr: Array,
    yr: Array,
    traj: Trajectories,
    t_target: float,
    pbl_h: float,
    weights: Weights,
    extra_sy: float,
    survival: Survival | None = None,
    max_age_h: int = MAX_AGE_H,
    sub_per_h: int = SUB_PER_H,
    sigma_theta: float = SIGMA_THETA,
) -> tuple[Array, Array]:
    """Sum of sub-puffs of ages 1 to `max_age_h` h released at sources (xs, ys) and seen at (xr, yr).

    Returns (ground level in g/m3, column in g/m2), shaped (receptors, sources), per 1 g/s.
    `weights(t_rel)` is the emission factor at release time (scalar or one per source).
    """
    survival = fixed_lifetime() if survival is None else survival
    g = np.zeros((len(xr), len(xs)))
    c = np.zeros((len(xr), len(xs)))
    dt = 3600 / sub_per_h
    ages = 1 + (np.arange(max_age_h * sub_per_h) + 0.5) / sub_per_h
    for age in ages:
        t_rel = t_target - age
        dx, dy, dist = traj.between(t_rel, t_target)
        w = weights(t_rel)
        sy2 = (
            (0.32 * dist / np.sqrt(1 + 0.0004 * dist)) ** 2
            + (sigma_theta * dist) ** 2
            + SIGMA0**2
            + extra_sy**2
        )
        sz = 0.24 * dist * np.sqrt(1 + 0.001 * dist)
        zeff = np.minimum(np.sqrt(np.pi / 2) * sz, pbl_h)
        r2 = (xr[:, None] - (xs[None, :] + dx)) ** 2 + (yr[:, None] - (ys[None, :] + dy)) ** 2
        col = w * dt * np.exp(-r2 / (2 * sy2)) / (2 * np.pi * sy2) * survival(t_rel, t_target, age)
        c += col
        g += col / zeff
    return g, c
