# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from nox_ml.data import tempo
from nox_ml.models.pinn import equation
from nox_ml.validation import report_eda as eda


def nox_table(stations=("AAA", "BBB"), start="2023-11-06 01:00", end="2023-11-12 00:00") -> pd.DataFrame:
    """Hourly NO, NO2 and NOX of some stations, as the SIMAT QC leaves them (naive local and UTC)."""
    hours = pd.date_range(start, end, freq="h")
    rng = np.random.default_rng(0)
    frames = []
    for i, station in enumerate(stations):
        nox = 20 + 10 * i + 5 * rng.random(len(hours))
        frames.append(
            pd.DataFrame(
                {
                    "id_station": station,
                    "local": hours,
                    "utc": hours + pd.Timedelta(hours=6),
                    "NO": nox / 2,
                    "NO2": nox / 2,
                    "NOX": nox,
                    "flag_hi": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_in_window_keeps_the_days_and_hour_labels_asked_for_inclusive():
    nox = nox_table()

    part = eda.in_window(nox, ("2023-11-07", "2023-11-08"), (12, 17))

    assert part["local"].dt.normalize().nunique() == 2
    assert part["local"].dt.hour.min() == 12
    assert part["local"].dt.hour.max() == 17


def test_structure_counts_the_columns_by_kind_and_gives_the_period():
    nox = nox_table()

    row = eda.structure({"nox": nox}).iloc[0]

    assert (row["rows"], row["columns"], row["numeric"], row["datetime"], row["bool"]) == (
        len(nox),
        7,
        3,
        2,
        1,
    )
    assert row["start"] == nox["local"].min()


def test_structure_takes_the_period_of_a_series_indexed_by_time():
    pbl = pd.DataFrame({"pbl_m": [1.0, 2.0]}, index=pd.date_range("2023-11-01", periods=2, freq="h"))

    assert eda.structure({"pbl": pbl}).iloc[0]["end"] == pd.Timestamp("2023-11-01 01:00")


def test_column_types_reports_the_missing_share_and_the_range():
    df = pd.DataFrame({"a": [1.0, np.nan, 3.0, np.nan], "b": list("wxyz")})

    a, b = eda.column_types(df).to_dict("records")

    assert (a["missing_pct"], a["min"], a["max"]) == (50.0, 1.0, 3.0)
    assert pd.isna(b["min"])


def test_describe_matches_pandas():
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 100.0, np.nan]})

    row = eda.describe(df, ["x"]).loc["x"]

    assert row["median"] == 3.0
    assert row["count"] == 5
    assert row["missing_pct"] == pytest.approx(100 / 6)
    assert row["skew"] == pytest.approx(df["x"].skew())


def test_station_summary_orders_the_stations_by_mean_with_their_names():
    catalog = pd.DataFrame({"station": ["AAA", "BBB"], "nom_estac": ["Alfa", "Beta"]})

    out = eda.station_summary(nox_table(), catalog)

    assert list(out.index) == ["BBB", "AAA"]
    assert out.loc["BBB", "name"] == "Beta"


def test_the_completeness_matrix_counts_afternoon_hours_and_fills_the_days_without_rows():
    nox = nox_table(stations=("AAA",))
    nox.loc[(nox["local"].dt.day == 7) & nox["local"].dt.hour.between(12, 14), "NOX"] = np.nan

    matrix = eda.completeness_matrix(nox, ("2023-11-06", "2023-11-14"))

    assert matrix.loc["2023-11-07", "AAA"] == 0.5
    assert matrix.loc["2023-11-06", "AAA"] == 1.0
    assert matrix.loc["2023-11-14", "AAA"] == 0.0  # no rows that day


def test_missing_by_station_counts_the_hours_without_row_and_the_station_that_never_reports():
    nox = nox_table(stations=("AAA", "BBB", "CCC"), start="2023-11-06 01:00", end="2023-11-08 00:00")
    nox.loc[nox["id_station"] == "CCC", "NOX"] = np.nan  # an NO2-only station
    nox = nox[~((nox["id_station"] == "BBB") & (nox["local"].dt.day == 7))]  # no rows at all that day

    out = eda.missing_by_station(nox, ("2023-11-06", "2023-11-07"))

    assert out.to_dict() == {"CCC": 100.0, "BBB": 50.0, "AAA": 0.0}


def test_missing_by_hour_counts_the_stations_and_days_without_a_row():
    nox = nox_table(stations=("AAA",), start="2023-11-06 00:00", end="2023-11-07 23:00")
    nox = nox[nox["local"] != "2023-11-07 13:00"]

    out = eda.missing_by_hour(nox, ("2023-11-06", "2023-11-07"))

    assert out[13] == 50.0
    assert out[12] == 0.0


def test_network_outages_lists_the_days_with_few_stations():
    matrix = pd.DataFrame(
        {"AAA": [1.0, 1.0, 0.0], "BBB": [1.0, 0.0, 0.0]}, index=pd.date_range("2023-11-06", periods=3)
    )

    out = eda.network_outages(matrix, min_stations=2)

    assert list(out["stations"]) == [1, 0]


def test_missing_patterns_names_what_is_absent_together():
    nox = nox_table()
    nox.loc[:9, ["NO", "NOX"]] = np.nan

    patterns = eda.missing_patterns(nox).set_index("missing")

    assert patterns.loc["NO, NOX", "rows"] == 10
    assert patterns["share_pct"].sum() == pytest.approx(100)


def test_missing_by_variable_counts_each_column_of_each_table():
    frames = {"a": pd.DataFrame({"x": [1.0, np.nan]}), "b": pd.DataFrame({"y": [np.nan, np.nan, 1.0]})}

    out = eda.missing_by_variable(frames, {"a": ["x"], "b": ["y"]})

    assert list(out["missing"]) == [1, 2]
    assert out["missing_pct"].iloc[1] == pytest.approx(200 / 3)


@pytest.mark.parametrize("column", ["fuente", "source"])
def test_pbl_sources_counts_the_hours_by_month_and_source_in_either_language(column):
    index = pd.date_range("2023-12-31 22:00", periods=4, freq="h")
    pbl = pd.DataFrame({"pbl_m": 1.0, column: ["ERA5", "ERA5", "MERRA", "MERRA"]}, index=index)

    counts = eda.pbl_sources(pbl)

    assert counts.loc["2023-12", "ERA5"] == 2
    assert counts.loc["2024-01", "MERRA"] == 2


def test_robust_z_is_zero_when_most_values_are_equal():
    assert (eda.robust_z(pd.Series([2.0, 2.0, 2.0, 9.0])) == 0).all()


def test_outlier_table_finds_a_planted_spike_by_each_rule():
    nox = nox_table(stations=("AAA",))
    nox.loc[5, "NOX"] = 400.0

    row = eda.outlier_table(nox).loc["AAA"]

    assert (row["above_250_ppb"], row["above_tukey_fence"], row["robust_z_high"]) == (1, 1, 1)


def stuck_table_input() -> pd.DataFrame:
    nox = nox_table(stations=("AAA",))
    nox.loc[20:29, "NOX"] = 33.0  # ten hours of the same value
    return nox


def test_stuck_table_counts_the_run_before_the_mask_and_none_after():
    from nox_ml.data import simat

    raw = stuck_table_input()

    table = eda.stuck_table(raw, simat.mask_stuck(raw)).loc["AAA"]

    assert (table["stuck_hours"], table["stuck_after_mask"]) == (10, 0)


def test_masked_hours_counts_only_the_hours_of_the_period_that_the_mask_removed():
    from nox_ml.data import simat

    raw = stuck_table_input()
    day = raw.loc[20, "local"].strftime("%Y-%m-%d")

    inside = eda.masked_hours(raw, simat.mask_stuck(raw), (day, day))
    outside = eda.masked_hours(raw, simat.mask_stuck(raw), ("2023-11-10", "2023-11-11"))

    assert inside["AAA"] > 0
    assert outside.empty


def test_the_longest_stuck_run_is_found_with_its_station_and_length():
    raw = stuck_table_input()
    raw.loc[40:47, "NOX"] = 25.0  # a shorter one

    station, first, last, length = eda.longest_stuck_run(raw)

    assert (station, length) == ("AAA", 10)
    assert first == raw.loc[20, "local"]
    assert last == raw.loc[29, "local"]


def test_there_is_no_stuck_run_in_clean_data():
    assert eda.longest_stuck_run(nox_table()) is None
    assert eda.plot_stuck_example(nox_table()) is None


def wind_table() -> pd.DataFrame:
    local = pd.to_datetime(["2023-12-15 12:00", "2024-01-15 12:00", "2025-01-01 00:00"])
    return pd.DataFrame(
        {
            "local": local,
            "WSP_raw": [2.0, 4.4, 5.0],
            "WSP": [2.0, 2.0, 5.0],
            "wsp_fix_mph": [False, True, False],
        }
    )


def test_wind_unit_step_shows_the_jump_that_the_correction_removes():
    steps = eda.wind_unit_step(wind_table())

    assert steps.loc["2024-01", "WSP_raw"] == 4.4
    assert steps.loc["2024-01", "WSP"] == 2.0


def test_wind_fix_gaps_finds_the_rows_of_2025_that_were_not_corrected():
    gaps = eda.wind_fix_gaps(wind_table())

    assert list(gaps["local"]) == [pd.Timestamp("2025-01-01 00:00")]


def pixels_table() -> pd.DataFrame:
    """Four pixels: good, bad flag, cloudy, and without column."""
    local = pd.Timestamp("2023-11-01 13:00")
    return pd.DataFrame(
        {
            "qf": [0, 1, 0, 0],
            "cf": [0.1, 0.1, 0.5, 0.1],
            "vcd": [1e15, 1e15, 1e15, np.nan],
            "valid": [True, False, False, False],
            "granule": "g1",
            "local": local,
        }
    )


def test_tempo_filters_leave_the_valid_pixels_at_the_end_of_the_sequence():
    out = eda.tempo_filters(pixels_table())

    assert list(out["left"]) == [4, 3, 2, 1]
    assert out["left"].iloc[-1] == pixels_table()["valid"].sum()
    assert out["alone_rejects_pct"].iloc[1] == 25.0


def test_tempo_column_summary_separates_the_valid_pixels_and_counts_the_negative_ones():
    px = pixels_table().assign(vcd=[1e15, -2e15, 5e15, np.nan])

    out = eda.tempo_column_summary(px)

    assert out.loc["valid", "pixels"] == 1
    assert out.loc["rejected", "pixels"] == 2
    assert out.loc["rejected", "negative_pct"] == 50.0


def test_tempo_by_month_gives_the_valid_share_and_the_median_column():
    out = eda.tempo_by_month(pixels_table()).loc["2023-11"]

    assert (out["granules"], out["pixels"], out["valid_pct"], out["median_vcd"]) == (1, 4, 25.0, 1e15)


def test_hourly_table_has_one_row_per_hour_with_the_local_hour_and_ventilation(make_inputs):
    data = make_inputs()

    hours = eda.hourly_table(data)

    first = data.hours[0]
    assert len(hours) == len(data.hours)
    assert hours["hour"].iloc[0] == 12
    assert hours["ventilation"].iloc[0] == pytest.approx(np.hypot(*first.wind) * first.pbl)
    assert hours["nox"].iloc[0] == pytest.approx(first.nox.mean())
    assert hours["n_pixels"].iloc[0] == 2


def test_feature_rows_repeat_each_hour_for_its_stations(make_inputs):
    data = make_inputs()

    rows = eda.feature_rows(data)

    assert len(rows) == data.n_station_rows
    assert set(rows["station"]) == {"AAA", "BBB", "CCC"}
    assert rows["nox"].iloc[0] == pytest.approx(data.hours[0].nox[0])


def rows_with(nox, ventilation, **extra) -> pd.DataFrame:
    n = len(nox)
    day = pd.date_range("2023-11-06", periods=n, freq="D")
    base = {
        "nox": nox,
        "ventilation": ventilation,
        "day": day,
        "hour": 14,
        "station": "AAA",
        "utc": day,
    }
    return pd.DataFrame(base | extra)


def test_ventilation_relation_finds_the_inverse_proportion_when_nox_is_emission_over_ventilation():
    vent = np.geomspace(300, 5000, 200)

    table, rho, slope = eda.ventilation_relation(rows_with(1e5 / vent, vent))

    assert rho == pytest.approx(-1)
    assert slope == pytest.approx(-1)
    assert table["nox_median"].is_monotonic_decreasing


def test_day_type_names_count_a_holiday_as_a_sunday():
    names = eda.day_type_names(pd.DatetimeIndex(["2023-12-22", "2023-12-23", "2023-12-24", "2023-12-25"]))

    assert list(names) == ["weekday", "saturday", "sunday_holiday", "sunday_holiday"]


def test_day_type_table_gives_the_ratio_to_the_weekday():
    days = pd.DatetimeIndex(["2023-12-18", "2023-12-19", "2023-12-24"])  # Mon, Tue, Sun
    rows = rows_with([30.0, 30.0, 15.0], [1000.0, 1000.0, 2000.0]).assign(day=days)

    table = eda.day_type_table(rows)

    assert table.loc["sunday_holiday", "nox_ratio"] == 0.5
    assert table.loc["sunday_holiday", "ventilation_ratio"] == 2.0
    assert table.loc["weekday", "days"] == 2


def test_the_daily_cycle_has_a_column_per_day_type_and_a_row_per_hour():
    nox = nox_table(start="2023-11-06 01:00", end="2023-11-13 00:00")

    cycle = eda.daily_cycle(nox, ("2023-11-06", "2023-11-12"))

    assert list(cycle.columns) == ["weekday", "saturday", "sunday_holiday"]
    assert len(cycle) == 24


def test_pair_correlations_give_one_for_a_perfect_line_and_use_granules_with_five_stations():
    pairs = pd.DataFrame(
        {
            "granule": ["g1"] * 6 + ["g2"] * 3,
            "station": list("ABCDEFABC"),
            "no2_ppb": [1.0, 2, 3, 4, 5, 6, 2, 3, 4],
            "vcd": [2e15, 4e15, 6e15, 8e15, 1e16, 1.2e16, 4e15, 6e15, 8e15],
        }
    )

    out = eda.pair_correlations(pairs)

    assert out["r"].round(6).tolist() == [1.0, 1.0, 1.0, 1.0]
    assert out.loc["within granule, median", "n"] == 1  # g2 has only 3 stations


def test_correlation_matrix_and_collinear_pairs_find_the_duplicated_feature():
    df = pd.DataFrame(
        {"a": np.arange(20.0), "b": np.arange(20.0) * 3, "c": np.random.default_rng(0).normal(size=20)}
    )

    corr = eda.correlation_matrix(df, ["a", "b", "c"])
    pairs = eda.collinear_pairs(corr)

    assert pairs[["a", "b"]].to_dict("records") == [{"a": "a", "b": "b"}]


def test_daily_series_and_weekly_cycle_average_over_stations_and_hours():
    rows = rows_with([10.0, 30.0], [1000.0, 2000.0], station=["AAA", "BBB"])
    rows["day"] = pd.Timestamp("2023-11-06")  # both rows on one Monday

    daily, weekly = eda.daily_series(rows), eda.weekly_cycle(rows)

    assert daily.loc["2023-11-06", ["nox", "stations"]].tolist() == [20.0, 2]
    assert weekly.loc[0, "days"] == 1


def tables(**changes) -> eda.Tables:
    """A tiny `Tables`: Nov 2023 to Jan 2024, one station, with a ten-hour stuck run."""
    nox = nox_table(stations=("AAA",), start="2023-11-01 01:00", end="2024-01-31 00:00")
    nox.loc[20:29, "NOX"] = 33.0
    from nox_ml.data import simat

    wind = pd.DataFrame(
        {
            "id_station": "AAA",
            "local": nox["local"],
            "WSP": 2.0,
            "WDR": 90.0,
            "WSP_raw": 2.0,
            "wsp_fix_mph": False,
        }
    )
    hours = pd.date_range("2023-11-01", "2024-01-31 23:00", freq="h")
    pbl = pd.DataFrame(
        {"pbl_m": 1000.0, "fuente": np.where(hours < "2024-01-01", "ERA5", "MERRA-2 corregido")}, index=hours
    )
    px = pixels_table()
    catalog = pd.DataFrame(
        {"station": ["AAA"], "nom_estac": ["Alfa"], "lon": -99.1, "lat": 19.4, "in_domain": True}
    )
    base = {
        "nox_raw": nox,
        "nox": simat.mask_stuck(nox),
        "wind": wind,
        "pbl": pbl,
        "pixels": px,
        "pixels_test": px.assign(local=pd.Timestamp("2024-03-01 13:00")),
        "catalog": catalog,
    }
    return eda.Tables(**(base | changes))


def test_quality_by_month_marks_the_test_months_as_quality_only():
    out = eda.quality_by_month(tables())

    assert out.loc["2023-11", "period"] == "modelado"
    assert out.loc["2024-01", "period"] == "prueba (solo calidad)"
    assert out.loc["2023-12", "pbl_merra_pct"] == 0
    assert out.loc["2024-01", "pbl_merra_pct"] == 100


def test_the_preprocessing_impact_counts_the_stuck_hours_and_says_nov_dec_has_no_merra_hours():
    out = eda.preprocessing_impact(tables()).set_index("decision")

    assert out.loc["Sensores atascados enmascarados", "amount"].startswith("10 horas")
    assert out.loc["Capa límite con MERRA-2 corregido", "amount"].endswith("nov–dic 2023: 0")


def test_tempo_station_pairs_use_the_valid_pixels_of_the_model_period():
    px = pd.DataFrame(
        {
            "granule": "g1",
            "utc": pd.Timestamp("2023-11-01 18:30"),
            "lat": [19.4, 19.4],
            "lon": [-99.1, -99.1],
            "vcd": [3e15, 9e15],
            "valid": [True, False],
        }
    )
    nox = pd.DataFrame({"id_station": ["AAA"], "utc": [pd.Timestamp("2023-11-01 19:00")], "NO2": [12.0]})

    pairs = eda.tempo_station_pairs(tables(pixels=px, nox=nox))

    assert pairs[["station", "no2_ppb", "vcd"]].to_dict("records") == [
        {"station": "AAA", "no2_ppb": 12.0, "vcd": 3e15}
    ]
    assert tempo.MATCH_KM > 0


def test_road_proxy_sums_the_weights_of_the_cells_within_the_radius():
    zones = pd.DataFrame({"x": [0.0, 900.0, 5000.0], "y": 0.0, "weight": [10.0, 5.0, 100.0]})
    stations = pd.DataFrame({"x": [0.0], "y": [0.0]}, index=["AAA"])

    assert eda.road_proxy(zones, stations, 1000)["AAA"] == 15.0
    assert eda.road_proxy(zones, stations, 6000)["AAA"] == 115.0


def test_proxy_relation_is_one_when_the_levels_follow_the_proxy():
    zones = pd.DataFrame(
        {"x": [0.0, 10_000.0, 10_100.0, 20_000.0, 20_100.0, 20_200.0], "y": 0.0, "weight": 1.0}
    )
    stations = pd.DataFrame({"x": [0.0, 10_000.0, 20_000.0], "y": 0.0}, index=["AAA", "BBB", "CCC"])
    rows = pd.concat([rows_with([20.0, 20.0], [1000.0, 1000.0], station=s) for s in ["AAA"]])
    rows = pd.concat(
        [rows_with([n, n], [1.0, 1.0], station=s) for s, n in {"AAA": 15.0, "BBB": 25.0, "CCC": 60.0}.items()]
    )

    out = eda.proxy_relation(zones, stations, rows, radii_m=[500])

    assert out["spearman"].iloc[0] == pytest.approx(1)
    assert out["stations"].iloc[0] == 3


def test_the_target_floors_the_nox_above_the_background_at_one_ppb():
    out = eda.transformed_target(pd.Series([2.0, 5.0, 5.0 + np.e]))

    assert out.tolist() == pytest.approx([0.0, 0.0, 1.0])


def test_the_log_transform_removes_the_skew_and_the_dominance_of_the_highest_values():
    nox = pd.Series(np.random.default_rng(0).lognormal(3, 0.7, 2000)) + 5

    effect = eda.transform_effect(nox)

    assert effect.loc["ppb", "skew"] > 1
    assert effect.loc["log(NOₓ)", "skew"] < effect.loc["ppb", "skew"]
    assert (
        effect.loc["log(NOₓ)", "top5pct_share_of_variance"] < effect.loc["ppb", "top5pct_share_of_variance"]
    )


def test_gamma_coverage_is_the_share_of_hours_inside_the_trained_range():
    speed = pd.Series([1.0, 2.0, 100.0])  # gamma at tau 8 h: 0.35, 0.17, 0.003

    out = eda.gamma_coverage(speed, tau_hours=[8])

    assert out.iloc[0]["inside_range_pct"] == pytest.approx(200 / 3)
    assert out.iloc[0]["gamma_median"] == pytest.approx(equation.L_M / (2.0 * 8 * 3600))


def test_the_nondimensional_table_uses_the_scales_of_the_equation():
    table = eda.nondimensional_table()

    assert f"{equation.L_M:,.0f}" in table["scale"].iloc[0]
    assert "γ" in table["nondimensional"].iloc[2]


def test_the_circle_makes_the_step_from_the_last_hour_to_the_first_as_short_as_any_other():
    check = eda.cyclic_check(24)

    assert check["raw_distance"].max() == 23
    assert check["circle_distance"].max() == pytest.approx(check["circle_distance"].min())


def test_floor_share_counts_the_values_within_one_ppb_of_the_background():
    assert eda.floor_share(pd.Series([3.0, 5.5, 7.0, 20.0, np.nan])) == 0.5


def test_variance_table_shows_a_constant_column_as_having_no_spread():
    df = pd.DataFrame({"flat": [3.0] * 10, "ramp": np.arange(10.0)})

    out = eda.variance_table(df, ["flat", "ramp"])

    assert out.loc["flat", "std"] == 0
    assert out.loc["flat", "top_value_share"] == 1
    assert out.loc["ramp", "unique"] == 10


def test_pca_of_collinear_columns_puts_the_variance_in_one_component():
    x = np.random.default_rng(0).normal(size=300)
    df = pd.DataFrame({"a": x, "b": 2 * x + 1e-3 * np.random.default_rng(1).normal(size=300), "c": -x})

    explained, loadings = eda.pca_table(df, ["a", "b", "c"])

    assert explained["explained"].iloc[0] > 0.999
    assert loadings["PC1"].abs().round(2).tolist() == pytest.approx([0.58, 0.58, 0.58], abs=0.01)


def test_feature_relevance_ranks_the_informative_feature_above_noise():
    rng = np.random.default_rng(0)
    signal = rng.normal(size=500)
    rows = pd.DataFrame({"signal": signal, "noise": rng.normal(size=500), "nox": 5 + np.exp(2 + signal)})

    out = eda.feature_relevance(rows, ["signal", "noise"])

    assert out.index[0] == "signal"
    assert out.loc["signal", "abs_spearman"] > 0.9


def test_station_pca_keeps_the_stations_present_in_most_hours_and_the_hours_with_all_of_them():
    rng = np.random.default_rng(0)
    common = rng.normal(size=60)
    rows = pd.DataFrame(
        [
            {
                "utc": pd.Timestamp("2023-11-01") + pd.Timedelta(hours=h),
                "station": s,
                "nox": 30 + 5 * c + rng.normal(),
            }
            for h, c in enumerate(common)
            for s in ["AAA", "BBB", "CCC"]
        ]
    )
    rows = rows[~((rows["station"] == "CCC") & (rows["utc"] < "2023-11-02"))]  # CCC present in 60 % of hours

    out = eda.station_pca(rows, min_share=0.8)

    assert out.attrs["stations"] == 2
    assert out["explained"].iloc[0] > 0.8


def test_the_observation_information_has_a_row_per_source(make_inputs):
    reduction, dofs = eda.observation_information(make_inputs())

    assert list(dofs["source"]) == ["stations", "tempo", "both"]
    assert (dofs["dofs"] > 0).all()
    assert (
        len(reduction) == 1 + 3 * 2
    )  # the point source and the road factors of three day types in two regions


def test_ventilation_features_of_the_hour_table_are_in_the_summary(make_inputs):
    rows = eda.feature_rows(make_inputs())

    summary = eda.feature_summary(rows)

    assert list(summary.index) == eda.FEATURES
    assert (summary["missing"] == 0).all()
    assert (summary.loc["ventilation_6h", "median"] > summary.loc["ventilation", "median"]).all()


def test_ventilation_gain_has_a_row_per_variable(make_inputs):
    out = eda.ventilation_gain(eda.feature_rows(make_inputs()))

    assert list(out.index) == ["viento", "capa límite", *eda.VENTILATION]


@pytest.fixture
def figures(make_inputs):
    """Every plot with the small inputs: name -> figure."""
    data = make_inputs()
    rows = eda.feature_rows(data)
    t = tables()
    nox = eda.in_window(t.nox, ("2023-11-01", "2023-11-30"), eda.AFTERNOON)
    corr = eda.correlation_matrix(rows, eda.FEATURES)
    explained, loadings = eda.pca_table(rows, eda.VENTILATION)
    return {
        "completeness": eda.plot_completeness(eda.completeness_matrix(t.nox, ("2023-11-01", "2023-11-30"))),
        "missing": eda.plot_missing_profile(t.nox, ("2023-11-06", "2023-11-12")),
        "pbl": eda.plot_pbl(t.pbl),
        "stuck": eda.plot_stuck_example(t.nox_raw),
        "wind": eda.plot_wind_step(wind_table()),
        "histograms": eda.plot_histograms({"NOx": nox["NOX"], "NO2": nox["NO2"]}, log=["NOx"]),
        "boxplots": eda.plot_station_boxplots(nox),
        "ventilation": eda.plot_ventilation(rows),
        "daily_cycle": eda.plot_daily_cycle(eda.daily_cycle(t.nox, ("2023-11-06", "2023-11-12"))),
        "tempo_pairs": eda.plot_tempo_pairs(
            pd.DataFrame(
                {"granule": "g", "station": list("ABC"), "no2_ppb": [1.0, 2, 3], "vcd": [1e15, 2e15, 3e15]}
            )
        ),
        "correlation": eda.plot_correlation(corr),
        "trend": eda.plot_daily_trend(eda.daily_series(rows)),
        "weekly": eda.plot_weekly_cycle(eda.weekly_cycle(rows)),
        "road_proxy": eda.plot_road_proxy(data.zones, data.station_xy, rows, 3000),
        "transform": eda.plot_transform(rows["nox"]),
        "green": eda.plot_green_function((0.1,)),
        "wind_rose": eda.plot_wind_rose(eda.hourly_table(data)),
        "pca": eda.plot_pca(explained, explained, loadings.assign(PC2=loadings["PC1"])),
        "information": eda.plot_information(eda.observation_information(data)[1]),
    }


def test_every_plot_returns_a_figure_with_axes(figures):
    assert all(isinstance(f, Figure) and f.axes for f in figures.values())
