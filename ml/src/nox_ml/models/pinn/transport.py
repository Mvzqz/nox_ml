"""Transport with the learned kernel: the plume of the PINN as a column of the source-receptor matrix.

Migrated from `scripts/pinn/model.py` (research-archive, `column`, `frame` and `jacobian_hour_pinn`). The
network is evaluated once on a table; the plume of any source at any receptor is then an interpolation, in
the wind frame, of ``F(A, C, gamma)`` (`nox_ml.models.pinn.equation`). Only numpy and scipy are needed here.

Differences with the Gaussian plume (`nox_ml.physics.plume`), as in the research:

- Horizontal: the column of the advection-diffusion equation, with diffusivity ``kappa |u|`` instead of the
  Briggs width plus the wind-direction spread, a little diffusion against the wind, and a loss with lifetime
  ``tau``. The pixel's own spread (`PIXEL_SIGMA_Y`) is not added: the source smoothing of the kernel is the
  only horizontal resolution.
- Vertical: the same effective mixing height as the plume, so the comparison isolates the horizontal physics.
- No wind at all (``u = v = 0``) gives no plume, as in `plume`.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

from nox_ml.inversion.jacobian import HourJacobian, Receptors, Sources, jacobian_hour_steady
from nox_ml.models.pinn.equation import L_M
from nox_ml.physics.plume import effective_height, speed

Array = NDArray[np.float64]


@dataclass(frozen=True)
class KernelTable:
    """``F`` on the grid of axes `a` (along, units of L), `c` (across, ``c >= 0``: the kernel is symmetric)
    and `gamma` (log-spaced); `values` is shaped ``(gamma, a, c)``."""

    a: Array
    c: Array
    gamma: Array
    values: NDArray[np.float32]

    def __call__(self, a: Array, c: Array, gamma: float) -> Array:
        """``F`` at `a` and `c` (units of L; ``c`` of either sign) for one `gamma`; zero outside the table."""
        log_gamma = np.log(self.gamma)
        g = np.clip((np.log(gamma) - log_gamma[0]) / (log_gamma[1] - log_gamma[0]), 0, len(log_gamma) - 1)
        coords = np.stack(
            [
                np.full(a.size, g),
                ((a - self.a[0]) / (self.a[1] - self.a[0])).ravel(),
                (np.abs(c) / (self.c[1] - self.c[0])).ravel(),
            ]
        )
        return map_coordinates(self.values, coords, order=1, mode="constant", cval=0.0).reshape(a.shape)


def wind_frame(dx: Array, dy: Array, u: float, v: float) -> tuple[Array, Array]:
    """Position of the receptor relative to the source in the wind frame: along (m) and across (m)."""
    mag = float(np.hypot(u, v))
    ex, ey = u / max(mag, 1e-6), v / max(mag, 1e-6)
    return dx * ex + dy * ey, -dx * ey + dy * ex


def column(
    dx: Array, dy: Array, u: float, v: float, table: KernelTable, tau_h: float, u_min: float
) -> tuple[Array, Array]:
    """Column (g/m2) left by 1 g/s, for receptors at (`dx`, `dy`) m from the source, in a wind (`u`, `v`)
    m/s, and the distance along the wind (m)."""
    along, across = wind_frame(dx, dy, u, v)
    if np.hypot(u, v) == 0:
        return np.zeros_like(dx), along
    s = float(speed(np.hypot(u, v), u_min))
    gamma = L_M / (s * tau_h * 3600)
    return table(along / L_M, across / L_M, gamma) / (s * L_M), along


def jacobian_hour_pinn(
    wind_h: tuple[float, float],
    pbl_h: float,
    sources: Sources,
    stations: Receptors,
    pixels: Receptors,
    no2_nox_ratio: float,
    table: KernelTable,
    tau_h: float,
    u_min: float,
) -> HourJacobian:
    """Matrix of one hour with the learned plume, in the format of `jacobian_hour_plume` (same columns and
    units), so it plugs into `nox_ml.inversion.linear` as the transport. Bind `table`, `tau_h` and `u_min`
    with `functools.partial`."""
    u, v = wind_h

    def response(xs: Array, ys: Array, xr: Array, yr: Array, extra_sy: float) -> tuple[Array, Array]:
        col, along = column(xr[:, None] - xs[None, :], yr[:, None] - ys[None, :], u, v, table, tau_h, u_min)
        return col / effective_height(along, pbl_h), col

    return jacobian_hour_steady(response, sources, stations, pixels, no2_nox_ratio)
