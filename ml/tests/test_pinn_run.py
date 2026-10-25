"""The PINN run reproduces the research figures. Run with `pytest -m slow` after `dvc pull` (about 20 min:
it trains the network from scratch once, then runs the inversion with its leave-one-out refits and placebo
fits)."""

import json
from pathlib import Path

import pytest

from nox_ml.models.pinn.cache import KernelCache
from nox_ml.models.pinn.kernel import validate
from nox_ml.models.pinn.params import PinnParams
from nox_ml.validation.experiment import read_config, run_experiment

ROOT = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (ROOT / "data" / "interim" / "simat_nox.parquet").exists(), reason="data not pulled"
    ),
]


@pytest.fixture(scope="module")
def metrics(tmp_path_factory) -> dict:
    config = read_config(ROOT / "configs" / "experiments" / "pinn_plume.yaml")
    out = run_experiment(
        config.model_copy(update={"data_dir": ROOT / "data"}), tmp_path_factory.mktemp("runs")
    )
    return json.loads((out / "metrics.json").read_text())


def test_the_network_trained_from_scratch_is_within_the_research_error_of_the_exact_solution(tmp_path):
    """`reports/pinn_prototipo.md`: median error 3.5-6.6 %, mass error within 6.4 %."""
    kernel = KernelCache(tmp_path).get(PinnParams())

    for row in validate(kernel.net).values():
        assert row["median_rel_error"] < 0.07
        assert abs(row["mass_error"]) < 0.07


def test_the_inputs_are_the_ones_of_the_baseline(metrics):
    assert (metrics["inputs"]["n_hours"], metrics["inputs"]["n_station_rows"]) == (366, 7537)
    assert metrics["inputs"]["n_pixels"] == 78227


def test_the_sunday_over_weekday_ratio_is_the_one_of_the_research_pinn(metrics):
    """Research PINN, nov-dec 2023: 0.43 (0.35-0.55) and Saturday 0.76. Here, with the baseline inputs and
    priors, the first run gave 0.42 (0.34-0.53) and 0.74."""
    days = metrics["day_types"]

    assert days["sunday_over_weekday"]["value"] == pytest.approx(0.43, abs=0.02)
    assert days["sunday_over_weekday"]["lo"] == pytest.approx(0.35, abs=0.03)
    assert days["sunday_over_weekday"]["hi"] == pytest.approx(0.55, abs=0.03)
    assert days["saturday_over_weekday"]["value"] == pytest.approx(0.76, abs=0.03)


def test_the_fit_to_stations_and_tempo_is_the_one_of_the_research_pinn(metrics):
    """Research PINN: leave-one-station-out RMSE 12.5 ppb, r with TEMPO 0.78, weekday road total about
    57,500 t/yr (58 % of the inventory)."""
    assert metrics["loo"]["rmse"]["model"] == pytest.approx(12.5, abs=0.2)
    assert metrics["in_sample"]["r_tempo"] == pytest.approx(0.78, abs=0.01)
    assert metrics["day_types"]["road_total"]["weekday"] == pytest.approx(57_500, rel=0.05)
