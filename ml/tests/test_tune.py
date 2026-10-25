from datetime import date

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.validation import experiment
from nox_ml.validation.tune import read_search, trials

PERIOD = {"start": "2023-11-06", "end": "2023-11-19"}


def write(tmp_path, search: dict, period: dict = PERIOD, model: str = "inversion_plume"):
    (tmp_path / "base.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "base",
                "period": period,
                "model": {"name": model, "params": {"bootstrap_n": 5}},
                "placebo": {"n": 20, "refits": 2},
            }
        )
    )
    path = tmp_path / "search.yaml"
    path.write_text(yaml.safe_dump({"model": "inversion_plume", "config": "base.yaml"} | search))
    return path


def test_the_search_refuses_a_period_that_overlaps_the_test_months(tmp_path):
    path = write(
        tmp_path,
        {"search": "grid", "space": {"u_min_ms": [1.0]}},
        {"start": "2023-12-15", "end": "2024-02-10"},
    )

    with pytest.raises(ValueError, match="reserved for the final model"):
        read_search(path)


def test_the_search_accepts_the_tuning_period(tmp_path):
    search, base = read_search(write(tmp_path, {"search": "grid", "space": {"u_min_ms": [1.0]}}))

    assert base.period.end < date(2024, 2, 1)
    assert search.model == "inversion_plume"


def test_the_search_rejects_params_the_model_does_not_have(tmp_path):
    with pytest.raises(ValueError, match="sigma_puff"):
        read_search(write(tmp_path, {"search": "grid", "space": {"sigma_puff": [1]}}))


def test_random_search_needs_a_number_of_trials(tmp_path):
    with pytest.raises(ValueError, match="n_trials"):
        read_search(write(tmp_path, {"search": "random", "space": {"u_min_ms": [0.5, 2.0]}}))


def test_grid_search_tries_every_combination(tmp_path):
    search, base = read_search(
        write(
            tmp_path, {"search": "grid", "space": {"u_min_ms": [0.5, 1.0, 2.0], "sigma_theta_deg": [10, 20]}}
        )
    )

    combos = trials(search, base)

    assert len(combos) == 6
    assert {(c["u_min_ms"], c["sigma_theta_deg"]) for c in combos} == {
        (u, s) for u in (0.5, 1.0, 2.0) for s in (10, 20)
    }


def test_random_search_draws_ranges_and_choices_reproducibly(tmp_path):
    space = {"sigma_theta_deg": [10, 45], "u_min_ms": [0.5, 1.0, 1.5], "bootstrap_n": [5, 9]}
    search, base = read_search(
        write(tmp_path, {"search": "random", "n_trials": 20, "seed": 3, "space": space})
    )

    a, b = trials(search, base), trials(search, base)

    assert a == b
    assert len(a) == 20
    assert all(10 <= t["sigma_theta_deg"] <= 45 for t in a)
    assert len({t["sigma_theta_deg"] for t in a}) > 1  # continuous, not the two ends
    assert {t["u_min_ms"] for t in a} <= {0.5, 1.0, 1.5}
    assert all(isinstance(t["bootstrap_n"], int) and 5 <= t["bootstrap_n"] <= 9 for t in a)


def test_every_trial_is_validated_before_any_runs(tmp_path):
    search, base = read_search(write(tmp_path, {"search": "grid", "space": {"u_min_ms": [1.0, -2.0]}}))

    with pytest.raises(ValueError, match="u_min_ms"):
        trials(search, base)


def test_the_cli_writes_the_trials_and_refits_the_best(tmp_path, monkeypatch, make_inputs):
    monkeypatch.setattr(experiment, "load_inputs", lambda *args: make_inputs())
    monkeypatch.setattr(cli, "load_inputs", lambda *args: make_inputs())
    path = write(tmp_path, {"search": "grid", "space": {"u_min_ms": [0.5, 1.0, 2.0]}})

    result = CliRunner().invoke(cli.app, ["tune", str(path), "--runs-dir", str(tmp_path / "runs")])

    assert result.exit_code == 0, result.output
    trials_csv = pd.read_csv(tmp_path / "runs" / "search" / "trials.csv")
    assert trials_csv["trial"].tolist() == [0, 1, 2]
    best = trials_csv.loc[trials_csv["loo_rmse_ppb"].idxmin(), "u_min_ms"]
    stored = yaml.safe_load((tmp_path / "runs" / "search" / "config.yaml").read_text())
    assert stored["model"]["params"]["u_min_ms"] == best
    assert (tmp_path / "runs" / "search" / "metrics.json").exists()


def test_the_cli_refuses_the_test_period_without_loading_data(tmp_path):
    path = write(
        tmp_path,
        {"search": "grid", "space": {"u_min_ms": [1.0]}},
        {"start": "2024-02-01", "end": "2024-05-31"},
    )

    result = CliRunner().invoke(cli.app, ["tune", str(path), "--runs-dir", str(tmp_path / "runs")])

    assert result.exit_code == 2
    assert "test period" in result.output
    assert not (tmp_path / "runs").exists()
