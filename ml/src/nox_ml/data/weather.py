"""The weather of the seasons after 2024: airport reports and ERA5, extended in place for the monitoring.

The airport reports (METAR of MMMX and MMSM: wind, temperature, humidity) come from the IEM ASOS archive
(Iowa State University) and the boundary layer height and wind of the city cell from ERA5 through the
Open-Meteo archive, the sources of ``raw/metar/`` and ``raw/era5_openmeteo/`` (``data/README.md``). Both are
free and need no key. `run_fetch` downloads a window and merges it into the files `inputs.openaq_sources`
reads, so a new month extends them without duplicating hours.
"""

import http.client
import io
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
AIRPORTS = ("MMMX", "MMSM")
METAR_COLUMNS = ("sknt", "drct", "tmpf", "relh")
ERA5_CELL = (19.5, -99.25)  # lat, lon of the city cell
ERA5_HOURLY = ("boundary_layer_height", "wind_speed_10m", "wind_direction_10m")
RETRIES = 4

Getter = Callable[[str], bytes]


def http_get(url: str) -> bytes:
    """GET `url`, retrying on server and network errors and when rate limited."""
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if (error.code < 500 and error.code != 429) or attempt == RETRIES - 1:  # 429: rate limited
                raise
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead):  # the network: wait, retry
            if attempt == RETRIES - 1:
                raise
        time.sleep(20 * (attempt + 1))
    raise RuntimeError("unreachable")


def metar_url(station: str, start: str, end: str) -> str:
    """The IEM request of `station`'s reports from `start` to `end` (UTC dates, end exclusive)."""
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    params = [("station", station), *(("data", c) for c in METAR_COLUMNS)]
    params += [
        ("year1", first.year), ("month1", first.month), ("day1", first.day),
        ("year2", last.year), ("month2", last.month), ("day2", last.day),
        ("tz", "Etc/UTC"), ("format", "onlycomma"), ("latlon", "no"), ("missing", "empty"),
        ("trace", "empty"), ("direct", "no"), ("report_type", 3), ("report_type", 4),
    ]  # fmt: skip
    return f"{IEM}?" + "&".join(f"{k}={v}" for k, v in params)


def era5_url(start: str, end: str) -> str:
    """The Open-Meteo request of ERA5 at the city cell from `start` to `end` (UTC dates, end exclusive)."""
    last = (pd.Timestamp(end) - pd.Timedelta(days=1)).date().isoformat()
    lat, lon = ERA5_CELL
    return (
        f"{OPEN_METEO}?latitude={lat}&longitude={lon}&start_date={start}&end_date={last}"
        f"&hourly={','.join(ERA5_HOURLY)}&models=era5&timezone=GMT"
    )


def merge_metar(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """The reports of both tables, one per station and time (the new one where both have it), in order."""
    both = pd.concat([old, new], ignore_index=True)
    both = both.drop_duplicates(subset=["station", "valid"], keep="last")
    return both.sort_values(["station", "valid"], ignore_index=True)


def merge_era5(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """`old` with the hours of `new` added or replaced, where the new value is not missing."""
    times = old["hourly"]["time"]
    hourly = {name: dict(zip(times, old["hourly"][name], strict=True)) for name in ERA5_HOURLY}
    for name in ERA5_HOURLY:
        for t, value in zip(new["hourly"]["time"], new["hourly"][name], strict=True):
            if value is not None or t not in hourly[name]:
                hourly[name][t] = value
    times = sorted(hourly[ERA5_HOURLY[0]])
    return old | {"hourly": {"time": times, **{n: [hourly[n][t] for t in times] for n in ERA5_HOURLY}}}


def run_fetch(start: str, end: str, raw_dir: Path, metar: tuple[str, ...], era5: str, get: Getter = http_get):
    """Download the airport reports and ERA5 from `start` to `end` (UTC dates, end exclusive) and merge them
    into ``raw_dir/metar/<metar>`` (one file per airport of `AIRPORTS`, in order) and
    ``raw_dir/era5_openmeteo/<era5>``. Returns the hours each file covers now."""
    covered = {}
    for station, name in zip(AIRPORTS, metar, strict=True):
        path = raw_dir / "metar" / name
        new = pd.read_csv(io.BytesIO(get(metar_url(station, start, end))), dtype={"valid": str})
        merged = merge_metar(pd.read_csv(path, dtype={"valid": str}), new)
        merged.to_csv(path, index=False, float_format="%.2f")
        covered[name] = (merged["valid"].min(), merged["valid"].max())
    path = raw_dir / "era5_openmeteo" / era5
    merged = merge_era5(json.loads(path.read_text()), json.loads(get(era5_url(start, end))))
    path.write_text(json.dumps(merged))
    pbl = zip(merged["hourly"]["time"], merged["hourly"]["boundary_layer_height"], strict=True)
    filled = [t for t, h in pbl if h is not None]
    covered[era5] = (filled[0], filled[-1])
    return covered
