from typing import cast

import pandas as pd

from nox_ml.time import local_day, local_hour, local_to_utc, utc_to_local


def ts(text: str) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(text))


def test_local_to_utc_adds_six_hours():
    local = pd.Series(pd.to_datetime(["2024-01-01 08:00"]))

    assert local_to_utc(local).iloc[0] == ts("2024-01-01 14:00")


def test_local_to_utc_keeps_the_offset_in_summer_because_there_is_no_dst():
    local = pd.Series(pd.to_datetime(["2023-01-15 12:00", "2023-07-15 12:00"]))

    offsets = local_to_utc(local) - local

    assert (offsets == pd.Timedelta(hours=6)).all()


def test_local_to_utc_crosses_midnight():
    local = pd.Series(pd.to_datetime(["2023-12-31 20:00"]))

    assert local_to_utc(local).iloc[0] == ts("2024-01-01 02:00")


def test_utc_to_local_inverts_local_to_utc():
    local = pd.Series(pd.date_range("2023-03-25", periods=48, freq="h"))

    assert (utc_to_local(local_to_utc(local)) == local).all()


def test_utc_to_local_accepts_a_timestamp():
    assert utc_to_local(ts("2024-03-15 05:00")) == ts("2024-03-14 23:00")


def test_local_hour_is_utc_minus_six_without_dst():
    index = pd.DatetimeIndex(["2023-01-01 18:00", "2023-07-01 18:00", "2023-01-01 03:00"])

    assert local_hour(index).tolist() == [12, 12, 21]
    assert local_hour(ts("2023-07-01 05:00")) == 23


def test_local_day_shifts_utc_to_mexico_city_time():
    utc = pd.Series(pd.to_datetime(["2024-03-15 05:59", "2024-03-15 06:00"]))
    expected = pd.to_datetime(["2024-03-14", "2024-03-15"]).tolist()

    assert local_day(utc).tolist() == expected
    assert local_day(pd.DatetimeIndex(utc)).tolist() == expected
    assert local_day(ts("2024-03-15 05:59")) == ts("2024-03-14")


def test_local_hour_accepts_a_series():
    utc = pd.Series(pd.to_datetime(["2024-03-15 05:59", "2024-03-15 06:00"]))

    assert local_hour(utc).tolist() == [23, 0]
