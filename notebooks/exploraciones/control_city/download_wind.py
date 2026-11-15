"""Hourly ERA5 wind (10 and 100 m) and boundary layer height at each city centre, from the Open-Meteo archive.

Usage: .venv/bin/python notebooks/exploraciones/control_city/download_wind.py
Writes data/raw/era5_openmeteo_cities/wind_pbl_<city>_2024-2026.json.
"""

import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cities import CENTRES

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/raw/era5_openmeteo_cities"
VARS = "wind_speed_10m,wind_direction_10m,wind_speed_100m,wind_direction_100m,boundary_layer_height"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for city, (lon, lat) in CENTRES.items():
        dst = OUT / f"wind_pbl_{city}_2024-2026.json"
        if dst.exists():
            continue
        url = (
            f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
            f"&start_date=2024-11-01&end_date=2026-05-31&hourly={VARS}&wind_speed_unit=ms&models=era5&timezone=GMT"
        )
        with urllib.request.urlopen(url, timeout=300) as r:
            dst.write_bytes(r.read())
        print(city, dst.stat().st_size)
        time.sleep(2)


if __name__ == "__main__":
    main()
