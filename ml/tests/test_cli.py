from typer.testing import CliRunner

from nox_ml import __version__
from nox_ml.cli import app


def test_version_prints_installed_version():
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_ficha_medida_rejects_overlapping_windows():
    result = CliRunner().invoke(
        app,
        [
            "ficha-medida",
            "--days",
            "2023-11-15",
            "--title",
            "T",
            "--data",
            "2023-11-01:2023-12-31",
            "--data",
            "2023-12-15:2024-01-31",
        ],
    )

    assert result.exit_code == 2 and "overlap" in result.output
