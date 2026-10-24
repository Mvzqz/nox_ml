"""Tiny inline fixtures: SIMAT zips, TEMPO and MERRA-2 NetCDF files, written to `tmp_path`."""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false

import zipfile
from collections.abc import Callable
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import pytest

# station -> (lon, lat, mean NOX in ppb); both inside the domain
STATIONS = {"MER": (-99.12, 19.40, 50.0), "AJM": (-99.16, 19.27, 20.0)}
SIMAT_HEADER = "\n".join(['"city: Ciudad de M&eacute;xico","","","",""'] * 9)
CATALOG = "Catalogo de estaciones,,,,,,\ncve_estac,nom_estac,longitud,latitud,alt,obs_estac,id_station\n"
UNITS = (
    "id_unidad,clave_unidad,nombre_unidad\n1,ppb,partes por billón\n3,m/s,metros por segundo\n4,°,grados\n"
)


def simat_hours(start="2024-01-01 01:00", end="2024-01-15 00:00") -> pd.DatetimeIndex:
    """Hour-ending local stamps; the last hour of each day is 00:00 of the next day."""
    return pd.date_range(start, end, freq="h")


def nox_long(hours: pd.DatetimeIndex) -> pd.DataFrame:
    """Two weeks of NO, NO2, NOX: morning peak at 8 h, Sundays 40 % lower, MER > AJM."""
    rows = []
    for station, (_, _, base) in STATIONS.items():
        shape = 1 + 2 * np.exp(-(((hours.hour - 8) / 2.0) ** 2))
        nox = base * shape * np.where(hours.day_of_week == 6, 0.6, 1.0) + np.arange(len(hours)) * 1e-3
        for param, values in {"NO": nox / 2, "NO2": nox / 2, "NOX": nox}.items():
            rows.append(
                pd.DataFrame(
                    {"date": hours, "id_station": station, "id_parameter": param, "value": values, "unit": 1}
                )
            )
    return pd.concat(rows, ignore_index=True)


def wind_long(hours: pd.DatetimeIndex, wsp_label: float = 6.711) -> pd.DataFrame:
    """Constant easterly wind; 6.711 mph is 3 m/s."""
    rows = []
    for station in STATIONS:
        for param, value, unit in (("WSP", wsp_label, 3), ("WDR", 90.0, 4)):
            rows.append(
                pd.DataFrame(
                    {
                        "date": hours,
                        "id_station": station,
                        "id_parameter": param,
                        "value": value,
                        "unit": unit,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def write_simat_zip(path: Path, table: pd.DataFrame) -> None:
    """SIMAT serves a ZIP named `.csv.gz`: 9 header lines, then the column names on line 10."""
    csv = SIMAT_HEADER + "\n" + table.to_csv(index=False, date_format="%Y-%m-%d %H:%M:%S")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(path.name.removesuffix(".gz"), csv)


@pytest.fixture
def simat_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "simat"
    raw.mkdir()
    hours = simat_hours()
    write_simat_zip(raw / "contaminantes_2024.csv.gz", nox_long(hours))
    write_simat_zip(raw / "meteorologia_2024.csv.gz", wind_long(hours))
    rows = "".join(f"{s},{s} station,{lon},{lat},2240,,1\n" for s, (lon, lat, _) in STATIONS.items())
    (raw / "cat_estacion.csv").write_bytes(
        (CATALOG + rows + "TLH,Tláhuac,-99.0,20.9,2240,,1\n").encode("latin1")
    )
    (raw / "cat_unidades.csv").write_bytes(UNITS.encode("latin1"))
    return raw


@pytest.fixture
def write_tempo_granule() -> Callable[..., Path]:
    def write(path: Path, lat, lon, vcd, qf=0, cf=0.1, units="molecules/cm^2") -> Path:
        """One scanline of pixels; `vcd` entries that are NaN are written as masked (fill value)."""
        n = len(lat)
        with netCDF4.Dataset(path, "w") as ds:
            ds.createDimension("pix", n)
            groups = {
                "product": ds.createGroup("product"),
                "support": ds.createGroup("support_data"),
                "geo": ds.createGroup("geolocation"),
            }
            v = groups["product"].createVariable(
                "vertical_column_troposphere", "f8", ("pix",), fill_value=-9e30
            )
            v.units = units
            v[:] = np.ma.masked_invalid(np.asarray(vcd, dtype=float))
            q = groups["product"].createVariable("main_data_quality_flag", "i2", ("pix",), fill_value=-1)
            q[:] = np.ma.masked_equal(np.broadcast_to(np.asarray(qf), (n,)).astype("i2"), -1)
            for name, values in {"eff_cloud_fraction": cf, "snow_ice_fraction": 0.0}.items():
                c = groups["support"].createVariable(name, "f8", ("pix",), fill_value=-9e30)
                c[:] = np.broadcast_to(np.asarray(values, dtype=float), (n,))
            for name, values in {"latitude": lat, "longitude": lon}.items():
                g = groups["geo"].createVariable(name, "f8", ("pix",), fill_value=-9e30)
                g[:] = np.asarray(values, dtype=float)
        return path

    return write


@pytest.fixture
def write_merra_file() -> Callable[..., Path]:
    def write(path: Path, day: str, values: np.ndarray) -> Path:
        """One day of PBLH (24 hourly values, m) in the 3 x 3 cell layout; time is minutes since midnight."""
        with netCDF4.Dataset(path, "w") as ds:
            ds.createDimension("time", 24)
            ds.createDimension("lat", 3)
            ds.createDimension("lon", 3)
            t = ds.createVariable("time", "i4", ("time",))
            t.units = f"minutes since {day} 00:00:00"
            t[:] = np.arange(24) * 60 + 30
            p = ds.createVariable("PBLH", "f4", ("time", "lat", "lon"), fill_value=1e15)
            p[:] = np.broadcast_to(values[:, None, None], (24, 3, 3))
        return path

    return write
