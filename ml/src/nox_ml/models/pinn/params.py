"""Hyperparameters of the PINN plume model."""

import hashlib
import json
from typing import Annotated

from pydantic import Field

from nox_ml.inversion.linear import U_MIN
from nox_ml.models.inversion_plume import PlumeInversionParams
from nox_ml.models.pinn import equation
from nox_ml.physics.puff import MAX_AGE_H

# The fields that decide the trained network; the others only matter when it is evaluated.
TRAINING_FIELDS = {
    "layers",
    "width",
    "learning_rate",
    "physics_weight",
    "adam_steps",
    "lbfgs_rounds",
    "seed",
}  # plus `kappa`, which enters the key as the equation constant it replaces

EQUATION_CONSTANTS = ("L_M", "KAPPA_M", "SOURCE_SIGMA", "A_RANGE", "C_MAX", "GAMMA_RANGE")


class PinnParams(PlumeInversionParams):
    """Hyperparameters of the PINN plume. The defaults are the research prototype
    (`reports/pinn_prototipo.md`). Training fields decide the network (and its cache entry); `tau_h` and
    `u_min` only enter when the network is evaluated, so changing them does not retrain. `seed` seeds the
    network and the bootstrap."""

    layers: Annotated[int, Field(ge=1, description="Hidden layers of the network.")] = 4
    width: Annotated[int, Field(ge=1, description="Neurons per hidden layer.")] = 64
    learning_rate: Annotated[
        float, Field(gt=0, description="Initial Adam rate; decays with a cosine to 1/100 of it.")
    ] = 2e-3
    physics_weight: Annotated[
        float,
        Field(gt=0, description="Weight of the equation residual against the boundary term (fixed at 10)."),
    ] = 1.0
    adam_steps: Annotated[int, Field(ge=0, description="Adam steps with fresh collocation points.")] = 3000
    lbfgs_rounds: Annotated[
        int, Field(ge=0, description="L-BFGS rounds (60 iterations each) on renewed fixed points.")
    ] = 15
    kappa: Annotated[
        float,
        Field(
            gt=0,
            description="Turbulent diffusivity over wind speed (m): K = kappa |u|. It enters the equation as "
            "eps = kappa / L, so each value needs its own network (the default is the bundled one).",
        ),
    ] = equation.KAPPA_M
    seed: int = 0  # the research seed of the network (the contract default, 7, would retrain it)
    tau_h: Annotated[
        float, Field(gt=0, description="Lifetime of NOx (h). 12 h is almost no loss within the domain.")
    ] = 12.0
    u_min: Annotated[float, Field(gt=0, description="Floor of the transport speed (m/s).")] = U_MIN
    kernel_dir: Annotated[
        str | None,
        Field(description="Folder where trained networks are cached on disk (none: only in memory)."),
    ] = None

    def training_key(self) -> str:
        """Hash of what determines the trained network: the name of its cache entry. It includes the equation
        constants, so a change to the physics does not reuse an old network."""
        physics = {name: getattr(equation, name) for name in EQUATION_CONSTANTS}
        physics["KAPPA_M"] = self.kappa  # the default gives the key of the bundled network
        text = json.dumps(
            {"params": self.model_dump(include=TRAINING_FIELDS), "physics": physics}, sort_keys=True
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class PinnPuffParams(PinnParams):
    """The PINN plume's hyperparameters plus the memory of the puffs. The network is the same (`max_age_h`
    does not enter the training key), so `pinn_puff` and `pinn_plume` share the bundled kernel."""

    max_age_h: Annotated[
        int, Field(ge=0, description="Hours a puff is followed (0: only the plume of the last hour).")
    ] = MAX_AGE_H
