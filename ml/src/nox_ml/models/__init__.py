"""Models and references behind one contract (``docs/models.md``). Register a class in `REGISTRY`."""

from nox_ml.models.base import Dataset, EmissionEstimate, Model, ModelParams
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.rf_deweather import RfDeweather

REGISTRY: dict[str, type[Model]] = {InversionPlume.name: InversionPlume, RfDeweather.name: RfDeweather}

try:
    from nox_ml.models.pinn.model import PinnPlume, PinnPuff
except ModuleNotFoundError as error:  # the PINN needs torch, an optional extra (`uv sync --extra pinn`)
    if error.name != "torch":
        raise
else:
    REGISTRY[PinnPlume.name] = PinnPlume
    REGISTRY[PinnPuff.name] = PinnPuff

__all__ = ["REGISTRY", "Dataset", "EmissionEstimate", "Model", "ModelParams"]
