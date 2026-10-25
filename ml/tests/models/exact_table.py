"""A kernel table made from the exact solution: the transport tests need no torch and no training."""

from functools import cache

import numpy as np

from nox_ml.models.pinn.equation import A_RANGE, C_MAX, GAMMA_RANGE, KAPPA_M, exact
from nox_ml.models.pinn.transport import KernelTable

STEP = 0.02


@cache
def exact_table(kappa: float = KAPPA_M) -> KernelTable:
    a = np.arange(A_RANGE[0], A_RANGE[1] + 1e-9, STEP)
    c = np.arange(0, C_MAX + 1e-9, STEP)
    gammas = np.exp(np.linspace(np.log(GAMMA_RANGE[0]), np.log(GAMMA_RANGE[1]), 16))
    values = []
    for gamma in gammas:
        ea, ec, field = exact(gamma, STEP, kappa)
        values.append(
            field[np.ix_(np.round((a - ea[0]) / STEP).astype(int), np.round((c - ec[0]) / STEP).astype(int))]
        )
    return KernelTable(a, c, gammas, np.array(values, dtype=np.float32))
