"""PINN plume model: the learned kernel as the transport of the Bayesian inversion.

The same inversion as the baseline (`nox_ml.models.inversion_plume`: point sources and a factor per road
region and day type, background of each hour integrated out); only the source-receptor matrix changes, from
the Gaussian plume to the plume of the network (`nox_ml.models.pinn.transport`). The network is trained
once with physics only (`nox_ml.models.pinn.kernel`) and does not see the data, so it is shared by every
fit, fold and period (`obtain_kernel`: memory, the bundled default network, a disk cache, or trained on
the spot).
"""

from functools import partial
from pathlib import Path
from typing import ClassVar

from nox_ml.inversion.jacobian import HourJacobianFn
from nox_ml.models.base import ModelParams
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.pinn.cache import obtain_kernel
from nox_ml.models.pinn.params import PinnParams
from nox_ml.models.pinn.transport import jacobian_hour_pinn


class PinnPlume(InversionPlume):
    name: ClassVar[str] = "pinn_plume"
    Params: ClassVar[type[ModelParams]] = PinnParams

    def _kernel(self):
        p = self.params
        assert isinstance(p, PinnParams)
        return obtain_kernel(p, Path(p.kernel_dir) if p.kernel_dir else None)

    def transport(self) -> HourJacobianFn:
        p = self.params
        assert isinstance(p, PinnParams)
        return partial(jacobian_hour_pinn, table=self._kernel().table, tau_h=p.tau_h, u_min=p.u_min)

    @property
    def n_params(self) -> int:
        """Unknowns of the inversion plus the weights of the network."""
        return super().n_params + sum(w.numel() for w in self._kernel().net.parameters())
