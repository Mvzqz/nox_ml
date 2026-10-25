"""Single entry point for all pipelines: `nox-ml <command>`.

Commands are added as research scripts are migrated.
"""

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from pydantic import ValidationError

from nox_ml import __version__
from nox_ml.data import pbl, simat, tempo
from nox_ml.data.qc import render
from nox_ml.validation import diagnostics, experiment

RAW = Path("data/raw")
INTERIM = Path("data/interim")

app = typer.Typer(help="nox-ml pipelines.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """nox-ml pipelines: data, physics, inversion and validation."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command("qc-simat")
def qc_simat(
    years: Annotated[list[int], typer.Argument(help="Years to load, e.g. 2023 2024.")],
    raw_dir: Annotated[Path, typer.Option(help="SIMAT raw files.")] = RAW / "simat",
    out_dir: Annotated[Path, typer.Option(help="Where tables are written.")] = INTERIM,
    mask: Annotated[bool, typer.Option(help="Set stuck-sensor NOx hours to NaN in the output.")] = True,
) -> None:
    """Load SIMAT NOx and wind, run the quality checks and write simat_nox/simat_wind parquet files."""
    typer.echo(render(simat.run_qc(raw_dir, out_dir, years, mask)))


@app.command("qc-tempo")
def qc_tempo(
    start: Annotated[str, typer.Argument(help="First day, YYYY-MM-DD.")],
    end: Annotated[str, typer.Argument(help="Last day (inclusive), YYYY-MM-DD.")],
    raw_dir: Annotated[Path, typer.Option(help="TEMPO granule subsets.")] = RAW / "tempo",
    simat_dir: Annotated[Path, typer.Option(help="SIMAT raw files (station catalog).")] = RAW / "simat",
    out_dir: Annotated[Path, typer.Option(help="Where tables are read and written.")] = INTERIM,
) -> None:
    """Check TEMPO NO2 pixels against the domain, clouds and station NO2; write tempo_pixels parquet.

    Needs simat_nox.parquet in out_dir (run qc-simat first).
    """
    checks = tempo.run_qc(raw_dir, out_dir, simat.load_catalog(simat_dir), start, end)
    typer.echo(render(checks))


@app.command("fetch-merra2")
def fetch_merra2(
    raw_dir: Annotated[Path, typer.Option(help="Where daily files are stored.")] = RAW / "merra2",
) -> None:
    """Download MERRA-2 PBLH (3x3 cells around Mexico City). Needs Earthdata credentials in ~/.netrc."""
    days = pd.date_range(*pbl.MERRA_DAYS, freq="D")
    failed = pbl.fetch_merra2(raw_dir, days)
    typer.echo(f"{len(days) - len(failed)} of {len(days)} days available.")
    if failed:
        typer.echo(f"Failed (first 5): {failed[:5]}", err=True)
        raise typer.Exit(1)


@app.command("fill-pbl")
def fill_pbl(
    merra_dir: Annotated[Path, typer.Option(help="Daily MERRA-2 files.")] = RAW / "merra2",
    era5_dir: Annotated[Path, typer.Option(help="Open-Meteo ERA5 files.")] = RAW / "era5_openmeteo",
    out_dir: Annotated[Path, typer.Option(help="Where pbl_2023_2024.parquet is written.")] = INTERIM,
) -> None:
    """Fill the ERA5 boundary-layer gap with bias-corrected MERRA-2."""
    typer.echo(render(pbl.run_fill(merra_dir, era5_dir, out_dir)))


@app.command()
def run(
    config: Annotated[Path, typer.Argument(help="Experiment YAML, e.g. configs/experiments/baseline.yaml.")],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>/ is written.")] = Path("runs"),
) -> None:
    """Run an experiment: invert, validate and write config, metrics and code version to runs/<name>/."""
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = experiment.run_experiment(cfg, runs_dir)
    typer.echo(experiment.headline(json.loads((out / "metrics.json").read_text())))
    typer.echo(f"Written to {out}/")


@app.command()
def diagnose(
    config: Annotated[Path, typer.Argument(help="Experiment YAML, e.g. configs/experiments/baseline.yaml.")],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>/diagnostics/ is written.")] = Path("runs"),
    seeds: Annotated[int, typer.Option(min=1, help="Random subsets per case in the ablation and curves.")] = (
        diagnostics.N_SEEDS
    ),
    only: Annotated[
        list[diagnostics.Stage] | None, typer.Option(help="Run only these stages (repeat the option).")
    ] = None,
) -> None:
    """Diagnostics of an experiment: information by observation, ablation and learning curves, as CSV files.

    The ablation and the curves refit the inversion many times (about 3 hours on the baseline).
    """
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = diagnostics.run_diagnostics(cfg, runs_dir, seeds, only or tuple(diagnostics.Stage), typer.echo)
    typer.echo(f"Written to {out}/")


if __name__ == "__main__":
    app()
