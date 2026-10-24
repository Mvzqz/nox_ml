"""Recorta EDGAR v8.1 NOx (malla 0.1°, t/año por celda) a los dominios de CDMX, Los Ángeles y Bogotá.

Lee los zip de data/raw/edgar/zip/ (un sector y año por archivo) y escribe un NetCDF por ciudad y año en
data/raw/edgar/ con una variable por sector. Los zip globales se pueden borrar después.
"""
import glob
import re
import tempfile
import zipfile
from pathlib import Path

import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/edgar"
PAD = 0.1  # margen para que las celdas del borde queden completas
DOMINIOS = {
    "cdmx": (-99.35, 19.25, -98.81, 19.77),   # scripts/config.py
    "la": (-118.55, 33.80, -117.95, 34.30),   # scripts/la_common.py
    "bogota": (-74.25, 4.45, -73.98, 4.85),   # área urbana de Bogotá y Soacha
}


def main():
    datos = {}  # (ciudad, año) -> {sector: DataArray}
    for z in sorted(glob.glob(str(RAW / "zip/*.zip"))):
        m = re.search(r"NOx_(\d{4})_(.+)_emi_nc\.zip", z)
        anio, sector = m.group(1), m.group(2)
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(z) as zf:
            nc = [n for n in zf.namelist() if n.endswith(".nc")][0]
            zf.extract(nc, tmp)
            with xr.open_dataset(Path(tmp) / nc) as ds:
                da = ds["emissions"]
                for ciudad, (x0, y0, x1, y1) in DOMINIOS.items():
                    sub = da.sel(lat=slice(y0 - PAD, y1 + PAD), lon=slice(x0 - PAD, x1 + PAD)).load()
                    datos.setdefault((ciudad, anio), {})[sector] = sub.rename(sector)
    for (ciudad, anio), sectores in datos.items():
        ds = xr.Dataset(sectores)
        ds.attrs.update(fuente="EDGAR v8.1 (FT2022) contaminantes del aire, NOx, emi_nc",
                        unidades="t/año por celda de 0.1°", anio=anio,
                        url="https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/NOx/",
                        licencia="CC BY 4.0, (c) European Union 1995-2026")
        out = RAW / f"edgar_nox_{ciudad}_{anio}.nc"
        ds.to_netcdf(out)
        print(out.name, {k: round(float(v.sum()), 0) for k, v in sectores.items() if k in ("TOTALS", "TRO")})


if __name__ == "__main__":
    main()
