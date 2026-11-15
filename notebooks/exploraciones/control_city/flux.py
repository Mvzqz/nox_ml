# ruff: noqa: E501
"""Daily NOx emission of a city from TEMPO alone, with the flux divergence of `nox_ml.validation.divergence`.

The scan emission is `divergence.scan_emission` itself; only the inputs change, so any city can be run:
- pixels from the city subsets (`data/raw/tempo_<city>/`, or `data/raw/tempo/` for the ZMVM), valid as in
  `nox_ml.data.tempo.clean_pixels` (quality flag 0, cloud fraction < 0.2), inside the city box;
- one ERA5 10 m wind per scan at the city centre (Open-Meteo, nearest hour), instead of the airport or
  station wind of the ZMVM run;
- a constant NO2/NOx ratio (it scales every day alike and cancels in the log anomalies and the ratios);
- a fixed 5 km grid over the city box.

Usage: .venv/bin/python notebooks/exploraciones/control_city/flux.py 2024-11-01 2024-12-31 monterrey puebla zmvm
Writes notebooks/exploraciones/control_city/out/daily_<city>_<start>_<end>.csv.
"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from nox_ml.data import calendar as calendar_days
from nox_ml.data.tempo import read_granule
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.inversion.normalized import day_type
from nox_ml.validation import divergence

sys.path.insert(0, str(Path(__file__).parent))
from cities import CENTRES, bbox

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw"
OUT = Path(__file__).parent / "out"
NO2_NOX = 0.75
M_PER_DEG = 111_320.0
LOCAL_OFFSET_H = -6  # all four cities are on UTC-6 without daylight saving since 2022


def granule_files(city: str, start: str, end: str) -> list[Path]:
    folder, glob = (RAW / "tempo", "*_zmvm.nc") if city == "zmvm" else (RAW / f"tempo_{city}", f"*_{city}.nc")
    first, last = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    out = []
    for f in sorted(folder.glob(f"TEMPO_NO2_L2_V04_{glob}")):
        t = pd.to_datetime(f.name.split("_")[4], format="%Y%m%dT%H%M%SZ") + pd.Timedelta(hours=LOCAL_OFFSET_H)
        if first <= t < last and 12 <= t.hour < 18:
            out.append(f)
    return out


def era5_wind(city: str) -> pd.DataFrame:
    """Hourly u, v (m/s) at 10 m, indexed by naive UTC hour."""
    d = json.loads((RAW / "era5_openmeteo_cities" / f"wind_pbl_{city}_2024-2026.json").read_text())["hourly"]
    speed, rad = (
        np.asarray(d["wind_speed_10m"], float),
        np.deg2rad(np.asarray(d["wind_direction_10m"], float)),
    )
    return pd.DataFrame(
        {"u": -speed * np.sin(rad), "v": -speed * np.cos(rad), "pbl": d["boundary_layer_height"]},
        index=pd.to_datetime(d["time"]),
    )


def daily(city: str, start: str, end: str) -> pd.DataFrame:
    box = bbox(city)
    lon0, lat0 = CENTRES[city]
    kx = M_PER_DEG * np.cos(np.deg2rad(lat0))
    grid = divergence.Grid(
        x0=(box[0] - lon0) * kx,
        y0=(box[1] - lat0) * M_PER_DEG,
        nx=int((box[2] - box[0]) * kx // divergence.CELL_M) + 1,
        ny=int((box[3] - box[1]) * M_PER_DEG // divergence.CELL_M) + 1,
    )
    wind = era5_wind(city)
    rows = []
    for f in granule_files(city, start, end):
        px = read_granule(f)
        px = px[px["lat"].between(box[1], box[3]) & px["lon"].between(box[0], box[2])]
        px = px[(px["qf"] == 0) & (px["cf"] < 0.2) & px["vcd"].notna()]
        utc = px["utc"].iloc[0] if len(px) else None
        if utc is None:
            continue
        w = wind.loc[utc.round("h")]
        hour = SimpleNamespace(
            no2=px["vcd"].to_numpy(),
            pixels=SimpleNamespace(
                x=((px["lon"] - lon0) * kx).to_numpy(), y=((px["lat"] - lat0) * M_PER_DEG).to_numpy()
            ),
            wind=(float(w["u"]), float(w["v"])),
        )
        scan = divergence.scan_emission(hour, grid, NO2_NOX)  # type: ignore[arg-type]
        if scan is not None:
            local = utc + pd.Timedelta(hours=LOCAL_OFFSET_H)
            rows.append({"day": local.normalize(), "pbl": float(w["pbl"]), **scan})
    scans = pd.DataFrame(rows)
    out = scans.groupby("day").mean().drop(columns="cover")
    out["scans"] = scans.groupby("day").size()
    days = pd.DatetimeIndex(out.index)
    out["kind"] = day_type(days, HOLIDAYS)
    out["atypical"] = days.isin(calendar_days.atypical_days(start, end))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("cities", nargs="+")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    for city in a.cities:
        d = daily(city, a.start, a.end)
        d.rename_axis("day").to_csv(OUT / f"daily_{city}_{a.start}_{a.end}.csv")
        print(city, len(d), "days,", int((d["kind"] == 0).sum()), "weekdays")


if __name__ == "__main__":
    main()
