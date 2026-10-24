import numpy as np
import pandas as pd
import pytest

from nox_ml.data.inputs import assemble, domain_wind, hourly_pbl, station_nox


def nox_table(rows):
    """Rows (station, local label, NOX, NO2); utc is local + 6 h and ``hour`` the hour of the label."""
    df = pd.DataFrame(rows, columns=["id_station", "local", "NOX", "NO2"])
    df["local"] = pd.to_datetime(df["local"])
    df["utc"] = df["local"] + pd.Timedelta(hours=6)
    df["hour"] = df["local"].dt.hour
    return df


def test_station_nox_keeps_the_window_and_labels_the_start_of_the_hour_in_utc():
    nox = nox_table(
        [
            ("AAA", "2023-11-01 12:00", 30.0, 20.0),  # in
            ("AAA", "2023-11-01 18:00", 30.0, 20.0),  # hour label out of 12-17
            ("AAA", "2023-10-31 13:00", 30.0, 20.0),  # day before
            ("AAA", "2023-11-02 17:00", 30.0, 20.0),  # last day, last hour: in
            ("ZZZ", "2023-11-01 13:00", 30.0, 20.0),  # not in the catalog
        ]
    )

    rows, _ = station_nox(nox, ["AAA"], "2023-11-01", "2023-11-02", (12, 17))

    assert list(rows["h"]) == [pd.Timestamp("2023-11-01 17:00"), pd.Timestamp("2023-11-02 22:00")]


def test_station_nox_ratio_uses_only_rows_with_both_values_and_drops_the_rows_without_nox():
    nox = nox_table(
        [
            ("AAA", "2023-11-01 12:00", 40.0, 20.0),
            ("AAA", "2023-11-01 13:00", 60.0, 40.0),
            ("AAA", "2023-11-01 14:00", np.nan, 500.0),  # NO2 only: not in the ratio
            ("AAA", "2023-11-01 15:00", 50.0, np.nan),  # NOx only: kept, not in the ratio
        ]
    )

    rows, ratio = station_nox(nox, ["AAA"], "2023-11-01", "2023-11-01", (12, 17))

    assert ratio == pytest.approx(60 / 100)
    assert list(rows["NOX"]) == [40.0, 60.0, 50.0]


def test_domain_wind_is_the_plain_mean_of_the_components_that_the_wind_blows_towards():
    utc = pd.Timestamp("2023-11-01 19:00")
    wind = pd.DataFrame(
        {
            "id_station": ["AAA", "BBB", "ZZZ", "CCC"],
            "utc": [utc] * 4,
            "WSP": [2.0, 4.0, 9.0, np.nan],
            "WDR": [90.0, 0.0, 0.0, 10.0],  # from the east, from the north
        }
    )

    w = domain_wind(wind, ["AAA", "BBB", "CCC"])

    assert w.index.tolist() == [pd.Timestamp("2023-11-01 18:00")]
    assert w.loc[w.index[0], "u"] == pytest.approx((-2.0 + 0.0) / 2)
    assert w.loc[w.index[0], "v"] == pytest.approx((0.0 - 4.0) / 2)


def test_hourly_pbl_fills_gaps_averages_with_the_next_hour_and_floors():
    index = pd.date_range("2023-11-01", periods=5, freq="h")
    filled = pd.Series([1000.0, np.nan, 100.0, 100.0, np.nan], index=index)
    era5 = pd.Series([0.0, 2000.0, 0.0, 0.0, np.nan], index=index)

    pbl = hourly_pbl(filled, era5)

    # filled, then ERA5: 1000, 2000, 100, 100, and nothing at 04 h (its median is NaN too)
    assert pbl.iloc[0] == pytest.approx(1500.0)
    assert pbl.iloc[1] == pytest.approx(1050.0)
    assert pbl.iloc[2] == 200.0  # (100 + 100) / 2 = 100, floored
    assert np.isnan(pbl.iloc[3])  # the next hour is missing
    assert np.isnan(pbl.iloc[4])


def test_hourly_pbl_uses_the_month_hour_median_when_nothing_else_has_the_hour():
    index = pd.date_range("2023-11-01", periods=48, freq="h")
    filled = pd.Series(np.where(index.hour == 12, 800.0, 400.0), index=index)
    filled.iloc[36] = np.nan  # day 2, 12 h
    pbl = hourly_pbl(filled, pd.Series(dtype=float))

    # the gap takes the median of its month-hour (800) and is averaged with the next hour (400)
    assert pbl.iloc[36] == pytest.approx((800.0 + 400.0) / 2)


def test_assemble_keeps_hours_with_station_rows_wind_and_pbl_and_the_pixels_of_those_hours():
    t = [pd.Timestamp("2023-11-01 18:00") + pd.Timedelta(hours=i) for i in range(4)]
    nox = pd.DataFrame(
        {
            "h": [t[0], t[0], t[1], t[2], t[3]],
            "id_station": ["AAA", "BBB", "AAA", "AAA", "AAA"],
            "NOX": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )
    wind = pd.DataFrame({"u": 1.0, "v": 2.0}, index=pd.Index([t[0], t[1], t[3]]))  # no wind at t[2]
    pbl = pd.Series(900.0, index=[t[0], t[1], t[2]])  # no pbl at t[3]
    pixels = pd.DataFrame(
        {"h": [t[0], t[0], t[1]], "x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0], "vcd": [7.0, 8.0, 9.0]}
    ).assign(extra=0)  # t[1] has pixels; t[2] and t[3] would, but are dropped with their hours
    station_xy = pd.DataFrame({"x": [0.0, 10.0], "y": [0.0, 20.0]}, index=["AAA", "BBB"])

    hours, ids = assemble(nox, wind, pbl, pixels, station_xy)

    assert [h.hour for h in hours] == [t[0], t[1]]
    assert hours[0].wind == (1.0, 2.0)
    assert hours[0].pbl == 900.0
    assert ids[0].tolist() == ["AAA", "BBB"]
    assert hours[0].stations.x.tolist() == [0.0, 10.0]
    assert hours[0].nox.tolist() == [10.0, 20.0]
    assert hours[0].no2.tolist() == [7.0, 8.0]
    assert hours[1].no2.tolist() == [9.0]


def test_assemble_gives_empty_pixels_to_an_hour_without_them():
    t = pd.Timestamp("2023-11-01 18:00")
    nox = pd.DataFrame({"h": [t], "id_station": ["AAA"], "NOX": [10.0]})
    pixels = pd.DataFrame({"h": [], "x": [], "y": [], "vcd": []})

    hours, _ = assemble(
        nox,
        pd.DataFrame({"u": [1.0], "v": [1.0]}, index=[t]),
        pd.Series(900.0, index=[t]),
        pixels,
        pd.DataFrame({"x": [0.0], "y": [0.0]}, index=["AAA"]),
    )

    assert len(hours[0].pixels.x) == 0
    assert len(hours[0].no2) == 0


def test_without_station_removes_its_rows_from_every_hour(make_inputs):
    inputs = make_inputs()

    hours = inputs.without_station("BBB")

    assert all(len(h.nox) == 2 for h in hours)
    assert len(inputs.hours[0].nox) == 3  # the original is untouched
    assert hours[0].nox.tolist() == inputs.hours[0].nox[[0, 2]].tolist()
    assert hours[0].stations.x.tolist() == [0.0, 2000.0]
