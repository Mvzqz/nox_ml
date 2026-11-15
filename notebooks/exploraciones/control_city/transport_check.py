# ruff: noqa: E501
"""Does ZMVM air reach the control city? Daily anomalies of both on the days the afternoon wind at the control
blows from the ZMVM (within 45 degrees of its bearing) against the other days.

If the ZMVM plume entered the control box, the two would correlate more on those days and a measure in the
ZMVM would partly show in the control, shrinking the difference in differences.

Usage: .venv/bin/python notebooks/exploraciones/control_city/transport_check.py puebla 2024-11-01:2024-12-31 ...
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from compare import load, normal_log

from nox_ml.validation import products

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw"
CENTRES = {
    "zmvm": (-99.08, 19.51),
    "puebla": (-98.21, 19.05),
    "toluca": (-99.65, 19.29),
    "monterrey": (-100.32, 25.69),
}


def afternoon_direction(city: str) -> pd.Series:
    """Vector-mean 10 m wind direction (from, degrees) of 18-23 UTC of each local day."""
    d = json.loads((RAW / "era5_openmeteo_cities" / f"wind_pbl_{city}_2024-2026.json").read_text())["hourly"]
    t = pd.to_datetime(d["time"])
    s, rad = np.asarray(d["wind_speed_10m"], float), np.deg2rad(np.asarray(d["wind_direction_10m"], float))
    df = pd.DataFrame({"x": s * np.sin(rad), "y": s * np.cos(rad)}, index=t)
    df = df[df.index.hour.isin(range(18, 24))]
    g = df.groupby((df.index - pd.Timedelta(hours=6)).normalize()).mean()
    return pd.Series((np.rad2deg(np.arctan2(g["x"], g["y"])) + 360) % 360, index=g.index)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("city")
    ap.add_argument("seasons", nargs="+")
    a = ap.parse_args()
    lon0, lat0 = CENTRES[a.city]
    lon1, lat1 = CENTRES["zmvm"]
    bearing = np.rad2deg(np.arctan2((lon1 - lon0) * np.cos(np.deg2rad(lat0)), lat1 - lat0)) % 360
    rows = []
    direction = afternoon_direction(a.city)
    for season in a.seasons:
        start, end = season.split(":")
        exclude = products.reference_exclusions(ROOT / "data", start, end, pd.DatetimeIndex([]))
        z = normal_log(load("zmvm", start, end), exclude)
        c = normal_log(load(a.city, start, end), pd.DatetimeIndex([]))
        both = z.index.intersection(c.index)
        delta = np.abs((direction.reindex(both) - bearing + 180) % 360 - 180)
        rows.append(
            pd.DataFrame({"z": z[both], "c": c[both], "from_zmvm": (delta < 45).to_numpy()}, index=both)
        )
    df = pd.concat(rows)
    print(f"bearing of the ZMVM from {a.city}: {bearing:.0f} deg")
    for flag, g in df.groupby("from_zmvm"):
        r = np.corrcoef(g["z"], g["c"])[0, 1] if len(g) > 2 else float("nan")
        print(
            f"wind from the ZMVM={flag}: {len(g)} days, r={r:.2f}, sd(diff)={np.std(g['z'] - g['c'], ddof=1):.2f}"
        )


if __name__ == "__main__":
    main()
