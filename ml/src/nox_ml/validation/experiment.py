# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Experiment runner: a validated YAML config in, ``runs/<name>/`` out (config, metrics, code version).

Every change to the method enters as a field of `ExperimentConfig` with the baseline as its default, so a run
of the new config can be compared metric by metric against the baseline run (``configs/experiments/``).

Metrics (`compute_metrics`), migrated from `real_check_linear.py` and `benchmark_common.py`
(research-archive):

- ``in_sample``: correlation of the fitted model with the station NOx and the TEMPO NO2 columns;
- ``loo``: leave-one-station-out RMSE of model, IDW and hybrid, with the bias / hour-to-hour split;
- ``day_types``: road emission by day type and Saturday/weekday and Sunday/weekday ratios, with a bootstrap
  over whole days (each replicate solves the inversion again on the resampled days);
- ``normalized``: the meteorology-normalized estimator (observed over modeled NOx with the prior emission) and
  the width of its placebo: fake Sundays drawn among weekdays;
- ``summary``: the flat `RunMetrics` of the run, including the placebo of the model itself (refits with fake
  Sundays) and its cost.

The method under test is any `nox_ml.models` entry (``model: {name, params}`` in the config); the harness only
fits, predicts and reads its emission estimate.
"""

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import HOLIDAYS, SIGMA_THETA, U_MIN, HourSystem, hour_systems
from nox_ml.inversion.normalized import SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.models import REGISTRY, EmissionEstimate, Model
from nox_ml.time import local_day
from nox_ml.validation import loo
from nox_ml.validation.metrics import PLACEBO_TOLERANCE, RunMetrics, gap_to_range
from nox_ml.validation.placebo import daily_table, split_placebo


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Period(Strict):
    start: date
    end: date

    @model_validator(mode="after")
    def ordered(self) -> "Period":
        if self.end < self.start:
            raise ValueError("end is before start")
        return self


class Placebo(Strict):
    """Placebos with fake Sundays among weekdays: the normalized estimator draws `n` splits; the model is
    fitted again on `refits` of them (each refit costs a fit)."""

    n: Annotated[int, Field(ge=1)] = 2000
    seed: int = 3
    level: Annotated[float, Field(gt=0, lt=1)] = 0.90
    refits: Annotated[int, Field(ge=2)] = 8


class ModelConfig(Strict):
    """Which model and its hyperparameters; `params` is stored with every default filled in."""

    name: str = "inversion_plume"
    params: dict[str, Any] = Field(default_factory=dict, validate_default=True)

    @field_validator("name")
    @classmethod
    def registered(cls, name: str) -> str:
        if name not in REGISTRY:
            raise ValueError(f"unknown model {name!r}; registered: {sorted(REGISTRY)}")
        return name

    @field_validator("params")
    @classmethod
    def resolved(cls, params: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        if "name" not in info.data:
            return params
        return REGISTRY[info.data["name"]].Params.model_validate(params).model_dump(mode="json")

    def build(self) -> Model:
        """A new, unfitted model."""
        cls = REGISTRY[self.name]
        return cls(cls.Params.model_validate(self.params))


class ExperimentConfig(Strict):
    """What a run needs. The defaults are the baseline; a config states only what differs."""

    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
    period: Period
    simat_hours: tuple[Annotated[int, Field(ge=0, le=23)], Annotated[int, Field(ge=0, le=23)]] = (12, 17)
    data_dir: Path = Path("data")
    model: ModelConfig = Field(default_factory=ModelConfig, validate_default=True)
    placebo: Placebo = Placebo()

    @model_validator(mode="after")
    def hours_ordered(self) -> "ExperimentConfig":
        if self.simat_hours[0] > self.simat_hours[1]:
            raise ValueError("simat_hours must be (first, last) with first <= last")
        return self


def read_config(path: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(yaml.safe_load(path.read_text()))


# --- Metrics -----------------------------------------------------------------------------------------------


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.corrcoef(a, b)[0, 1])


def normalized_estimator(
    inputs: Inputs, systems: list[HourSystem], config: Placebo
) -> dict[str, float | int]:
    """Observed over modeled station NOx with the prior emission (no background), per day; the spread of the
    ratio between fake and real-looking weekdays is the placebo width (half of the central interval)."""
    n_points = len(inputs.points)
    prior = inputs.points["prior"].to_numpy(float)
    rows = []
    for hour, system in zip(inputs.hours, systems, strict=True):
        k = system.jacobian.stations
        if len(k):
            model = k[:, :n_points] @ prior + k[:, n_points:].sum(axis=1)
            rows.append({"h": hour.hour, "obs": hour.nox.mean(), "model": model.mean()})
    hourly = pd.DataFrame(rows).assign(day=lambda x: local_day(x["h"]))
    days = daily_table(hourly, HOLIDAYS)
    kinds = day_type(pd.DatetimeIndex(days.index), HOLIDAYS)
    weekdays, n_sundays = days[kinds == WEEKDAY], int((kinds == SUNDAY_HOLIDAY).sum())
    daily_index = weekdays["obs"] / weekdays["model"]
    samples = split_placebo(weekdays, n_sundays, config.n, np.random.default_rng(config.seed))
    lo, hi = interval(samples, config.level)
    return {
        "placebo_half_width": (hi - lo) / 2,
        "placebo_lo": lo,
        "placebo_hi": hi,
        "weekday_cv": float(daily_index.std() / daily_index.mean()),
        "n_weekdays": len(weekdays),
        "n_sundays": n_sundays,
    }


@dataclass(frozen=True)
class Evaluation:
    """What a run produces: the metrics, the out-of-fold predictions and the emission estimate (models)."""

    metrics: dict[str, Any]
    oof: pd.DataFrame
    emissions: EmissionEstimate | None


def model_placebo(inputs: Inputs, make_model: Callable[[], Model], config: Placebo) -> dict[str, float]:
    """Sunday over weekday of the model fitted on weekdays only, a random subset of them relabeled as Sundays
    (as many as the period has). There is no change to find: the center should be 1."""
    days = pd.DatetimeIndex(sorted({local_day(h.hour) for h in inputs.hours}))
    kinds = day_type(days, HOLIDAYS)
    weekdays, n_fake = days[kinds == WEEKDAY], int((kinds == SUNDAY_HOLIDAY).sum())
    if not 0 < n_fake < len(weekdays):
        raise ValueError(
            f"placebo needs Sundays and more weekdays than Sundays, got {n_fake}/{len(weekdays)}"
        )
    base = inputs.on_days(weekdays)
    rng = np.random.default_rng(config.seed)
    ratios = []
    for _ in range(config.refits):
        fake = rng.choice(len(weekdays), n_fake, replace=False)
        relabeled = base.with_day_kinds(dict.fromkeys(weekdays[fake], SUNDAY_HOLIDAY))
        ratios.append(make_model().fit(relabeled).estimate_emissions().day_type_ratio("sunday_holiday"))
    lo, hi = interval(np.array(ratios), config.level)
    return {"center": float(np.median(ratios)), "half_width": (hi - lo) / 2, "lo": lo, "hi": hi}


def day_types_block(inputs: Inputs, estimate: EmissionEstimate) -> dict[str, Any]:
    """Road emission by day type and the ratios to the weekday, as the baseline table reports them."""
    out: dict[str, Any] = {"road_prior": float(inputs.zones["weight"].sum())}
    if estimate.kind == "absolute":
        out["road_total"] = estimate.table.groupby("day_type")["mean"].sum().astype(float).to_dict()
    for key, kind in (("saturday_over_weekday", "saturday"), ("sunday_over_weekday", "sunday_holiday")):
        bounds = estimate.day_type_interval(kind)
        out[key] = {
            "value": estimate.day_type_ratio(kind),
            "lo": bounds[0] if bounds else None,
            "hi": bounds[1] if bounds else None,
        }
    level = None if estimate.ratio_ci is None else float(estimate.ratio_ci["level"].iloc[0])
    return out | {"bootstrap_level": level, "n_days": len({local_day(h.hour) for h in inputs.hours})}


def evaluate(inputs: Inputs, config: ExperimentConfig) -> Evaluation:
    """All the metrics of a run, as a JSON-ready dict, with the out-of-fold predictions and the emissions."""
    make_model = config.model.build
    model = make_model()
    rows = loo.station_rows(inputs)
    stations = sorted(rows["station"].unique())

    start = time.perf_counter()
    model.fit(inputs)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    fitted = model.predict_stations(inputs, stations)
    predict_seconds = time.perf_counter() - start
    fitted = rows.merge(fitted, left_on=["station", "h"], right_on=["station", "utc"], how="left")
    pred, obs = fitted["nox_ppb_pred"].to_numpy(float), rows["obs"].to_numpy()
    tempo = getattr(model, "tempo_correlation", None)
    in_sample = {
        "r_stations": _correlation(pred, obs),
        "rmse_stations": float(np.sqrt(np.mean((pred - obs) ** 2))),
        "r_tempo": tempo(inputs) if tempo else None,
    }

    table, oof = loo.leave_one_out(inputs, make_model)
    pooled = loo.summarize(table)
    start, end = (d.isoformat() for d in (config.period.start, config.period.end))
    metrics: dict[str, Any] = {
        "inputs": {
            "n_hours": len(inputs.hours),
            "n_station_rows": inputs.n_station_rows,
            "n_pixels": inputs.n_pixels,
            "no2_nox_ratio": inputs.no2_nox_ratio,
            "holidays": sorted(d for d in HOLIDAYS if start <= d <= end),
        },
        "in_sample": in_sample,
        "loo": pooled | {"stations": table.round(4).to_dict("index")},
        "day_types": None,
        "normalized": None,
    }
    summary: dict[str, Any] = {
        "model": model.name,
        "role": model.role,
        "loo_rmse_ppb": pooled["rmse"]["model"],
        "loo_bias_ppb": pooled["bias"]["model"],
        "loo_hourly_rmse_ppb": pooled["hourly"]["model"],
        "r_tempo": in_sample["r_tempo"],
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        "n_params": model.n_params,
    }
    estimate = None
    if model.role == "model":
        estimate = model.estimate_emissions().validate()
        metrics["day_types"] = day_types_block(inputs, estimate)
        systems = hour_systems(
            inputs.hours,
            inputs.zones,
            inputs.points,
            inputs.no2_nox_ratio,
            inputs.n_regions,
            HOLIDAYS,
            jacobians=inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)),
        )
        metrics["normalized"] = normalized_estimator(inputs, systems, config.placebo)
        placebo = model_placebo(inputs, make_model, config.placebo)
        sunday = metrics["day_types"]["sunday_over_weekday"]
        summary |= {
            "sunday_ratio": sunday["value"],
            "sunday_ratio_lo": sunday["lo"],
            "sunday_ratio_hi": sunday["hi"],
            "sunday_ratio_gap": gap_to_range(sunday["value"]),
            "placebo_center": placebo["center"],
            "placebo_halfwidth": placebo["half_width"],
            "eligible": abs(placebo["center"] - 1) <= PLACEBO_TOLERANCE,
        }
    summary = dict.fromkeys(RunMetrics.model_fields) | summary
    metrics["summary"] = RunMetrics.model_validate(summary).model_dump()
    return Evaluation(metrics, oof, estimate)


# --- Run ---------------------------------------------------------------------------------------------------


def code_version() -> dict[str, Any]:
    """Git hash of the code and whether the working tree has uncommitted changes (``unknown`` outside git)."""
    here = Path(__file__).parent

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=here, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {"git_hash": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"git_hash": "unknown", "dirty": None}


def run_experiment(config: ExperimentConfig, runs_dir: Path = Path("runs")) -> Path:
    """Run the experiment and write ``runs_dir/<name>/``: ``config.yaml`` (as validated, defaults included),
    ``metrics.json``, ``code_version.json``, ``oof.parquet`` (leave-one-station-out predictions) and, for
    models, ``emissions.parquet``. Returns the folder."""
    inputs = load_inputs(
        config.data_dir, config.period.start.isoformat(), config.period.end.isoformat(), config.simat_hours
    )
    result = evaluate(inputs, config)
    out = runs_dir / config.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False))
    (out / "metrics.json").write_text(json.dumps(result.metrics, indent=2) + "\n")
    result.oof.to_parquet(out / "oof.parquet", index=False)
    if result.emissions is not None:
        result.emissions.to_frame().to_parquet(out / "emissions.parquet", index=False)
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def headline(metrics: dict[str, Any]) -> str:
    """The numbers of the baseline table in a few lines, for the terminal."""
    s, loo_, run = metrics["in_sample"], metrics["loo"], metrics["summary"]
    r_tempo = "n/a" if s["r_tempo"] is None else f"{s['r_tempo']:.2f}"
    lines = [
        f"model {run['model']} ({run['role']}); fit {run['fit_seconds']:.1f} s",
        f"in-sample r: stations {s['r_stations']:.2f}, TEMPO {r_tempo}",
        "LOO RMSE model / IDW / hybrid (ppb): "
        + " / ".join(f"{loo_['rmse'][k]:.1f}" for k in loo.PREDICTORS)
        + f" (hybrid beats IDW at {loo_['hybrid_beats_idw']} of {loo_['n_stations']} stations)",
        f"  bias / hour-to-hour of the hybrid: {loo_['bias']['hybrid']:.1f} / {loo_['hourly']['hybrid']:.1f}",
    ]
    if run["role"] == "model":
        day = metrics["day_types"]
        sunday, lo, hi = run["sunday_ratio"], run["sunday_ratio_lo"], run["sunday_ratio_hi"]
        interval_text = "" if lo is None else f" ({lo:.2f}-{hi:.2f})"
        lines += [
            f"Sunday/weekday {sunday:.2f}{interval_text}, "
            f"Saturday/weekday {day['saturday_over_weekday']['value']:.2f}",
            f"placebo of the model: center {run['placebo_center']:.2f} +-{run['placebo_halfwidth']:.2f}"
            f" ({'eligible' if run['eligible'] else 'NOT eligible'}); "
            f"normalized placebo +-{metrics['normalized']['placebo_half_width']:.2f}",
        ]
    return "\n".join(lines)
