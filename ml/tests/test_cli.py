from typer.testing import CliRunner

from nox_ml import __version__
from nox_ml.cli import app


def test_version_prints_installed_version():
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
