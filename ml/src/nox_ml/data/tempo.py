# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""TEMPO tropospheric NO2 (L2, V04) subsets over the study domain.

Each granule is a small NetCDF subset (`TEMPO_NO2_L2_V04_<yyyymmddThhmmssZ>_<scan>_zmvm.nc`). Pixels are valid
when the main quality flag is 0, the effective cloud fraction is below 0.2 and the column is not missing.

Pure functions parse names, filter pixels and compute checks; the I/O layer at the end reads NetCDF files and
parquet tables.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data.domain import CORE_LAT, CORE_LON, LAT, LON
from nox_ml.data.qc import Check
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


# --- Pure functions ----------------------------------------------------------------------------------------


def granule_time(name: str) -> pd.Timestamp:
    """Scan start (naive UTC) from a granule file name."""
    return pd.to_datetime(name.split("_")[4], format="%Y%m%dT%H%M%SZ")


def in_period(t: pd.Timestamp, start: str, end: str) -> bool:
    """True when `t` is on or after `start` and before the end of the day `end` (both inclusive dates)."""
    return pd.Timestamp(start) <= t < pd.Timestamp(end) + pd.Timedelta(days=1)


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
) -> list[Check]:
    """Check TEMPO pixels and write `tempo_pixels_<start>_<end>.parquet` to `out_dir`.

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

    px.drop(columns="units").to_parquet(out_dir / f"tempo_pixels_{start}_{end}.parquet")
    return checks
