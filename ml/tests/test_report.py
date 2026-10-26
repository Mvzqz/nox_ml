import json

import pandas as pd
import pytest
import yaml

from nox_ml.validation import compare, report


def write_run(folder, model, rmse, role="model", eligible: bool | None = True, trials=None):
    folder.mkdir(parents=True)
    summary = {"model": model, "role": role, "loo_rmse_ppb": rmse, "eligible": eligible, "sunday_ratio": 0.6}
    (folder / "metrics.json").write_text(json.dumps({"summary": summary}))
    (folder / "config.yaml").write_text(yaml.safe_dump({"model": {"name": model}}))
    if trials is not None:
        pd.DataFrame(trials).to_csv(folder / "trials.csv", index=False)


@pytest.fixture
def runs(tmp_path):
    write_run(tmp_path / "baseline", "inversion_plume", 13.6)
    write_run(tmp_path / "puff", "inversion_puff", 12.0)
    write_run(tmp_path / "rf", "rf_deweather", 11.0, eligible=False)
    write_run(tmp_path / "idw", "idw", 11.6, role="reference", eligible=None)
    trials = {"trial": [0, 1, 2], "u_min_ms": [0.5, 1.0, 2.0], "loo_rmse_ppb": [13.0, 11.5, 12.0]}
    write_run(tmp_path / "puff_tuned", "inversion_puff", 11.5, trials=trials)
    return tmp_path


def comparison(runs):
    return compare.collect(report.run_dirs(runs))[0]


def test_the_comparison_leaves_out_the_tuned_runs_and_the_tuned_runs_are_listed_apart(runs):
    assert "puff_tuned" not in set(comparison(runs)["run"])
    assert [p.name for p in report.run_dirs(runs, tuned=True)] == ["puff_tuned"]


def test_the_ranking_has_one_row_per_planned_model_and_leaves_out_variants_and_references(runs):
    write_run(runs / "pinn_puff", "pinn_puff", 11.9)
    write_run(runs / "pinn_puff_oh", "pinn_puff", 11.9)  # a variant of the tuning, not a planned run
    table = comparison(runs)

    ranked = report.ranking(table)

    assert list(ranked["run"]) == ["pinn_puff", "baseline"]
    assert list(ranked["id"]) == ["E5b", "E1"]
    assert list(report.references(table)["run"]) == ["idw"]


def test_find_runs_looks_for_the_given_folder_in_the_repository(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")

    assert report.find_runs("results/runs") == tmp_path.resolve() / "results" / "runs"
    assert report.find_runs() == tmp_path.resolve() / "runs"


def test_missing_lists_the_planned_models_without_a_run(runs):
    pending = report.missing(comparison(runs))

    assert {"inversion_plume", "inversion_puff", "rf_deweather", "idw"}.isdisjoint(pending["model"])
    assert {"regularized_ls", "pinn_plume"} <= set(pending["model"])


def test_selection_takes_the_best_eligible_models_and_never_a_reference(runs):
    best = report.selection(comparison(runs))

    assert list(best["model"]) == ["inversion_puff", "inversion_plume"]  # rf is faster but fails the placebo


def test_selection_with_fewer_eligible_models_than_asked_returns_those(tmp_path):
    write_run(tmp_path / "baseline", "inversion_plume", 13.6)

    assert len(report.selection(comparison(tmp_path))) == 1


def test_tuning_summary_reports_the_gain_over_the_untuned_run(runs):
    summary = report.tuning_summary(runs, comparison(runs)).iloc[0]

    assert (summary["model"], summary["n_trials"], summary["best_trial"]) == ("inversion_puff", 3, 1)
    assert summary["gain_ppb"] == pytest.approx(12.0 - 11.5)
    assert summary["refit_rmse_ppb"] == pytest.approx(11.5)


def test_search_space_shows_the_range_each_param_took(runs):
    space = report.search_space(report.read_trials(runs)["puff_tuned"])

    assert space.iloc[0].to_dict() == {"param": "u_min_ms", "min": 0.5, "max": 2.0, "values": 3}


def test_everything_tolerates_a_folder_without_runs(tmp_path):
    empty = tmp_path / "no_runs_here"
    table = comparison(empty)

    assert table.empty
    assert len(report.missing(table)) == len(report.PLANNED)
    assert report.selection(table).empty
    assert report.ranking(table).empty
    assert report.references(table).empty
    assert report.read_trials(empty) == {}
    assert report.tuning_summary(empty, table).empty
    assert report.kappa_grid(empty).empty
    assert report.models(table, ["pinn_puff"]).empty
    assert report.plot_trials(empty, table) is None


def test_the_trial_curve_has_one_panel_per_search(runs):
    fig = report.plot_trials(runs, comparison(runs))

    assert fig is not None
    assert len(fig.axes) == 1


def test_models_keeps_the_requested_order_and_skips_the_ones_without_run(runs):
    shown = report.models(comparison(runs), ["rf_deweather", "pinn_puff", "inversion_plume"])

    assert list(shown["model"]) == ["rf_deweather", "inversion_plume"]


def test_pinn_joint_is_not_expected_because_the_advance_leaves_it_out(tmp_path):
    assert "pinn_joint" not in set(report.missing(comparison(tmp_path))["model"])


def test_param_effects_ranks_the_params_by_how_much_they_move_the_error():
    trials = pd.DataFrame(
        {
            "trial": range(5),
            "u_min": [1.0, 1.5, 2.0, 1.0, 2.0],
            "width": [32, 32, 32, 32, 32],  # one value: nothing to measure
            "tau_h": [6.0, 12.0, 6.0, 12.0, 12.0],
            "loo_rmse_ppb": [12.08, 12.0, 11.9, 12.08, 11.9],
        }
    )

    effects = report.param_effects(trials).set_index("param")

    assert list(effects.index) == ["u_min", "tau_h"]
    assert effects.loc["u_min", "rank_corr"] < -0.9
    assert effects.loc["u_min", "best_value"] == 2.0
    assert effects.loc["u_min", "best_by_value_spread_ppb"] == pytest.approx(0.18)
    assert abs(effects.loc["tau_h", "rank_corr"]) < abs(effects.loc["u_min", "rank_corr"])


def test_the_kappa_grid_is_sorted_by_kappa_and_stays_out_of_the_comparison(tmp_path):
    for name, kappa, rmse in [("pinn_puff_k3000", 3000, 12.4), ("pinn_puff_k500", 500, 12.9)]:
        write_run(tmp_path / name, "pinn_puff", rmse)
        (tmp_path / name / "config.yaml").write_text(
            yaml.safe_dump({"model": {"name": "pinn_puff", "params": {"kappa": kappa}}})
        )
    write_run(tmp_path / "pinn_puff", "pinn_puff", 12.08)  # default kappa: not in its config

    grid = report.kappa_grid(tmp_path)

    assert list(grid["kappa_m"]) == [500.0, 1500.0, 3000.0]
    assert list(grid["loo_rmse_ppb"]) == [12.9, 12.08, 12.4]
    assert list(comparison(tmp_path)["run"]) == ["pinn_puff"]


def test_the_road_total_ratio_compares_the_weekday_road_emission_of_two_runs(tmp_path):
    for name, total in [("baseline", 40_000), ("pinn_plume", 57_500)]:
        (tmp_path / name).mkdir()
        metrics = {"day_types": {"road_total": {"weekday": total}}}
        (tmp_path / name / "metrics.json").write_text(json.dumps(metrics))

    row = report.road_total_ratio(tmp_path, "pinn_plume").iloc[0]

    assert row["ratio"] == pytest.approx(1.4375)


def test_the_road_total_ratio_is_empty_when_a_run_is_missing(tmp_path):
    assert report.road_total_ratio(tmp_path, "pinn_plume").empty
