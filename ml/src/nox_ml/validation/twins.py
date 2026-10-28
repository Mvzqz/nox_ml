# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Twin experiments: real hours, stations and pixels with observations simulated from a known emission.

There is no measured truth of the emission. A twin gives one: the observations of the real receptors are
replaced by those of a forward model (the *generator*, a model of the registry with a transport) with a
chosen road emission by day type, plus a regional background and noise. Every model is then fitted to the
twin and its Sunday / weekday ratio is compared with the true one. A model fitted with the generator's own
transport measures the error of the method; with another transport, the error of the method plus that of the
physics. Scenarios add what the real data has and the clean twin lacks:

- ``clean``: constant background, small noise;
- ``realistic``: a regional background that persists for days (AR(1) by day, the same for every receptor of
  an hour), day-to-day variation of the emission common to the city, and hourly noise at the stations and
  pixels of the size of the model errors.

The level of the road emission is scaled so the weekday NOx of the twin matches the real one on average.
"""

import json
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.linear import BACKGROUND_PIXEL, BACKGROUND_STATION, HOLIDAYS, HourTransport
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, day_type
from nox_ml.models import Model
from nox_ml.models.ensemble import MemberConfig
from nox_ml.time import local_day
from nox_ml.validation.experiment import ExperimentConfig, code_version

TRUTH = {WEEKDAY: 1.0, SATURDAY: 0.85, SUNDAY_HOLIDAY: 0.69}  # road emission by day type; Sunday: traffic
DAY_TYPE_NAMES = {WEEKDAY: "weekday", SATURDAY: "saturday", SUNDAY_HOLIDAY: "sunday_holiday"}


@dataclass(frozen=True)
class Scenario:
    """What the twin adds to the generator's NOx. Background in ppb at the stations (the pixels get the same
    relative change around `BACKGROUND_PIXEL`); `persistence` is the day-to-day autocorrelation of its log;
    `day_sd` the log sd of the city's emission from one day to the next; `noise` the log sd of every hourly
    observation."""

    background_ppb: float
    background_sd: float
    persistence: float
    day_sd: float
    noise: float


SCENARIOS = {
    "clean": Scenario(
        background_ppb=BACKGROUND_STATION[0], background_sd=0.0, persistence=0.0, day_sd=0.0, noise=0.05
    ),
    "realistic": Scenario(background_ppb=10.0, background_sd=0.35, persistence=0.7, day_sd=0.15, noise=0.30),
}


def _ar1(rng: np.random.Generator, n: int, sd: float, persistence: float) -> np.ndarray:
    """Stationary AR(1) of length `n` with marginal sd `sd`."""
    out = np.zeros(n)
    if sd == 0:
        return out
    out[0] = rng.normal(0, sd)
    innovation = sd * np.sqrt(1 - persistence**2)
    for i in range(1, n):
        out[i] = persistence * out[i - 1] + rng.normal(0, innovation)
    return out


def twin(
    inputs: Inputs,
    key: Hashable,
    transport: HourTransport,
    scenario: Scenario,
    truth: dict[int, float] = TRUTH,
    seed: int = 0,
) -> Inputs:
    """`inputs` with every station and pixel observation simulated by the transport (`key` for the Jacobian
    cache) from the point-source prior and the road emission ``truth[day type] * level`` of every region,
    plus the background and noise of `scenario`. The cache is kept: the matrices depend on where the
    receptors are, not on what they measured."""
    rng = np.random.default_rng(seed)
    jacobians = inputs.jacobians(key, transport)
    n_points = len(inputs.points)
    prior = inputs.points["prior"].to_numpy(float)
    days = pd.DatetimeIndex(sorted({local_day(h.hour) for h in inputs.hours}))
    kinds = dict(zip(days, day_type(days, HOLIDAYS), strict=True))
    road = [jac.stations[:, n_points:].sum(axis=1) for jac in jacobians]
    points = [jac.stations[:, :n_points] @ prior for jac in jacobians]
    weekday = [k for k, h in enumerate(inputs.hours) if kinds[local_day(h.hour)] == WEEKDAY]
    real = np.mean([inputs.hours[k].nox.mean() for k in weekday])
    modeled = np.mean([(points[k] + road[k]).mean() for k in weekday])
    level = max((real - scenario.background_ppb) / modeled, 0.1)  # the twin's weekday NOx is the real one
    background = dict(
        zip(days, np.exp(_ar1(rng, len(days), scenario.background_sd, scenario.persistence)), strict=True)
    )
    city = dict(zip(days, np.exp(rng.normal(0, scenario.day_sd, len(days))), strict=True))
    hours = []
    for hour, jac in zip(inputs.hours, jacobians, strict=True):
        day = local_day(hour.hour)
        factor = truth[kinds[day]] * city[day]
        state = np.r_[prior, np.full(inputs.n_regions, level * factor)]
        bg = background[day]
        nox = (jac.stations @ state + scenario.background_ppb * bg) * rng.lognormal(
            0, scenario.noise, len(hour.nox)
        )
        no2 = hour.no2
        if len(no2):
            no2 = (jac.pixels @ state + BACKGROUND_PIXEL[0] * bg) * rng.lognormal(0, scenario.noise, len(no2))
        hours.append(replace(hour, nox=nox, no2=no2))
    return replace(inputs, hours=hours)


def recovery(
    data: Inputs, members: Sequence[MemberConfig], truth: dict[int, float] = TRUTH
) -> list[dict[str, Any]]:
    """Sunday and Saturday over weekday of each model fitted on the twin, against the truth."""
    rows = []
    for member in members:
        model: Model = member.build()
        estimate = model.fit(data).estimate_emissions()
        row: dict[str, Any] = {"model": member.name}
        for kind in (SUNDAY_HOLIDAY, SATURDAY):
            name = DAY_TYPE_NAMES[kind]
            true = truth[kind] / truth[WEEKDAY]
            bounds = estimate.day_type_interval(name)
            row[name] = {
                "estimate": estimate.day_type_ratio(name),
                "lo": None if bounds is None else bounds[0],
                "hi": None if bounds is None else bounds[1],
                "truth": true,
                "covered": None if bounds is None else bool(bounds[0] <= true <= bounds[1]),
            }
        rows.append(row)
    return rows


def run_twins(
    generator: ExperimentConfig,
    estimators: Sequence[ExperimentConfig],
    scenarios: Sequence[str],
    runs_dir: Path = Path("runs"),
    seed: int = 0,
) -> Path:
    """Twins of the period of `generator` (its model's transport), one per scenario, and the recovery of
    every estimator, written to ``runs_dir/twins/<generator>.seed<seed>.json``. Only `nox-ml twin` calls
    this."""
    model = generator.model.build()
    if not hasattr(model, "transport"):
        raise ValueError(f"{generator.model.name} has no transport to generate a twin")
    inputs = load_inputs(
        generator.data_dir,
        generator.period.start.isoformat(),
        generator.period.end.isoformat(),
        generator.simat_hours,
    )
    members = [MemberConfig(name=e.model.name, params=e.model.params) for e in estimators]
    result: dict[str, Any] = {
        "generator": {"name": generator.name, "model": generator.model.name},
        "period": {"start": generator.period.start.isoformat(), "end": generator.period.end.isoformat()},
        "truth": {DAY_TYPE_NAMES[k]: v for k, v in TRUTH.items()},
        "estimators": [e.name for e in estimators],
        "scenarios": {},
    }
    for name in scenarios:
        data = twin(inputs, model.transport_key(), model.transport(), SCENARIOS[name], seed=seed)
        rows = recovery(data, members)
        for row, estimator in zip(rows, estimators, strict=True):
            row["config"] = estimator.name
        result["scenarios"][name] = rows
    out = runs_dir / "twins" / f"{generator.name}.seed{seed}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result | {"code_version": code_version()}, indent=2) + "\n")
    (out.with_suffix(".yaml")).write_text(
        yaml.safe_dump(
            {"generator": generator.model_dump(mode="json"), "scenarios": list(scenarios)}, sort_keys=False
        )
    )
    return out


def headline(result: dict[str, Any]) -> str:
    """Recovered Sunday / weekday by scenario and estimator, for the terminal."""
    truth = result["truth"]["sunday_holiday"] / result["truth"]["weekday"]
    lines = [f"generator {result['generator']['name']}; true Sunday / weekday {truth:.2f}"]
    for scenario, rows in result["scenarios"].items():
        lines.append(f"{scenario}:")
        for row in rows:
            s = row["sunday_holiday"]
            bounds = "" if s["lo"] is None else f" ({s['lo']:.2f}-{s['hi']:.2f})"
            lines.append(f"  {row['config']:<22} {s['estimate']:.2f}{bounds}")
    return "\n".join(lines)
