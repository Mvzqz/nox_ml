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
    assert report.read_trials(empty) == {}
    assert report.tuning_summary(empty, table).empty
    assert report.plot_trials(empty, table) is None


def test_the_trial_curve_has_one_panel_per_search(runs):
    fig = report.plot_trials(runs, comparison(runs))

    assert fig is not None
    assert len(fig.axes) == 1
