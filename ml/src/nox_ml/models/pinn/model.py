"""PINN plume model: the learned kernel as the transport of the Bayesian inversion.

The same inversion as the baseline (`nox_ml.models.inversion_plume`: point sources and a factor per road
region and day type, background of each hour integrated out); only the source-receptor matrix changes, from
the Gaussian plume to the plume of the network (`nox_ml.models.pinn.transport`). The network is trained
once with physics only (`nox_ml.models.pinn.kernel`) and does not see the data, so it is shared by every
fit, fold and period (`obtain_kernel`: memory, the bundled default network, a disk cache, or trained on
the spot).

`PinnPuff` (E5b) is the same inversion with the kernel applied to the puffs of the previous hours
(`nox_ml.models.pinn.puff`) instead of a stationary plume.
"""

from functools import partial
from pathlib import Path
from typing import ClassVar

from nox_ml.inversion.jacobian import HourJacobianFn
from nox_ml.inversion.linear import HistoryTransport
from nox_ml.models.base import ModelParams
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.pinn.cache import obtain_kernel
from nox_ml.models.pinn.params import PinnParams, PinnPuffParams
from nox_ml.models.pinn.puff import PinnPuffTransport
from nox_ml.models.pinn.transport import jacobian_hour_pinn


class PinnInversion(InversionPlume):
    """What the PINN models share: the kernel (by `obtain_kernel`) and the count of weights it adds."""

    Params: ClassVar[type[ModelParams]] = PinnParams

    def _kernel(self):
        p = self.params
        assert isinstance(p, PinnParams)
        return obtain_kernel(p, Path(p.kernel_dir) if p.kernel_dir else None)

    @property
    def n_params(self) -> int:
        """Unknowns of the inversion plus the weights of the network."""
        return super().n_params + sum(w.numel() for w in self._kernel().net.parameters())


class PinnPlume(PinnInversion):
    name: ClassVar[str] = "pinn_plume"

    def transport(self) -> HourJacobianFn:
        p = self.params
        assert isinstance(p, PinnParams)
        return partial(jacobian_hour_pinn, table=self._kernel().table, tau_h=p.tau_h, u_min=p.u_min)

    def transport_key(self) -> tuple:
        """The kernel (by its training hash) and the params it is evaluated with: never the plume's key."""
        p = self.params
        assert isinstance(p, PinnParams)
        return ("pinn", p.training_key(), p.tau_h, p.u_min)


class PinnPuff(PinnInversion):
    name: ClassVar[str] = "pinn_puff"
    Params: ClassVar[type[ModelParams]] = PinnPuffParams

    def transport(self) -> HistoryTransport:
        p = self.params
        assert isinstance(p, PinnPuffParams)
        return PinnPuffTransport(self._kernel().table, p.tau_h, p.u_min, p.max_age_h)

    def transport_key(self) -> tuple:
        """The kernel, how it is evaluated and how long the puffs live: never the plume's, the PINN plume's or
        a Gaussian puff's key (that one has no kernel identity)."""
        p = self.params
        assert isinstance(p, PinnPuffParams)
        return ("pinn_puff", p.training_key(), p.tau_h, p.u_min, p.max_age_h)
