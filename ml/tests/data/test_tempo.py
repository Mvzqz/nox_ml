# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import numpy as np
import pandas as pd
import pytest

from nox_ml.data import simat, tempo

NAME = "TEMPO_NO2_L2_V04_20231101T185519Z_S009G06_zmvm.nc"
VCD_CORE, VCD_RURAL = 2.0e16, 0.8e16


def test_granule_time_reads_scan_start_in_utc_from_the_file_name():
    assert tempo.granule_time(NAME) == pd.Timestamp("2023-11-01 18:55:19")


def test_in_period_includes_the_whole_last_day_and_excludes_the_next():
    last_second = pd.Timestamp("2023-12-31 23:59:59")

    assert tempo.in_period(last_second, "2023-11-01", "2023-12-31")
    assert not tempo.in_period(last_second + pd.Timedelta(seconds=1), "2023-11-01", "2023-12-31")
    assert not tempo.in_period(pd.Timestamp("2023-10-31 23:59:59"), "2023-11-01", "2023-12-31")


def pixels(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["granule", "utc", "lat", "lon", "vcd", "qf", "cf"])
    df["utc"] = pd.to_datetime(df["utc"])
    df["units"] = "molecules/cm^2"
    return df


def test_clean_pixels_drops_pixels_outside_the_domain():
    px = pixels(
        [
            ("g", "2023-11-01 20:00", 19.4, -99.1, 1e16, 0, 0.1),
            ("g", "2023-11-01 20:00", 21.0, -99.1, 1e16, 0, 0.1),
        ]
    )

    assert tempo.clean_pixels(px)["lat"].tolist() == [19.4]


@pytest.mark.parametrize(
    ("vcd", "qf", "cf", "valid"),
    [
        (1e16, 0, 0.19, True),
        (1e16, 1, 0.1, False),  # quality flag
        (1e16, 0, 0.2, False),  # cloud fraction at the limit is rejected
        (np.nan, 0, 0.1, False),  # missing column
        (1e16, 0, np.nan, False),  # missing cloud fraction
    ],
)
def test_clean_pixels_marks_valid_only_with_good_flag_low_clouds_and_a_column(vcd, qf, cf, valid):
    px = tempo.clean_pixels(pixels([("g", "2023-11-01 20:00", 19.4, -99.1, vcd, qf, cf)]))

    assert px["valid"].tolist() == [valid]


def test_clean_pixels_adds_local_time_six_hours_before_utc():
    px = tempo.clean_pixels(pixels([("g", "2023-11-01 03:00", 19.4, -99.1, 1e16, 0, 0.1)]))

    assert px.loc[px.index[0], "local"] == pd.Timestamp("2023-10-31 21:00")


def granules(n=4) -> pd.DataFrame:
    """n granules over consecutive days: a core pixel, a rural pixel and a cloudy pixel each."""
    rows = []
    for i in range(n):
        t = f"2023-11-0{i + 1} 20:00"
        rows += [
            (f"g{i}", t, 19.43, -99.1, VCD_CORE, 0, 0.1),
            (f"g{i}", t, 19.70, -98.9, VCD_RURAL, 0, 0.1),
            (f"g{i}", t, 19.60, -99.3, 3e16, 0, 0.9),
        ]
    return tempo.clean_pixels(pixels(rows))


def test_pixel_checks_pass_for_a_clear_scene_with_a_urban_core():
    px = granules()

    checks = tempo.pixel_checks(px)

    assert [str(c) for c in checks if c.ok is False] == []
    ratio = next(c for c in checks if c.message.startswith("Core / surroundings"))
    assert "2.50x" in ratio.message


def test_pixel_checks_fail_when_units_are_unexpected():
    px = granules()
    px["units"] = "mol/m^2"

    assert any(c.ok is False and c.message.startswith("Units") for c in tempo.pixel_checks(px))


def test_pixel_checks_fail_when_the_core_is_not_more_polluted_than_its_surroundings():
    px = granules()
    px.loc[px["vcd"] == VCD_CORE, "vcd"] = VCD_RURAL

    assert any(c.ok is False and c.message.startswith("Core / surroundings") for c in tempo.pixel_checks(px))


def test_pixel_checks_fail_when_most_granules_are_cloudy():
    px = granules()
    px["cf"] = 0.9
    px["valid"] = False
    px.loc[px.index[:1], ["cf", "valid"]] = [0.1, True]

    assert any(c.ok is False and c.message.startswith("Granules with") for c in tempo.pixel_checks(px))


STATION_XY = pd.DataFrame({"station": ["MER", "AJM"], "lon": [-99.12, -99.16], "lat": [19.40, 19.27]})


def test_match_stations_pairs_the_nearest_pixel_with_the_hour_stamped_one_hour_later():
    valid = (
        granules()[lambda d: d["valid"]]
        .iloc[:1]
        .assign(lat=19.405, lon=-99.12, utc=pd.Timestamp("2023-11-01 19:30"))
    )
    no2 = pd.DataFrame(
        {
            "id_station": "MER",
            "utc": [pd.Timestamp("2023-11-01 20:00"), pd.Timestamp("2023-11-01 19:00")],
            "NO2": [30.0, 99.0],
        }
    )

    pairs = tempo.match_stations(valid, no2, STATION_XY)

    assert pairs[["station", "no2_ppb"]].to_dict("records") == [{"station": "MER", "no2_ppb": 30.0}]
    assert pairs.loc[0, "vcd"] == VCD_CORE


def test_match_stations_skips_stations_with_no_pixel_within_three_kilometres():
    valid = (
        granules()[lambda d: d["valid"]]
        .iloc[:1]
        .assign(lat=19.43, lon=-99.12, utc=pd.Timestamp("2023-11-01 19:30"))
    )
    no2 = pd.DataFrame(
        {"id_station": "MER", "utc": pd.Timestamp("2023-11-01 20:00"), "NO2": [30.0]}
    )  # ~3.3 km away

    assert tempo.match_stations(valid, no2, STATION_XY).empty


def test_match_stations_ignores_unknown_stations_and_missing_no2():
    valid = (
        granules()[lambda d: d["valid"]]
        .iloc[:1]
        .assign(lat=19.40, lon=-99.12, utc=pd.Timestamp("2023-11-01 19:30"))
    )
    t = pd.Timestamp("2023-11-01 20:00")
    no2 = pd.DataFrame({"id_station": ["MER", "ZZZ"], "utc": [t, t], "NO2": [np.nan, 30.0]})

    assert tempo.match_stations(valid, no2, STATION_XY).empty


def test_match_stations_picks_the_closest_of_two_pixels():
    base = granules()[lambda d: d["valid"]].iloc[:2].assign(utc=pd.Timestamp("2023-11-01 19:30"))
    valid = base.assign(lat=[19.415, 19.402], lon=-99.12, vcd=[5e15, 7e15])
    no2 = pd.DataFrame({"id_station": "MER", "utc": pd.Timestamp("2023-11-01 20:00"), "NO2": [30.0]})

    assert tempo.match_stations(valid, no2, STATION_XY)["vcd"].tolist() == [7e15]


def test_pair_checks_fail_without_pairs():
    empty = pd.DataFrame(columns=["granule", "station", "no2_ppb", "vcd"])

    assert [c.ok for c in tempo.pair_checks(empty)] == [False]


def test_pair_checks_report_positive_correlation_between_tempo_and_stations():
    n = 12
    pairs = pd.DataFrame(
        {
            "granule": ["g1"] * 6 + ["g2"] * 6,
            "station": [f"S{i % 6}" for i in range(n)],
            "no2_ppb": np.arange(n, dtype=float),
            "vcd": np.arange(n) * 1e15 + 1e16,
        }
    )

    checks = tempo.pair_checks(pairs)

    assert checks[0].ok is True
    assert "r = 1.00" in checks[0].message
    assert "2 granules" in checks[1].message


# --- I/O ----------------------------------------------------------------------------------------------------


def test_read_granule_returns_one_row_per_pixel_with_masked_values_as_nan(tmp_path, write_tempo_granule):
    path = write_tempo_granule(
        tmp_path / NAME, lat=[19.4, 19.5], lon=[-99.1, -99.2], vcd=[1e16, np.nan], qf=0
    )

    df = tempo.read_granule(path)

    assert len(df) == 2
    assert df["vcd"].iloc[0] == 1e16
    assert np.isnan(df["vcd"].iloc[1])
    assert df["utc"].unique().tolist() == [pd.Timestamp("2023-11-01 18:55:19")]
    assert df["units"].unique().tolist() == ["molecules/cm^2"]


def test_load_pixels_keeps_only_granules_inside_the_period(tmp_path, write_tempo_granule):
    write_tempo_granule(tmp_path / NAME, lat=[19.4], lon=[-99.1], vcd=[1e16])
    write_tempo_granule(tmp_path / NAME.replace("20231101", "20231201"), lat=[19.4], lon=[-99.1], vcd=[1e16])

    px = tempo.load_pixels(tmp_path, "2023-11-01", "2023-11-30")

    assert px["utc"].dt.month.unique().tolist() == [11]


def test_load_pixels_fails_clearly_when_there_are_no_granules(tmp_path):
    with pytest.raises(FileNotFoundError, match="No TEMPO granules"):
        tempo.load_pixels(tmp_path, "2023-11-01", "2023-11-30")


def test_run_qc_writes_pixels_and_pairs_them_with_simat_stations(tmp_path, simat_dir, write_tempo_granule):
    out, raw = tmp_path / "interim", tmp_path / "tempo"
    raw.mkdir()
    simat.run_qc(simat_dir, out, [2024])  # writes simat_nox.parquet
    # scan at 19:30 UTC = 13:30 local; MER NO2 stamped 14:00 local = 20:00 UTC
    scan = "TEMPO_NO2_L2_V04_20240102T193000Z_S011G06_zmvm.nc"
    write_tempo_granule(raw / scan, lat=[19.40, 19.60], lon=[-99.12, -99.0], vcd=[2e16, 1e16])

    checks = tempo.run_qc(raw, out, simat.load_catalog(simat_dir), "2024-01-02", "2024-01-02")

    stored = pd.read_parquet(out / "tempo_pixels_2024-01-02_2024-01-02.parquet")
    assert len(stored) == 2
    assert "units" not in stored.columns
    assert any("hour-station pairs, n=1" in c.message for c in checks)
