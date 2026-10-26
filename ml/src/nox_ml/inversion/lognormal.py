"""Log-normal emissions: the MAP of the hour systems with L-BFGS-B and its Laplace approximation.

Every unknown is ``x = exp(eta)`` with ``eta`` normal, so emissions are always positive. The prior of each
one has the mean and standard deviation of the baseline's Gaussian prior (`prior_state`): with
``cv = sd / mean``, ``s^2 = log(1 + cv^2)`` and ``mu = log(mean) - s^2 / 2``. With the summed data term
``1/2 x^T H x - g^T x`` (`nox_ml.inversion.normal_equations`, background already integrated out) the MAP
minimises

    f(eta) = 1/2 x^T H x - g^T x + 1/2 sum ((eta - mu) / s)^2,        x = exp(eta)

whose gradient is ``x * (H x - g) + (eta - mu) / s^2``. The uncertainty is the inverse Hessian of ``f`` at
the MAP (Laplace), ``diag(x) H diag(x) + diag(x * (H x - g)) + diag(1 / s^2)``, a covariance of ``eta``;
by the delta method the one of ``x`` is ``diag(x) C diag(x)``.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

Array = NDArray[np.float64]
HESSIAN_FLOOR = 1e-12  # eigenvalues of the Hessian below this fraction of the largest are lifted to it


@dataclass(frozen=True)
class LogPrior:
    mu: Array
    s: Array


@dataclass(frozen=True)
class LogNormalMap:
    """The MAP: `eta` (log scale), `x = exp(eta)` and the Laplace covariance `cov_eta` of `eta`."""

    eta: Array
    cov_eta: Array
    converged: bool

    @property
    def x(self) -> Array:
        return np.exp(self.eta)

    @property
    def cov_x(self) -> Array:
        x = self.x
        return self.cov_eta * np.outer(x, x)


def log_prior(mean: Array, sd: Array, sd_mult: float = 1.0) -> LogPrior:
    """Log-normal prior with the given mean and standard deviation; `sd_mult` multiplies the log-scale
    standard deviation ``s`` (small values pin the estimate to the prior mean)."""
    s = np.sqrt(np.log1p((sd / mean) ** 2)) * sd_mult
    return LogPrior(np.log(mean) - s**2 / 2, s)


def objective(eta: Array, info: Array, gradient: Array, prior: LogPrior) -> tuple[float, Array]:
    """``f(eta)`` and its analytic gradient."""
    x = np.exp(eta)
    hx = info @ x
    z = (eta - prior.mu) / prior.s
    value = 0.5 * x @ hx - gradient @ x + 0.5 * z @ z
    return float(value), x * (hx - gradient) + z / prior.s


def hessian(eta: Array, info: Array, gradient: Array, prior: LogPrior) -> Array:
    """Hessian of `objective` in ``eta``."""
    x = np.exp(eta)
    return info * np.outer(x, x) + np.diag(x * (info @ x - gradient) + 1 / prior.s**2)


def laplace_covariance(hess: Array) -> Array:
    """Inverse of the Hessian; at a minimum it is positive definite, any eigenvalue that is not (the
    optimiser stopped short) is lifted to a floor so the covariance is a valid one."""
    values, vectors = np.linalg.eigh((hess + hess.T) / 2)
    values = np.maximum(values, HESSIAN_FLOOR * values.max())
    return (vectors / values) @ vectors.T


def map_estimate(
    info: Array,
    gradient: Array,
    prior_mean: Array,
    prior_sd: Array,
    sd_mult: float = 1.0,
    max_iter: int = 1000,
) -> LogNormalMap:
    """MAP of the log-normal emissions from the data term ``(info, gradient)``, started at the prior mean
    of ``eta``, and its Laplace covariance."""
    prior = log_prior(prior_mean, prior_sd, sd_mult)
    result = minimize(
        objective,
        prior.mu,
        args=(info, gradient, prior),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": max_iter, "ftol": 1e-14, "gtol": 1e-9},
    )
    return LogNormalMap(
        result.x, laplace_covariance(hessian(result.x, info, gradient, prior)), bool(result.success)
    )
