"""Single entry point for all pipelines: `nox-ml <command>`.

Commands are added as research scripts are migrated.
"""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from pydantic import ValidationError

from nox_ml import __version__
from nox_ml.data import openaq, pbl, simat, tempo
from nox_ml.data.inputs import load_inputs
from nox_ml.data.qc import render
from nox_ml.validation import compare as comparison
from nox_ml.validation import diagnostics, episodes, events, experiment, twins
from nox_ml.validation import lockdown as lockdown_validation
from nox_ml.validation import tune as tuning

RAW = Path("data/raw")
INTERIM = Path("data/interim")
DETECTION_DAYS = (3, 5, 9, 15, 20)  # event lengths of `detection`, in business days


class Period(StrEnum):
    test = "test"


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


@app.command("fetch-openaq")
def fetch_openaq(
    start: Annotated[str, typer.Argument(help="First day, YYYY-MM-DD (UTC).")],
    end: Annotated[str, typer.Argument(help="Day after the last one, YYYY-MM-DD (UTC, exclusive).")],
    data_dir: Annotated[Path, typer.Option(help="Data folder (raw/ and interim/).")] = Path("data"),
) -> None:
    """Download hourly station NOx, NO, NO2 and O3 from OpenAQ (SINAICA) for years SIMAT has not published.

    Needs an OpenAQ API key in OPENAQ_API_KEY. Writes raw/openaq/ and interim/openaq_nox_<start>_<end>.parquet
    (the table of qc-simat). Takes about a second per request (the key's rate limit)."""
    raw, interim = openaq.run_fetch(start, end, data_dir)
    typer.echo(f"Written to {raw} and {interim}")


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
def evaluate(
    config: Annotated[Path, typer.Argument(help="Frozen experiment YAML, e.g. runs/<name>/config.yaml.")],
    period: Annotated[Period, typer.Option(help="The only period is the test period (feb-may 2024).")],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>.test/ is written.")] = Path("runs"),
) -> None:
    """Run a frozen config on the test period (the same metrics as `run`) and write runs/<name>.test/."""
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = experiment.run_on_test_period(cfg, runs_dir)
    typer.echo(experiment.headline(json.loads((out / "metrics.json").read_text())))
    typer.echo(f"Written to {out}/")


@app.command()
def contingencies(
    config: Annotated[Path, typer.Argument(help="Frozen experiment YAML, e.g. runs/<name>/config.yaml.")],
    period: Annotated[Period, typer.Option(help="The only period is the test period (feb-may 2024).")],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>.contingencies/ is written.")] = Path(
        "runs"
    ),
    sensitivity: Annotated[
        bool, typer.Option(help="Also count every day with an active contingency (activation included).")
    ] = False,
    refits: Annotated[
        int | None,
        typer.Option(min=2, help="Fake-day draws per placebo (default: the config's placebo.refits)."),
    ] = None,
    inject: Annotated[
        list[float] | None,
        typer.Option(
            help="Emission drop added to the measure days (repeatable: --inject 0.1 --inject 0.2): "
            "the drop the analysis detects."
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            help="Atypical days kept out of the normal ones (school holidays), "
            "YYYY-MM-DD[:YYYY-MM-DD] (repeatable)."
        ),
    ] = None,
) -> None:
    """Emission on 2024 contingency days over normal days, with placebos (test period only).

    Fits the model 1 + 2 * refits times per scenario: a cheap model (E7, E6) can afford hundreds of draws,
    which a placebo interval needs; an expensive one keeps the config's. Writes runs/<name>.contingencies/."""
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    if refits is not None:
        cfg = cfg.model_copy(update={"placebo": cfg.placebo.model_copy(update={"refits": refits})})
    try:
        atypical = parse_days(exclude) if exclude else None
    except ValueError as error:
        typer.echo(f"Invalid days {exclude}: {error}", err=True)
        raise typer.Exit(2) from error
    out = events.run_contingencies(cfg, runs_dir, sensitivity, inject or [], atypical)
    typer.echo(events.headline(json.loads((out / "contingencies.json").read_text())))
    typer.echo(f"Written to {out}/")


def parse_days(spans: list[str]) -> pd.DatetimeIndex:
    """Local days of ``YYYY-MM-DD`` or ``YYYY-MM-DD:YYYY-MM-DD`` (inclusive) spans."""
    days = set()
    for span in spans:
        start, _, end = span.partition(":")
        days.update(pd.date_range(start, end or start, freq="D"))
    return pd.DatetimeIndex(sorted(days))


@app.command()
def calendar(
    config: Annotated[Path, typer.Argument(help="Frozen experiment YAML, e.g. runs/<name>/config.yaml.")],
    days: Annotated[
        list[str],
        typer.Option(help="Event days, YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD (inclusive; repeatable)."),
    ],
    label: Annotated[
        str, typer.Option(help="Name of the event, e.g. year_end: runs/<name>.calendar-<label>/.")
    ],
    period: Annotated[
        Period | None, typer.Option(help="Run on the test period (feb-may 2024) instead of the config's.")
    ] = None,
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>.calendar-<label>/ is written.")] = Path(
        "runs"
    ),
    refits: Annotated[
        int | None,
        typer.Option(min=2, help="Fake-day draws per placebo (default: the config's placebo.refits)."),
    ] = None,
    inject: Annotated[
        list[float] | None,
        typer.Option(
            help="Emission drop added to the event days (repeatable): the drop the analysis detects."
        ),
    ] = None,
) -> None:
    """Emission on calendar days (school holidays, year-end) over normal business days, with placebos.

    The positive control of the event analysis: days when traffic is known to fall. Contingency days are left
    out of the normal ones. Writes runs/<name>.calendar-<label>/."""
    try:
        cfg = experiment.read_config(config)
        event_days = parse_days(days)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    except ValueError as error:
        typer.echo(f"Invalid days {days}: {error}", err=True)
        raise typer.Exit(2) from error
    if refits is not None:
        cfg = cfg.model_copy(update={"placebo": cfg.placebo.model_copy(update={"refits": refits})})
    out = events.run_calendar(cfg, event_days, label, runs_dir, period is Period.test, inject or [])
    typer.echo(events.headline(json.loads((out / "calendar.json").read_text())))
    typer.echo(f"Written to {out}/")


@app.command()
def detection(
    config: Annotated[Path, typer.Argument(help="Frozen experiment YAML, e.g. runs/<name>/config.yaml.")],
    days: Annotated[
        list[int] | None, typer.Option(min=1, help="Event lengths in business days (repeatable).")
    ] = None,
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>.detection/ is written.")] = Path("runs"),
    refits: Annotated[
        int | None,
        typer.Option(min=2, help="Fake-day draws per length (default: the config's placebo.refits)."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(help="Atypical days kept out of the normal ones, YYYY-MM-DD[:YYYY-MM-DD] (repeatable)."),
    ] = None,
    label: Annotated[
        str | None, typer.Option(help="Suffix of the output: runs/<name>.detection-<label>/.")
    ] = None,
) -> None:
    """The smallest emission drop an event of k business days can show, on the period of the config.

    From the placebo of k fake days drawn from the normal days; also extrapolated to longer events. Answers
    "how many days does a measure need". Writes runs/<name>.detection/."""
    try:
        cfg = experiment.read_config(config)
        excluded = parse_days(exclude or [])
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    except ValueError as error:
        typer.echo(f"Invalid days {exclude}: {error}", err=True)
        raise typer.Exit(2) from error
    if refits is not None:
        cfg = cfg.model_copy(update={"placebo": cfg.placebo.model_copy(update={"refits": refits})})
    out = events.run_detection(cfg, days or list(DETECTION_DAYS), runs_dir, exclude=excluded, label=label)
    typer.echo(events.detection_headline(json.loads((out / "detection.json").read_text())))
    typer.echo(f"Written to {out}/")


@app.command()
def episode(
    days: Annotated[
        list[str],
        typer.Option(help="Episode days, YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD (inclusive; repeatable)."),
    ],
    data: Annotated[
        str, typer.Option(help="Data window START:END with TEMPO pixels, e.g. 2023-11-01:2023-12-31.")
    ],
    label: Annotated[
        str | None, typer.Option(help="Name of the output (default: first and last day).")
    ] = None,
    data_dir: Annotated[Path, typer.Option(help="Data folder (raw/ and interim/).")] = Path("data"),
    runs_dir: Annotated[Path, typer.Option(help="Where runs/episodes/<label>.json is written.")] = Path(
        "runs"
    ),
    seed: Annotated[int, typer.Option(help="Seed of the fake episodes.")] = 0,
) -> None:
    """Why an episode was high or low: weather, emission or regional background, against normal days.

    No model is fitted: the weather is the baseline plume with the prior emission and the emission is the
    normalized estimator. Contingency days are not used as references. Writes runs/episodes/<label>.json."""
    try:
        episode_days = parse_days(days)
        start, end = (pd.Timestamp(day).date().isoformat() for day in data.split(":"))
    except ValueError as error:
        typer.echo(f"Invalid days {days} or window {data}: {error}", err=True)
        raise typer.Exit(2) from error
    result = episodes.run_episode(data_dir, start, end, episode_days, seed)
    name = label or f"{episode_days[0]:%Y-%m-%d}_{episode_days[-1]:%Y-%m-%d}"
    out = runs_dir / "episodes" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    typer.echo(episodes.headline(result))
    typer.echo(f"Written to {out}")


@app.command()
def twin(
    generator: Annotated[
        Path, typer.Argument(help="Experiment YAML whose model's transport makes the twin.")
    ],
    estimators: Annotated[
        list[Path], typer.Argument(help="Experiment YAMLs of the models fitted to the twin.")
    ],
    scenario: Annotated[
        list[str] | None, typer.Option(help="Scenarios (repeatable): clean, realistic. Default: both.")
    ] = None,
    runs_dir: Annotated[
        Path, typer.Option(help="Where runs/twins/<generator>.seed<seed>.json is written.")
    ] = Path("runs"),
    seed: Annotated[int, typer.Option(help="Seed of the background and noise.")] = 0,
) -> None:
    """Twin experiment: real receptors with observations simulated from a known emission (Sunday / weekday
    0.69); every estimator is fitted to it and its ratio is compared with the truth."""
    scenarios = scenario or list(twins.SCENARIOS)
    unknown = sorted(set(scenarios) - set(twins.SCENARIOS))
    try:
        if unknown:
            raise ValueError(f"unknown scenarios {unknown}; known: {sorted(twins.SCENARIOS)}")
        gen = experiment.read_config(generator)
        configs = [experiment.read_config(path) for path in estimators]
    except (ValidationError, ValueError) as error:
        typer.echo(f"Invalid input:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = twins.run_twins(gen, configs, scenarios, runs_dir, seed)
    typer.echo(twins.headline(json.loads(out.read_text())))
    typer.echo(f"Written to {out}")


@app.command()
def lockdown(
    config: Annotated[
        Path, typer.Argument(help="Experiment YAML of the model, e.g. configs/experiments/<name>.yaml.")
    ],
    runs_dir: Annotated[Path, typer.Option(help="Where runs/<name>.lockdown/ is written.")] = Path("runs"),
) -> None:
    """The 2020 lockdown against the same dates of 2019: emission of each phase over the base, by year, and
    2020 over 2019 (a known drop: the positive control). Stations only; writes runs/<name>.lockdown/."""
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = lockdown_validation.run_lockdown(cfg, runs_dir)
    typer.echo(lockdown_validation.headline(json.loads((out / "lockdown.json").read_text())))
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
    # numbers come out of pandas as numpy scalars (`.item()` makes them plain), text as is
    params = base.model.params | {
        k: best[k].item() if hasattr(best[k], "item") else best[k] for k in space.space
    }
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
    """Diagnostics of an experiment (information by observation, ablation, learning curves), as CSV files."""
    try:
        cfg = experiment.read_config(config)
    except ValidationError as error:
        typer.echo(f"Invalid config {config}:\n{error}", err=True)
        raise typer.Exit(2) from error
    out = diagnostics.run_diagnostics(cfg, runs_dir, seeds, only or tuple(diagnostics.Stage), typer.echo)
    typer.echo(f"Written to {out}/")


if __name__ == "__main__":
    app()
