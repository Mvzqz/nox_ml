"""Models and references behind one contract (``docs/models.md``). Register a class in `REGISTRY`."""

from nox_ml.models.base import Dataset, EmissionEstimate, Model, ModelParams
from nox_ml.models.inversion_plume import InversionPlume

REGISTRY: dict[str, type[Model]] = {InversionPlume.name: InversionPlume}

__all__ = ["REGISTRY", "Dataset", "EmissionEstimate", "Model", "ModelParams"]
