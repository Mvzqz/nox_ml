# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Diagnostics of the baseline for the BASELINE report: where the information comes from, what happens when
an input is taken away or degraded, and how the errors change with the amount of data.

Every function takes the inputs of the harness (`Inputs`, `ExperimentConfig`) and returns DataFrames; the
files are written by `run_diagnostics` (``nox-ml diagnose``).

- `information_by_observation`: the posterior is Gaussian, so what the observations tell about an unknown
  does not depend on their values. With the prior precision ``P0`` and the information ``J^T R^-1 J`` of a
  source of observations (stations or TEMPO, background integrated out), the posterior covariance is
  ``(P0 + J^T R^-1 J)^-1``. The variance reduction of an unknown is ``1 - var_post / var_prior``, which is
  also the diagonal of the averaging kernel ``A = I - S_post P0``: the degrees of freedom for signal (trace
  of ``A``) are the sum of the reductions.
- `ablation`: the harness metrics of the baseline rerun without TEMPO, with fewer stations (random subsets
  that keep the spatial coverage) and with a rotated wind.
- `learning_curve`: in-sample and leave-one-station-out errors with fewer days (blocks of consecutive days)
  and fewer stations.

Cases that keep everything (all the stations, all the days) are deterministic and run once.
"""

import json
import warnings
from collections.abc import Callable, Collection, Iterator, Sequence
from dataclasses import replace
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.jacobian import HourJacobian, Receptors
from nox_ml.inversion.linear import (
    BACKGROUND_PIXEL,
    BACKGROUND_STATION,
    DAY_TYPE_NAMES,
    HOLIDAYS,
    SIGMA_PIXEL,
    SIGMA_STATION,
    HourSystem,
    hour_systems,
    marginalized_block,
    prior_state,
)
from nox_ml.models import Model
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.time import local_day
from nox_ml.validation import loo
from nox_ml.validation.experiment import ExperimentConfig, code_version, evaluate

Array = NDArray[np.float64]

N_SEEDS = 5
STATION_COUNTS = (24, 15, 9)  # ablation
WIND_BIASES = (15.0, 30.0)  # degrees, clockwise
DAY_COUNTS = (15, 30, 45, 61)  # learning curve
CURVE_STATION_COUNTS = (6, 12, 18, 24)  # learning curve
SOURCES = ("stations", "tempo", "both")


class Stage(StrEnum):
    information = "information"
    ablation = "ablation"
    learning = "learning"


# --- Information ------------------------------------------------------------------------------------------


def source_information(systems: Sequence[HourSystem], n_unknowns: int) -> dict[str, Array]:
    """``J^T R^-1 J`` of the unknowns (without the prior) for ``none``, ``stations``, ``tempo`` and ``both``.

    The information of an hour block does not depend on the observed values, only on its Jacobian and on
    how many observations share the background."""
    info = {name: np.zeros((n_unknowns, n_unknowns)) for name in ("stations", "tempo")}
    for system in systems:
        blocks = (
            ("stations", system.jacobian.stations, SIGMA_STATION, BACKGROUND_STATION),
            ("tempo", system.jacobian.pixels, SIGMA_PIXEL, BACKGROUND_PIXEL),
        )
        for name, k, sigma, background in blocks:
            if len(k):
                block, _ = marginalized_block(k, np.zeros(len(k)), sigma, background)
                info[name][np.ix_(system.columns, system.columns)] += block
    return {"none": np.zeros((n_unknowns, n_unknowns)), **info, "both": info["stations"] + info["tempo"]}


def posterior_sd(prior_sd: Array, info: Array) -> Array:
    """Posterior standard deviation of every unknown, from the prior and the information of the data."""
    precision = np.diag(1 / prior_sd**2) + info
    return np.sqrt(np.diag(np.linalg.inv(precision)))


def information_by_observation(
    systems: Sequence[HourSystem], points: pd.DataFrame, n_regions: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """What each kind of observation tells about the unknowns, with the stations only, TEMPO only and both.

    Returns ``(reduction, dofs)``:

    - ``reduction``: one row per unknown (``label``, ``group``: ``points`` or the day type, ``zone``: road
      region, empty for points, ``prior_sd``) with ``sd_<source>`` and ``reduction_<source>``, the fraction
      of the prior variance removed, for ``stations``, ``tempo`` and ``both``;
    - ``dofs``: one row per source, with the degrees of freedom for signal in total and by group.

    With no observations the reduction is 0 and the posterior is the prior.
    """
    prior_mean, prior_sd, labels = prior_state(points, n_regions)
    n_points = len(points)
    info = source_information(systems, len(prior_mean))
    roads = range(len(labels) - n_points)
    reduction = pd.DataFrame(
        {
            "label": labels,
            "group": ["points"] * n_points + [DAY_TYPE_NAMES[i // n_regions] for i in roads],
            "zone": pd.array([None] * n_points + [i % n_regions for i in roads], dtype="Int64"),
            "prior_sd": prior_sd,
        }
    )
    for source in SOURCES:
        sd = posterior_sd(prior_sd, info[source])
        reduction[f"sd_{source}"] = sd
        reduction[f"reduction_{source}"] = 1 - sd**2 / prior_sd**2
    groups = ["points", *DAY_TYPE_NAMES]
    dofs = pd.DataFrame(
        {
            "source": SOURCES,
            "dofs": [reduction[f"reduction_{s}"].sum() for s in SOURCES],
            **{
                g: [reduction.loc[reduction["group"] == g, f"reduction_{s}"].sum() for s in SOURCES]
                for g in groups
            },
        }
    )
    return reduction, dofs


# --- Variants of the inputs -------------------------------------------------------------------------------
#
# Every variant that keeps the hours' winds (all but `rotate_wind`) gets the Jacobians already cached in the
# inputs, sliced to its hours and receptors, so no Jacobian is built twice (rows of a Jacobian depend on their
# own receptor alone).


def station_ids(inputs: Inputs) -> list[str]:
    """The stations that have at least one NOx row, sorted."""
    return sorted(np.unique(np.concatenate(inputs.station_ids)).tolist())


def derived(
    inputs: Inputs,
    index: Sequence[int],
    slice_jacobian: Callable[[HourJacobian, int], HourJacobian] = lambda jac, k: jac,
    **changes: Any,
) -> Inputs:
    """The inputs of the hours at position `index` of `inputs`; `changes` replaces the fields of the variant
    (``hours``, ``station_ids``...), aligned with `index`. Each cached Jacobian goes through
    ``slice_jacobian(jacobian, position in the variant)``."""
    cache = {
        key: [slice_jacobian(jacobians[i], k) for k, i in enumerate(index)]
        for key, jacobians in inputs.jacobian_cache.items()
    }
    return replace(inputs, jacobian_cache=cache, **changes)


def with_stations(inputs: Inputs, keep: Collection[str]) -> Inputs:
    """The inputs with only the rows of the stations `keep`. Hours left without station rows are dropped, as
    the input assembly does. The wind and boundary layer height of an hour are not recomputed."""
    index, hours, ids, masks = [], [], [], []
    for i, (hour, hour_ids) in enumerate(zip(inputs.hours, inputs.station_ids, strict=True)):
        use = np.isin(hour_ids, list(keep))
        if use.any():
            stations = Receptors(hour.stations.x[use], hour.stations.y[use])
            index.append(i)
            hours.append(replace(hour, stations=stations, nox=hour.nox[use]))
            ids.append(hour_ids[use])
            masks.append(use)
    return derived(
        inputs,
        index,
        lambda jac, k: jac.without_stations(masks[k]),
        hours=hours,
        station_ids=ids,
        station_xy=inputs.station_xy.loc[sorted(keep)],
    )


def with_days(inputs: Inputs, days: Collection[pd.Timestamp]) -> Inputs:
    """The inputs of the hours whose local day is in `days`."""
    index = [i for i, h in enumerate(inputs.hours) if local_day(h.hour) in days]
    return derived(
        inputs,
        index,
        hours=[inputs.hours[i] for i in index],
        station_ids=[inputs.station_ids[i] for i in index],
    )


def without_tempo(inputs: Inputs) -> Inputs:
    """The inputs without TEMPO pixels."""
    none = np.empty(0)
    return derived(
        inputs,
        range(len(inputs.hours)),
        lambda jac, k: HourJacobian(jac.stations, jac.pixels[:0]),
        hours=[replace(h, pixels=Receptors(none, none), no2=none) for h in inputs.hours],
    )


def rotate_wind(inputs: Inputs, degrees: float) -> Inputs:
    """The inputs with the wind of every hour turned `degrees` clockwise (a wind from the south that blows
    towards the north now blows towards the north-east for +45): a systematic error of the wind direction.
    The speed is the same. The Jacobians depend on the wind, so this variant builds its own."""
    angle = np.deg2rad(degrees)
    cos, sin = np.cos(angle), np.sin(angle)
    turned = [
        replace(h, wind=(h.wind[0] * cos + h.wind[1] * sin, -h.wind[0] * sin + h.wind[1] * cos))
        for h in inputs.hours
    ]
    return replace(inputs, hours=turned, jacobian_cache={})


def spatial_subset(xy: pd.DataFrame, k: int, rng: np.random.Generator) -> list[str]:
    """`k` stations chosen at random but spread out: the first one uniformly, each next one with probability
    proportional to its squared distance to the ones already chosen (the seeding of k-means++), so a pair of
    neighbors is unlikely and the subset covers the domain."""
    points = xy[["x", "y"]].to_numpy(float)
    chosen = [int(rng.integers(len(points)))]
    while len(chosen) < k:
        d2 = ((points[:, None, :] - points[chosen][None]) ** 2).sum(axis=2).min(axis=1)
        chosen.append(int(rng.choice(len(points), p=d2 / d2.sum())))
    return sorted(str(xy.index[i]) for i in chosen)


def day_block(days: Sequence[pd.Timestamp], n: int, rng: np.random.Generator) -> list[pd.Timestamp]:
    """`n` consecutive days (of the days with data) starting at a random one."""
    start = int(rng.integers(len(days) - n + 1))
    return list(days[start : start + n])


def local_days(inputs: Inputs) -> list[pd.Timestamp]:
    """The local days with data, sorted."""
    return sorted({local_day(h.hour) for h in inputs.hours})


# --- Ablation ---------------------------------------------------------------------------------------------


def flatten(metrics: dict[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """The scalar leaves of the metrics of `evaluate` as ``block.name`` (the per-station table and the
    holidays are left out)."""
    for key, value in metrics.items():
        if isinstance(value, dict) and key != "stations":
            yield from flatten(value, f"{prefix}{key}.")
        elif not isinstance(value, dict | list):
            yield f"{prefix}{key}", value


def ablation(
    inputs: Inputs,
    config: ExperimentConfig,
    station_counts: Sequence[int] = STATION_COUNTS,
    wind_biases: Sequence[float] = WIND_BIASES,
    seeds: Sequence[int] = range(N_SEEDS),
) -> pd.DataFrame:
    """The harness metrics (`evaluate` with the model of `config`, flattened as ``block.name``) of the
    baseline and of its variants: ``baseline``; ``no_tempo``; ``stations`` with each count of
    `station_counts` and each seed (a count of all the stations is the baseline); ``wind_bias`` with the wind
    turned by each of `wind_biases` degrees clockwise. Columns ``case``, ``setting`` (stations kept,
    degrees) and ``seed`` come first. The Jacobians of the baseline are reused by every variant but the wind
    ones."""

    def row(case: str, setting: float | None, seed: int | None, variant: dict[str, Any]) -> dict[str, Any]:
        return {"case": case, "setting": setting, "seed": seed, **variant}

    def run(variant: Inputs) -> dict[str, Any]:
        with warnings.catch_warnings():
            if variant.n_pixels == 0:  # the correlation with TEMPO is empty (NaN) and numpy warns about it
                warnings.simplefilter("ignore", RuntimeWarning)
            return dict(flatten(evaluate(variant, config).metrics))

    base = run(inputs)  # also fills the Jacobian cache the variants slice
    rows = [row("baseline", None, None, base), row("no_tempo", None, None, run(without_tempo(inputs)))]
    ids = station_ids(inputs)
    for k in station_counts:
        if k >= len(ids):
            rows.append(row("stations", float(k), None, base))
            continue
        for seed in seeds:
            keep = spatial_subset(inputs.station_xy.loc[ids], k, np.random.default_rng((seed, k)))
            rows.append(row("stations", float(k), seed, run(with_stations(inputs, keep))))
    for degrees in wind_biases:
        rows.append(row("wind_bias", float(degrees), None, run(rotate_wind(inputs, degrees))))
    return pd.DataFrame(rows).astype({"seed": "Int64"})


# --- Learning curve ---------------------------------------------------------------------------------------


def validation_errors(inputs: Inputs, make_model: Callable[[], Model]) -> dict[str, float]:
    """In-sample RMSE (ppb) of the model fitted on all the stations and its leave-one-station-out RMSE
    (`loo.leave_one_out`) for the model, IDW and the hybrid, with the sizes of the inputs."""
    rows = loo.station_rows(inputs)
    fitted = make_model().fit(inputs).predict_stations(inputs, sorted(rows["station"].unique()))
    fitted = rows.merge(fitted, left_on=["station", "h"], right_on=["station", "utc"], how="left")
    table, _ = loo.leave_one_out(inputs, make_model)
    rmse = loo.summarize(table)["rmse"]
    return {
        "n_days": len(local_days(inputs)),
        "n_hours": len(inputs.hours),
        "n_stations": len(station_ids(inputs)),
        "rmse_in_sample": float(np.sqrt(np.mean((fitted["nox_ppb_pred"] - fitted["obs"]) ** 2))),
        **{f"rmse_loo_{name}": rmse[name] for name in loo.PREDICTORS},
    }


def learning_curve(
    inputs: Inputs,
    make_model: Callable[[], Model],
    day_counts: Sequence[int] = DAY_COUNTS,
    station_counts: Sequence[int] = CURVE_STATION_COUNTS,
    seeds: Sequence[int] = range(N_SEEDS),
) -> pd.DataFrame:
    """In-sample and leave-one-station-out RMSE (`validation_errors`) with fewer data: ``days`` keeps a block
    of consecutive days (all the stations), ``stations`` a spread-out subset (all the days). Counts beyond
    what the inputs have are the full inputs; a case that uses everything runs once (seed 0). The Jacobians
    of the full inputs are built once and sliced for every case."""
    make_model().fit(inputs)  # fills the Jacobian cache the variants slice
    days, ids = local_days(inputs), station_ids(inputs)
    rows = []
    for axis, total, counts in (("days", len(days), day_counts), ("stations", len(ids), station_counts)):
        for n in sorted({min(n, total) for n in counts}):
            for seed in seeds if n < total else seeds[:1]:
                rng = np.random.default_rng((seed, n))
                if n == total:
                    variant = inputs
                elif axis == "days":
                    variant = with_days(inputs, day_block(days, n, rng))
                else:
                    variant = with_stations(inputs, spatial_subset(inputs.station_xy.loc[ids], n, rng))
                rows.append({"axis": axis, "n": n, "seed": seed, **validation_errors(variant, make_model)})
    return pd.DataFrame(rows)


# --- Run --------------------------------------------------------------------------------------------------


def model_systems(inputs: Inputs, model: Model) -> list[HourSystem]:
    """The hour systems of a plume inversion model on all the inputs, with the Jacobians of the cache."""
    if not isinstance(model, InversionPlume):
        raise ValueError(f"the information analysis needs a plume inversion model, got {model.name!r}")
    return hour_systems(
        inputs.hours,
        inputs.zones,
        inputs.points,
        inputs.no2_nox_ratio,
        inputs.n_regions,
        HOLIDAYS,
        day_kinds=inputs.day_kinds,
        jacobians=inputs.jacobians(model.transport_key(), model.transport()),
    )


def run_diagnostics(
    config: ExperimentConfig,
    runs_dir: Path = Path("runs"),
    n_seeds: int = N_SEEDS,
    stages: Collection[Stage] = tuple(Stage),
    echo=lambda message: None,
) -> Path:
    """Compute the diagnostics of the experiment and write them to ``runs_dir/<name>/diagnostics/``:
    ``variance_reduction.csv`` and ``degrees_of_freedom.csv`` (information), ``ablation.csv``,
    ``learning_curve.csv`` and ``code_version.json``. Returns the folder."""
    inputs = load_inputs(
        config.data_dir, config.period.start.isoformat(), config.period.end.isoformat(), config.simat_hours
    )
    out = runs_dir / config.name / "diagnostics"
    out.mkdir(parents=True, exist_ok=True)
    seeds = range(n_seeds)
    if Stage.information in stages:
        echo("information by observation")
        systems = model_systems(inputs, config.model.build())
        reduction, dofs = information_by_observation(systems, inputs.points, inputs.n_regions)
        reduction.to_csv(out / "variance_reduction.csv", index=False)
        dofs.to_csv(out / "degrees_of_freedom.csv", index=False)
    if Stage.ablation in stages:
        echo("ablation")
        ablation(inputs, config, seeds=seeds).to_csv(out / "ablation.csv", index=False)
    if Stage.learning in stages:
        echo("learning curve")
        learning_curve(inputs, config.model.build, seeds=seeds).to_csv(
            out / "learning_curve.csv", index=False
        )
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out
