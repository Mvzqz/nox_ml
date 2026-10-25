"""The advection-diffusion equation the network learns, and its exact solution.

Migrated from `scripts/pinn/kernel.py` (research-archive, `reports/pinn_prototipo.md`). With one uniform wind
per hour the 2D equation is linear and does not change under translations or rotations, so the column left by
a source at a receptor depends only on the receptor position in the wind frame (along `A`, across `C`) and on
``gamma = L / (|u| tau)``. One function ``F(A, C, gamma)``, the Green function, is enough: the field of any
inventory is a sum of plumes.

In the wind frame, with lengths in units of ``L`` and the column ``G = F / (|u| L)`` (g/m2 per 1 g/s)::

    dF/dA - eps (d2F/dA2 + d2F/dC2) + gamma F = delta_s(A, C),    eps = kappa / L

``K = kappa |u|`` is the diffusivity: it stands for the meandering of the wind (kappa = 1,500 m gives the
width of a plume with a 30 degree wind spread at about 10 km). `kappa` is in metres (the diffusivity per unit
of wind speed, so K is in m2/s) and enters only through ``eps = kappa / L``, the inverse of a Peclet number
for the length ``L``: ``F`` is a function of ``(A, C, gamma, eps)``. A network is trained for one ``eps`` and
cannot be rescaled to another exactly: scaling the lengths by ``s`` maps ``(kappa, gamma)`` to
``(kappa / s, gamma / s)`` for a point source, but the source smoothing (1.5 km, fixed in metres) would
become ``1.5 / s`` km, and the tables are cut at ``A_RANGE``, ``C_MAX`` and ``GAMMA_RANGE``. So each
``kappa`` has its own network (`PinnParams.kappa` is part of the training key). ``tau`` is the lifetime of
NOx (chemistry and ventilation). ``delta_s`` is a Gaussian source of unit mass and 1.5 km: the model does
not resolve less.

For constant coefficients the solution is known (a Bessel K0 kernel convolved with the source), which is how
the network is checked.
"""

import numpy as np
from numpy.typing import NDArray
from scipy.signal import fftconvolve
from scipy.special import k0

Array = NDArray[np.float64]

L_M = 10_000.0  # length scale (m)
KAPPA_M = 1_500.0  # diffusivity over wind speed (m)
EPS = KAPPA_M / L_M
SOURCE_SIGMA = 0.15  # sd of the smoothed source, in units of L (1.5 km)
A_RANGE = (-1.0, 5.0)  # along the wind: 10 km upwind to 50 km downwind
C_MAX = 4.0  # across the wind: +-40 km
GAMMA_RANGE = (0.03, 0.75)  # tau of 4-12 h with a wind of 1-6 m/s
GAMMA_CHECKS = (0.04, 0.1, 0.25, 0.6)  # typical situations the network is validated at


def exact(gamma: float, step: float = 0.02, kappa: float = KAPPA_M) -> tuple[Array, Array, Array]:
    """Exact ``F`` for a diffusivity `kappa` (m) on a grid of spacing `step` (units of L): axes ``a`` and
    ``c`` and the field shaped ``(len(a), len(c))``. The Bessel kernel is convolved with the Gaussian source
    by FFT; its logarithmic singularity at the origin is capped at a quarter of the spacing."""
    a = np.arange(A_RANGE[0] - 1, A_RANGE[1] + 1 + step / 2, step)
    c = np.arange(-C_MAX - 1, C_MAX + 1 + step / 2, step)
    eps = kappa / L_M
    aa, cc = np.meshgrid(a, c, indexing="ij")
    r = np.maximum(np.hypot(aa, cc), step / 4)
    lam = np.sqrt(1 / (4 * eps**2) + gamma / eps)
    green = np.exp(aa / (2 * eps)) * k0(lam * r) / (2 * np.pi * eps)
    k = np.arange(-4 * SOURCE_SIGMA, 4 * SOURCE_SIGMA + step / 2, step)
    ka, kc = np.meshgrid(k, k, indexing="ij")
    source = np.exp(-(ka**2 + kc**2) / (2 * SOURCE_SIGMA**2))
    source /= source.sum()
    return a, c, fftconvolve(green, source, mode="same")
