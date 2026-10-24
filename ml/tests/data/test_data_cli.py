import pandas as pd
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.cli import app
from nox_ml.data import pbl

runner = CliRunner()


def test_qc_simat_command_prints_checks_and_writes_tables(simat_dir, tmp_path):
    out = tmp_path / "interim"

    result = runner.invoke(app, ["qc-simat", "2024", "--raw-dir", str(simat_dir), "--out-dir", str(out)])

    assert result.exit_code == 0, result.output
    assert "[ok] NO/NO2/NOX units: ['ppb']" in result.stdout
    assert (out / "simat_nox.parquet").exists()
    assert (out / "simat_wind.parquet").exists()


def test_qc_tempo_command_uses_the_simat_catalog_and_output_folder(simat_dir, tmp_path, write_tempo_granule):
    out, raw = tmp_path / "interim", tmp_path / "tempo"
    raw.mkdir()
    runner.invoke(app, ["qc-simat", "2024", "--raw-dir", str(simat_dir), "--out-dir", str(out)])
    scan = "TEMPO_NO2_L2_V04_20240102T193000Z_S011G06_zmvm.nc"
    write_tempo_granule(raw / scan, lat=[19.40], lon=[-99.12], vcd=[2e16])

    result = runner.invoke(
        app,
        [
            "qc-tempo",
            "2024-01-02",
            "2024-01-02",
            "--raw-dir",
            str(raw),
            "--simat-dir",
            str(simat_dir),
            "--out-dir",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "TEMPO NO2 L2 V04, 2024-01-02 to 2024-01-02" in result.stdout
    assert (out / "tempo_pixels_2024-01-02_2024-01-02.parquet").exists()


def test_fetch_merra2_command_succeeds_when_every_day_is_available(tmp_path, monkeypatch):
    monkeypatch.setattr(pbl, "fetch_merra2", lambda raw_dir, days: [])

    result = runner.invoke(app, ["fetch-merra2", "--raw-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "547 of 547 days available" in result.stdout


def test_fetch_merra2_command_exits_with_error_when_days_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(pbl, "fetch_merra2", lambda raw_dir, days: [(pd.Timestamp("2023-01-01"), "curl 22")])

    result = runner.invoke(app, ["fetch-merra2", "--raw-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "546 of 547 days available" in result.stdout


def test_fill_pbl_command_prints_the_result_of_run_fill(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli.pbl, "run_fill", lambda merra_dir, era5_dir, out_dir: [cli.pbl.Check(None, "done")]
    )

    result = runner.invoke(app, ["fill-pbl", "--out-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert result.stdout.strip() == "[info] done"
