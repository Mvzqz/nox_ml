"""Regularized and non-negative least squares on the hour systems, without a Bayesian reading.

The unknowns are normalised by their prior assumption: ``u = x / x0`` with ``x0`` the prior mean (t/yr for the
point sources, 1 for the road factors), so every parameter is about 1 and one penalty weight treats them all
alike. With ``H`` and ``g`` the summed data term (`nox_ml.inversion.normal_equations`) the estimate solves

    min_{u >= 0}  1/2 u^T H_u u - g_u^T u + alpha m / 2 * |u - c|^2

where ``H_u = D H D``, ``g_u = D g``, ``D = diag(x0)``, ``m`` is the median diagonal of ``H_u`` (so
``alpha`` is relative to the information the data carry, not to the units) and ``c`` is 1 (shrink to the
prior assumption) or 0 (plain ridge).
"""

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import nnls

from nox_ml.inversion.normal_equations import DayEquations

Array = NDArray[np.float64]
Penalty = Literal["prior", "zero"]
RANK_TOLERANCE = 1e-12  # eigenvalues below this fraction of the largest are directions the data do not see


def solve_regularized(
    info: Array, gradient: Array, scale: Array, alpha: float, penalty: Penalty = "prior"
) -> Array:
    """Non-negative ridge estimate of the unknowns ``x = scale * u`` (see the module docstring). The
    quadratic is turned into a least-squares problem through the eigendecomposition of its matrix, which
    also copes with unknowns the data do not constrain (``alpha = 0``)."""
    h = info * np.outer(scale, scale)
    g = gradient * scale
    weight = alpha * float(np.median(np.diag(h)))
    centre = np.ones_like(g) if penalty == "prior" else np.zeros_like(g)
    matrix = h + weight * np.eye(len(g))
    rhs = g + weight * centre
    values, vectors = np.linalg.eigh((matrix + matrix.T) / 2)
    seen = values > RANK_TOLERANCE * values.max()
    root = np.sqrt(values[seen])
    u, _ = nnls(root[:, None] * vectors[:, seen].T, vectors[:, seen].T @ rhs / root)
    return u * scale


def bootstrap_regularized(
    days: DayEquations,
    constraint: tuple[Array, Array],
    scale: Array,
    alpha: float,
    penalty: Penalty,
    n: int,
    seed: int,
) -> Array:
    """The estimate on `n` replicates of the days drawn with replacement, shaped (n, unknowns). The
    `constraint` terms are added once to every replicate."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        info, gradient = days.total(days.resample(rng))
        out.append(solve_regularized(info + constraint[0], gradient + constraint[1], scale, alpha, penalty))
    return np.array(out)
