"""Steady-state Gaussian plume and the wind floor.

Migrated from `scripts/feasibility_linear.py` (research-archive). Standard configuration: wind-direction
uncertainty of 30 degrees and a transport-speed floor of 2.0 m/s (`reports/estancamiento.md`).
"""

import numpy as np
from numpy.typing import ArrayLike, NDArray

Array = NDArray[np.float64]

# Units: emissions in t/yr, concentrations in g/m3 (ppb) and g/m2 (molecules/cm2).
T_PER_YR_TO_GS = 1e6 / 3.156e7  # 1 t/yr in g/s
PPB_PER_GM3 = 8.314 * 293 / (77_000 * 46) * 1e9  # NOx as NO2, ~2,240 m a.s.l.
MOLEC_CM2_PER_GM2 = 6.022e23 / 46 / 1e4

SIGMA_THETA = np.deg2rad(30.0)  # wind-direction uncertainty (measured error: 28-32 degrees)
U_MIN = 2.0  # floor of the transport speed (m/s); 1.0 was the previous standard
X_MAX = 40_000.0  # maximum downwind distance of the plume (m)
MIN_ALONG = 300.0  # dispersion is evaluated at no less than this distance (m)


def speed(mag: ArrayLike, u_min: float = U_MIN) -> Array:
    """Effective transport speed (m/s) from the speed of the domain-mean vector wind."""
    return np.maximum(mag, u_min)


def plume(
    xs: Array,
    ys: Array,
    xr: Array,
    yr: Array,
    u: ArrayLike,
    v: ArrayLike,
    pbl: float,
    extra_sy: float = 0.0,
    x_max: float = X_MAX,
    sigma_theta: float = SIGMA_THETA,
    u_min: float = U_MIN,
) -> tuple[Array, Array]:
    """Contribution of sources (xs, ys) at receptors (xr, yr) per 1 g/s.

    `u`, `v` are scalars (one wind for the domain) or (receptors, sources) matrices. Returns the ground-level
    concentration (g/m3) and the column (g/m2), both shaped (receptors, sources). Ground-level Gaussian
    source, urban Briggs class B, mixing limited by the boundary layer `pbl` (m).
    """
    mag = np.hypot(u, v)
    sp = speed(mag, u_min)
    ex, ey = u / np.maximum(mag, 1e-6), v / np.maximum(mag, 1e-6)
    dx = xr[:, None] - xs[None, :]
    dy = yr[:, None] - ys[None, :]
    along = dx * ex + dy * ey
    cross = -dx * ey + dy * ex
    ok = (along > 0) & (along < x_max)
    a = np.maximum(along, MIN_ALONG)
    sy = np.sqrt((0.32 * a / np.sqrt(1 + 0.0004 * a)) ** 2 + (a * sigma_theta) ** 2 + extra_sy**2)
    sz = 0.24 * a * np.sqrt(1 + 0.001 * a)
    zeff = np.minimum(np.sqrt(np.pi / 2) * sz, pbl)
    lateral = np.exp(-(cross**2) / (2 * sy**2)) / (np.sqrt(2 * np.pi) * sy * sp)
    col = np.where(ok, lateral, 0.0)
    return col / zeff, col
