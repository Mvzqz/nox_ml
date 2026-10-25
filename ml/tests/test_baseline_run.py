"""The baseline run reproduces the research row. Run with `pytest -m slow` after `dvc pull` (about 4 min)."""

import json
from pathlib import Path

import pytest

from nox_ml.validation.experiment import read_config, run_experiment

ROOT = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not (ROOT / "data" / "interim" / "simat_nox.parquet").exists(), reason="data not pulled"
    ),
]

PPB, RATIO = 0.05, 0.01  # tolerances of the acceptance: ppb for RMSE, absolute for r and ratios


@pytest.fixture(scope="module")
def metrics(tmp_path_factory) -> dict:
    config = read_config(ROOT / "configs" / "experiments" / "baseline.yaml")
    out = run_experiment(
        config.model_copy(update={"data_dir": ROOT / "data"}), tmp_path_factory.mktemp("runs")
    )
    assert {p.name for p in out.iterdir()} == {
        "config.yaml",
        "metrics.json",
        "code_version.json",
        "oof.parquet",
        "emissions.parquet",
    }
    return json.loads((out / "metrics.json").read_text())


def test_inputs_are_the_ones_of_the_research(metrics):
    """real_check_linear_domain_sin_industria: 366 hours, 7,537 station rows, 78,227 TEMPO pixels."""
    assert metrics["inputs"]["n_hours"] == 366
    assert metrics["inputs"]["n_station_rows"] == 7537
    assert metrics["inputs"]["n_pixels"] == 78227


def test_in_sample_correlations_match_base_sigma30(metrics):
    """'Dominio, sin industria' 15 degrees: r 0.77 at the stations, 0.74 with TEMPO."""
    assert metrics["in_sample"]["r_stations"] == pytest.approx(0.77, abs=RATIO)
    assert metrics["in_sample"]["r_tempo"] == pytest.approx(0.74, abs=RATIO)


def test_leave_one_out_matches_base_sigma30(metrics):
    """RMSE model / IDW / hybrid 13.6 / 11.6 / 11.7 ppb; hybrid bias / hour-to-hour 6.1 / 10.0; 15 of 24."""
    loo = metrics["loo"]
    assert loo["rmse"]["model"] == pytest.approx(13.6, abs=PPB)
    assert loo["rmse"]["idw"] == pytest.approx(11.6, abs=PPB)
    assert loo["rmse"]["hybrid"] == pytest.approx(11.7, abs=PPB)
    assert loo["bias"]["hybrid"] == pytest.approx(6.1, abs=PPB)
    assert loo["hourly"]["hybrid"] == pytest.approx(10.0, abs=PPB)
    assert (loo["hybrid_beats_idw"], loo["n_stations"]) == (15, 24)


def test_sunday_and_saturday_over_weekday_match_base_sigma30(metrics):
    """Sunday 0.42 (0.35-0.54) and Saturday 0.78."""
    days = metrics["day_types"]
    assert days["sunday_over_weekday"]["value"] == pytest.approx(0.42, abs=RATIO)
    assert days["sunday_over_weekday"]["lo"] == pytest.approx(0.35, abs=RATIO)
    assert days["sunday_over_weekday"]["hi"] == pytest.approx(0.54, abs=RATIO)
    assert days["saturday_over_weekday"]["value"] == pytest.approx(0.78, abs=RATIO)


def test_normalized_placebo_width_stays_where_the_baseline_run_put_it(metrics):
    """Not in base_sigma30.md: the value of the first baseline run (0.25; the research had 0.26 with another
    region scheme), a guard against drift. 41 weekdays and 11 Sundays or holidays."""
    normalized = metrics["normalized"]
    assert normalized["placebo_half_width"] == pytest.approx(0.25, abs=0.02)
    assert (normalized["n_weekdays"], normalized["n_sundays"]) == (41, 11)
