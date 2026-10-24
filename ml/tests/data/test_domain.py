import pandas as pd

from nox_ml.data.domain import local_to_utc, utc_to_local
from nox_ml.data.qc import Check, render


def test_local_to_utc_adds_six_hours():
    local = pd.Series(pd.to_datetime(["2024-01-01 08:00"]))

    assert local_to_utc(local).iloc[0] == pd.Timestamp("2024-01-01 14:00")


def test_local_to_utc_keeps_the_offset_in_summer_because_there_is_no_dst():
    local = pd.Series(pd.to_datetime(["2023-01-15 12:00", "2023-07-15 12:00"]))

    offsets = local_to_utc(local) - local

    assert (offsets == pd.Timedelta(hours=6)).all()


def test_local_to_utc_crosses_midnight():
    local = pd.Series(pd.to_datetime(["2023-12-31 20:00"]))

    assert local_to_utc(local).iloc[0] == pd.Timestamp("2024-01-01 02:00")


def test_utc_to_local_inverts_local_to_utc():
    local = pd.Series(pd.date_range("2023-03-25", periods=48, freq="h"))

    assert (utc_to_local(local_to_utc(local)) == local).all()


def test_check_renders_status_marks():
    checks = [Check(True, "a"), Check(False, "b"), Check(None, "c")]

    assert render(checks) == "[ok] a\n[FAIL] b\n[info] c"
