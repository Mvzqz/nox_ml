"""Extending the airport reports and ERA5 files with a new window, without the network."""

import json
from pathlib import Path

import pandas as pd
import pytest

from nox_ml.data import weather


def test_new_reports_extend_the_file_and_replace_the_hours_they_repeat():
    old = pd.DataFrame(
        {"station": ["MMMX", "MMMX"], "valid": ["2026-05-31 22:50", "2026-05-31 23:50"], "sknt": [5.0, 6.0]}
    )
    new = pd.DataFrame(
        {"station": ["MMMX", "MMMX"], "valid": ["2026-05-31 23:50", "2026-06-01 00:50"], "sknt": [7.0, 8.0]}
    )

    merged = weather.merge_metar(old, new)

    assert list(merged["valid"]) == ["2026-05-31 22:50", "2026-05-31 23:50", "2026-06-01 00:50"]
    assert list(merged["sknt"]) == [5.0, 7.0, 8.0]


def era5(times, pbl):
    n = len(times)
    hourly = {
        "time": times,
        "boundary_layer_height": pbl,
        "wind_speed_10m": [1.0] * n,
        "wind_direction_10m": [90] * n,
    }
    return {"latitude": 19.5, "hourly": hourly}


def test_era5_keeps_old_values_where_the_new_window_is_still_missing():
    old = era5(["2026-06-01T00:00", "2026-06-01T01:00"], [500.0, 600.0])
    new = era5(["2026-06-01T01:00", "2026-06-01T02:00"], [None, 700.0])

    merged = weather.merge_era5(old, new)

    assert merged["latitude"] == 19.5
    assert merged["hourly"]["time"] == ["2026-06-01T00:00", "2026-06-01T01:00", "2026-06-01T02:00"]
    assert merged["hourly"]["boundary_layer_height"] == [500.0, 600.0, 700.0]


def test_run_fetch_merges_both_airports_and_era5_into_the_files_it_names(tmp_path):
    (tmp_path / "metar").mkdir()
    (tmp_path / "era5_openmeteo").mkdir()
    for name in ("A.csv", "B.csv"):
        pd.DataFrame({"station": ["X"], "valid": ["2026-05-31 23:50"], "sknt": [5.0]}).to_csv(
            tmp_path / "metar" / name, index=False
        )
    (tmp_path / "era5_openmeteo" / "e.json").write_text(json.dumps(era5(["2026-05-31T23:00"], [400.0])))

    def get(url: str) -> bytes:
        if url.startswith(weather.IEM):
            station = url.split("station=")[1].split("&")[0]
            return f"station,valid,sknt\n{station},2026-06-01 00:50,9.00\n".encode()
        return json.dumps(era5(["2026-06-01T00:00"], [800.0])).encode()

    covered = weather.run_fetch("2026-06-01", "2026-06-02", tmp_path, ("A.csv", "B.csv"), "e.json", get)

    assert covered["A.csv"] == ("2026-05-31 23:50", "2026-06-01 00:50")
    assert set(pd.read_csv(tmp_path / "metar" / "B.csv")["station"]) == {"X", "MMSM"}
    assert covered["e.json"] == ("2026-05-31T23:00", "2026-06-01T00:00")


def test_a_rate_limited_request_is_retried(monkeypatch):
    import io
    import urllib.error
    from email.message import Message

    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", Message(), None)
        return io.BytesIO(b"ok")

    monkeypatch.setattr(weather.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(weather.time, "sleep", lambda s: None)

    assert weather.http_get("https://example.org") == b"ok" and len(calls) == 2


def test_a_dropped_connection_is_retried(monkeypatch):
    import http.client
    import io

    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise http.client.RemoteDisconnected("closed without response")
        if len(calls) == 2:
            raise ConnectionResetError("reset by peer")
        return io.BytesIO(b"ok")

    monkeypatch.setattr(weather.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(weather.time, "sleep", lambda s: None)

    assert weather.http_get("https://example.org") == b"ok" and len(calls) == 3


def test_retry_after_of_a_rate_limit_sets_the_wait(monkeypatch):
    import io
    import urllib.error
    from email.message import Message

    waits, calls = [], []
    headers = Message()
    headers["Retry-After"] = "7"

    def urlopen(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", headers, None)
        if len(calls) == 2:  # a date instead of seconds: the default wait
            date = Message()
            date["Retry-After"] = "Wed, 21 Oct 2026 07:28:00 GMT"
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", date, None)
        return io.BytesIO(b"ok")

    monkeypatch.setattr(weather.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(weather.time, "sleep", waits.append)

    assert weather.http_get("https://example.org") == b"ok"
    assert waits == [7.0, 40]


def test_the_csv_keeps_two_decimals_like_the_existing_files(tmp_path):
    (tmp_path / "metar").mkdir()
    (tmp_path / "era5_openmeteo").mkdir()
    for name in ("A.csv", "B.csv"):
        pd.DataFrame({"station": ["X"], "valid": ["2026-05-31 23:50"], "sknt": [5.0]}).to_csv(
            tmp_path / "metar" / name, index=False
        )
    (tmp_path / "era5_openmeteo" / "e.json").write_text(json.dumps(era5(["2026-05-31T23:00"], [400.0])))

    def get(url: str) -> bytes:
        if url.startswith(weather.IEM):
            return b"station,valid,sknt\nMMMX,2026-06-01 00:50,9.456\n"
        return json.dumps(era5(["2026-06-01T00:00"], [800.0])).encode()

    weather.run_fetch("2026-06-01", "2026-06-02", tmp_path, ("A.csv", "B.csv"), "e.json", get)

    assert (tmp_path / "metar" / "A.csv").read_text().splitlines()[1:] == [
        "MMMX,2026-06-01 00:50,9.46",
        "X,2026-05-31 23:50,5.00",
    ]


def test_a_failed_write_leaves_the_weather_files_as_they_were(tmp_path, monkeypatch):
    (tmp_path / "metar").mkdir()
    (tmp_path / "era5_openmeteo").mkdir()
    for name in ("A.csv", "B.csv"):
        pd.DataFrame({"station": ["X"], "valid": ["2026-05-31 23:50"], "sknt": [5.0]}).to_csv(
            tmp_path / "metar" / name, index=False
        )
    era5_file = tmp_path / "era5_openmeteo" / "e.json"
    era5_file.write_text(json.dumps(era5(["2026-05-31T23:00"], [400.0])))
    csv_before, json_before = (tmp_path / "metar" / "A.csv").read_text(), era5_file.read_text()

    def get(url: str) -> bytes:
        if url.startswith(weather.IEM):
            return b"station,valid,sknt\nMMMX,2026-06-01 00:50,9.00\n"
        return json.dumps(era5(["2026-06-01T00:00"], [800.0])).encode()

    def broken(self, path, *a, **k):
        Path(path).write_text("half")
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", broken)
    with pytest.raises(OSError):
        weather.run_fetch("2026-06-01", "2026-06-02", tmp_path, ("A.csv", "B.csv"), "e.json", get)
    assert (tmp_path / "metar" / "A.csv").read_text() == csv_before

    monkeypatch.undo()
    monkeypatch.setattr(weather, "write_text", lambda path, text: (_ for _ in ()).throw(OSError("full")))
    with pytest.raises(OSError):
        weather.run_fetch("2026-06-01", "2026-06-02", tmp_path, ("A.csv", "B.csv"), "e.json", get)
    assert era5_file.read_text() == json_before
