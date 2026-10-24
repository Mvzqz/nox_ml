"""Research figures reproduced from the real data (DVC). Run with `pytest -m slow` after `dvc pull`."""

from pathlib import Path

import pandas as pd
import pytest

from nox_ml.data import pbl, simat, tempo

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not (RAW / "simat").exists(), reason="data not pulled")]


@pytest.fixture(scope="module")
def simat_checks(tmp_path_factory):
    out = tmp_path_factory.mktemp("interim")
    return out, [c.message for c in simat.run_qc(RAW / "simat", out, [2023, 2024])]


def test_simat_reproduces_the_research_qc_figures(simat_checks):
    _, messages = simat_checks

    assert "NOX hours in runs > 6 h with identical value: 59 (ACO:9, MON:14, PED:7, TAH:29)" in messages
    assert "Correction applied: WSP of 2024 / 2.237 (142,690 rows; original in WSP_raw)" in messages
    assert "Hours > 250 ppb (flagged): NO=299, NO2=0, NOX=810" in messages
    assert "Mean afternoon wind direction (from): 51 deg" in messages


def test_tempo_reproduces_the_research_qc_figures(simat_checks):
    out, _ = simat_checks

    messages = [
        c.message
        for c in tempo.run_qc(
            RAW / "tempo", out, simat.load_catalog(RAW / "simat"), "2023-11-01", "2023-12-31"
        )
    ]

    assert any("Granules with >= 50 % of the domain valid: 48% (191 of 396)" in m for m in messages)
    assert any("hour-station pairs, n=4906): r = 0.77" in m for m in messages)
    assert any("Core / surroundings: 2.15x" in m for m in messages)


def test_pbl_reproduces_the_merra2_vs_era5_agreement(tmp_path):
    messages = [c.message for c in pbl.run_fill(RAW / "merra2", RAW / "era5_openmeteo", tmp_path)]

    assert any(m.startswith("Afternoon: r = 0.68, median bias MERRA-2 - ERA5 = 224 m") for m in messages)
    assert "MERRA-2 corrected: 4368 hours" in messages
    filled = pd.read_parquet(tmp_path / "pbl_2023_2024.parquet")
    assert bool((filled["source"] != "missing").all())
