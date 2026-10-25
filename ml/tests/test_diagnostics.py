# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import dataclasses

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.inversion.linear import DAY_TYPE_NAMES, hour_jacobians, hour_systems, solve
from nox_ml.models import REGISTRY
from nox_ml.validation import diagnostics
from nox_ml.validation.diagnostics import (
    ablation,
    information_by_observation,
    learning_curve,
    model_systems,
    posterior_sd,
    rotate_wind,
    spatial_subset,
    with_days,
    with_stations,
    without_tempo,
)
from nox_ml.validation.experiment import ExperimentConfig

N_REGIONS = 2
TOL = 1e-9


def config(**changes) -> ExperimentConfig:
    base = {
        "name": "t",
        "period": {"start": "2023-11-06", "end": "2023-11-19"},
        "model": {"name": "inversion_plume", "params": {"bootstrap_n": 4}},
        "placebo": {"n": 20, "refits": 2},
    }
    return ExperimentConfig.model_validate(base | changes)


MAKE_MODEL = config().model.build  # the registered baseline, inversion_plume


def systems_of(inputs):
    return model_systems(inputs, config().model.build())


@pytest.fixture
def information(make_inputs):
    inputs = make_inputs()
    return information_by_observation(systems_of(inputs), inputs.points, N_REGIONS)


# --- information ------------------------------------------------------------------------------------------


def test_every_source_reduces_the_variance_and_both_reduce_it_more_than_either(information):
    reduction, _ = information

    for source in ("stations", "tempo"):
        assert (reduction[f"reduction_{source}"] >= -TOL).all()
        assert (reduction["reduction_both"] >= reduction[f"reduction_{source}"] - TOL).all()
        assert reduction["reduction_both"].sum() > reduction[f"reduction_{source}"].sum()
    assert (reduction["reduction_both"] <= 1).all()


def test_the_variance_reduction_with_both_sources_is_that_of_the_posterior(make_inputs):
    inputs = make_inputs()
    systems = systems_of(inputs)

    reduction, _ = information_by_observation(systems, inputs.points, N_REGIONS)

    posterior = solve(systems, inputs.points, N_REGIONS)
    assert reduction["sd_both"].to_numpy() == pytest.approx(posterior.sd)
    assert reduction["prior_sd"].to_numpy() == pytest.approx(posterior.prior_sd)


def test_without_observations_the_posterior_is_the_prior(make_inputs):
    inputs = make_inputs()
    nothing = [
        dataclasses.replace(h, stations=type(h.stations)(np.empty(0), np.empty(0)), nox=np.empty(0))
        for h in without_tempo(inputs).hours
    ]
    for systems in ([], hour_systems(nothing, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)):
        reduction, dofs = information_by_observation(systems, inputs.points, N_REGIONS)

        for source in diagnostics.SOURCES:
            assert reduction[f"sd_{source}"].to_numpy() == pytest.approx(reduction["prior_sd"].to_numpy())
            assert reduction[f"reduction_{source}"].abs().max() < TOL
        assert dofs["dofs"].abs().max() < TOL


def test_the_table_has_one_row_per_unknown_with_its_group_and_zone(information):
    reduction, dofs = information

    assert len(reduction) == 1 + 3 * N_REGIONS  # one point source, 3 day types x 2 regions
    assert reduction["group"].tolist() == ["points", *[g for g in DAY_TYPE_NAMES for _ in range(N_REGIONS)]]
    assert reduction["zone"].tolist() == [pd.NA, 0, 1, 0, 1, 0, 1]
    assert dofs["source"].tolist() == ["stations", "tempo", "both"]


def test_the_degrees_of_freedom_are_the_trace_of_the_averaging_kernel(make_inputs):
    inputs = make_inputs()
    systems = systems_of(inputs)
    _, dofs = information_by_observation(systems, inputs.points, N_REGIONS)

    posterior = solve(systems, inputs.points, N_REGIONS)
    kernel = np.eye(len(posterior.mean)) - posterior.cov @ np.diag(1 / posterior.prior_sd**2)
    both = dofs.set_index("source").loc["both"]
    assert both["dofs"] == pytest.approx(np.trace(kernel))
    assert both["dofs"] == pytest.approx(both[["points", *DAY_TYPE_NAMES]].sum())
    for source in ("stations", "tempo"):
        assert both["dofs"] >= dofs.set_index("source").loc[source, "dofs"] - TOL


def test_one_scalar_unknown_has_the_textbook_degrees_of_freedom():
    prior_sd, info = np.array([2.0]), np.array([[1.0]])  # prior variance 4, precision of the data 1

    sd = posterior_sd(prior_sd, info)

    assert sd[0] ** 2 == pytest.approx(1 / (1 / 4 + 1))
    assert 1 - sd[0] ** 2 / 4 == pytest.approx(4 / 5)  # lambda / (1 + lambda) with lambda = 4 * 1


# --- variants of the inputs -------------------------------------------------------------------------------


def test_without_tempo_keeps_the_stations(make_inputs):
    inputs = make_inputs()

    out = without_tempo(inputs)

    assert out.n_pixels == 0
    assert out.n_station_rows == inputs.n_station_rows


def test_with_stations_keeps_only_their_rows_and_drops_hours_left_empty(make_inputs):
    inputs = make_inputs()
    inputs.station_ids[0][:] = ["AAA", "AAA", "AAA"]  # the first hour has no BBB nor CCC

    out = with_stations(inputs, ["BBB", "CCC"])

    assert len(out.hours) == len(inputs.hours) - 1
    assert set(np.concatenate(out.station_ids)) == {"BBB", "CCC"}
    assert out.n_station_rows == 2 * len(out.hours)
    assert out.hours[0].nox.tolist() == inputs.hours[1].nox[1:].tolist()
    assert out.station_xy.index.tolist() == ["BBB", "CCC"]


def test_with_days_keeps_the_hours_of_those_days(make_inputs):
    inputs = make_inputs()
    days = diagnostics.local_days(inputs)

    out = with_days(inputs, days[3:6])

    assert diagnostics.local_days(out) == days[3:6]
    assert len(out.hours) == 3 * 6
    assert len(out.station_ids) == len(out.hours)


@pytest.mark.parametrize("degrees", [15.0, 90.0, -30.0])
def test_rotating_the_wind_keeps_its_speed_and_turns_it_clockwise(make_inputs, degrees):
    inputs = make_inputs()

    out = rotate_wind(inputs, degrees)

    def bearing(wind):  # degrees clockwise from the north, towards which it blows
        return np.rad2deg(np.arctan2(wind[0], wind[1]))

    for before, after in zip(inputs.hours, out.hours, strict=True):
        assert np.hypot(*after.wind) == pytest.approx(np.hypot(*before.wind))
        assert (bearing(after.wind) - bearing(before.wind) - degrees + 180) % 360 - 180 == pytest.approx(
            0, abs=1e-9
        )


def test_a_wind_to_the_north_rotated_90_degrees_blows_to_the_east(make_inputs):
    inputs = make_inputs()
    inputs = dataclasses.replace(inputs, hours=[dataclasses.replace(inputs.hours[0], wind=(0.0, 2.0))])

    assert rotate_wind(inputs, 90).hours[0].wind == pytest.approx((2.0, 0.0))


def test_spatial_subsets_have_distinct_stations_and_follow_their_seed():
    xy = pd.DataFrame({"x": np.arange(10) * 1000.0, "y": 0.0}, index=[f"S{i}" for i in range(10)])

    subsets = [spatial_subset(xy, 4, np.random.default_rng(seed)) for seed in range(6)]

    assert all(len(set(s)) == 4 for s in subsets)
    assert subsets[0] == spatial_subset(xy, 4, np.random.default_rng(0))
    assert len({tuple(s) for s in subsets}) > 1


def test_spatial_subsets_take_one_station_of_each_far_apart_cluster():
    x = [0.0, 10.0, 20.0, 50_000.0, 50_010.0, 50_020.0]
    xy = pd.DataFrame({"x": x, "y": 0.0}, index=list("ABCDEF"))

    for seed in range(30):
        subset = spatial_subset(xy, 2, np.random.default_rng(seed))

        assert len({s in "ABC" for s in subset}) == 2


# --- ablation ---------------------------------------------------------------------------------------------


@pytest.fixture
def table(make_inputs):
    return ablation(make_inputs(), config(), station_counts=(3, 2), wind_biases=(15.0, 30.0), seeds=range(2))


def test_the_ablation_has_a_row_per_case_and_seed(table):
    cases = table[["case", "setting", "seed"]].astype(object).where(table.notna(), None).values.tolist()

    assert cases == [
        ["baseline", None, None],
        ["no_tempo", None, None],
        ["stations", 3.0, None],  # all the stations: the baseline, once
        ["stations", 2.0, 0],
        ["stations", 2.0, 1],
        ["wind_bias", 15.0, None],
        ["wind_bias", 30.0, None],
    ]


def test_the_ablation_reports_the_harness_metrics(table):
    assert {"in_sample.r_stations", "loo.rmse.hybrid", "day_types.sunday_over_weekday.value"} <= set(table)
    assert "loo.stations" not in table
    assert table.loc[2, "loo.rmse.model"] == table.loc[0, "loo.rmse.model"]  # all stations = baseline


def test_the_ablation_changes_what_it_says_it_changes(table):
    by_case = table.groupby("case")

    assert table.loc[1, "inputs.n_pixels"] == 0
    assert np.isnan(table.loc[1, "in_sample.r_tempo"])
    assert table.loc[0, "inputs.n_pixels"] > 0
    assert (by_case.get_group("stations").loc[3:4, "loo.n_stations"] == 2).all()
    assert table.loc[5, "in_sample.rmse_stations"] != table.loc[0, "in_sample.rmse_stations"]  # wind matters
    assert table.loc[5, "inputs.n_hours"] == table.loc[0, "inputs.n_hours"]


# --- learning curve ---------------------------------------------------------------------------------------


@pytest.fixture
def curve(make_inputs):
    return learning_curve(
        make_inputs(), MAKE_MODEL, day_counts=(5, 9, 14, 61), station_counts=(2, 3, 9), seeds=range(2)
    )


def test_the_learning_curve_runs_full_cases_once_and_counts_beyond_the_data_as_full(curve):
    rows = curve[["axis", "n", "seed"]].values.tolist()

    assert rows == [
        ["days", 5, 0],
        ["days", 5, 1],
        ["days", 9, 0],
        ["days", 9, 1],
        ["days", 14, 0],
        ["stations", 2, 0],
        ["stations", 2, 1],
        ["stations", 3, 0],
    ]


def test_the_learning_curve_cases_have_the_size_they_name(curve):
    days, stations = curve[curve["axis"] == "days"], curve[curve["axis"] == "stations"]

    assert days["n_days"].tolist() == days["n"].tolist()
    assert (days["n_stations"] == 3).all()
    assert stations["n_stations"].tolist() == stations["n"].tolist()
    assert (stations["n_days"] == 14).all()


def test_in_sample_error_is_not_larger_than_the_leave_one_out_error(curve):
    assert (curve["rmse_in_sample"] <= curve["rmse_loo_model"]).all()


def test_the_learning_curve_is_reproducible_from_its_seeds(make_inputs, curve):
    again = learning_curve(
        make_inputs(), MAKE_MODEL, day_counts=(5, 9, 14, 61), station_counts=(2, 3, 9), seeds=range(2)
    )

    pd.testing.assert_frame_equal(curve, again)


# --- the run ----------------------------------------------------------------------------------------------


@pytest.fixture
def fake_data(monkeypatch, make_inputs):
    monkeypatch.setattr(diagnostics, "load_inputs", lambda *args: make_inputs())


def test_the_run_writes_the_csv_files(tmp_path, fake_data):
    out = diagnostics.run_diagnostics(config(), tmp_path, n_seeds=1)

    assert out == tmp_path / "t" / "diagnostics"
    assert {p.name for p in out.iterdir()} == {
        "variance_reduction.csv",
        "degrees_of_freedom.csv",
        "ablation.csv",
        "learning_curve.csv",
        "code_version.json",
    }
    assert pd.read_csv(out / "variance_reduction.csv")["reduction_both"].between(0, 1).all()
    assert set(pd.read_csv(out / "ablation.csv")["case"]) == {"baseline", "no_tempo", "stations", "wind_bias"}


def test_the_cli_runs_only_the_stages_asked_for(tmp_path, fake_data):
    path = tmp_path / "trial.yaml"
    path.write_text("name: trial\nperiod: {start: 2023-11-06, end: 2023-11-19}\n")

    result = CliRunner().invoke(
        cli.app, ["diagnose", str(path), "--runs-dir", str(tmp_path / "runs"), "--only", "information"]
    )

    assert result.exit_code == 0, result.output
    assert {p.name for p in (tmp_path / "runs" / "trial" / "diagnostics").iterdir()} == {
        "variance_reduction.csv",
        "degrees_of_freedom.csv",
        "code_version.json",
    }


def test_the_cli_reports_an_invalid_config_without_running(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: bad\nperiod: {start: 2023-12-01, end: 2023-11-01}\n")

    result = CliRunner().invoke(cli.app, ["diagnose", str(path), "--runs-dir", str(tmp_path / "runs")])

    assert result.exit_code == 2
    assert not (tmp_path / "runs").exists()


# --- the model and the Jacobian cache ---------------------------------------------------------------------


@pytest.fixture
def jacobian_builds(monkeypatch):
    """The number of hours of every call that builds Jacobians (`Inputs.jacobians` goes through
    `hour_jacobians`)."""
    from nox_ml.data import inputs as inputs_module

    calls = []
    build = inputs_module.hour_jacobians

    def counted(hours, *args, **kwargs):
        calls.append(len(hours))
        return build(hours, *args, **kwargs)

    monkeypatch.setattr(inputs_module, "hour_jacobians", counted)
    return calls


def test_the_diagnostics_use_the_registered_baseline_model():
    assert type(MAKE_MODEL()) is REGISTRY["inversion_plume"]


def test_the_systems_come_from_the_cache_of_the_model(make_inputs, jacobian_builds):
    inputs = make_inputs()
    model = MAKE_MODEL()

    first = model_systems(inputs, model)
    again = model_systems(inputs, model)

    assert len(jacobian_builds) == 1
    assert (
        first[0].jacobian
        is again[0].jacobian
        is inputs.jacobians(model.transport_key(), model.transport())[0]
    )


def test_the_information_needs_a_plume_inversion_model(make_inputs):
    class Reference:
        name = "idw"

    with pytest.raises(ValueError, match="plume inversion"):
        model_systems(make_inputs(), Reference())


@pytest.mark.parametrize(
    "variant",
    [
        lambda i: with_stations(i, ["AAA", "CCC"]),
        lambda i: with_days(i, diagnostics.local_days(i)[2:7]),
        without_tempo,
    ],
    ids=["stations", "days", "no_tempo"],
)
def test_a_variant_slices_the_cached_jacobians_instead_of_building_them(
    make_inputs, jacobian_builds, variant
):
    inputs = make_inputs()
    model = MAKE_MODEL()
    key, transport = model.transport_key(), model.transport()
    inputs.jacobians(key, transport)  # the baseline fills the cache
    builds = list(jacobian_builds)

    out = variant(inputs)
    sliced = out.jacobians(key, transport)

    assert jacobian_builds == builds  # nothing built for the variant
    fresh = hour_jacobians(
        out.hours, out.zones, out.points, out.no2_nox_ratio, out.n_regions, jacobian=transport
    )
    for a, b in zip(sliced, fresh, strict=True):
        np.testing.assert_allclose(a.stations, b.stations, rtol=1e-12)
        np.testing.assert_allclose(a.pixels, b.pixels, rtol=1e-12)


def test_a_rotated_wind_builds_its_own_jacobians(make_inputs, jacobian_builds):
    inputs = make_inputs()
    model = MAKE_MODEL()
    inputs.jacobians(model.transport_key(), model.transport())

    out = rotate_wind(inputs, 30)
    out.jacobians(model.transport_key(), model.transport())

    assert jacobian_builds == [len(inputs.hours)] * 2
    assert len(inputs.jacobian_cache) == 1  # the baseline cache is untouched


def test_the_ablation_and_the_curves_build_the_jacobians_of_all_the_hours_once_unless_the_wind_changes(
    make_inputs, jacobian_builds
):
    inputs = make_inputs()
    n_hours = len(inputs.hours)

    ablation(inputs, config(), station_counts=(3, 2), wind_biases=(15.0,), seeds=range(2))
    after_ablation = jacobian_builds.count(n_hours)
    learning_curve(inputs, MAKE_MODEL, day_counts=(5, 14), station_counts=(2, 3), seeds=range(2))

    assert after_ablation == 2  # the baseline and the one wind bias; the other variants slice the baseline's
    assert jacobian_builds.count(n_hours) == after_ablation
    assert max(jacobian_builds) == n_hours
