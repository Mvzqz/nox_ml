"""OpenAQ station data: matching to SIMAT stations, paging and the qc-simat table."""

import urllib.error
from email.message import Message

import pandas as pd
import pytest

from nox_ml.data import openaq

CATALOG = pd.DataFrame({"lat": [19.4, 19.5], "lon": [-99.1, -99.2]}, index=["MER", "CAM"])


def location(id_, lat, lon, provider=openaq.PROVIDER, parameters=("nox", "no2", "pm10")):
    return {
        "id": id_,
        "provider": {"name": provider},
        "coordinates": {"latitude": lat, "longitude": lon},
        "sensors": [{"id": id_ * 10 + k, "parameter": {"name": p}} for k, p in enumerate(parameters)],
    }


def test_sensors_are_matched_to_the_nearest_station_of_the_provider():
    locations = [
        location(1, 19.4005, -99.1005),  # MER, ~70 m
        location(2, 19.5, -99.2, provider="AirNow"),  # another feed
        location(3, 19.7, -99.5),  # far from every station
        location(4, 19.501, -99.2, parameters=("no", "o3")),  # CAM
    ]

    sensors = openaq.match_sensors(locations, CATALOG)

    assert sensors[["location", "station", "parameter"]].values.tolist() == [
        [1, "MER", "nox"],
        [1, "MER", "no2"],
        [4, "CAM", "no"],
        [4, "CAM", "o3"],
    ]
    assert bool((sensors["km"] < openaq.MAX_MATCH_KM).all())


def test_a_sensor_is_read_page_after_page():
    hours = pd.date_range("2025-03-01", periods=2500, freq="h")
    asked = []

    def get(path, params):
        asked.append(params["page"])
        chunk = hours[(params["page"] - 1) * openaq.PAGE : params["page"] * openaq.PAGE]
        return {
            "results": [
                {"period": {"datetimeFrom": {"utc": f"{h:%Y-%m-%dT%H:%M:%SZ}"}}, "value": 0.05} for h in chunk
            ]
        }

    table = openaq.sensor_hours(7, "2025-03-01", "2025-06-01", get)

    assert asked == [1, 2, 3]
    assert len(table) == 2500 and table["h"].iloc[0] == pd.Timestamp("2025-03-01")


def test_the_simat_table_is_in_ppb_stamped_at_the_end_of_the_hour():
    h = pd.Timestamp("2025-03-01 18:00")
    raw = pd.DataFrame(
        {
            "sensor": [1, 2, 3, 4, 5],
            "location": [1, 1, 9, 1, 1],
            "station": "MER",
            "parameter": ["nox", "no2", "nox", "no", "o3"],
            "h": h,
            "value": [0.050, 0.030, 0.070, -0.001, 0.040],
        }
    )

    table = openaq.simat_table(raw)

    (row,) = table.to_dict("records")
    assert row["NOX"] == pytest.approx(60.0)  # two locations of the station: their mean
    assert row["NO2"] == pytest.approx(30.0) and pd.isna(row["NO"])  # negative: dropped
    assert row["O3"] == pytest.approx(40.0)
    assert row["utc"] == h + pd.Timedelta(hours=1)
    assert row["local"] == pd.Timestamp("2025-03-01 13:00")


def test_the_key_is_required(monkeypatch):
    monkeypatch.delenv(openaq.KEY_VARIABLE, raising=False)

    with pytest.raises(RuntimeError, match=openaq.KEY_VARIABLE):
        openaq.api_get("/locations", {})


def test_a_sensor_the_server_keeps_failing_on_is_skipped_with_a_warning():
    locations = [location(1, 19.4005, -99.1005, parameters=("nox", "no2"))]

    def get(path, params):
        if path == "/locations":
            return {"results": locations}
        if path == "/sensors/10/measurements":  # the nox sensor
            raise urllib.error.HTTPError(path, 500, "Internal Server Error", Message(), None)
        return {"results": [{"period": {"datetimeFrom": {"utc": "2026-03-01T18:00:00Z"}}, "value": 0.02}]}

    with pytest.warns(UserWarning, match="sensor 10"):
        raw = openaq.fetch("2026-03-01", "2026-03-02", CATALOG, get)

    assert raw["parameter"].tolist() == ["no2"]
