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
from nox_ml.data.inputs import load_inputs
from nox_ml.data.qc import render
from nox_ml.validation import compare as comparison
from nox_ml.validation import experiment
from nox_ml.validation import tune as tuning

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


@app.command("compare")
def compare(
    runs: Annotated[list[Path], typer.Argument(help="Run folders, e.g. runs/*.")],
    out_dir: Annotated[Path, typer.Option(help="Where comparison.csv and comparison.md are written.")] = Path(
        "runs"
    ),
) -> None:
    """Compare runs: a table sorted by loo_rmse_ppb with emission metrics, placebo gate and times."""
    table, skipped = comparison.collect(runs)
    for path in skipped:
        typer.echo(f"Skipped {path}: no summary in metrics.json", err=True)
    if table.empty:
        typer.echo("No runs to compare.", err=True)
        raise typer.Exit(1)
    text = comparison.markdown(table)
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "comparison.csv", index=False)
    (out_dir / "comparison.md").write_text(text + "\n")
    typer.echo(text)


@app.command("tune")
def tune(
    search: Annotated[Path, typer.Argument(help="Search YAML next to the experiment config.")],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>/ is written.")] = Path("runs"),
) -> None:
    """Search the params of a model on the tuning period, write trials.csv and refit the best trial."""
    try:
        space, base = tuning.read_search(search)
        tuning.trials(space, base)  # every trial is valid before the first one runs
    except (ValidationError, ValueError, OSError) as error:
        typer.echo(f"Invalid search {search}:\n{error}", err=True)
        raise typer.Exit(2) from error
    name = search.stem.removesuffix(".search")
    inputs = load_inputs(
        base.data_dir, base.period.start.isoformat(), base.period.end.isoformat(), base.simat_hours
    )
    table = tuning.tune(space, base, inputs)
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "trials.csv", index=False)
    best = table.loc[table["loo_rmse_ppb"].idxmin()]
    params = base.model.params | {k: best[k].item() for k in space.space}
    typer.echo(table.to_string(index=False))
    typer.echo(f"Best trial {int(best['trial'])}: {best['loo_rmse_ppb']:.2f} ppb with {params}")
    config = base.model_copy(update={"name": name, "model": base.model.model_copy(update={"params": params})})
    experiment.run_experiment(config, runs_dir)
    typer.echo(f"Trials and the refit of the best in {out}/")


@app.command("train-pinn")
def train_pinn(
    config: Annotated[Path, typer.Argument(help="Experiment YAML with model: {name: pinn_plume}.")],
) -> None:
    """Train (or find in the cache) the PINN kernel of an experiment and print its validation against the
    exact solution. Needs the ``pinn`` extra. Takes a few minutes the first time; the default network is
    bundled and needs no training."""
    from nox_ml.models.pinn.cache import obtain_kernel
    from nox_ml.models.pinn.params import PinnParams

    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    if cfg.model.name != "pinn_plume":
        typer.echo(f"{config} runs model {cfg.model.name!r}, not 'pinn_plume'.", err=True)
        raise typer.Exit(2)
    params = PinnParams.model_validate(cfg.model.params)
    directory = Path(params.kernel_dir) if params.kernel_dir else None
    kernel = obtain_kernel(params, directory, progress=typer.echo)
    typer.echo(f"Kernel {params.training_key()} (trained in {kernel.seconds:.0f} s)")
    typer.echo("gamma  median_rel_error  p90_rel_error  mass_error")
    for gamma, row in kernel.validation.items():
        errors = (row["median_rel_error"], row["p90_rel_error"], row["mass_error"])
        typer.echo(f"{gamma:>5}  {errors[0]:>16.1%}  {errors[1]:>13.1%}  {errors[2]:>+10.1%}")


if __name__ == "__main__":
    app()
