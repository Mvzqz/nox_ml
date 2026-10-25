"""The default network (3,000 Adam steps + 15 L-BFGS rounds, seed 0), bundled with the package so the tests
that need a good kernel do not train. When the equation changes, train the default parameters again and copy
``kernel-<key>.pt`` and ``.json`` from the cache into ``nox_ml/models/pinn/bundled/``."""

from nox_ml.models.pinn.cache import BUNDLED
from nox_ml.models.pinn.kernel import TrainedKernel
from nox_ml.models.pinn.params import PinnParams


def reference_kernel() -> TrainedKernel:
    kernel = BUNDLED.load(PinnParams())
    assert kernel is not None, "the bundled network does not match the training key of the default parameters"
    return kernel
