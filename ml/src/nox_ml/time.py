"""Local time of the study city.

Mexico City is on UTC-6 all year (no daylight saving time since 2022; none in the 2023-2024 data). Timestamps
in the package are naive: UTC unless a name says ``local``. This is the only place that knows the offset.
"""

from typing import Any, cast, overload

import pandas as pd

LOCAL_OFFSET_H = -6  # local time minus UTC
LOCAL_OFFSET = pd.Timedelta(hours=LOCAL_OFFSET_H)


def utc_to_local[T](utc: T) -> T:
    """Naive UTC timestamps (Series, DatetimeIndex or Timestamp) to naive local time."""
    return cast(Any, utc) + LOCAL_OFFSET


def local_to_utc[T](local: T) -> T:
    """Naive local timestamps (Series, DatetimeIndex or Timestamp) to naive UTC."""
    return cast(Any, local) - LOCAL_OFFSET


def local_day[T](utc: T) -> T:
    """Local calendar day (midnight) of naive UTC timestamps."""
    local = cast(Any, utc_to_local(utc))
    return local.dt.normalize() if isinstance(utc, pd.Series) else local.normalize()


@overload
def local_hour(utc: pd.Series) -> pd.Series: ...
@overload
def local_hour(utc: pd.DatetimeIndex) -> pd.Index: ...
@overload
def local_hour(utc: pd.Timestamp) -> int: ...
def local_hour(utc: Any) -> Any:
    """Local hour of the day (0-23) of naive UTC timestamps."""
    local = utc_to_local(utc)
    return local.dt.hour if isinstance(utc, pd.Series) else local.hour
