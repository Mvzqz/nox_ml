# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import io

import numpy as np
import pandas as pd
import pytest
from conftest import STATIONS, UNITS, nox_long, simat_hours, write_simat_zip

from nox_ml.data import simat


def table_bytes(rows: str) -> io.BytesIO:
    header = "\n".join(['"city: x","","","",""'] * 9)
    return io.BytesIO(f'{header}\n"date","id_station","id_parameter","value","unit"\n{rows}'.encode())


def hourly(values, start="2023-01-02 01:00") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="h"), dtype=float)


# --- parsing ----------------------------------------------------------------------------------------------


def test_parse_table_skips_nine_header_lines_and_reads_column_names_from_line_ten():
    df = simat.parse_table(table_bytes('"2024-01-01 01:00:00","MER","NO2","12.5","1"\n'))

    assert list(df.columns) == ["id_station", "id_parameter", "value", "unit", "local", "utc"]
    assert df.loc[0, "value"] == 12.5


def test_parse_table_converts_local_time_to_utc_adding_six_hours():
    df = simat.parse_table(table_bytes('"2024-01-01 08:00:00","MER","NO2","1","1"\n'))

    assert df.loc[0, "utc"] == pd.Timestamp("2024-01-01 14:00")


def test_parse_table_reads_hour_24_as_midnight_of_the_next_day():
    df = simat.parse_table(table_bytes('"2024-01-02 00:00:00","MER","NO2","1","1"\n'))

    assert df.loc[0, "local"] == pd.Timestamp("2024-01-02 00:00")
    assert df.loc[0, "utc"] == pd.Timestamp("2024-01-02 06:00")


def test_parse_table_keeps_empty_values_as_nan():
    df = simat.parse_table(table_bytes('"2024-01-01 01:00:00","MER","NO2","","1"\n'))

    assert np.isnan(df.loc[0, "value"])


def test_parse_catalog_reads_latin1_names_and_marks_stations_inside_the_domain():
    text = (
        "Catalogo,,,\ncve_estac,nom_estac,longitud,latitud\nMER,Merced,-99.12,19.42\nXAL,Xalapa,-96.9,19.5\n"
    )
    cat = simat.parse_catalog(io.BytesIO(text.replace("Merced", "Mercéd").encode("latin1")))

    assert cat.loc[0, "nom_estac"] == "Mercéd"
    assert dict(zip(cat["station"], cat["in_domain"], strict=True)) == {"MER": True, "XAL": False}


def test_parse_units_maps_id_to_symbol():
    units = simat.parse_units(io.BytesIO(UNITS.encode("latin1")))

    assert units[3] == "m/s"
    assert units[4] == "°"


# --- cleaning ---------------------------------------------------------------------------------------------


def long_rows(rows):
    df = pd.DataFrame(rows, columns=["id_station", "id_parameter", "local", "value"])
    df["local"] = pd.to_datetime(df["local"])
    df["utc"] = df["local"] + pd.Timedelta(hours=6)
    return df


def test_clean_nox_turns_negative_values_into_nan():
    pol = long_rows([("MER", "NOX", "2024-01-01 10:00", -3.0), ("MER", "NO", "2024-01-01 10:00", 4.0)])

    wide = simat.clean_nox(pol)

    assert np.isnan(wide.loc[0, "NOX"])
    assert wide.loc[0, "NO"] == 4.0


def test_clean_nox_flags_hours_above_250_ppb_without_dropping_them():
    pol = long_rows([("MER", "NOX", "2024-01-01 10:00", 300.0), ("MER", "NOX", "2024-01-01 11:00", 250.0)])

    wide = simat.clean_nox(pol)

    assert wide["flag_hi"].tolist() == [True, False]
    assert wide["NOX"].tolist() == [300.0, 250.0]


def test_clean_nox_ignores_other_pollutants():
    pol = long_rows([("MER", "CO", "2024-01-01 10:00", 1.0), ("MER", "NOX", "2024-01-01 10:00", 9.0)])

    assert list(simat.clean_nox(pol).columns) == ["id_station", "local", "utc", "NO", "NO2", "NOX", "flag_hi"]


def test_stuck_mask_flags_runs_longer_than_six_hours():
    mask = simat.stuck_mask(hourly([5.0] * 7 + [6.0]))

    assert mask.tolist() == [True] * 7 + [False]


def test_stuck_mask_keeps_a_six_hour_run():
    assert not simat.stuck_mask(hourly([5.0] * 6 + [6.0])).any()


def test_stuck_mask_ignores_flat_series_at_or_below_one_ppb():
    assert not simat.stuck_mask(hourly([1.0] * 10)).any()


def test_stuck_mask_never_flags_missing_hours():
    values = hourly([5.0] * 7 + [np.nan] * 3 + [8.0])

    mask = simat.stuck_mask(values)

    assert mask.tolist() == [True] * 7 + [False] * 4


def test_stuck_hours_by_station_counts_each_station_separately():
    local = pd.date_range("2024-01-01", periods=8, freq="h")
    wide = pd.concat(
        [
            pd.DataFrame({"id_station": "TAH", "local": local, "NOX": 7.0}),
            pd.DataFrame({"id_station": "MER", "local": local, "NOX": np.arange(8) + 10.0}),
        ]
    )

    assert simat.stuck_hours_by_station(wide).to_dict() == {"MER": 0, "TAH": 8}


def stuck_wide() -> pd.DataFrame:
    """TAH is stuck at 7 ppb for 8 hours among varying readings; MER varies throughout."""
    local = pd.date_range("2024-01-01", periods=12, freq="h")
    tah = np.r_[[3.0, 4.0], [7.0] * 8, [5.0, 6.0]]
    wide = pd.concat(
        [
            pd.DataFrame({"id_station": s, "local": local, "NO": v - 1, "NO2": v - 2, "NOX": v})
            for s, v in (("TAH", tah), ("MER", np.arange(12) + 10.0))
        ],
        ignore_index=True,
    )
    wide["flag_hi"] = wide["NOX"] > simat.HIGH_NOX_PPB
    return wide


def test_mask_stuck_sets_nox_to_nan_only_in_the_stuck_run():
    masked = simat.mask_stuck(stuck_wide())

    tah = masked[masked["id_station"] == "TAH"]
    assert tah["NOX"].isna().tolist() == [False] * 2 + [True] * 8 + [False] * 2
    assert tah["NOX"].dropna().tolist() == [3.0, 4.0, 5.0, 6.0]


def test_mask_stuck_masks_no_and_no2_together_with_nox():
    masked = simat.mask_stuck(stuck_wide())

    stuck = masked[(masked["id_station"] == "TAH") & masked["NOX"].isna()]
    assert len(stuck) == 8
    assert stuck[["NO", "NO2"]].isna().all().all()


def test_mask_stuck_leaves_other_stations_untouched():
    wide = stuck_wide()

    masked = simat.mask_stuck(wide)

    mer = wide["id_station"] == "MER"
    pd.testing.assert_frame_equal(masked[mer], wide[mer])


def test_mask_stuck_keeps_the_input_unchanged():
    wide = stuck_wide()
    before = wide.copy()

    simat.mask_stuck(wide)

    pd.testing.assert_frame_equal(wide, before)


def test_mask_stuck_is_a_no_op_without_stuck_runs():
    wide = stuck_wide()
    wide = wide[wide["id_station"] == "MER"].reset_index(drop=True)

    pd.testing.assert_frame_equal(simat.mask_stuck(wide), wide)


def test_mask_stuck_leaves_nothing_for_the_stuck_check_to_report():
    masked = simat.mask_stuck(stuck_wide())

    assert simat.stuck_hours_by_station(masked).to_dict() == {"MER": 0, "TAH": 0}


def test_mask_stuck_clears_flag_hi_on_masked_hours():
    wide = stuck_wide()
    wide.loc[(wide["id_station"] == "TAH") & (wide["NOX"] == 7.0), ["NOX", "flag_hi"]] = [300.0, True]

    assert not simat.mask_stuck(wide)["flag_hi"].any()


def wind_wide(local, wsp, wdr=90.0):
    df = pd.DataFrame({"id_station": "MER", "local": pd.to_datetime(local), "WSP": wsp, "WDR": wdr})
    df["utc"] = df["local"] + pd.Timedelta(hours=6)
    return df


def test_fix_wind_speed_converts_2024_from_mph_to_ms():
    w = simat.fix_wind_speed(wind_wide(["2024-03-01 12:00"], 22.37))

    assert w.loc[0, "WSP"] == pytest.approx(10.0)
    assert w.loc[0, "WSP_raw"] == 22.37
    assert w.loc[0, "wsp_fix_mph"]


def test_fix_wind_speed_leaves_2023_untouched():
    w = simat.fix_wind_speed(wind_wide(["2023-12-31 23:00"], 3.0))

    assert w.loc[0, "WSP"] == 3.0
    assert not w.loc[0, "wsp_fix_mph"]


def test_fix_wind_speed_switches_on_local_new_year_not_utc():
    # 2023-12-31 20:00 local is already 2024-01-01 02:00 UTC but still belongs to the 2023 (m/s) data
    w = simat.fix_wind_speed(wind_wide(["2023-12-31 20:00", "2024-01-01 00:00"], 3.0))

    assert w["wsp_fix_mph"].tolist() == [False, True]


def test_fix_wind_speed_does_not_touch_direction_and_flags_calms():
    w = simat.fix_wind_speed(
        wind_wide(["2024-01-01 12:00", "2024-01-01 13:00"], [1.0, 22.37], wdr=[45.0, 90.0])
    )

    assert w["WDR"].tolist() == [45.0, 90.0]
    assert w["calm"].tolist() == [True, False]  # 1.0 mph = 0.45 m/s < 0.5


def test_fix_wind_speed_keeps_missing_speed_as_nan():
    w = simat.fix_wind_speed(wind_wide(["2024-01-01 12:00"], np.nan))

    assert np.isnan(w.loc[0, "WSP"])
    assert not w.loc[0, "calm"]


def test_clean_wind_pivots_speed_and_direction_to_columns():
    met = long_rows([("MER", "WSP", "2024-01-01 12:00", 4.474), ("MER", "WDR", "2024-01-01 12:00", 180.0)])

    w = simat.clean_wind(met)

    assert w.loc[0, "WSP"] == pytest.approx(2.0)
    assert w.loc[0, "WDR"] == 180.0


def test_mean_wind_direction_of_steady_east_wind_is_90():
    assert simat.mean_wind_direction(pd.Series([2.0, 3.0]), pd.Series([90.0, 90.0])) == pytest.approx(90.0)


def test_mean_wind_direction_wraps_around_north():
    direction = simat.mean_wind_direction(pd.Series([2.0, 2.0]), pd.Series([350.0, 10.0]))

    assert min(direction, 360 - direction) == pytest.approx(0.0, abs=1e-6)


# --- completeness and coverage ------------------------------------------------------------------------------


def test_afternoon_completeness_counts_only_dry_season_afternoon_hours_of_domain_stations():
    afternoon = pd.date_range("2024-01-10 12:00", periods=6, freq="h")
    full = pd.DataFrame({"id_station": "MER", "local": afternoon, "NOX": 10.0})
    gappy = pd.DataFrame({"id_station": "AJM", "local": afternoon, "NOX": [10.0, 10.0, 10.0] + [np.nan] * 3})
    other_hours = pd.DataFrame(
        {"id_station": "MER", "local": pd.date_range("2024-01-10 00:00", periods=6, freq="h"), "NOX": np.nan}
    )
    wet_season = pd.DataFrame(
        {"id_station": "MER", "local": pd.date_range("2024-07-10 12:00", periods=6, freq="h"), "NOX": 10.0}
    )
    outside = pd.DataFrame({"id_station": "XXX", "local": afternoon, "NOX": 10.0})
    wide = pd.concat([full, gappy, other_hours, wet_season, outside])

    comp = simat.afternoon_completeness(wide, {"MER", "AJM"})

    assert comp.index.astype(str).tolist() == ["2024-01"]
    assert comp.loc[comp.index[0]].to_dict() == {"AJM": 0.5, "MER": 1.0}


def wind_hours(n_valid: int, hour: str) -> pd.DataFrame:
    stations = [f"S{i:02d}" for i in range(12)]
    wsp = [2.0] * n_valid + [np.nan] * (12 - n_valid)
    return pd.DataFrame({"id_station": stations, "local": pd.Timestamp(hour), "WSP": wsp, "WDR": 90.0})


def test_wind_station_coverage_requires_ten_valid_stations_per_hour():
    w = pd.concat([wind_hours(10, "2024-01-10 12:00"), wind_hours(9, "2024-01-10 13:00")])

    cov = simat.wind_station_coverage(w, {f"S{i:02d}" for i in range(12)})

    row = cov.iloc[0]
    assert row["share_hours_ok"] == 0.5
    assert row["median_stations"] == 9.5


# --- quality checks -----------------------------------------------------------------------------------------


def clean_nox_fixture():
    pol = nox_long(simat_hours()).rename(columns={"date": "local"})
    pol["utc"] = pol["local"] + pd.Timedelta(hours=6)
    return pol, simat.clean_nox(pol)


def catalog():
    return pd.DataFrame({"station": list(STATIONS), "in_domain": True})


UNIT_SYMBOLS = pd.Series({1: "ppb", 3: "m/s", 4: "°"})


def test_nox_checks_pass_on_clean_realistic_data():
    pol, wide = clean_nox_fixture()

    checks = simat.nox_checks(pol, wide, catalog(), UNIT_SYMBOLS)

    failed = [str(c) for c in checks if c.ok is False]
    assert failed == []


def test_nox_checks_fail_on_station_missing_from_the_catalog():
    pol, wide = clean_nox_fixture()

    checks = simat.nox_checks(pol, wide, catalog().iloc[:1], UNIT_SYMBOLS)

    assert [c.message for c in checks if c.ok is False] == ["Stations in catalog (unknown: ['AJM'])"]


def test_nox_checks_fail_when_units_are_not_ppb():
    pol, wide = clean_nox_fixture()
    pol["unit"] = 3

    checks = simat.nox_checks(pol, wide, catalog(), UNIT_SYMBOLS)

    assert any(c.ok is False and c.message.startswith("NO/NO2/NOX units") for c in checks)


def test_nox_checks_report_stuck_sensor_hours():
    pol, wide = clean_nox_fixture()
    wide.loc[wide["id_station"] == "MER", "NOX"] = 30.0

    checks = simat.nox_checks(pol, wide, catalog(), UNIT_SYMBOLS)

    stuck = next(c for c in checks if "identical value" in c.message)
    assert stuck.ok is False
    assert "MER:" in stuck.message


def test_nox_checks_fail_when_sunday_is_not_lower_than_weekdays():
    pol, wide = clean_nox_fixture()
    wide.loc[wide["local"].dt.day_of_week == 6, "NOX"] *= 10

    checks = simat.nox_checks(pol, wide, catalog(), UNIT_SYMBOLS)

    assert any(c.ok is False and c.message.startswith("Sunday") for c in checks)


def test_wind_checks_pass_after_the_mph_correction():
    met = long_rows([("MER", "WSP", "2024-01-01 12:00", 6.711), ("MER", "WDR", "2024-01-01 12:00", 90.0)])
    met["unit"] = met["id_parameter"].map({"WSP": 3, "WDR": 4})
    w = simat.clean_wind(met)

    checks = simat.wind_checks(met, w, UNIT_SYMBOLS)

    assert [c for c in checks if c.ok is False] == []


def test_wind_checks_fail_when_speed_is_implausibly_high():
    met = long_rows([("MER", "WSP", "2023-01-01 12:00", 9.0), ("MER", "WDR", "2023-01-01 12:00", 90.0)])
    met["unit"] = met["id_parameter"].map({"WSP": 3, "WDR": 4})

    checks = simat.wind_checks(met, simat.clean_wind(met), UNIT_SYMBOLS)

    assert any(c.ok is False and "Hourly median WSP" in c.message for c in checks)


# --- I/O ----------------------------------------------------------------------------------------------------


def test_load_table_reads_zip_files_named_csv_gz_for_several_years(tmp_path):
    for year in (2023, 2024):
        hours = pd.date_range(f"{year}-01-01 01:00", periods=2, freq="h")
        write_simat_zip(tmp_path / f"contaminantes_{year}.csv.gz", nox_long(hours))

    df = simat.load_table(tmp_path, "contaminantes", [2023, 2024])

    assert sorted(df["local"].dt.year.unique()) == [2023, 2024]
    assert df["utc"].min() == pd.Timestamp("2023-01-01 07:00")


def test_run_qc_writes_clean_tables_and_applies_the_wind_correction(simat_dir, tmp_path):
    out = tmp_path / "interim"

    checks = simat.run_qc(simat_dir, out, [2024])

    nox = pd.read_parquet(out / "simat_nox.parquet")
    wind = pd.read_parquet(out / "simat_wind.parquet")
    assert {"NO", "NO2", "NOX", "flag_hi", "utc"} <= set(nox.columns)
    assert wind["WSP"].round(3).unique().tolist() == [3.0]
    assert wind["WSP_raw"].round(3).unique().tolist() == [6.711]
    assert (out / "simat_nox_completeness.csv").exists()
    assert [str(c) for c in checks if c.ok is False] == []


def test_run_qc_lists_the_stations_of_the_catalog_inside_the_domain(simat_dir, tmp_path):
    checks = simat.run_qc(simat_dir, tmp_path, [2024])

    assert "Catalog stations inside the domain: 2" in [c.message for c in checks]


def write_stuck_mer(simat_dir, hours=12, value=40.0):
    """Overwrite the first `hours` NOX readings of MER in the standard fixture with one flat run."""
    pol = nox_long(simat_hours())
    stuck = (pol["id_station"] == "MER") & (pol["id_parameter"] == "NOX")
    first = pol.index[stuck][:hours]
    pol.loc[first, "value"] = value
    write_simat_zip(simat_dir / "contaminantes_2024.csv.gz", pol)


def test_run_qc_masks_stuck_hours_by_default_and_still_reports_them(simat_dir, tmp_path):
    write_stuck_mer(simat_dir)

    checks = simat.run_qc(simat_dir, tmp_path, [2024])

    nox = pd.read_parquet(tmp_path / "simat_nox.parquet")
    assert nox.loc[nox["id_station"] == "MER", "NOX"].isna().sum() == 12
    assert nox.loc[nox["id_station"] == "AJM", "NOX"].notna().all()
    messages = [c.message for c in checks]
    assert any("identical value: 12 (MER:12)" in m for m in messages)
    assert "Stuck NOX hours set to NaN: 12" in messages


def test_run_qc_keeps_stuck_hours_when_masking_is_off(simat_dir, tmp_path):
    write_stuck_mer(simat_dir)

    simat.run_qc(simat_dir, tmp_path, [2024], mask=False)

    nox = pd.read_parquet(tmp_path / "simat_nox.parquet")
    assert nox.loc[nox["id_station"] == "MER", "NOX"].notna().all()
