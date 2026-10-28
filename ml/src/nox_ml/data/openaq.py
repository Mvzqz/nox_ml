# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Station NOx from OpenAQ, for the years SIMAT has not published (2025 onward).

SIMAT publishes its yearly hourly tables up to 2024. OpenAQ (API v3, a free key in ``OPENAQ_API_KEY``)
relays the same stations through SINAICA, the national system: hourly, unvalidated. Against the validated
SIMAT tables of nov-dec 2024 they agree (r 0.97, the same mean, 4.5-5 ppb mean absolute difference) and carry
60-65 % of the hours. OpenAQ has no wind, temperature or humidity of these stations: the wind comes from the
airports (`inputs.airport_wind`).

`fetch` writes the raw measurements (``raw/openaq/``) and `simat_table` turns them into the table of
`qc-simat` (``id_station``, ``local``, ``utc`` stamped at the end of the hour as SIMAT does, ``NO``, ``NO2``,
``NOX``, ``O3`` in ppb), so `inputs.load_inputs` reads it like SIMAT's.
"""

import json
import os
import time
import urllib.error
import urllib.request
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nox_ml.time import utc_to_local

API = "https://api.openaq.org/v3"
KEY_VARIABLE = "OPENAQ_API_KEY"
PROVIDER = "Sinaica Mexico"
PARAMETERS = {"no": "NO", "no2": "NO2", "nox": "NOX", "o3": "O3"}  # OpenAQ name -> SIMAT column
PPM_TO_PPB = 1000.0
MAX_MATCH_KM = 1.5  # an OpenAQ location farther than this from every SIMAT station is left out
PAGE = 1000  # measurements per request (the API maximum)
PAUSE_S = 1.1  # between requests: the free key allows 60 per minute
RETRIES = 5
BBOX = (-99.4, 19.1, -98.8, 19.8)  # lon, lat of the domain (SW, NE)

Getter = Callable[[str, dict[str, Any]], dict[str, Any]]


def api_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET an OpenAQ v3 endpoint with the key of ``OPENAQ_API_KEY``, retrying when rate limited."""
    key = os.environ.get(KEY_VARIABLE)
    if not key:
        raise RuntimeError(f"set {KEY_VARIABLE} to an OpenAQ API key")
    query = "&".join(f"{k}={v}" for k, v in params.items())
    request = urllib.request.Request(f"{API}{path}?{query}", headers={"X-API-Key": key})
    for attempt in range(RETRIES):
        time.sleep(PAUSE_S)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
            time.sleep(30 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):  # the network, not the request: wait and try again
            if attempt == RETRIES - 1:
                raise
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("unreachable")


def distance_km(lat0: np.ndarray, lon0: np.ndarray, lat1: float, lon1: float) -> np.ndarray:
    """Great-circle distance (km)."""
    p0, p1, dl = np.deg2rad(lat0), np.deg2rad(lat1), np.deg2rad(lon1 - lon0)
    a = np.sin((p1 - p0) / 2) ** 2 + np.cos(p0) * np.cos(p1) * np.sin(dl / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def match_sensors(locations: Sequence[dict[str, Any]], catalog: pd.DataFrame) -> pd.DataFrame:
    """The sensors of `PARAMETERS` of the `PROVIDER` locations, with the SIMAT station each one is (the
    nearest of `catalog`, columns ``lat`` and ``lon`` indexed by code, within `MAX_MATCH_KM`): columns
    ``sensor``, ``location``, ``station``, ``parameter``, ``km``. A station can have several locations over
    time (OpenAQ opens a new one when the feed changes)."""
    rows = []
    for location in locations:
        if (location.get("provider") or {}).get("name") != PROVIDER:
            continue
        coordinates = location["coordinates"]
        km = distance_km(
            catalog["lat"].to_numpy(),
            catalog["lon"].to_numpy(),
            coordinates["latitude"],
            coordinates["longitude"],
        )
        nearest = int(np.argmin(km))
        if km[nearest] > MAX_MATCH_KM:
            continue
        for sensor in location["sensors"]:
            name = sensor["parameter"]["name"]
            if name in PARAMETERS:
                rows.append(
                    {
                        "sensor": sensor["id"],
                        "location": location["id"],
                        "station": catalog.index[nearest],
                        "parameter": name,
                        "km": float(km[nearest]),
                    }
                )
    return pd.DataFrame(rows, columns=["sensor", "location", "station", "parameter", "km"])


def sensor_hours(sensor: int, start: str, end: str, get: Getter = api_get) -> pd.DataFrame:
    """Hourly values of a sensor from `start` to `end` (UTC dates, end exclusive): ``h`` (start of the
    hour, UTC, naive) and ``value`` (the sensor's units), every page."""
    rows, page = [], 1
    while True:
        params = {
            "datetime_from": f"{start}T00:00:00Z",
            "datetime_to": f"{end}T00:00:00Z",
            "limit": PAGE,
            "page": page,
        }
        results = get(f"/sensors/{sensor}/measurements", params).get("results", [])
        rows += [(r["period"]["datetimeFrom"]["utc"], r["value"]) for r in results]
        if len(results) < PAGE:
            break
        page += 1
    table = pd.DataFrame(rows, columns=["h", "value"])
    table["h"] = pd.to_datetime(table["h"], utc=True).dt.tz_localize(None)
    return table


def fetch(start: str, end: str, catalog: pd.DataFrame, get: Getter = api_get) -> pd.DataFrame:
    """Raw hourly measurements of every matched sensor from `start` to `end`: ``sensor``, ``location``,
    ``station``, ``parameter``, ``h``, ``value``."""
    west, south, east, north = BBOX
    locations = get("/locations", {"bbox": f"{west},{south},{east},{north}", "limit": 1000})["results"]
    sensors = match_sensors(locations, catalog)
    frames = []
    for row in sensors.itertuples():
        try:
            hours = sensor_hours(row.sensor, start, end, get)
        except (
            urllib.error.HTTPError
        ) as error:  # a sensor the server keeps failing on: the others still count
            warnings.warn(
                f"OpenAQ sensor {row.sensor} ({row.station} {row.parameter}) skipped: {error}", stacklevel=2
            )
            continue
        frames.append(
            hours.assign(
                sensor=row.sensor, location=row.location, station=row.station, parameter=row.parameter
            )
        )
    columns = ["sensor", "location", "station", "parameter", "h", "value"]
    return pd.concat(frames, ignore_index=True)[columns] if frames else pd.DataFrame(columns=columns)


def simat_table(raw: pd.DataFrame) -> pd.DataFrame:
    """The raw measurements as the table of `qc-simat`: one row per station and hour, ``NO``, ``NO2``,
    ``NOX`` and ``O3`` in ppb (OpenAQ gives ppm; negative values are dropped), ``utc`` and ``local`` stamped
    at the end of the hour like SIMAT. Where two locations of a station report the same hour, their mean."""
    ok = raw[raw["value"] >= 0].assign(column=lambda x: x["parameter"].map(PARAMETERS))
    wide = (
        ok.pivot_table(index=["station", "h"], columns="column", values="value", aggfunc="mean") * PPM_TO_PPB
    )
    wide = wide.reindex(columns=list(PARAMETERS.values())).reset_index()
    wide.columns.name = None
    utc = wide["h"] + pd.Timedelta(hours=1)
    return pd.DataFrame(
        {
            "id_station": wide["station"],
            "local": utc_to_local(utc),
            "utc": utc,
            **{c: wide[c] for c in PARAMETERS.values()},
        }
    )


def run_fetch(start: str, end: str, data_dir: Path) -> tuple[Path, Path]:
    """`fetch` and `simat_table`, written to ``raw/openaq/openaq_<start>_<end>.parquet`` and
    ``interim/openaq_nox_<start>_<end>.parquet``."""
    import geopandas as gpd

    catalog = gpd.read_file(data_dir / "interim" / "estaciones.gpkg").to_crs(4326).set_index("cve_estac")
    catalog = pd.DataFrame({"lat": catalog.geometry.y, "lon": catalog.geometry.x})
    raw = fetch(start, end, catalog)
    if raw.empty:
        raise RuntimeError(f"OpenAQ returned no measurements for {start} to {end}")
    raw_path = data_dir / "raw" / "openaq" / f"openaq_{start}_{end}.parquet"
    interim_path = data_dir / "interim" / f"openaq_nox_{start}_{end}.parquet"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(raw_path, index=False)
    simat_table(raw).to_parquet(interim_path, index=False)
    return raw_path, interim_path
