"""Road-emission proxy: OSM road length weighted by class, on the 1 km UTM 14N grid of the domain."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from nox_ml.data.domain import BBOX

UTM = "EPSG:32614"
CELL_M = 1000  # grid cell size
SAMPLE_M = 100  # segments are cut into pieces of about this length before binning
N_SPLIT = 3  # regions: the domain is split N_SPLIT x N_SPLIT

# Relative emission per metre of road, by OSM `highway` class (`*_link` counts as its class).
# Any other class weighs 1.
ROAD_WEIGHT = {"motorway": 3, "trunk": 3, "primary": 2, "secondary": 1.5, "tertiary": 1}

MOBILE_ZMVM = 124_115  # t/yr, vehicular NOx of the whole ZMVM (2018 inventory)
DOMAIN_SHARE = 0.8  # assumption: ~80 % of it falls inside the domain
ROAD_PRIOR_TOTAL = DOMAIN_SHARE * MOBILE_ZMVM  # 99,292 t/yr


def domain_bounds_utm() -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of the domain bounding box in UTM 14N metres."""
    lon0, lat0, lon1, lat1 = BBOX
    corners = gpd.GeoSeries.from_xy([lon0, lon1], [lat0, lat1], crs=4326).to_crs(UTM)
    (x0, x1), (y0, y1) = corners.x.to_numpy(), corners.y.to_numpy()
    return float(x0), float(y0), float(x1), float(y1)


def read_roads(path: Path) -> gpd.GeoDataFrame:
    """OSM roads (`data/interim/roads.gpkg`): `highway` class and line geometry in UTM 14N."""
    return gpd.read_file(path)


def class_weight(highway: pd.Series) -> pd.Series:
    """Weight of each OSM `highway` value (`_link` stripped; unlisted classes weigh 1)."""
    return highway.str.replace("_link", "").map(ROAD_WEIGHT).fillna(1.0).astype(float)


def road_emission_cells(
    roads: gpd.GeoDataFrame,
    total: float = ROAD_PRIOR_TOTAL,
    bounds: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    """Prior road emission per 1 km cell, with the cell's region.

    Each segment contributes ``length x class weight``, cut into ~100 m pieces that are binned by
    their midpoint (pieces outside ``bounds`` are dropped). The cell sums are scaled so that they add
    up to ``total`` t/yr. Regions are the 3x3 split of the domain: 0 = SW, 1 = S, 2 = SE ... 8 = NE.

    ``roads`` must be in UTM 14N metres. Returns columns ``x``, ``y`` (cell centre, UTM metres),
    ``weight`` (t/yr) and ``region`` (int 0-8), only for cells with road, sorted by cell.
    """
    x0, y0, x1, y1 = bounds or domain_bounds_utm()
    geoms = roads.geometry.to_numpy()
    weights = class_weight(pd.Series(roads["highway"])).to_numpy()
    lengths = shapely.length(geoms)

    pieces = np.maximum((lengths // SAMPLE_M).astype(int), 1)
    seg = np.repeat(np.arange(len(geoms)), pieces)
    k = np.arange(len(seg)) - np.repeat(np.cumsum(pieces) - pieces, pieces)
    step = lengths[seg] / pieces[seg]
    mid = shapely.line_interpolate_point(geoms[seg], (k + 0.5) * step)
    px, py = shapely.get_x(mid), shapely.get_y(mid)
    pw = weights[seg] * step

    inside = (px >= x0) & (px < x1) & (py >= y0) & (py < y1)
    ix = ((px[inside] - x0) // CELL_M).astype(int)
    iy = ((py[inside] - y0) // CELL_M).astype(int)
    cells = pd.DataFrame({"ix": ix, "iy": iy, "weight": pw[inside]}).groupby(["ix", "iy"]).weight.sum()
    cells = cells.reset_index()

    nx, ny = int((x1 - x0) // CELL_M) + 1, int((y1 - y0) // CELL_M) + 1
    region = cells.ix * N_SPLIT // nx + N_SPLIT * (cells.iy * N_SPLIT // ny)
    return pd.DataFrame(
        {
            "x": x0 + CELL_M / 2 + CELL_M * cells.ix,
            "y": y0 + CELL_M / 2 + CELL_M * cells.iy,
            "weight": cells.weight / cells.weight.sum() * total,
            "region": region.astype(int),
        }
    )
