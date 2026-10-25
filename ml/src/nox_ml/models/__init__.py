"""Models and references behind one contract (``docs/models.md``). Register a class in `REGISTRY`."""

from nox_ml.models.base import Dataset, EmissionEstimate, Model, ModelParams
from nox_ml.models.inversion_plume import InversionPlume

REGISTRY: dict[str, type[Model]] = {InversionPlume.name: InversionPlume}

try:
    from nox_ml.models.pinn.model import PinnPlume
except ModuleNotFoundError as error:  # the PINN needs torch, an optional extra (`uv sync --extra pinn`)
    if error.name != "torch":
        raise
else:
    REGISTRY[PinnPlume.name] = PinnPlume

__all__ = ["REGISTRY", "Dataset", "EmissionEstimate", "Model", "ModelParams"]
