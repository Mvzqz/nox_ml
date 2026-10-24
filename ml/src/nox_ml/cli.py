"""Single entry point for all pipelines: `nox-ml <command>`.

Commands are added as research scripts are migrated.
"""

import typer

from nox_ml import __version__

app = typer.Typer(help="nox-ml pipelines.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """nox-ml pipelines: data, physics, inversion and validation."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
