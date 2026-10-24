"""P1: descarga TEMPO NO₂ L2 V04 sobre el dominio y guarda solo un recorte.

Cada granulo pesa ~150 MB y solo ~300 píxeles caen en el dominio, así que se descarga a un
temporal, se recorta (dominio + margen) con las variables que usa el POC y se borra el original.
El manifiesto guarda URL, hora de descarga y tamaño del original para poder re-descargarlo.

Requiere ~/.netrc con credenciales de Earthdata.
Uso: .venv/bin/python scripts/tempo_download.py 2023-11-01 2023-12-31 [--workers 4]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/tempo"
MANIFEST = OUT / "manifest.csv"
from config import BBOX
HDF5_LOCK = threading.Lock()  # netCDF4/HDF5 no es thread-safe
MARGIN = 0.1  # grados alrededor del dominio
UTC_HOURS = range(18, 24)  # 12:00–17:59 hora local (UTC−6)
KEEP = {
    "product": ["vertical_column_troposphere", "vertical_column_troposphere_uncertainty", "main_data_quality_flag"],
    "geolocation": ["latitude", "longitude", "latitude_bounds", "longitude_bounds", "time",
                    "solar_zenith_angle", "viewing_zenith_angle"],
    "support_data": ["eff_cloud_fraction", "amf_troposphere", "ground_pixel_quality_flag", "snow_ice_fraction",
                     "surface_pressure", "terrain_height"],
}


def granules(start, end):
    url = ("https://cmr.earthdata.nasa.gov/search/granules.json?short_name=TEMPO_NO2_L2&version=V04"
           f"&bounding_box={','.join(map(str, BBOX))}&temporal={start}T00:00:00Z,{end}T23:59:59Z&page_size=2000")
    with urllib.request.urlopen(url, timeout=120) as r:
        feed = json.load(r)["feed"]["entry"]
    if len(feed) == 2000:
        raise SystemExit("Más de 2000 granulos: divide el periodo")
    out = []
    for e in feed:
        t = datetime.fromisoformat(e["time_start"].replace("Z", "+00:00"))
        href = next(l["href"] for l in e["links"] if l["href"].startswith("https") and l["href"].endswith(".nc"))
        if t.hour in UTC_HOURS:
            out.append((t, href))
    return sorted(out)


def subset(src, dst):
    with netCDF4.Dataset(src) as ds:
        lat = ds["geolocation/latitude"][:].filled(np.nan)
        lon = ds["geolocation/longitude"][:].filled(np.nan)
        m = ((lat > BBOX[1] - MARGIN) & (lat < BBOX[3] + MARGIN) & (lon > BBOX[0] - MARGIN) & (lon < BBOX[2] + MARGIN))
        if not m.any():
            return 0
        r = np.where(m.any(1))[0]
        c = np.where(m.any(0))[0]
        rs, cs = slice(r[0], r[-1] + 1), slice(c[0], c[-1] + 1)
        with netCDF4.Dataset(dst, "w") as out:
            out.setncatts({k: ds.getncattr(k) for k in ds.ncattrs()})
            out.source_granule = Path(src).name
            out.subset_rows = f"{rs.start}:{rs.stop}"
            out.subset_cols = f"{cs.start}:{cs.stop}"
            out.createDimension("mirror_step", rs.stop - rs.start)
            out.createDimension("xtrack", cs.stop - cs.start)
            out.createDimension("corner", 4)
            for grp, names in KEEP.items():
                g = out.createGroup(grp)
                for n in names:
                    v = ds[f"{grp}/{n}"]
                    dims = {1: ("mirror_step",), 2: ("mirror_step", "xtrack"), 3: ("mirror_step", "xtrack", "corner")}[v.ndim]
                    fill = getattr(v, "_FillValue", None)
                    nv = g.createVariable(n, v.dtype, dims, zlib=True, complevel=4, fill_value=fill)
                    nv.setncatts({k: v.getncattr(k) for k in v.ncattrs() if k != "_FillValue"})
                    nv[:] = v[rs] if v.ndim == 1 else v[rs, cs]
        return int(m.sum())


def fetch(t, href):
    name = href.rsplit("/", 1)[1]
    dst = OUT / name.replace(".nc", "_zmvm.nc")
    if dst.exists():
        return None
    with tempfile.TemporaryDirectory(dir=OUT) as tmp:
        src = Path(tmp) / name
        t0 = time.time()
        cookies = str(Path.home() / ".urs_cookies")
        res = subprocess.run(["curl", "-sfL", "-n", "-c", cookies, "-b", cookies, "--retry", "3",
                              "-m", "1800", "-o", str(src), href], capture_output=True)
        if res.returncode != 0:
            return {"granule": name, "status": f"curl error {res.returncode}"}
        size = src.stat().st_size
        with HDF5_LOCK:
            npx = subset(src, dst.with_suffix(".part"))
        if npx:
            dst.with_suffix(".part").rename(dst)
        return {"granule": name, "time_utc": t.isoformat(), "url": href, "original_bytes": size,
                "pixels_with_margin": npx, "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "seconds": round(time.time() - t0), "status": "ok" if npx else "no pixels"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = granules(a.start, a.end)
    print(f"{len(todo)} granulos 18–23 UTC en {a.start}..{a.end}", flush=True)
    new = not MANIFEST.exists()
    fields = ["granule", "time_utc", "url", "original_bytes", "pixels_with_margin", "downloaded_utc", "seconds", "status"]
    with open(MANIFEST, "a", newline="") as fh, ThreadPoolExecutor(a.workers) as ex:
        w = csv.DictWriter(fh, fields)
        if new:
            w.writeheader()
        done = 0
        for f in as_completed([ex.submit(fetch, t, h) for t, h in todo]):
            done += 1
            row = f.result()
            if row:
                w.writerow(row)
                fh.flush()
                print(f"[{done}/{len(todo)}] {row['granule']} {row['status']} {row.get('seconds', '')}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
