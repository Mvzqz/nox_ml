# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""E2, `inversion_puff`: the baseline inversion with the transport of puffs (`jacobian_hour_puff`).

The same inversion as `nox_ml.models.inversion_plume` (point sources, a factor per road region and day type,
background integrated out); only the source-receptor matrix changes. Each hour is the plume of the last hour
plus the puffs released in the previous `max_age_h` hours, which follow the wind of the whole period. Their
NOx survives by the OH-based loss rate of the inputs (``lifetime="oh"``) or by a constant lifetime.

The puff transport has the parameters of the standard configuration of the research (wind-direction
uncertainty 30 degrees, transport speed floor 2 m/s, `nox_ml.physics.puff`), which are not exposed here: the
matrix is the one verified against the research (`ml/tests/inversion/test_jacobian.py`).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal

import pandas as pd
from pydantic import Field

from nox_ml.inversion.jacobian import (
    HourJacobian,
    Sources,
    Transport,
    jacobian_hour_puff,
    road_emission_profile,
)
from nox_ml.inversion.linear import HOLIDAYS, History, HourData
from nox_ml.models.base import ModelParams
from nox_ml.models.inversion_plume import InversionPlume, PlumeInversionParams
from nox_ml.physics.puff import (
    Trajectories,
    cumulative_loss,
    fixed_lifetime,
    local_hour_profile,
    variable_lifetime,
)


class InversionPuffParams(PlumeInversionParams):
    max_age_h: int = Field(default=24, ge=0, description="hours a puff is followed")
    lifetime: Literal["oh", "fixed"] = Field(
        default="fixed",
        description="survival of the puffs: tau_h (default, as pinn_puff; no inputs needed), or the OH-based "
        "NOx loss of the inputs (`lifetime: oh` in configs/experiments/inversion_puff.yaml)",
    )
    tau_h: float = Field(default=12.0, gt=0, description="constant NOx lifetime (h), when lifetime is fixed")


@dataclass(frozen=True)
class PuffTransport:
    """The puff transport as a `HistoryTransport`: bound to the hours being fitted, it builds the trajectories
    from the hourly wind of the whole period (`History.wind`, or the winds of the hours themselves), the road
    profile from the Infovial counts (or the typical traffic profile) and the survival of the puffs."""

    max_age_h: int
    lifetime: Literal["oh", "fixed"]
    tau_h: float

    def for_hours(
        self, hours: Sequence[HourData], history: History
    ) -> Callable[[HourData, Sources, float], HourJacobian]:
        wind = history.wind
        if wind is None:
            wind = pd.DataFrame(
                [h.wind for h in hours], columns=["u", "v"], index=pd.DatetimeIndex([h.hour for h in hours])
            ).sort_index()
        profile = (
            road_emission_profile(history.infovial, HOLIDAYS)
            if history.infovial is not None
            else local_hour_profile()
        )
        traj = Trajectories.from_wind(wind)
        if self.lifetime == "oh":
            if history.loss_rate is None:
                raise ValueError("lifetime='oh' needs the NOx loss rate: the inputs have no `loss_rate`")
            survival = variable_lifetime(cumulative_loss(history.loss_rate, traj))
        else:
            survival = fixed_lifetime(self.tau_h)
        transport = Transport(traj, survival, profile, self.max_age_h)

        def at(data: HourData, sources: Sources, no2_nox_ratio: float) -> HourJacobian:
            return jacobian_hour_puff(
                data.hour, data.wind, data.pbl, transport, sources, data.stations, data.pixels, no2_nox_ratio
            )

        return at


class InversionPuff(InversionPlume):
    name: ClassVar[str] = "inversion_puff"
    Params: ClassVar[type[ModelParams]] = InversionPuffParams

    def transport(self) -> PuffTransport:
        p = self.params
        assert isinstance(p, InversionPuffParams)
        return PuffTransport(p.max_age_h, p.lifetime, p.tau_h)

    def transport_key(self) -> tuple:
        """Puffs have no kernel identity: the transport and its lifetime are the key. Never equal to the
        plume's key, so the two never share cached Jacobians."""
        p = self.params
        assert isinstance(p, InversionPuffParams)
        return ("inversion_puff", p.max_age_h, p.lifetime, p.tau_h)
