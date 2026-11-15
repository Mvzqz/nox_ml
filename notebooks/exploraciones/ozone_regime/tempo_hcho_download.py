"""Download TEMPO HCHO L2 V04 over the domain, already cut, through NASA's OPeNDAP (Hyrax) server.

Same cut and hours as the NO2 granules of `data/raw/tempo/` (domain + 0.1 deg, 18-22 UTC = 12-16 h local):
the rows and columns of each scan are taken from the NO2 granule of the same scan (`subset_rows`,
`subset_cols`); without one, from the granule's own latitude and longitude. Only the variables needed for
HCHO/NO2 are kept. Needs Earthdata credentials in ~/.netrc (curl -n; never printed).

Usage: uv run python notebooks/exploraciones/ozone_regime/tempo_hcho_download.py 2024-02-01 2024-05-31
"""

import argparse
import csv
import json
import subprocess
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import netCDF4
import numpy as np

from nox_ml.data import tempo

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "raw" / "tempo_hcho"
NO2_DIR = ROOT / "data" / "raw" / "tempo"
MANIFEST = OUT / "manifest.csv"
BBOX = tempo.BBOX
MARGIN = tempo.MARGIN_DEG
UTC_HOURS = range(18, 23)  # inside tempo.SCAN_HOURS_UTC: the 12-16 h local formation hours
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/C3685912035-LARC_CLOUD/granules"  # HCHO L2 V04
VARS_2D = (
    "product/vertical_column",
    "product/vertical_column_uncertainty",
    "product/main_data_quality_flag",
    "geolocation/latitude",
    "geolocation/longitude",
    "geolocation/solar_zenith_angle",
    "support_data/eff_cloud_fraction",
    "support_data/amf",
)
COOKIES = str(Path.home() / ".urs_cookies")
HDF5_LOCK = threading.Lock()  # netCDF4/HDF5 is not thread-safe


def granules(start: str, end: str) -> list[tuple[datetime, str]]:
    """OPeNDAP URLs of the afternoon HCHO granules, with the CMR month windows and the scan-hour filter of
    `nox_ml.data.tempo` (the NO2 search with the HCHO collection)."""
    found = []
    for first, last in tempo.month_windows(start, end):
        url = tempo.cmr_url(first, last).replace("short_name=TEMPO_NO2_L2", "short_name=TEMPO_HCHO_L2")
        with urllib.request.urlopen(url, timeout=120) as r:
            entries = json.load(r)["feed"]["entry"]
        if len(entries) >= tempo.CMR_PAGE:
            raise SystemExit(f"CMR returned {len(entries)} granules for {first}..{last}")
        for t, href in tempo.afternoon_granules(entries):
            if t.hour in UTC_HOURS:
                found.append((t.to_pydatetime(), f"{OPENDAP}/{href.rsplit('/', 1)[1]}"))
    return sorted(found)


def curl(url: str, dst: Path, ce: str) -> int:
    cmd = [
        "curl",
        "-sfL",
        "-n",
        "-c",
        COOKIES,
        "-b",
        COOKIES,
        "--retry",
        "4",
        "-m",
        "600",
        "-o",
        str(dst),
        "-G",
    ]
    return subprocess.run(
        [*cmd, url + ".dap.nc4", "--data-urlencode", f"dap4.ce={ce}"], check=False
    ).returncode


def window(name: str, href: str, tmp: Path) -> tuple[slice, slice] | None:
    """Rows and columns of the domain: from the NO2 granule of the same scan, or from the geolocation."""
    no2 = NO2_DIR / name.replace("HCHO", "NO2").replace(".nc", "_zmvm.nc")
    if no2.exists():
        with HDF5_LOCK, netCDF4.Dataset(no2) as ds:
            r0, r1 = map(int, ds.subset_rows.split(":"))
            c0, c1 = map(int, ds.subset_cols.split(":"))
        return slice(r0, r1), slice(c0, c1)
    geo = tmp / "geo.nc4"
    if curl(href, geo, "/geolocation/latitude;/geolocation/longitude") != 0:
        return None
    with HDF5_LOCK, netCDF4.Dataset(geo) as ds:
        lat = ds["geolocation/latitude"][:].filled(np.nan)
        lon = ds["geolocation/longitude"][:].filled(np.nan)
    m = (
        (lat > BBOX[1] - MARGIN)
        & (lat < BBOX[3] + MARGIN)
        & (lon > BBOX[0] - MARGIN)
        & (lon < BBOX[2] + MARGIN)
    )
    if not m.any():
        return None
    r, c = np.where(m.any(1))[0], np.where(m.any(0))[0]
    return slice(r[0], r[-1] + 1), slice(c[0], c[-1] + 1)


def fetch(t: datetime, href: str) -> dict | None:
    name = href.rsplit("/", 1)[1]
    dst = OUT / tempo.subset_name(href)
    if dst.exists():
        return None
    t0 = time.time()
    with tempfile.TemporaryDirectory(dir=OUT) as tmp:
        win = window(name, href, Path(tmp))
        if win is None:
            return {"granule": name, "time_utc": t.isoformat(), "url": href, "status": "no pixels"}
        rs, cs = win
        sel = f"[{rs.start}:1:{rs.stop - 1}][{cs.start}:1:{cs.stop - 1}]"
        ce = ";".join([f"/{v}{sel}" for v in VARS_2D] + [f"/geolocation/time[{rs.start}:1:{rs.stop - 1}]"])
        part = Path(tmp) / "cut.nc4"
        code = curl(href, part, ce)
        if code != 0:
            return {"granule": name, "time_utc": t.isoformat(), "url": href, "status": f"curl error {code}"}
        part.rename(dst)
    return {
        "granule": name,
        "time_utc": t.isoformat(),
        "url": href,
        "rows": f"{rs.start}:{rs.stop}",
        "cols": f"{cs.start}:{cs.stop}",
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - t0),
        "status": "ok",
    }


def safe_fetch(t: datetime, href: str) -> dict | None:
    try:
        return fetch(t, href)
    except Exception as e:  # one bad granule must not stop the rest
        return {
            "granule": href.rsplit("/", 1)[1],
            "time_utc": t.isoformat(),
            "url": href,
            "status": f"error {e}",
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = granules(a.start, a.end)
    print(f"{len(todo)} granules 18-22 UTC in {a.start}..{a.end}", flush=True)
    fields = ["granule", "time_utc", "url", "rows", "cols", "downloaded_utc", "seconds", "status"]
    new = not MANIFEST.exists()
    with open(MANIFEST, "a", newline="") as f, ThreadPoolExecutor(a.workers) as pool:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        for i, row in enumerate(pool.map(lambda x: safe_fetch(*x), todo)):
            if row:
                w.writerow(row)
                f.flush()
            if i % 50 == 0:
                print(i, row and row["status"], flush=True)


if __name__ == "__main__":
    main()
