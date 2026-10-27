"""Acceptance checks of Avance 5: each front runs its own when its part is done.

    uv run pytest -m acceptance -k front_a     # X1 bagged_inversion, X2 wind_ensemble
    uv run pytest -m acceptance -k front_b     # X5 stacking, X6 bayes_average
    uv run pytest -m acceptance -k front_c     # X4 gb_deweather (X3 pinn_seeds, if registered)
    uv run pytest -m acceptance -k delivery    # the whole delivery (coordination)

They are deselected from the default run (and CI) until then: they fail on purpose while a part is missing.
They check the shape of the delivery (registered model, config, tuning, stored run), not the science; the
contract tests (`ml/tests/models/test_contract.py`) check the model itself.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from nox_ml.models import REGISTRY
from nox_ml.validation.experiment import read_config
from nox_ml.validation.metrics import RunMetrics
from nox_ml.validation.tune import read_search

pytestmark = pytest.mark.acceptance

ROOT = Path(__file__).resolve().parents[3]
CONFIGS = ROOT / "configs" / "experiments"
RUNS = ROOT / "results" / "runs"

TUNING_PERIOD = (date(2023, 11, 1), date(2023, 12, 31))
BEST_INDIVIDUAL = ("pinn_puff", "inversion_puff", "pinn_plume")  # E5b, E2, E5a: the stacking bases
MIN_STATIONS = 20  # held-out stations an out-of-fold file must cover

# name -> (front, kind, tuned)
ENSEMBLES = {
    "bagged_inversion": ("front_a", "homogeneous", True),
    "wind_ensemble": ("front_a", "homogeneous", True),
    "stacking": ("front_b", "heterogeneous", True),
    "bayes_average": ("front_b", "heterogeneous", False),
    "gb_deweather": ("front_c", "homogeneous", True),
}
OPTIONAL = {"pinn_seeds": ("front_c", "homogeneous", False)}


def cases(table: dict[str, tuple[str, str, bool]], tuned_only: bool = False) -> list:
    return [
        pytest.param(name, id=f"{front}-{name}")
        for name, (front, _, tuned) in table.items()
        if tuned or not tuned_only
    ]


def summary(run: Path) -> RunMetrics:
    return RunMetrics.model_validate(json.loads((run / "metrics.json").read_text())["summary"])


def run_model(run: Path) -> str | None:
    config = run / "config.yaml"
    return yaml.safe_load(config.read_text())["model"]["name"] if config.exists() else None


# --- Per ensemble ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", cases(ENSEMBLES))
def test_the_ensemble_is_registered_as_a_model(name):
    assert name in REGISTRY, f"{name} is not in nox_ml.models.REGISTRY"
    assert REGISTRY[name].role == "model", "an ensemble estimates emissions: role must be 'model'"


@pytest.mark.parametrize("name", cases(ENSEMBLES))
def test_its_config_runs_on_the_tuning_period_like_the_other_models(name):
    config = read_config(CONFIGS / f"{name}.yaml")
    baseline = read_config(CONFIGS / "baseline.yaml")

    assert config.model.name == name
    period = (config.period.start, config.period.end)
    assert period == TUNING_PERIOD, "nov-dec 2023 only: feb-may 2024 is the test period"
    assert config.simat_hours == baseline.simat_hours
    assert config.placebo == baseline.placebo, "the same placebo as every other model"


@pytest.mark.parametrize("name", cases(ENSEMBLES, tuned_only=True))
def test_its_search_is_valid_and_was_run(name):
    searches = [p for p in CONFIGS.glob("*.search.yaml") if yaml.safe_load(p.read_text())["model"] == name]
    assert searches, f"no configs/experiments/*.search.yaml with model: {name}"
    for path in searches:
        read_search(path)  # valid, existing params, and outside the test period

    tuned = [p.parent for p in RUNS.glob("*/trials.csv") if run_model(p.parent) == name]
    assert tuned, f"no results/runs/<run>/trials.csv of {name}: run `nox-ml tune` and copy the folder"
    trials = pd.read_csv(tuned[0] / "trials.csv")
    assert len(trials) >= 4, "the search must be deep enough to show where the optimum is"


@pytest.mark.parametrize("name", cases(ENSEMBLES))
def test_its_run_is_stored_with_metrics_predictions_and_emissions(name):
    run = RUNS / name
    for file in ("config.yaml", "metrics.json", "oof.parquet", "emissions.parquet", "code_version.json"):
        assert (run / file).exists(), f"results/runs/{name}/{file} is missing: run `nox-ml run` and copy it"
    assert run_model(run) == name

    s = summary(run)
    assert s.role == "model"
    assert s.sunday_ratio is not None and s.placebo_center is not None, "emission metrics are required"
    assert s.eligible is not None
    assert s.fit_seconds > 0, "training time is part of the comparison table"

    oof = pd.read_parquet(run / "oof.parquet")
    assert {"station", "utc", "nox_ppb_pred"} <= set(oof.columns)
    assert len(set(oof["station"])) >= MIN_STATIONS
    assert bool(oof["nox_ppb_pred"].notna().all())
    assert len(pd.read_parquet(run / "emissions.parquet")) > 0


@pytest.mark.parametrize("name", [n for n, (front, *_) in ENSEMBLES.items() if front == "front_b"])
def test_front_b_the_heterogeneous_ensembles_combine_the_best_individual_models(name):
    text = (CONFIGS / f"{name}.yaml").read_text()
    missing = [m for m in BEST_INDIVIDUAL if m not in text]
    assert not missing, f"{name} must combine the best models of Avance 4; missing {missing}"


@pytest.mark.parametrize("name", cases(OPTIONAL))
def test_an_optional_ensemble_if_registered_is_complete(name):
    if name not in REGISTRY:
        pytest.skip(f"{name} is optional and not registered")
    test_its_config_runs_on_the_tuning_period_like_the_other_models(name)
    test_its_run_is_stored_with_metrics_predictions_and_emissions(name)


# --- The whole delivery (coordination) ---------------------------------------------------------------------


def stored_ensembles() -> dict[str, str]:
    table = ENSEMBLES | OPTIONAL
    return {name: table[name][1] for name in table if (RUNS / name / "metrics.json").exists()}


def test_delivery_has_at_least_four_ensembles_of_both_kinds():
    stored = stored_ensembles()
    assert len(stored) >= 4, f"at least 4 ensembles with a stored run; have {sorted(stored)}"
    assert set(stored.values()) == {"homogeneous", "heterogeneous"}, "both strategies are required"


def test_delivery_the_comparison_includes_the_best_individual_model():
    assert (RUNS / BEST_INDIVIDUAL[0] / "metrics.json").exists()


def test_delivery_the_final_model_was_evaluated_once_on_the_test_period():
    runs = [p for p in RUNS.glob("*.test") if (p / "metrics.json").exists()]
    assert runs, "no results/runs/<final>.test/: run `nox-ml evaluate <config> --period test`"
    for run in runs:
        config = yaml.safe_load((run / "config.yaml").read_text())
        assert str(config["period"]["start"]) >= "2024-02-01", f"{run.name} is not on feb-may 2024"
        assert (run / "oof.parquet").exists(), "the plots of the final model need its out-of-fold predictions"


def test_delivery_the_notebook_exists_with_outputs_and_ends_with_the_ai_declaration():
    path = ROOT / "notebooks" / "Avance5.39.ipynb"
    assert path.exists()
    cells = json.loads(path.read_text())["cells"]
    code = [c for c in cells if c["cell_type"] == "code"]
    assert code and all(c["outputs"] for c in code), "run it top to bottom and store it with its outputs"
    assert cells[-1]["cell_type"] == "markdown"
    assert "Declaración del uso de herramientas de IA" in "".join(cells[-1]["source"])
    assert (ROOT / "docs" / "entregables" / "html" / "Avance5.39.html").exists()
