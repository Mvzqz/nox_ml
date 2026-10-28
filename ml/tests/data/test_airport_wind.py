"""The domain wind from airport METAR reports."""

import numpy as np
import pandas as pd
import pytest

from nox_ml.data.inputs import KNOT_MS, airport_chemistry, airport_wind


def test_the_reports_of_an_hour_are_averaged_per_airport_then_over_airports_and_scaled():
    north = pd.DataFrame(
        {"valid": ["2025-03-01 18:46", "2025-03-01 18:55"], "sknt": [10.0, 10.0], "drct": [0.0, 0.0]}
    )
    east = pd.DataFrame(
        {"valid": ["2025-03-01 18:47", "2025-03-01 19:47"], "sknt": [10.0, np.nan], "drct": [90.0, 90.0]}
    )

    wind = airport_wind([north, east], factor=0.5)

    assert list(wind.index) == [pd.Timestamp("2025-03-01 18:00")]  # the report without speed is dropped
    speed = 10 * KNOT_MS
    # from the north blows south (v < 0), from the east blows west (u < 0); the mean of the two, halved
    assert wind.loc["2025-03-01 18:00", "u"] == pytest.approx(-speed / 2 * 0.5)
    assert wind.loc["2025-03-01 18:00", "v"] == pytest.approx(-speed / 2 * 0.5)


def test_the_airport_chemistry_takes_ozone_from_the_stations_and_weather_from_the_airports():
    stations = pd.DataFrame(
        {
            "id_station": ["MER", "CAM", "XXX"],
            "utc": pd.to_datetime(["2025-03-01 19:00"] * 3),  # end of the hour 18-19 UTC
            "O3": [40.0, 60.0, 500.0],
        }
    )
    metar = pd.DataFrame(
        {"valid": ["2025-03-01 18:46", "2025-03-01 18:55"], "tmpf": [68.0, 77.0], "relh": [30.0, 40.0]}
    )

    chemistry = airport_chemistry(stations, [metar], ["MER", "CAM"])

    row = chemistry.loc[pd.Timestamp("2025-03-01 18:00")]
    assert row["O3"] == pytest.approx(50.0)  # XXX is not one of the stations
    assert row["TMP"] == pytest.approx(22.5)  # 20 and 25 C
    assert row["RH"] == pytest.approx(35.0)
