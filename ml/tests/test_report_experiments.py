# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import json

import numpy as np
import pandas as pd
import pytest
import yaml

from nox_ml.data.pbl import ERA5_FILE
from nox_ml.inversion.normalized import SUNDAY_HOLIDAY, WEEKDAY
from nox_ml.validation import report
from nox_ml.validation import report_experiments as rx

# --- Synthetic twin -------------------------------------------------------------------------------


def test_truth_has_the_day_type_ratios_it_was_built_with(make_inputs):
    inputs = make_inputs()
    truth = rx.make_truth(inputs, seed=1, saturday=0.8, sunday=0.4)
    prior = rx.region_prior(inputs)

    assert truth.ratio(prior, SUNDAY_HOLIDAY) == pytest.approx(0.4)
    assert truth.ratio(prior, 1) == pytest.approx(0.8)


def test_truth_changes_with_the_seed(make_inputs):
    inputs = make_inputs()

    assert not np.allclose(rx.make_truth(inputs, 0).points, rx.make_truth(inputs, 1).points)


def test_a_twin_without_noise_is_the_response_of_the_model_to_the_truth(make_inputs):
    inputs = make_inputs()
    truth = rx.make_truth(inputs, 0)

    twin = rx.simulate_observations(inputs, truth, station_noise_ppb=0, pixel_noise=0, background=(0.0, 0.0))
    first = twin.jacobians(*_key())[0]
    state = np.r_[truth.points, truth.roads[WEEKDAY]]  # 2023-11-06 is a Monday

    np.testing.assert_allclose(twin.hours[0].nox, first.stations @ state)
    np.testing.assert_allclose(twin.hours[0].wind, inputs.hours[0].wind)


def _key():
    from nox_ml.models.inversion_plume import InversionPlume

    model = InversionPlume()
    return model.transport_key(), model.transport()


def test_the_twin_keeps_the_wind_so_it_shares_the_jacobians_and_a_perturbed_wind_builds_its_own(make_inputs):
    inputs = make_inputs()
    inputs.jacobians(*_key())
    twin = rx.simulate_observations(inputs, rx.make_truth(inputs, 0))

    assert twin.jacobian_cache is inputs.jacobian_cache
    assert rx.perturb_wind(twin, 20, seed=0).jacobian_cache == {}


def test_perturbing_the_wind_keeps_the_speed_and_has_the_requested_spread(make_inputs):
    inputs = make_inputs()
    turned = rx.perturb_wind(inputs, 20.0, seed=0)
    before, after = np.array([h.wind for h in inputs.hours]), np.array([h.wind for h in turned.hours])
    degrees = rx.angle_difference(rx.direction_from(*before.T), rx.direction_from(*after.T))

    np.testing.assert_allclose(np.hypot(*before.T), np.hypot(*after.T))
    assert 10 < np.sqrt(np.mean(degrees**2)) < 30  # root mean square of a Gaussian error is its sigma


def test_a_twin_without_noise_and_without_wind_error_is_recovered(make_inputs):
    inputs = make_inputs()
    truth = rx.make_truth(inputs, 0)
    twin = rx.simulate_observations(
        inputs, truth, station_noise_ppb=0.1, pixel_noise=1e13, background=(5.0, 0.0)
    )

    table = rx.recovery(twin, truth)

    assert set(table["quantity"]) == {"punto", "zona", "total vial", "domingo/hábil", "sábado/hábil"}
    assert table.loc[table["quantity"] == "total vial", "rel_error"].iloc[0] < 0.1


def test_the_wind_error_twin_loses_more_the_more_wrong_the_wind_is(make_inputs):
    inputs = make_inputs()

    twin = rx.wind_error_twin(inputs, sigmas=(0, 40), seeds=(0, 1), station_noise_ppb=0.5, pixel_noise=1e14)
    summary = rx.twin_summary(twin)

    assert set(twin["sigma"]) == {0.0, 40.0}
    assert set(twin["seed"]) == {0, 1}
    assert summary.loc[0.0, "total vial"] < summary.loc[40.0, "total vial"]
    assert rx.plot_wind_twin(twin).axes


# --- Estimators and placebo -----------------------------------------------------------------------


def test_the_daily_table_labels_sundays(make_inputs):
    daily = rx.daily_normalized(make_inputs())

    assert list(daily.columns[:3]) == ["obs", "model", "hours"]
    assert daily.loc["2023-11-12", "kind"] == SUNDAY_HOLIDAY
    assert daily.loc["2023-11-14", "kind"] == WEEKDAY
    assert (daily["hours"] == 6).all()


def test_the_raw_concentration_ratio_of_a_sunday_that_emits_half_is_about_half(make_inputs):
    daily = rx.daily_normalized(make_inputs(sunday_scale=0.5))

    value, lo, hi = rx.index_ratio(daily, per_hour=True, n_boot=200)

    assert value == pytest.approx(0.5, abs=0.1)
    assert lo < hi


def test_the_estimator_table_has_one_row_per_estimator_with_ordered_intervals(make_inputs):
    table = rx.estimator_table(
        make_inputs(sunday_scale=0.5),
        n_boot=50,
        rf_params={"n_estimators": 40, "bootstrap_n": 2, "weather_samples": 2},
    )

    assert list(table["estimator"][:2]) == [
        "concentración sin corregir clima",
        "normalizado (observado ÷ modelo)",
    ]
    assert list(table["estimator"][2:]) == ["rf_deweather", "inversion_plume"]
    assert (table["lo"] <= table["hi"]).all()
    assert rx.plot_estimators(table, truth=0.5, band=rx.TRAFFIC_BAND).axes


def test_fake_sundays_among_weekdays_are_centered_on_one(make_inputs):
    daily = rx.daily_normalized(make_inputs())

    ratios = rx.fake_sunday_ratios(daily, n=300, seed=0)

    assert len(ratios) == 300
    assert np.median(ratios) == pytest.approx(1.0, abs=0.15)


def test_the_placebo_of_a_model_refits_it_once_per_replicate(make_inputs):
    ratios = rx.model_placebo_ratios(make_inputs(), "inversion_plume", refits=3, seed=1)

    assert ratios.shape == (3,)
    assert np.isfinite(ratios).all()


def test_the_placebo_of_the_forest_works_with_its_own_params(make_inputs):
    ratios = rx.model_placebo_ratios(
        make_inputs(), "rf_deweather", refits=2, n_estimators=40, weather_samples=2
    )

    assert ratios.shape == (2,)


def test_the_placebo_summary_passes_a_null_centered_on_one_and_not_one_that_drifts():
    centered = np.linspace(0.8, 1.2, 101)
    drifting = np.linspace(1.0, 1.6, 101)

    table = rx.placebo_summary(centered, drifting)

    assert list(table["estimador"]) == ["normalizado", "modelo"]
    assert table["pasa"].tolist() == [True, False]
    assert table["semiancho"].iloc[0] == pytest.approx(0.18, abs=0.01)
    assert list(rx.placebo_summary(centered)["estimador"]) == ["normalizado"]


def test_the_figures_draw_themselves_in_a_notebook(make_inputs):
    fig = rx.plot_obs_vs_model(rx.daily_normalized(make_inputs()))

    assert fig._repr_png_().startswith(b"\x89PNG")  # what Jupyter shows when a cell ends with the figure


def test_the_diagnostic_plots_of_the_estimators_draw_their_panels(make_inputs):
    daily = rx.daily_normalized(make_inputs())
    null = rx.fake_sunday_ratios(daily, n=100)

    assert len(rx.plot_obs_vs_model(daily).axes) == 1
    assert len(rx.plot_daily_index(daily).axes) == 1
    assert len(rx.plot_placebo(null, (0.5, 0.4, 0.6), model_null=null[:5]).axes) == 1


# --- Wind -----------------------------------------------------------------------------------------


def test_angle_difference_wraps_around_north():
    np.testing.assert_allclose(
        rx.angle_difference(np.array([350.0, 10.0, 0.0]), np.array([10.0, 350.0, 180.0])), [20, 20, 180]
    )


def test_a_wind_blowing_east_comes_from_the_west():
    assert rx.direction_from(np.array([2.0]), np.array([0.0]))[0] == pytest.approx(270.0)


def wind_table(rows):
    """Winds of stations given as ``(station, hour, direction from, speed)``."""
    frame = pd.DataFrame(rows, columns=["station", "h", "direction", "speed"])
    towards = np.deg2rad(frame["direction"])
    return frame.assign(u=-frame["speed"] * np.sin(towards), v=-frame["speed"] * np.cos(towards))


def test_a_station_with_a_different_wind_is_the_one_the_others_cannot_predict():
    hours = pd.date_range("2023-11-01 18:00", periods=5, freq="h")
    rows = [(s, h, 270.0 if s != "D" else 310.0, 3.0) for h in hours for s in "ABCD"]
    xy = pd.DataFrame({"x": [0.0, 5e3, 1e4, 1.5e4], "y": [0.0, 0.0, 0.0, 0.0]}, index=list("ABCD"))

    errors = rx.wind_leave_one_out(wind_table(rows), xy)
    by_station = errors.groupby("station")["error_domain"].median()

    assert by_station["D"] == pytest.approx(40.0)  # the others all say 270
    assert by_station["A"] < 20  # D pulls the mean only a little


def test_idw_gives_the_nearest_station_more_weight_than_the_domain_mean():
    hours = pd.date_range("2023-11-01 18:00", periods=3, freq="h")
    direction = {"A": 270.0, "B": 270.0, "C": 270.0, "D": 330.0}
    rows = [(s, h, direction[s], 3.0) for h in hours for s in "ABCD"]
    xy = pd.DataFrame(
        {"x": [0.0, 20e3, 30e3, 1e3], "y": [0.0, 0.0, 0.0, 0.0]}, index=list("ABCD")
    )  # D next to A

    errors = rx.wind_leave_one_out(wind_table(rows), xy)
    a = errors[errors["station"] == "A"]

    assert (
        a["error_idw"] > a["error_domain"]
    ).all()  # A follows its neighbour D, so it is further from 270...
    assert (a["idw"] > a["domain"]).all()


def test_calm_station_hours_are_not_scored_but_still_feed_the_prediction():
    hours = pd.date_range("2023-11-01 18:00", periods=2, freq="h")
    rows = [(s, h, 270.0, 0.4 if s == "C" else 3.0) for h in hours for s in "ABC"]
    xy = pd.DataFrame({"x": [0.0, 5e3, 1e4], "y": [0.0, 0.0, 0.0]}, index=list("ABC"))

    errors = rx.wind_leave_one_out(wind_table(rows), xy)

    assert set(errors["station"]) == {"A", "B"}


def write_era5(data_dir, directions, speeds, start="2023-11-01 00:00"):
    folder = data_dir / "raw" / "era5_openmeteo"
    folder.mkdir(parents=True)
    time = pd.date_range(start, periods=len(directions), freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
    payload = {"hourly": {"time": time, "wind_direction_10m": directions, "wind_speed_10m": speeds}}
    (folder / ERA5_FILE).write_text(json.dumps(payload))


def test_era5_errors_are_the_difference_to_the_observed_direction_and_skip_missing_hours(tmp_path):
    write_era5(tmp_path, [270.0] * 4, [3.0] * 4)
    errors = pd.DataFrame(
        {
            "h": pd.to_datetime(["2023-11-01 01:00", "2023-11-01 02:00", "2023-12-01 00:00"]),
            "observed": [270.0, 300.0, 270.0],
        }
    )

    out = rx.era5_wind_errors(rx.era5_wind(tmp_path), errors)

    np.testing.assert_allclose(out, [0.0, 30.0], atol=1e-9)  # the third hour is not in the ERA5 file


def test_station_winds_keeps_the_window_the_stations_of_the_catalog_and_the_label_shift(tmp_path):
    import geopandas as gpd

    interim = tmp_path / "interim"
    interim.mkdir()
    catalog = gpd.GeoDataFrame({"cve_estac": ["AAA"]}, geometry=gpd.points_from_xy([-99.1], [19.4]), crs=4326)
    catalog.to_file(interim / "estaciones.gpkg", driver="GPKG")
    local = pd.to_datetime(
        ["2023-11-02 11:00", "2023-11-02 12:00", "2023-11-02 18:00", "2023-12-31 17:00", "2024-01-01 12:00"]
    )
    wind = pd.DataFrame(
        {"id_station": "AAA", "local": local, "utc": local + pd.Timedelta(hours=6), "WSP": 2.0, "WDR": 90.0}
    )
    wind = pd.concat([wind, wind.assign(id_station="ZZZ")])  # a station that is not in the catalog
    wind.to_parquet(interim / "simat_wind.parquet")

    table, xy = rx.station_winds(tmp_path, "2023-11-01", "2023-12-31", (12, 17))

    assert list(xy.index) == ["AAA"]
    assert list(table["station"]) == ["AAA", "AAA"]
    assert list(table["h"]) == [
        pd.Timestamp("2023-11-02 17:00"),
        pd.Timestamp("2023-12-31 22:00"),
    ]  # label - 1 h, in UTC
    assert table["u"].iloc[0] == pytest.approx(-2.0)  # from the east, it blows towards the west


def test_the_wind_error_summary_lists_the_methods_and_the_figure_draws_two_panels():
    errors = pd.DataFrame(
        {"station": ["A", "A", "B"], "error_domain": [10.0, 30.0, 50.0], "error_idw": [5.0, 15.0, 25.0]}
    )

    summary = rx.wind_error_summary(errors, np.array([60.0, 80.0]))

    assert summary["mediana"].tolist() == [30.0, 15.0, 70.0]
    assert len(rx.plot_wind_errors(errors, np.array([60.0, 80.0])).axes) == 2


# --- Transport ------------------------------------------------------------------------------------

pytest.importorskip("torch")


@pytest.fixture(scope="module")
def kernel():
    return rx.default_kernel()


@pytest.fixture
def suite(kernel, make_inputs):
    return rx.TransportSuite(make_inputs(), kernel)


def test_every_transport_gives_a_matrix_with_the_columns_of_the_sources(suite):
    data = suite.inputs.hours[10]

    for name in rx.TRANSPORT_NAMES:
        jac = suite.jacobian(name, data)
        assert jac.stations.shape == (len(data.nox), suite.sources.n_columns)
        assert jac.pixels.shape == (len(data.no2), suite.sources.n_columns)
        assert (jac.stations >= 0).all()


def test_an_unknown_transport_is_refused(suite):
    with pytest.raises(ValueError, match="unknown transport"):
        suite.jacobian("wrf", suite.inputs.hours[0])


def test_pick_hour_is_a_weekday_at_the_local_hour_asked(suite):
    index = suite.inputs.hours[rx.pick_hour(suite.inputs, 15)]

    assert rx.local_hour(index.hour) == 15
    assert index.hour.day_of_week not in (5, 6)  # UTC hour 21 is the same day in local time


def test_the_maps_have_a_field_per_transport_and_the_figure_has_its_panels(suite):
    maps = rx.concentration_maps(suite, rx.pick_hour(suite.inputs), n=12)

    assert set(maps.fields) == set(rx.TRANSPORT_NAMES)
    assert all(field.shape == (12, 12) and (field >= 0).all() for field in maps.fields.values())
    assert len(rx.plot_maps(maps).axes) >= 8


def test_a_plume_without_loss_carries_all_its_mass_and_the_kernel_the_mass_of_its_equation(kernel):
    flux = rx.crosswind_flux(kernel, distances_km=(5, 20, 40))

    np.testing.assert_allclose(flux["pluma gaussiana"], 1.0, atol=0.03)
    np.testing.assert_allclose(flux["núcleo de la PINN"], flux["solución exacta"], rtol=0.05)
    assert flux["núcleo de la PINN"].is_monotonic_decreasing


def test_a_puff_conserves_its_mass_with_the_gaussian_and_with_the_kernel_profile(kernel):
    mass = rx.puff_mass_check(kernel, ages_h=(2.125, 4.125))

    np.testing.assert_allclose(mass["puffs gaussianos"], 1.0, atol=0.03)
    np.testing.assert_allclose(mass["puffs con el núcleo"], 1.0, atol=0.05)
    assert len(rx.plot_mass(rx.crosswind_flux(kernel, distances_km=(5, 20)), mass).axes) == 2


def test_the_kernel_is_close_to_the_exact_solution_where_the_plume_is(kernel):
    result = rx.kernel_error(kernel, 0.1)

    assert result.exact.shape == result.network.shape == (len(result.a), len(result.c))
    assert np.nanmedian(result.relative_error) < 0.1
    assert len(rx.plot_kernel_error(kernel, gammas=(0.1,)).axes) >= 3


def test_the_stored_validation_of_the_kernel_is_one_row_per_gamma(kernel):
    table = rx.kernel_validation(kernel)

    assert list(table.columns) == ["median_rel_error", "p90_rel_error", "mass_error"]
    assert table.index.is_monotonic_increasing
    assert (table["median_rel_error"] < 0.1).all()


def test_the_jacobian_differences_compare_each_transport_with_the_plume_column_by_column(suite):
    stacks = rx.sample_jacobians(suite, step=20)
    labels = rx.column_labels(suite.inputs)

    differences = rx.jacobian_differences(stacks, labels)

    assert labels == ["P0", "zona 0", "zona 1"]
    assert set(differences["transport"]) == {"kernel", "gauss_puffs", "kernel_puffs"}
    stations = differences[differences["receptor"] == "stations"]
    assert (stations["total_ratio"] > 0).all()
    assert rx.difference_summary(differences).index.names == ["receptor", "transport"]
    assert len(rx.plot_jacobian_differences(stacks, differences).axes) >= 2


# --- Runs, diagnostics and the comparison with the transport --------------------------------------


def write_run(folder, kappa=None, rmse=12.5, sunday=0.5, trials=None, model="pinn_puff"):
    folder.mkdir(parents=True)
    summary = {
        "model": model,
        "role": "model",
        "loo_rmse_ppb": rmse,
        "eligible": True,
        "sunday_ratio": sunday,
        "sunday_ratio_lo": sunday - 0.1,
        "sunday_ratio_hi": sunday + 0.1,
        "placebo_center": 1.0,
        "placebo_halfwidth": 0.1,
    }
    (folder / "metrics.json").write_text(json.dumps({"summary": summary}))
    params = {} if kappa is None else {"kappa": kappa}
    (folder / "config.yaml").write_text(yaml.safe_dump({"model": {"name": model, "params": params}}))
    if trials is not None:
        pd.DataFrame(trials).to_csv(folder / "trials.csv", index=False)


def test_runs_status_lists_what_is_missing_with_the_command_that_makes_it(tmp_path):
    write_run(tmp_path / "pinn_puff")
    write_run(tmp_path / "pinn_puff_k500", kappa=500)

    status = rx.runs_status(tmp_path).set_index("run")

    assert status.loc["pinn_puff", "exists"]
    assert not status.loc["pinn_plume", "exists"]
    assert status.loc["pinn_plume", "command"].startswith("nox-ml run")
    assert status.loc["pinn_puff_k500", "exists"]
    assert "pinn_puff_k*" not in status.index


def test_runs_status_without_a_runs_folder_says_everything_is_missing(tmp_path):
    status = rx.runs_status(tmp_path / "nothing")

    assert not status["exists"].any()
    assert "pinn_puff_k*" in set(status["run"])


def test_the_kappa_grid_is_sorted_by_kappa_and_plotted(tmp_path):
    write_run(tmp_path / "pinn_puff_k3000", kappa=3000, rmse=12.9)
    write_run(tmp_path / "pinn_puff_k500", kappa=500, rmse=12.4)
    write_run(tmp_path / "pinn_puff_k1500", kappa=1500, rmse=12.1)
    write_run(tmp_path / "pinn_puff", rmse=12.1)

    table = rx.kappa_runs(tmp_path)

    assert list(table["kappa"]) == [500, 1500, 3000]
    figure = rx.plot_kappa(table)
    assert figure is not None
    assert len(figure.axes) == 3


def test_the_kappa_grid_tolerates_missing_runs(tmp_path):
    assert rx.kappa_runs(tmp_path / "nothing").empty
    assert rx.plot_kappa(rx.kappa_runs(tmp_path / "nothing")) is None


def test_the_trial_figure_has_a_panel_per_searched_param_and_a_log_axis_for_wide_ranges():
    trials = pd.DataFrame(
        {
            "trial": [0, 1, 2],
            "tau_h": [2.0, 12.0, 96.0],
            "max_age_h": [6, 12, 24],
            "loo_rmse_ppb": [13.0, 12.0, 12.5],
        }
    )

    fig = rx.plot_trial_params(trials, "búsqueda")

    assert fig is not None
    assert len(fig.axes) == 2
    assert fig.axes[0].get_xscale() == "log"
    assert fig.axes[1].get_xscale() == "linear"


def test_a_search_that_was_not_run_has_no_trials_no_overview_and_no_figure(tmp_path):
    assert rx.read_search(tmp_path, "pinn_puff.kernel") is None
    assert rx.search_overview(None).empty
    assert rx.plot_trial_params(None) is None


def test_the_overview_of_a_search_gives_the_range_and_the_best_value_of_each_param(tmp_path):
    trials = {"trial": [0, 1, 2], "tau_h": [6.0, 12.0, 24.0], "loo_rmse_ppb": [12.3, 12.0, 12.4]}
    write_run(tmp_path / "pinn_puff.transport", trials=trials)

    overview = rx.search_overview(rx.read_search(tmp_path, "pinn_puff.transport"))

    assert overview.iloc[0].to_dict() == {
        "param": "tau_h",
        "min": 6.0,
        "max": 24.0,
        "values": 3,
        "best": 12.0,
    }


def test_the_pinn_family_table_has_the_pinn_runs_but_not_the_searches_nor_other_models(tmp_path):
    write_run(tmp_path / "pinn_plume", model="pinn_plume", rmse=12.5)
    write_run(tmp_path / "pinn_puff", rmse=12.1)
    write_run(tmp_path / "baseline", model="inversion_plume", rmse=13.6)
    write_run(
        tmp_path / "pinn_puff.transport",
        rmse=12.0,
        trials={"trial": [0], "tau_h": [6.0], "loo_rmse_ppb": [12.0]},
    )

    table = rx.pinn_family_table(tmp_path)

    assert list(table["run"]) == ["pinn_puff", "pinn_plume"]
    assert rx.pinn_family_table(tmp_path / "nothing").empty


def test_tuning_sentences_report_the_gain_over_the_untuned_run(tmp_path):
    write_run(tmp_path / "pinn_puff", rmse=12.5)
    trials = {"trial": [0, 1], "tau_h": [6.0, 12.0], "loo_rmse_ppb": [12.3, 12.0]}
    write_run(tmp_path / "pinn_puff.transport", rmse=12.0, trials=trials)
    table = report.compare.collect(report.run_dirs(tmp_path))[0]

    sentences = rx.tuning_sentences(report.tuning_summary(tmp_path, table))

    assert sentences == [
        "pinn_puff.transport: 2 pruebas; el mejor error con estación oculta es 12.00 ppb (prueba 1), "
        "12.50 sin ajustar (+0.50 ppb de ganancia)."
    ]


def write_diagnostics(folder):
    folder.mkdir(parents=True, exist_ok=True)
    ablation = pd.DataFrame(
        {
            "case": ["baseline", "no_tempo", "stations", "stations", "wind_bias", "wind_bias"],
            "setting": [np.nan, np.nan, 15.0, 15.0, 15.0, 30.0],
            "seed": [pd.NA, pd.NA, 0, 1, pd.NA, pd.NA],
            "loo.rmse.model": [13.0, 13.4, 13.6, 13.8, 13.1, 13.2],
            "loo.rmse.hybrid": [11.0, 11.2, 11.4, 11.6, 11.1, 11.2],
            "in_sample.r_tempo": [0.8, np.nan, 0.8, 0.7, 0.8, 0.8],
            "day_types.sunday_over_weekday.value": [0.4, 0.5, 0.5, 0.5, 0.4, 0.4],
            "normalized.placebo_half_width": [0.25] * 6,
        }
    )
    curve = pd.DataFrame(
        {
            "axis": ["days", "days", "stations", "stations"],
            "n": [15, 30, 6, 12],
            "seed": [0, 0, 0, 0],
            "rmse_in_sample": [10.0, 11.0, 9.0, 10.0],
            "rmse_loo_model": [14.0, 13.0, 15.0, 14.0],
            "rmse_loo_idw": [12.0, 12.0, 14.0, 13.0],
        }
    )
    ablation.to_csv(folder / "ablation.csv", index=False)
    curve.to_csv(folder / "learning_curve.csv", index=False)
    pd.DataFrame({"label": ["P0"], "reduction_both": [0.5]}).to_csv(
        folder / "variance_reduction.csv", index=False
    )
    pd.DataFrame({"source": ["both"], "dofs": [3.0]}).to_csv(folder / "degrees_of_freedom.csv", index=False)


def write_config(path, name="baseline"):
    path.write_text(yaml.safe_dump({"name": name, "period": {"start": "2023-11-01", "end": "2023-12-31"}}))


def test_diagnostics_are_read_from_runs_when_they_exist_and_not_computed_again(tmp_path, monkeypatch):
    from nox_ml.validation import diagnostics

    write_diagnostics(tmp_path / "runs" / "baseline" / "diagnostics")
    write_config(tmp_path / "baseline.yaml")
    monkeypatch.setattr(diagnostics, "run_diagnostics", lambda *a, **k: pytest.fail("computed again"))

    tables = rx.diagnostics_for(tmp_path / "baseline.yaml", tmp_path / "runs", echo=lambda _: None)

    assert set(tables) == set(rx.DIAGNOSTIC_FILES)
    assert len(tables["ablation"]) == 6


def test_missing_diagnostics_are_computed_once_by_the_harness(tmp_path, monkeypatch):
    from nox_ml.validation import diagnostics

    calls = []

    def fake(cfg, runs_dir, seeds, echo):
        calls.append((cfg.name, seeds))
        write_diagnostics(runs_dir / cfg.name / "diagnostics")

    monkeypatch.setattr(diagnostics, "run_diagnostics", fake)
    write_config(tmp_path / "baseline.yaml")
    messages = []

    rx.diagnostics_for(tmp_path / "baseline.yaml", tmp_path / "runs", seeds=2, echo=messages.append)
    rx.diagnostics_for(tmp_path / "baseline.yaml", tmp_path / "runs", seeds=2, echo=messages.append)

    assert calls == [("baseline", 2)]
    assert len(messages) == 1


def test_the_ablation_summary_has_a_row_per_case_in_spanish_with_the_spread_of_the_subsets(tmp_path):
    write_diagnostics(tmp_path)

    summary = rx.ablation_summary(pd.read_csv(tmp_path / "ablation.csv"))

    assert list(summary.index) == [
        "línea base",
        "sin TEMPO",
        "15 estaciones",
        "viento girado +15°",
        "viento girado +30°",
    ]
    assert summary.loc["15 estaciones", "rmse"] == pytest.approx(13.7)
    assert summary.loc["15 estaciones", "rmse_sd"] > 0
    assert summary.loc["línea base", "rmse_sd"] == 0
    assert len(rx.plot_ablation(summary).axes) == 3


def test_the_learning_summary_gives_the_gap_between_held_out_and_in_sample_error(tmp_path):
    write_diagnostics(tmp_path)
    curve = pd.read_csv(tmp_path / "learning_curve.csv")

    summary = rx.learning_summary(curve)

    assert summary.loc[summary["n"] == 15, "brecha"].iloc[0] == pytest.approx(4.0)
    assert len(rx.plot_learning_curves(curve).axes) == 2


def test_the_plume_to_puff_comparison_reads_the_runs_and_falls_back_to_the_reported_values(tmp_path):
    reported = rx.plume_to_puff(tmp_path / "nothing")
    write_run(tmp_path / "pinn_plume", rmse=12.6)
    mixed = rx.plume_to_puff(tmp_path)

    assert reported["rmse_ppb"].tolist() == [12.49, 12.08]
    assert set(reported["fuente"]) == {"reportado por el proyecto"}
    assert mixed["rmse_ppb"].tolist() == [12.6, 12.08]
    assert mixed["fuente"].tolist() == ["runs/pinn_plume", "reportado por el proyecto"]


def test_rotating_the_wind_changes_the_error_less_than_the_change_of_transport_in_the_comparison(tmp_path):
    write_diagnostics(tmp_path)
    ablation = pd.read_csv(tmp_path / "ablation.csv")

    changes = rx.error_changes(ablation, rx.plume_to_puff(tmp_path / "nothing"))

    assert changes["cambio de"].tolist() == [
        "viento girado +15°",
        "viento girado +30°",
        "pluma → puffs (PINN)",
    ]
    np.testing.assert_allclose(changes["cambio_ppb"], [0.1, 0.2, -0.41])
    assert changes.attrs["noise_ppb"] == pytest.approx(0.1414, abs=1e-3)  # 13.6 and 13.8 with 15 stations
    assert len(rx.plot_error_changes(changes).axes) == 1
