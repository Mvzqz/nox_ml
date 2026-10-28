"""Models and references behind one contract (``docs/models.md``). Register a class in `REGISTRY`."""

from nox_ml.models.base import Dataset, EmissionEstimate, Model, ModelParams
from nox_ml.models.ensemble import ConvexEnsemble
from nox_ml.models.gb_deweather import GbDeweather
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.inversion_puff import InversionPuff
from nox_ml.models.lognormal_map import LognormalMap
from nox_ml.models.normalized_ratio import NormalizedRatio
from nox_ml.models.references import Idw, Kriging
from nox_ml.models.regularized_ls import RegularizedLs
from nox_ml.models.rf_deweather import RfDeweather

REGISTRY: dict[str, type[Model]] = {
    ConvexEnsemble.name: ConvexEnsemble,
    GbDeweather.name: GbDeweather,
    InversionPlume.name: InversionPlume,
    InversionPuff.name: InversionPuff,
    RfDeweather.name: RfDeweather,
    NormalizedRatio.name: NormalizedRatio,
    RegularizedLs.name: RegularizedLs,
    LognormalMap.name: LognormalMap,
    Idw.name: Idw,
    Kriging.name: Kriging,
}

try:
    from nox_ml.models.pinn.model import PinnPlume, PinnPuff
    from nox_ml.models.pinn.seeds import PinnSeeds
except ModuleNotFoundError as error:  # the PINN needs torch, an optional extra (`uv sync --extra pinn`)
    if error.name != "torch":
        raise
else:
    REGISTRY[PinnPlume.name] = PinnPlume
    REGISTRY[PinnPuff.name] = PinnPuff
    REGISTRY[PinnSeeds.name] = PinnSeeds

__all__ = ["REGISTRY", "Dataset", "EmissionEstimate", "Model", "ModelParams"]
