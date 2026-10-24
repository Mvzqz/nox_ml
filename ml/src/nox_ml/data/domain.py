"""Study domain and conventions shared by the data loaders."""

import pandas as pd

# Domain (lon_min, lat_min, lon_max, lat_max): Mexico City metropolitan area plus ~10 km N and E,
# so the Valle de México power plant (Acolman) is not on the border.
BBOX = (-99.35, 19.25, -98.81, 19.77)
LON = (BBOX[0], BBOX[2])
LAT = (BBOX[1], BBOX[3])

# Urban core, used to compare TEMPO columns against their surroundings.
CORE_LAT, CORE_LON = (19.33, 19.53), (-99.20, -99.03)

# Mexico City is on UTC-6 all year (no daylight saving time since 2022; none in 2023-2024 data).
LOCAL_UTC_OFFSET = pd.Timedelta(hours=6)

DRY_MONTHS = (11, 12, 1, 2, 3, 4, 5)
AFTERNOON_HOURS = tuple(range(12, 18))  # 12:00-17:59 local, when TEMPO scans the domain


def local_to_utc(local: pd.Series) -> pd.Series:
    """Convert naive local timestamps (UTC-6, no DST) to naive UTC."""
    return local + LOCAL_UTC_OFFSET


def utc_to_local(utc: pd.Series | pd.DatetimeIndex):
    """Convert naive UTC timestamps to naive local time (UTC-6, no DST)."""
    return utc - LOCAL_UTC_OFFSET
