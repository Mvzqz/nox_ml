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
  the width of its placebo: fake Sundays drawn among weekdays.
"""

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.linear import HOLIDAYS, HourSystem, hour_systems, solve
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.time import local_day
from nox_ml.validation import loo
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


class Bootstrap(Strict):
    """Bootstrap over whole days of the road totals by day type."""

    n: Annotated[int, Field(ge=1)] = 200
    seed: int = 7
    level: Annotated[float, Field(gt=0, lt=1)] = 0.90


class Placebo(Strict):
    """Placebo of the normalized estimator: fake Sundays among weekdays."""

    n: Annotated[int, Field(ge=1)] = 2000
    seed: int = 3
    level: Annotated[float, Field(gt=0, lt=1)] = 0.90


class ExperimentConfig(Strict):
    """What a run needs. The defaults are the baseline; a config states only what differs."""

    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
    period: Period
    simat_hours: tuple[Annotated[int, Field(ge=0, le=23)], Annotated[int, Field(ge=0, le=23)]] = (12, 17)
    data_dir: Path = Path("data")
    bootstrap: Bootstrap = Bootstrap()
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


def road_totals(factors: np.ndarray, prior: np.ndarray) -> np.ndarray:
    """Road emission (t/yr equivalent) of each day type: ``factors`` (day type, region) times the prior of
    the regions."""
    return factors @ prior


def bootstrap_day_types(
    systems: list[HourSystem], inputs: Inputs, n_regions: int, prior: np.ndarray, config: Bootstrap
) -> np.ndarray:
    """Road totals by day type, shaped (replicate, day type), solving again on days drawn with replacement."""
    days, day_index = np.unique([s.day for s in systems], return_inverse=True)
    rng = np.random.default_rng(config.seed)
    out = []
    for _ in range(config.n):
        pick = rng.choice(len(days), len(days))
        weights = np.bincount(pick, minlength=len(days))[day_index]
        post = solve(systems, inputs.points, n_regions, weights)
        out.append(road_totals(post.road_factors(), prior))
    return np.array(out)


def ratio_with_interval(total: np.ndarray, boot: np.ndarray, kind: int, level: float) -> dict[str, float]:
    """Ratio of day type `kind` over weekday emission, with the percentile interval of the bootstrap."""
    lo, hi = interval(boot[:, kind] / boot[:, WEEKDAY], level)
    return {"value": float(total[kind] / total[WEEKDAY]), "lo": lo, "hi": hi}


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


def compute_metrics(inputs: Inputs, config: ExperimentConfig) -> dict[str, Any]:
    """All the metrics of a run, as a JSON-ready dict."""
    n_regions = inputs.n_regions
    systems = hour_systems(
        inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, n_regions, HOLIDAYS
    )
    post = solve(systems, inputs.points, n_regions)

    rows = loo.station_rows(inputs)
    fitted = loo.predict_stations(inputs, systems, post)
    pixel_model, pixel_obs = loo.predict_pixels(inputs, systems, post)
    in_sample = {
        "r_stations": _correlation(fitted, rows["obs"].to_numpy()),
        "rmse_stations": float(np.sqrt(np.mean((fitted - rows["obs"].to_numpy()) ** 2))),
        "r_tempo": _correlation(pixel_model, pixel_obs),
    }

    prior = inputs.zones.groupby("region")["weight"].sum().reindex(range(n_regions), fill_value=0).to_numpy()
    total = road_totals(post.road_factors(), prior)
    boot = bootstrap_day_types(systems, inputs, n_regions, prior, config.bootstrap)
    day_types = {
        "road_total": {
            "weekday": total[WEEKDAY],
            "saturday": total[SATURDAY],
            "sunday_holiday": total[SUNDAY_HOLIDAY],
        },
        "road_prior": float(prior.sum()),
        "saturday_over_weekday": ratio_with_interval(total, boot, SATURDAY, config.bootstrap.level),
        "sunday_over_weekday": ratio_with_interval(total, boot, SUNDAY_HOLIDAY, config.bootstrap.level),
        "bootstrap_level": config.bootstrap.level,
        "n_days": len({s.day for s in systems}),
    }

    table = loo.leave_one_out(inputs, systems)
    start, end = (d.isoformat() for d in (config.period.start, config.period.end))
    return {
        "inputs": {
            "n_hours": len(inputs.hours),
            "n_station_rows": inputs.n_station_rows,
            "n_pixels": inputs.n_pixels,
            "no2_nox_ratio": inputs.no2_nox_ratio,
            "holidays": sorted(d for d in HOLIDAYS if start <= d <= end),
        },
        "in_sample": in_sample,
        "loo": loo.summarize(table) | {"stations": table.round(4).to_dict("index")},
        "day_types": day_types,
        "normalized": normalized_estimator(inputs, systems, config.placebo),
    }


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
    ``metrics.json`` and ``code_version.json``. Returns the folder."""
    inputs = load_inputs(
        config.data_dir, config.period.start.isoformat(), config.period.end.isoformat(), config.simat_hours
    )
    metrics = compute_metrics(inputs, config)
    out = runs_dir / config.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False))
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def headline(metrics: dict[str, Any]) -> str:
    """The numbers of the baseline table in a few lines, for the terminal."""
    s, loo_, day, norm = metrics["in_sample"], metrics["loo"], metrics["day_types"], metrics["normalized"]
    sunday = day["sunday_over_weekday"]
    return "\n".join(
        [
            f"in-sample r: stations {s['r_stations']:.2f}, TEMPO {s['r_tempo']:.2f}",
            "LOO RMSE model / IDW / hybrid (ppb): "
            + " / ".join(f"{loo_['rmse'][k]:.1f}" for k in loo.PREDICTORS)
            + f" (hybrid beats IDW at {loo_['hybrid_beats_idw']} of {loo_['n_stations']} stations)",
            "  bias / hour-to-hour of the hybrid: "
            f"{loo_['bias']['hybrid']:.1f} / {loo_['hourly']['hybrid']:.1f}",
            f"Sunday/weekday {sunday['value']:.2f} ({sunday['lo']:.2f}-{sunday['hi']:.2f}), "
            f"Saturday/weekday {day['saturday_over_weekday']['value']:.2f}",
            f"normalized placebo: +-{norm['placebo_half_width']:.2f}",
        ]
    )
