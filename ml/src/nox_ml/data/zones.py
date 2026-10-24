"""Road zones: the groups of boroughs and municipalities that share one emission factor.

Migrated from `assign_regions` in `scripts/feasibility_linear.py` (research-archive). The standard scheme is
`admin_grupos` (`data/interim/zonas_admin.gpkg`, one layer per scheme; the row order of a layer is the zone
index).
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from numpy.typing import NDArray

STANDARD_SCHEME = "admin_grupos"


def read_zones(path: Path, scheme: str = STANDARD_SCHEME) -> gpd.GeoDataFrame:
    """Zone polygons of a scheme, in the order of their indices."""
    return gpd.GeoDataFrame(gpd.read_file(path, layer=scheme).reset_index(drop=True))


def assign_zones(x: NDArray[np.float64], y: NDArray[np.float64], zones: gpd.GeoDataFrame) -> NDArray[np.int_]:
    """Zone index of each point (same projection as `zones`). Points outside every polygon (the edges of the
    domain) go to the nearest zone."""
    points = gpd.GeoDataFrame(geometry=gpd.GeoSeries.from_xy(x, y, crs=zones.crs))
    joined = gpd.sjoin_nearest(points, gpd.GeoDataFrame(geometry=zones.geometry), how="left")
    zone = pd.Series(joined["index_right"].to_numpy(), index=joined.index)
    return (
        zone.loc[~zone.index.duplicated()].reindex(points.index).to_numpy(dtype=int)
    )  # a tie keeps the first
