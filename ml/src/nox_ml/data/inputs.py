# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Inputs of the baseline inversion, assembled from the interim tables.

Migrated from `load_inputs` (`scripts/feasibility_linear.py`) and `build` (`scripts/real_check_linear.py`,
research-archive), in the baseline configuration: stations with NOx only, the plain hourly mean of the
station winds for the whole domain, TEMPO pixels at the hour they are scanned.

Hours: only those with station NOx rows *and* wind *and* boundary layer height are kept, as the research did
(``hours = sorted(set(nox.h) & set(wind.index))``). That drops the TEMPO pixels of hours without station
rows. Time labels: SIMAT stamps the end of the hour (local), so the start of the hour in UTC is ``utc - 1 h``.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from nox_ml.data.pbl import ERA5_FILE, parse_era5
from nox_ml.data.roads import N_SPLIT, UTM, read_roads, road_emission_cells
from nox_ml.inversion.jacobian import Receptors
from nox_ml.inversion.linear import HourData, baseline_point_sources

MIN_PBL_M = 200.0  # floor of the boundary layer height after averaging with the next hour
LABEL_SHIFT = pd.Timedelta(hours=1)  # SIMAT labels the end of the hour


@dataclass(frozen=True)
class Inputs:
    """Everything the baseline inversion needs, ready to run.

    `hours` and `station_ids` are aligned: ``station_ids[k][i]`` is the station of the ``i``-th station row of
    ``hours[k]``. `zones` and `points` are the road cells and the point sources as `invert` takes them.
    """

    hours: list[HourData]
    station_ids: list[np.ndarray]
    station_xy: pd.DataFrame  # index: station id; columns x, y (UTM 14N, m)
    zones: pd.DataFrame
    points: pd.DataFrame
    no2_nox_ratio: float
    n_regions: int  # road regions of `zones`, passed explicitly to `invert`

    @property
    def n_station_rows(self) -> int:
        return sum(len(ids) for ids in self.station_ids)

    @property
    def n_pixels(self) -> int:
        return sum(len(h.no2) for h in self.hours)

    def without_station(self, station: str) -> list[HourData]:
        """The hours with the rows of `station` removed: for leave-one-out, before the system is built."""
        out = []
        for hour, ids in zip(self.hours, self.station_ids, strict=True):
            keep = ids != station
            stations = Receptors(hour.stations.x[keep], hour.stations.y[keep])
            out.append(replace(hour, stations=stations, nox=hour.nox[keep]))
        return out


# --- Pure functions ----------------------------------------------------------------------------------------


def station_nox(
    nox: pd.DataFrame, stations: Sequence[str], start: str, end: str, local_hours: tuple[int, int]
) -> tuple[pd.DataFrame, float]:
    """NOx rows of the stations in the window, with ``h`` (start of the hour, UTC), and the NO2/NOx ratio.

    The window is the local days ``start`` to ``end`` and the SIMAT hour labels ``local_hours`` (inclusive).
    The ratio is the sum of NO2 over the sum of NOx of the rows that have both, before dropping the rows
    without NOx.
    """
    rows = nox[
        nox["local"].between(start, f"{end} 23:59")
        & nox["hour"].between(*local_hours)
        & nox["id_station"].isin(stations)
    ]
    both = rows[rows["NOX"].notna() & rows["NO2"].notna()]
    ratio = float(both["NO2"].sum() / both["NOX"].sum())
    rows = rows[rows["NOX"].notna()].copy()
    rows["h"] = rows["utc"] - LABEL_SHIFT
    return rows, ratio


def domain_wind(wind: pd.DataFrame, stations: Sequence[str]) -> pd.DataFrame:
    """Plain hourly mean of the station winds (``u``, ``v`` in m/s, blowing towards), indexed by ``h``.

    `wind` has SIMAT ``WSP`` (m/s) and ``WDR`` (degrees, from); rows without either are dropped.
    """
    w = wind[wind["id_station"].isin(stations)].dropna(subset=["WSP", "WDR"])
    direction = np.deg2rad(w["WDR"])
    u, v = -w["WSP"] * np.sin(direction), -w["WSP"] * np.cos(direction)
    return pd.DataFrame({"h": w["utc"] - LABEL_SHIFT, "u": u, "v": v}).groupby("h")[["u", "v"]].mean()


def hourly_pbl(filled: pd.Series, era5: pd.Series) -> pd.Series:
    """Boundary layer height (m) of each hour: the filled ERA5 + MERRA-2 series, then ERA5, then the
    month-hour median for what is left; averaged with the next hour and floored at `MIN_PBL_M`."""
    pbl = filled.combine_first(era5)
    median = pbl.groupby([pbl.index.month, pbl.index.hour]).median()
    gap = pbl.isna()
    keys = pd.MultiIndex.from_arrays([pbl.index[gap].month, pbl.index[gap].hour])
    pbl[gap] = median.reindex(keys).to_numpy()
    return ((pbl + pbl.shift(-1)) / 2).clip(lower=MIN_PBL_M)


def assemble(
    nox: pd.DataFrame,
    wind: pd.DataFrame,
    pbl: pd.Series,
    pixels: pd.DataFrame,
    station_xy: pd.DataFrame,
) -> tuple[list[HourData], list[np.ndarray]]:
    """`HourData` of the hours that have station rows, wind and boundary layer height, and the station ids
    of their rows. `nox` and `pixels` carry ``h``; `pixels` also ``x``, ``y``, ``vcd``."""
    hours = [h for h in sorted(set(nox["h"]) & set(wind.index)) if h in pbl.index]
    by_hour = dict(tuple(nox.groupby("h")))
    pixels_by_hour: dict[Any, pd.DataFrame] = dict(tuple(pixels.groupby("h")))
    empty: pd.DataFrame = pixels.iloc[:0]
    data, ids = [], []
    for h in hours:
        rows = by_hour[h]
        xy = station_xy.loc[rows["id_station"].to_numpy()]
        px = pixels_by_hour.get(h, empty)
        u, v = wind.loc[h, ["u", "v"]]
        data.append(
            HourData(
                hour=h,
                wind=(float(u), float(v)),
                pbl=float(pbl.loc[h]),
                stations=Receptors(xy["x"].to_numpy(float), xy["y"].to_numpy(float)),
                nox=rows["NOX"].to_numpy(float),
                pixels=Receptors(px["x"].to_numpy(float), px["y"].to_numpy(float)),
                no2=px["vcd"].to_numpy(float),
            )
        )
        ids.append(rows["id_station"].to_numpy())
    return data, ids


# --- I/O ---------------------------------------------------------------------------------------------------


def load_pixels(path: Path) -> pd.DataFrame:
    """Valid TEMPO pixels (`nox-ml qc-tempo`) with UTM position ``x``, ``y`` and scan hour ``h``."""
    px = pd.read_parquet(path)
    px = px[px["valid"]].copy()
    xy = gpd.GeoSeries.from_xy(px["lon"], px["lat"], crs=4326).to_crs(UTM)
    px["x"], px["y"], px["h"] = xy.x.to_numpy(), xy.y.to_numpy(), px["utc"].dt.floor("h")
    return px


def load_inputs(data_dir: Path, start: str, end: str, local_hours: tuple[int, int] = (12, 17)) -> Inputs:
    """The inputs of the baseline inversion for the local days ``start`` to ``end`` from `data_dir`
    (``interim/`` for the tables of `qc-simat`, `qc-tempo` and `fill-pbl`, ``raw/`` for ERA5)."""
    interim = data_dir / "interim"
    catalog = gpd.read_file(interim / "estaciones.gpkg").to_crs(UTM).set_index("cve_estac")
    station_xy = pd.DataFrame({"x": catalog.geometry.x, "y": catalog.geometry.y})
    ids = list(station_xy.index)

    nox, ratio = station_nox(pd.read_parquet(interim / "simat_nox.parquet"), ids, start, end, local_hours)
    wind = domain_wind(pd.read_parquet(interim / "simat_wind.parquet"), ids)
    era5 = parse_era5(json.loads((data_dir / "raw" / "era5_openmeteo" / ERA5_FILE).read_text()))
    pbl = hourly_pbl(pd.read_parquet(interim / "pbl_2023_2024.parquet")["pbl_m"], era5)
    pixels = load_pixels(interim / f"tempo_pixels_{start}_{end}.parquet")

    hours, station_ids = assemble(nox, wind, pbl, pixels, station_xy)
    zones = road_emission_cells(read_roads(interim / "roads.gpkg"))
    return Inputs(hours, station_ids, station_xy, zones, baseline_point_sources(), ratio, N_SPLIT**2)
