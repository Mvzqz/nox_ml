# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""TEMPO tropospheric NO2 (L2, V04) subsets over the study domain.

Each granule is a small NetCDF subset (`TEMPO_NO2_L2_V04_<yyyymmddThhmmssZ>_<scan>_zmvm.nc`). Pixels are valid
when the main quality flag is 0, the effective cloud fraction is below 0.2 and the column is not missing.

Pure functions parse names, filter pixels and compute checks; the I/O layer at the end reads NetCDF files and
parquet tables. `fetch_window` downloads the granules of a window from NASA (CMR search, Earthdata
download with the credentials of ``~/.netrc``) and keeps only the subset over the domain.
"""

import csv
import json
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nox_ml.data.domain import BBOX, CORE_LAT, CORE_LON, LAT, LON
from nox_ml.data.qc import Check
from nox_ml.data.weather import http_get
from nox_ml.time import utc_to_local

MAX_CLOUD_FRACTION = 0.2
MATCH_KM = 3.0  # max distance between a station and the pixel paired with it
KM_PER_DEG = 111.32
EXPECTED_UNITS = "molecules/cm^2"
GRANULE_GLOB = "TEMPO_NO2_L2_V04_*_zmvm.nc"

# NetCDF variable -> column
VARIABLES = {
    "vcd": "product/vertical_column_troposphere",
    "qf": "product/main_data_quality_flag",
    "cf": "support_data/eff_cloud_fraction",
    "lat": "geolocation/latitude",
    "lon": "geolocation/longitude",
    "snow": "support_data/snow_ice_fraction",
}
FILL = {"qf": 255}  # masked values default to NaN, except the quality flag (255 = no data)

# Download
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
CMR_PAGE = 2000  # a query that returns this many entries may have been cut: it is split by month
SCAN_HOURS_UTC = range(18, 24)  # 12:00-17:59 local (UTC-6), the afternoon scans the project uses
MARGIN_DEG = 0.1  # around the domain, kept in the subset
MANIFEST = "manifest.csv"
MANIFEST_FIELDS = (
    "granule",
    "time_utc",
    "url",
    "original_bytes",
    "pixels_with_margin",
    "downloaded_utc",
    "seconds",
    "status",
)
DONE_STATUSES = ("ok", "no pixels")  # a granule with another status (a failed download) is tried again
DOWNLOAD_TIMEOUT_S = 1800
# variables kept in the subset, by NetCDF group
KEEP = {
    "product": [
        "vertical_column_troposphere",
        "vertical_column_troposphere_uncertainty",
        "main_data_quality_flag",
    ],
    "geolocation": [
        "latitude",
        "longitude",
        "latitude_bounds",
        "longitude_bounds",
        "time",
        "solar_zenith_angle",
        "viewing_zenith_angle",
    ],
    "support_data": [
        "eff_cloud_fraction",
        "amf_troposphere",
        "ground_pixel_quality_flag",
        "snow_ice_fraction",
        "surface_pressure",
        "terrain_height",
    ],
}  # fmt: skip
HDF5_LOCK = threading.Lock()  # netCDF4 / HDF5 are not thread-safe

Getter = Callable[[str], bytes]
Downloader = Callable[[str, Path], None]


# --- Pure functions ----------------------------------------------------------------------------------------


def granule_time(name: str) -> pd.Timestamp:
    """Scan start (naive UTC) from a granule file name."""
    return pd.to_datetime(name.split("_")[4], format="%Y%m%dT%H%M%SZ")


def in_period(t: pd.Timestamp, start: str, end: str) -> bool:
    """True when `t` is on or after `start` and before the end of the day `end` (both inclusive dates)."""
    return pd.Timestamp(start) <= t < pd.Timestamp(end) + pd.Timedelta(days=1)


def month_windows(start: str, end: str) -> list[tuple[str, str]]:
    """The calendar months that `start` to `end` (inclusive dates) touch, as (first day, last day) pairs cut
    to the window."""
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    windows = []
    for month in pd.period_range(first, last, freq="M"):
        windows.append(
            (max(first, month.start_time).date().isoformat(), min(last, month.end_time).date().isoformat())
        )
    return windows


def cmr_url(start: str, end: str) -> str:
    """The CMR search of the TEMPO NO2 L2 V04 granules over the domain scanned from `start` to `end`
    (inclusive dates, UTC)."""
    return (
        f"{CMR}?short_name=TEMPO_NO2_L2&version=V04&bounding_box={','.join(map(str, BBOX))}"
        f"&temporal={start}T00:00:00Z,{end}T23:59:59Z&page_size={CMR_PAGE}"
    )


def afternoon_granules(entries: list[dict[str, Any]]) -> list[tuple[pd.Timestamp, str]]:
    """(scan start, download URL) of the CMR entries scanned in `SCAN_HOURS_UTC`, in order. Entries with no
    https NetCDF link are left out."""
    out = []
    for entry in entries:
        t = pd.Timestamp(entry["time_start"]).tz_convert("UTC").tz_localize(None)
        hrefs = [
            x["href"] for x in entry["links"] if x["href"].startswith("https") and x["href"].endswith(".nc")
        ]
        if hrefs and t.hour in SCAN_HOURS_UTC:
            out.append((t, hrefs[0]))
    return sorted(out)


def list_granules(start: str, end: str, get: Getter = http_get) -> list[tuple[pd.Timestamp, str]]:
    """The afternoon granules of `start` to `end` (inclusive dates), asking CMR one month at a time."""
    found = []
    for first, last in month_windows(start, end):
        entries = json.loads(get(cmr_url(first, last)))["feed"]["entry"]
        if len(entries) >= CMR_PAGE:
            raise RuntimeError(
                f"CMR returned {len(entries)} granules for {first} to {last}: split the window"
            )
        found += afternoon_granules(entries)
    return sorted(found)


def subset_name(href: str) -> str:
    """File name of the subset of the granule at `href`."""
    return href.rsplit("/", 1)[1].replace(".nc", "_zmvm.nc")


def clean_pixels(px: pd.DataFrame) -> pd.DataFrame:
    """Keep pixels inside the domain; add `valid` and `local` (UTC-6) time."""
    px = px[px["lat"].between(*LAT) & px["lon"].between(*LON)].copy()
    px["valid"] = (px["qf"] == 0) & (px["cf"] < MAX_CLOUD_FRACTION) & px["vcd"].notna()
    px["local"] = utc_to_local(px["utc"])
    return px


def _in_core(px: pd.DataFrame) -> pd.Series:
    return px["lat"].between(*CORE_LAT) & px["lon"].between(*CORE_LON)


def pixel_checks(px: pd.DataFrame) -> list[Check]:
    """QC of cleaned pixels (output of `clean_pixels`, with a `units` column)."""
    checks = [
        Check(
            None,
            f"Granules: {px['granule'].nunique()}; days: {px['utc'].dt.date.nunique()}; "
            f"domain pixels per granule: median {px.groupby('granule').size().median():.0f}",
        )
    ]
    units = list(px["units"].unique())
    checks.append(Check(units == [EXPECTED_UNITS], f"Units: {units}"))

    valid = px[px["valid"]]
    core = valid[_in_core(valid)]
    median_core = core["vcd"].median()
    checks.append(
        Check(
            bool(1e15 <= median_core <= 3e16),
            f"Median tropospheric VCD in the urban core: {median_core:.2e} (target 1e15-3e16)",
        )
    )

    frac = px.groupby("granule")["valid"].mean()
    good = frac >= 0.5
    checks.append(
        Check(
            bool(good.mean() > 0.5),
            f"Granules with >= 50 % of the domain valid: {good.mean():.0%} ({good.sum()} of {len(frac)})",
        )
    )
    checks.append(
        Check(
            None,
            f"Rejected pixels: flag != 0 {(px['qf'] != 0).mean():.0%}, "
            f"clouds >= {MAX_CLOUD_FRACTION} {(px['cf'] >= MAX_CLOUD_FRACTION).mean():.0%}",
        )
    )
    by_day = px.groupby(px["local"].dt.date)["valid"].mean()
    checks.append(
        Check(
            None, f"Days with >= 50 % valid pixels in the afternoon: {(by_day >= 0.5).sum()} of {len(by_day)}"
        )
    )

    surroundings = valid[~_in_core(valid)]
    ratio = core["vcd"].mean() / surroundings["vcd"].mean()
    checks.append(
        Check(
            bool(ratio > 1.2),
            f"Core / surroundings: {ratio:.2f}x "
            f"({core['vcd'].mean():.2e} vs {surroundings['vcd'].mean():.2e})",
        )
    )
    return checks


def match_stations(valid: pd.DataFrame, no2: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """Pair each station NO2 hour with the nearest valid TEMPO pixel (within `MATCH_KM`) of the same hour.

    `valid`: valid pixels (`granule`, `utc`, `lat`, `lon`, `vcd`). `no2`: `id_station`, `utc`, `NO2`.
    `stations`: `station`, `lon`, `lat`. SIMAT stamps the hour at the end of the period, so a scan at
    13:xx UTC is compared with the station value stamped 14:00.
    Returns `granule`, `station`, `no2_ppb`, `vcd`.
    """
    xy = stations.set_index("station")[["lon", "lat"]]
    no2 = no2[no2["id_station"].isin(xy.index) & no2["NO2"].notna()]
    obs_by_hour = {t: g for t, g in no2.groupby("utc")}
    km_per_deg_lon = KM_PER_DEG * np.cos(np.deg2rad(19.45))
    rows = []
    hour = valid["utc"].dt.floor("h")
    for (granule, hr), px in valid.groupby(["granule", hour]):
        obs = obs_by_hour.get(hr + pd.Timedelta(hours=1))
        if obs is None:
            continue
        for o in obs.itertuples():
            lon, lat = xy.loc[o.id_station, "lon"], xy.loc[o.id_station, "lat"]
            d = np.hypot((px["lon"] - lon) * km_per_deg_lon, (px["lat"] - lat) * KM_PER_DEG).to_numpy()
            if d.min() <= MATCH_KM:
                rows.append((granule, o.id_station, o.NO2, px["vcd"].to_numpy()[d.argmin()]))
    return pd.DataFrame(rows, columns=["granule", "station", "no2_ppb", "vcd"])


def pair_checks(pairs: pd.DataFrame) -> list[Check]:
    """Correlation between TEMPO columns and station NO2 (all pairs, within granule, station means)."""
    if pairs.empty:
        return [Check(False, "No station-pixel pairs")]
    r_all = pairs["no2_ppb"].corr(pairs["vcd"])
    per_granule = [g["no2_ppb"].corr(g["vcd"]) for _, g in pairs.groupby("granule") if len(g) >= 5]
    r_granule = pd.Series(per_granule).dropna()
    by_station = pairs.groupby("station")[["no2_ppb", "vcd"]].mean()
    r_station = by_station["no2_ppb"].corr(by_station["vcd"])
    return [
        Check(bool(r_all > 0), f"TEMPO vs station NO2 (hour-station pairs, n={len(pairs)}): r = {r_all:.2f}"),
        Check(
            None,
            f"Spatial correlation within granule: median r = {r_granule.median():.2f} "
            f"({len(r_granule)} granules with >= 5 stations)",
        ),
        Check(None, f"Correlation of station means ({len(by_station)} stations): r = {r_station:.2f}"),
    ]


# --- I/O ---------------------------------------------------------------------------------------------------


def read_granule(path: Path) -> pd.DataFrame:
    """One pixel per row, with `granule`, `utc` and `units` columns."""
    import netCDF4

    with netCDF4.Dataset(path) as ds:
        units = ds[VARIABLES["vcd"]].units
        cols = {col: ds[var][:].filled(FILL.get(col, np.nan)).ravel() for col, var in VARIABLES.items()}
    df = pd.DataFrame(cols)
    df["granule"], df["utc"], df["units"] = path.name, granule_time(path.name), units
    return df


def load_pixels(raw_dir: Path, start: str, end: str) -> pd.DataFrame:
    """Cleaned pixels of every granule scanned between the dates `start` and `end` (inclusive)."""
    files = [f for f in sorted(raw_dir.glob(GRANULE_GLOB)) if in_period(granule_time(f.name), start, end)]
    if not files:
        raise FileNotFoundError(f"No TEMPO granules between {start} and {end} in {raw_dir}")
    return clean_pixels(pd.concat([read_granule(f) for f in files], ignore_index=True))


def run_qc(
    raw_dir: Path,
    out_dir: Path,
    catalog: pd.DataFrame,
    start: str,
    end: str,
    stations_file: str = "simat_nox.parquet",
    table_end: str | None = None,
) -> list[Check]:
    """Check TEMPO pixels and write `tempo_pixels_<start>_<end>.parquet` to `out_dir`.

    With `table_end` the table is named by it instead of `end`: a season that is still running keeps the
    name of its full window (`nox-ml update`).

    The station comparison needs the station table `stations_file` in `out_dir` (`simat_nox.parquet` from
    `nox-ml qc-simat`, or an OpenAQ table from `nox-ml fetch-openaq` after 2024) and the SIMAT catalog for
    station coordinates.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    px = load_pixels(raw_dir, start, end)
    checks = [Check(None, f"TEMPO NO2 L2 V04, {start} to {end}"), *pixel_checks(px)]

    no2 = pd.read_parquet(out_dir / stations_file, columns=["id_station", "utc", "NO2"])
    stations = catalog[catalog["in_domain"]]
    checks += pair_checks(match_stations(px[px["valid"]], no2, stations))

    px.drop(columns="units").to_parquet(out_dir / f"tempo_pixels_{start}_{table_end or end}.parquet")
    return checks


# --- Download ----------------------------------------------------------------------------------------------


def download_granule(href: str, dst: Path) -> None:
    """Download `href` to `dst` with curl and the Earthdata credentials of ``~/.netrc`` (the login redirect
    needs cookies: a throwaway jar next to `dst`). Raises RuntimeError when curl fails."""
    with tempfile.TemporaryDirectory(dir=dst.parent) as jar:
        cookies = str(Path(jar) / "cookies")
        command = ["curl", "-sfL", "-n", "-c", cookies, "-b", cookies, "--retry", "3"]
        result = subprocess.run(
            [*command, "-m", str(DOWNLOAD_TIMEOUT_S), "-o", str(dst), href], capture_output=True
        )
    if result.returncode != 0:
        dst.unlink(missing_ok=True)
        raise RuntimeError(f"curl error {result.returncode}")


def subset_granule(src: Path, dst: Path) -> int:
    """Write to `dst` the rows and columns of the granule `src` that touch the domain (plus `MARGIN_DEG`),
    with the variables of `KEEP`. Returns the pixels inside that box; 0 (and no file) when there are none."""
    import netCDF4

    west, south, east, north = BBOX
    with netCDF4.Dataset(src) as ds:
        lat = ds["geolocation/latitude"][:].filled(np.nan)
        lon = ds["geolocation/longitude"][:].filled(np.nan)
        inside = (
            (lat > south - MARGIN_DEG)
            & (lat < north + MARGIN_DEG)
            & (lon > west - MARGIN_DEG)
            & (lon < east + MARGIN_DEG)
        )
        if not inside.any():
            return 0
        rows, cols = np.where(inside.any(1))[0], np.where(inside.any(0))[0]
        rs, cs = slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1)
        with netCDF4.Dataset(dst, "w") as out:
            out.setncatts({k: ds.getncattr(k) for k in ds.ncattrs()})
            out.source_granule = src.name
            out.subset_rows = f"{rs.start}:{rs.stop}"
            out.subset_cols = f"{cs.start}:{cs.stop}"
            out.createDimension("mirror_step", rs.stop - rs.start)
            out.createDimension("xtrack", cs.stop - cs.start)
            out.createDimension("corner", 4)
            for group, names in KEEP.items():
                target = out.createGroup(group)
                for name in names:
                    var = ds[f"{group}/{name}"]
                    dims = {
                        1: ("mirror_step",),
                        2: ("mirror_step", "xtrack"),
                        3: ("mirror_step", "xtrack", "corner"),
                    }[var.ndim]
                    fill = getattr(var, "_FillValue", None)
                    new = target.createVariable(
                        name, var.dtype, dims, zlib=True, complevel=4, fill_value=fill
                    )
                    new.setncatts({k: var.getncattr(k) for k in var.ncattrs() if k != "_FillValue"})
                    new[:] = var[rs] if var.ndim == 1 else var[rs, cs]
        return int(inside.sum())


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    """The manifest rows by granule name (empty when there is no manifest)."""
    if not path.exists():
        return {}
    with open(path, newline="") as handle:
        return {row["granule"]: row for row in csv.DictReader(handle)}


def _fetch_one(raw_dir: Path, scan: pd.Timestamp, href: str, download: Downloader) -> dict[str, Any]:
    """Download one granule into a temporary folder, keep its subset and delete the original."""
    name = href.rsplit("/", 1)[1]
    dst = raw_dir / subset_name(href)
    started = time.time()
    row: dict[str, Any] = {"granule": name, "time_utc": scan.isoformat(), "url": href}
    try:
        with tempfile.TemporaryDirectory(dir=raw_dir) as tmp:
            src = Path(tmp) / name
            download(href, src)
            row["original_bytes"] = src.stat().st_size
            part = dst.with_suffix(".part")
            with HDF5_LOCK:
                pixels = subset_granule(src, part)
            if pixels:
                part.rename(dst)
    except (RuntimeError, OSError) as error:  # a failed granule is tried again by the next call
        return row | {"status": f"error: {error}"}
    return row | {
        "pixels_with_margin": pixels,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.time() - started),
        "status": "ok" if pixels else "no pixels",
    }


def fetch_window(
    raw_dir: Path,
    start: str,
    end: str,
    get: Getter = http_get,
    download: Downloader = download_granule,
    workers: int = 2,
    progress: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Download the afternoon granules scanned from `start` to `end` (inclusive dates, UTC) that `raw_dir`
    does not have yet and keep their subsets (`_zmvm.nc`), recording each one in ``manifest.csv``.

    A granule is skipped when its subset exists or the manifest says it was downloaded (a granule with no
    pixel in the domain leaves no file), so a repeated call only fetches what is new. Returns the counts
    ``found``, ``new``, ``failed`` and ``skipped``."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = raw_dir / MANIFEST
    known = {name for name, row in read_manifest(manifest).items() if row["status"] in DONE_STATUSES}
    found = list_granules(start, end, get)
    todo = [
        (t, href)
        for t, href in found
        if not (raw_dir / subset_name(href)).exists() and href.rsplit("/", 1)[1] not in known
    ]
    counts = {"found": len(found), "new": 0, "failed": 0, "skipped": len(found) - len(todo)}
    new_file = not manifest.exists()
    with open(manifest, "a", newline="") as handle, ThreadPoolExecutor(workers) as pool:
        writer = csv.DictWriter(handle, MANIFEST_FIELDS, restval="")
        if new_file:
            writer.writeheader()
        for done, future in enumerate(
            as_completed([pool.submit(_fetch_one, raw_dir, t, href, download) for t, href in todo]), 1
        ):
            row = future.result()
            writer.writerow(row)
            handle.flush()
            counts["new" if row["status"] in DONE_STATUSES else "failed"] += 1
            if progress:
                progress(f"[{done}/{len(todo)}] {row['granule']} {row['status']}")
    return counts
