import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.validation import experiment
from nox_ml.validation.experiment import (
    ExperimentConfig,
    ModelConfig,
    Placebo,
    code_version,
    evaluate,
    read_config,
    run_experiment,
)

BASELINE = Path(__file__).parents[2] / "configs" / "experiments" / "baseline.yaml"


def config(**changes) -> ExperimentConfig:
    base = {
        "name": "t",
        "period": {"start": "2023-11-06", "end": "2023-11-19"},
        "model": {"name": "inversion_plume", "params": {"bootstrap_n": 8}},
        "placebo": {"n": 50, "refits": 3},
    }
    return ExperimentConfig.model_validate(base | changes)


# --- the config ---------------------------------------------------------------------------------------------


def test_baseline_yaml_is_valid_and_states_the_defaults_it_documents():
    cfg = read_config(BASELINE)

    assert cfg.name == "baseline"
    assert (cfg.period.start.isoformat(), cfg.period.end.isoformat()) == ("2023-11-01", "2023-12-31")
    assert cfg.simat_hours == (12, 17)
    assert cfg.model == ModelConfig()  # the YAML repeats the defaults; they must not drift apart
    assert cfg.placebo == Placebo()


def test_config_rejects_unknown_fields_so_a_typo_does_not_run_the_baseline():
    with pytest.raises(ValidationError, match="sigma_thetta"):
        config(sigma_thetta=30)


@pytest.mark.parametrize(
    "changes",
    [
        {"period": {"start": "2023-12-01", "end": "2023-11-01"}},
        {"simat_hours": [17, 12]},
        {"simat_hours": [12, 25]},
        {"name": "../escape"},
        {"model": {"params": {"bootstrap_n": 0}}},
        {"model": {"params": {"bootstrap_level": 1.5}}},
        {"model": {"name": "nope"}},
        {"model": {"params": {"sigma_thetta_deg": 30}}},
        {"placebo": {"refits": 1}},
    ],
)
def test_config_rejects_values_that_make_no_sense(changes):
    with pytest.raises(ValidationError):
        config(**changes)


# --- code version -------------------------------------------------------------------------------------------


def test_code_version_is_the_git_hash_of_the_checkout():
    version = code_version()

    assert len(version["git_hash"]) == 40
    assert isinstance(version["dirty"], bool)


def test_code_version_is_unknown_outside_git(monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(experiment.subprocess, "run", no_git)

    assert code_version() == {"git_hash": "unknown", "dirty": None}


# --- metrics ------------------------------------------------------------------------------------------------


def test_metrics_cover_every_block_of_the_baseline_table(make_inputs):
    metrics = evaluate(make_inputs(), config()).metrics

    assert metrics["inputs"]["n_hours"] == 84
    assert set(metrics["in_sample"]) == {"r_stations", "rmse_stations", "r_tempo"}
    assert set(metrics["loo"]["rmse"]) == {"model", "idw", "hybrid"}
    assert set(metrics["loo"]["stations"]) == {"AAA", "BBB", "CCC"}
    assert metrics["loo"]["n_stations"] == 3
    assert metrics["day_types"]["n_days"] == 14
    assert metrics["normalized"]["n_sundays"] == 2
    assert metrics["normalized"]["n_weekdays"] == 10
    json.dumps(metrics)  # serializable as is


def test_sunday_over_weekday_is_below_one_when_sundays_have_less_nox(make_inputs):
    metrics = evaluate(make_inputs(sunday_scale=0.3), config()).metrics

    sunday = metrics["day_types"]["sunday_over_weekday"]
    assert sunday["value"] < 0.8
    assert sunday["lo"] <= sunday["hi"]


def test_the_bootstrap_is_reproducible_from_its_seed(make_inputs):
    inputs = make_inputs()

    a = evaluate(inputs, config()).metrics["day_types"]["sunday_over_weekday"]
    b = evaluate(inputs, config()).metrics["day_types"]["sunday_over_weekday"]
    c = evaluate(inputs, config(model={"params": {"bootstrap_n": 8, "seed": 99}})).metrics["day_types"][
        "sunday_over_weekday"
    ]

    assert a == b
    assert (a["lo"], a["hi"]) != (c["lo"], c["hi"])
    assert a["value"] == c["value"]  # the point estimate does not depend on the bootstrap


def test_placebo_half_width_is_half_the_interval_around_one(make_inputs):
    quiet = evaluate(make_inputs(seed=1), config()).metrics["normalized"]
    assert quiet["placebo_lo"] < 1 < quiet["placebo_hi"]
    assert quiet["placebo_half_width"] == pytest.approx((quiet["placebo_hi"] - quiet["placebo_lo"]) / 2)


# --- the run ------------------------------------------------------------------------------------------------


@pytest.fixture
def fake_data(monkeypatch, make_inputs):
    """Replace the file loading with the small synthetic inputs."""
    monkeypatch.setattr(experiment, "load_inputs", lambda *args: make_inputs())


def test_a_run_writes_config_metrics_and_code_version(tmp_path, fake_data):
    out = run_experiment(config(name="trial"), tmp_path)

    assert out == tmp_path / "trial"
    assert read_config(out / "config.yaml") == config(name="trial")
    assert "r_stations" in json.loads((out / "metrics.json").read_text())["in_sample"]
    assert json.loads((out / "code_version.json").read_text())["git_hash"] == code_version()["git_hash"]


def test_the_stored_config_includes_the_defaults(tmp_path, fake_data):
    out = run_experiment(config(name="trial"), tmp_path)

    stored = yaml.safe_load((out / "config.yaml").read_text())
    assert stored["simat_hours"] == [12, 17]
    assert stored["model"] == {
        "name": "inversion_plume",
        "params": {
            "seed": 7,
            "sigma_theta_deg": 15.0,
            "u_min_ms": 1.0,
            "bootstrap_n": 8,
            "bootstrap_level": 0.9,
        },
    }


def test_the_cli_runs_a_config_and_prints_the_headline(tmp_path, fake_data):
    path = tmp_path / "trial.yaml"
    path.write_text(
        "name: trial\nperiod: {start: 2023-11-06, end: 2023-11-19}\n"
        "model: {name: inversion_plume, params: {bootstrap_n: 4}}\nplacebo: {n: 20, refits: 2}\n"
    )

    result = CliRunner().invoke(cli.app, ["run", str(path), "--runs-dir", str(tmp_path / "runs")])

    assert result.exit_code == 0, result.output
    assert "in-sample r: stations" in result.stdout
    assert (tmp_path / "runs" / "trial" / "metrics.json").exists()


def test_the_cli_reports_an_invalid_config_without_running(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: bad\nperiod: {start: 2023-12-01, end: 2023-11-01}\n")

    result = CliRunner().invoke(cli.app, ["run", str(path), "--runs-dir", str(tmp_path / "runs")])

    assert result.exit_code == 2
    assert "end is before start" in result.output
    assert not (tmp_path / "runs").exists()
