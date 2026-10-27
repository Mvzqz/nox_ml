"""``nox-ml evaluate <config> --period test``: a frozen config on feb-may 2024, kept apart from tuning."""

import json
from datetime import date

import pytest
import yaml
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.validation import experiment
from nox_ml.validation.compare import collect
from nox_ml.validation.experiment import TEST_PERIOD

TUNING = {"start": "2023-11-06", "end": "2023-11-19"}


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "frozen.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "frozen",
                "period": TUNING,
                "model": {"name": "inversion_plume", "params": {"bootstrap_n": 5}},
                "placebo": {"n": 20, "refits": 2},
            }
        )
    )
    return path


@pytest.fixture
def loaded(monkeypatch, make_inputs):
    """The periods `load_inputs` is asked for, with the synthetic inputs in place of the real data."""
    asked = []

    def load(data_dir, start, end, hours):
        asked.append((start, end))
        return make_inputs()

    monkeypatch.setattr(experiment, "load_inputs", load)
    return asked


def evaluate(config, tmp_path, *extra):
    return CliRunner().invoke(
        cli.app, ["evaluate", str(config), "--runs-dir", str(tmp_path / "runs"), *extra]
    )


def test_evaluate_runs_the_config_on_the_test_period_and_writes_name_dot_test(config, tmp_path, loaded):
    result = evaluate(config, tmp_path, "--period", "test")

    assert result.exit_code == 0, result.output
    assert loaded == [(TEST_PERIOD[0].isoformat(), TEST_PERIOD[1].isoformat())]
    out = tmp_path / "runs" / "frozen.test"
    for name in ("config.yaml", "metrics.json", "oof.parquet", "emissions.parquet", "code_version.json"):
        assert (out / name).exists()
    stored = yaml.safe_load((out / "config.yaml").read_text())
    assert stored["period"] == {"start": TEST_PERIOD[0].isoformat(), "end": TEST_PERIOD[1].isoformat()}
    assert stored["model"]["params"]["bootstrap_n"] == 5  # the rest of the config is the frozen one


def test_evaluate_leaves_a_record_in_metrics_json_with_the_same_metrics_as_run(config, tmp_path, loaded):
    evaluate(config, tmp_path, "--period", "test")

    metrics = json.loads((tmp_path / "runs" / "frozen.test" / "metrics.json").read_text())

    assert metrics["evaluation"] == {
        "period": "test",
        "start": TEST_PERIOD[0].isoformat(),
        "end": TEST_PERIOD[1].isoformat(),
        "frozen_on": TUNING,
    }
    reference = experiment.run_experiment(experiment.read_config(config), tmp_path / "reference")
    run_metrics = json.loads((reference / "metrics.json").read_text())
    assert "evaluation" not in run_metrics
    assert set(metrics) - {"evaluation"} == set(run_metrics)
    assert set(metrics["summary"]) == set(run_metrics["summary"])


def test_evaluating_twice_does_not_stack_test_suffixes(config, tmp_path, loaded):
    first = evaluate(config, tmp_path, "--period", "test")
    again = evaluate(tmp_path / "runs" / "frozen.test" / "config.yaml", tmp_path, "--period", "test")

    assert first.exit_code == again.exit_code == 0
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == ["frozen.test"]


def test_evaluate_needs_the_period_option_and_only_accepts_test(config, tmp_path, loaded):
    assert evaluate(config, tmp_path).exit_code == 2
    assert evaluate(config, tmp_path, "--period", "tuning").exit_code == 2
    assert loaded == []


def test_evaluate_refuses_an_invalid_config_without_loading_data(tmp_path, loaded):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"name": "bad", "period": TUNING, "model": {"name": "nope"}}))

    result = evaluate(bad, tmp_path, "--period", "test")

    assert result.exit_code == 2
    assert loaded == []


def test_compare_marks_the_period_of_each_run(config, tmp_path, loaded):
    experiment.run_experiment(experiment.read_config(config), tmp_path / "runs")
    evaluate(config, tmp_path, "--period", "test")

    table, _ = collect(sorted((tmp_path / "runs").iterdir()))

    assert dict(zip(table["run"], table["period"], strict=True)) == {
        "frozen": "tuning",
        "frozen.test": "test",
    }


def search_file(tmp_path, config_name: str):
    path = tmp_path / "search.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "model": "inversion_plume",
                "config": config_name,
                "search": "grid",
                "space": {"u_min_ms": [1.0]},
            }
        )
    )
    return path


def test_tune_refuses_the_config_that_evaluate_wrote(config, tmp_path, loaded):
    evaluate(config, tmp_path, "--period", "test")
    loaded.clear()
    stored = tmp_path / "runs" / "frozen.test" / "config.yaml"

    result = CliRunner().invoke(
        cli.app, ["tune", str(search_file(stored.parent, stored.name)), "--runs-dir", str(tmp_path / "t")]
    )

    assert result.exit_code == 2
    assert "test period" in result.output
    assert loaded == []  # refused before any data was loaded


def test_tune_has_no_way_to_ask_for_the_test_period():
    result = CliRunner().invoke(cli.app, ["tune", "--help"])

    assert "--period" not in result.output


def test_the_test_period_is_feb_to_may_2024():
    assert (date(2024, 2, 1), date(2024, 5, 31)) == TEST_PERIOD
