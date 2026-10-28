# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Did the emission fall on the days with contingency measures? Any model of the registry, with placebos.

Same mechanism as the placebo of the model (`experiment.placebo_ratios`): the model is fitted on business days
only and the event days are relabeled as Sundays (`Inputs.with_day_kinds`), so the model's Sunday / weekday
ratio is the emission of the event days over the normal ones. The placebos relabel *fake* event days drawn
from the normal days, where nothing changed, to show how far from 1 a null result lands.

Day groups (`split_days`), for the days of the data:

- **event**: business days of the requested set (the measure days, or every active day as a sensitivity);
- **normal**: business days with no contingency active, which are the reference *and* the pool of the fake
  days, so a real event never serves as reference or as fake;
- **left out**: activation days, when the requested set is the measure days: in neither group;
- **dropped**: requested days that are not business days (Saturday, Sunday, holiday) and requested days
  without data.

Weekends and holidays with measures are dropped, not relabeled. The model separates day types by the
weekday / Sunday contrast, and a Sunday already is a Sunday, so relabeling it changes nothing; a Saturday
relabeled as Sunday would mix the contingency with the Saturday pattern of traffic, which the business-day
comparison cannot separate. A measure day on a weekend is a day we cannot measure, so it is listed, not used.

This reads the test period (the contingencies are held out data): `run_contingencies` only runs on it, like
`experiment.run_on_test_period`, and nothing here is reachable from `tune`.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from nox_ml.data import contingencies
from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import HOLIDAYS, SIGMA_THETA, U_MIN
from nox_ml.inversion.normalized import SUNDAY_HOLIDAY, WEEKDAY, day_type, interval
from nox_ml.models import Model
from nox_ml.time import local_day
from nox_ml.validation.experiment import (
    EVALUATION_PERIOD,
    ExperimentConfig,
    Period,
    Placebo,
    code_version,
    normalized_days,
)
from nox_ml.validation.stagnation import poorly_ventilated_mask

SUFFIX = ".contingencies"


@dataclass(frozen=True)
class Groups:
    """The days of an analysis (see the module docstring). All are local days of the data except
    `without_data`."""

    event: pd.DatetimeIndex
    normal: pd.DatetimeIndex
    left_out: pd.DatetimeIndex
    not_business: pd.DatetimeIndex
    without_data: pd.DatetimeIndex


def data_days(inputs: Inputs) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted({local_day(h.hour) for h in inputs.hours}))


def split_days(inputs: Inputs, requested: pd.DatetimeIndex, active: pd.DatetimeIndex) -> Groups:
    """Groups for event days `requested` (a subset of `active`, every day with a contingency)."""
    days = data_days(inputs)
    business = days[day_type(days, HOLIDAYS) == WEEKDAY]
    event = business.intersection(requested)
    return Groups(
        event=event,
        normal=business.difference(active),
        left_out=business.intersection(active).difference(event),
        not_business=days.intersection(requested).difference(business),
        without_data=requested.difference(days),
    )


def _fit_ratio(
    days_inputs: Inputs, make_model: Callable[[], Model], relabeled: pd.DatetimeIndex
) -> tuple[float, tuple[float, float] | None]:
    """Sunday over weekday of the model fitted on `days_inputs` (the inputs of the days of the fit, from
    `Inputs.on_days`) with `relabeled` as Sundays, and its interval. The relabeling shares the Jacobian cache
    of `days_inputs`, so draws over the same days build the matrices once."""
    data = days_inputs.with_day_kinds(dict.fromkeys(relabeled, SUNDAY_HOLIDAY))
    estimate = make_model().fit(data).estimate_emissions()
    return estimate.day_type_ratio("sunday_holiday"), estimate.day_type_interval("sunday_holiday")


def fake_event_ratios(
    inputs: Inputs,
    make_model: Callable[[], Model],
    groups: Groups,
    pool: pd.DatetimeIndex,
    refits: int,
    seed: int,
) -> np.ndarray:
    """Contingency over normal ratio of the model with as many fake event days as real ones, drawn from
    `pool` (a subset of the normal days), once per refit. The model sees no real event day. There is no change
    to find: they should be centered on 1."""
    n_fake = len(groups.event)
    if n_fake > len(pool) or n_fake >= len(groups.normal):
        raise ValueError(
            f"placebo needs {n_fake} fake days from a pool of {len(pool)}, "
            f"with more than {n_fake} normal days left (has {len(groups.normal)})"
        )
    rng = np.random.default_rng(seed)
    normal = inputs.on_days(groups.normal)  # once: `on_days` starts an empty Jacobian cache
    return np.array(
        [
            _fit_ratio(normal, make_model, pool[rng.choice(len(pool), n_fake, replace=False)])[0]
            for _ in range(refits)
        ]
    )


def poorly_ventilated_pool(daily: pd.DataFrame, groups: Groups) -> pd.DatetimeIndex:
    """Normal days at least as stagnant as the bulk of the event days (`poorly_ventilated_mask`), judged by
    the ``stagnation`` of the daily table (`normalized_days`: the NOx the plume predicts with the prior
    emission, so high means poorly ventilated, as in the research). Empty without event days in `daily`."""
    event = groups.event.intersection(daily.index)
    if event.empty:
        return pd.DatetimeIndex([])
    return daily.index[poorly_ventilated_mask(daily, event)].intersection(groups.normal)


def summarize(ratios: np.ndarray, level: float, n_fake: int, n_pool: int) -> dict[str, Any]:
    lo, hi = interval(ratios, level)
    return {
        "center": float(np.median(ratios)),
        "lo": lo,
        "hi": hi,
        "half_width": (hi - lo) / 2,
        "n_fake_days": n_fake,
        "n_pool_days": n_pool,
        "ratios": [float(r) for r in ratios],
    }


def day_list(days: pd.DatetimeIndex) -> list[str]:
    return [d.date().isoformat() for d in days]


def analyze(
    inputs: Inputs,
    make_model: Callable[[], Model],
    groups: Groups,
    daily: pd.DataFrame,
    config: Placebo,
) -> dict[str, Any]:
    """Ratio of the event days over the normal ones, its interval and the two placebos (random fake days and
    poorly ventilated fake days; ``None`` for the second if no event day has ventilation data)."""
    if groups.event.empty:
        raise ValueError("no event day is a business day with data")
    ratio, bounds = _fit_ratio(inputs.on_days(groups.event.union(groups.normal)), make_model, groups.event)
    placebos: dict[str, Any] = {}
    for name, pool in (
        ("random", groups.normal),
        ("poorly_ventilated", poorly_ventilated_pool(daily, groups)),
    ):
        if pool.empty:
            placebos[name] = None
            continue
        ratios = fake_event_ratios(inputs, make_model, groups, pool, config.refits, config.seed)
        placebos[name] = summarize(ratios, config.level, len(groups.event), len(pool))
    return {
        "ratio": ratio,
        "lo": None if bounds is None else bounds[0],
        "hi": None if bounds is None else bounds[1],
        "days": {
            "event": day_list(groups.event),
            "n_normal": len(groups.normal),
            "left_out": day_list(groups.left_out),
            "not_business": day_list(groups.not_business),
            "without_data": day_list(groups.without_data),
        },
        "placebos": placebos,
    }


def contingency_effect(
    inputs: Inputs,
    make_model: Callable[[], Model],
    episodes: pd.DataFrame,
    config: Placebo,
    sensitivity: bool = False,
) -> dict[str, Any]:
    """Scenario ``measures`` (the days with measures, activation days left out) and, with `sensitivity`,
    ``all_active`` (every day with an active contingency). Each is `analyze`. Fits the model
    ``1 + 2 * config.refits`` times per scenario."""
    if make_model().role != "model":
        raise ValueError("contingencies need a model that estimates emissions, not a reference")
    active = contingencies.active_days(episodes)
    daily = normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)))
    requested = {"measures": contingencies.measure_days(episodes)}
    if sensitivity:
        requested["all_active"] = active
    return {
        name: analyze(inputs, make_model, split_days(inputs, days, active), daily, config)
        for name, days in requested.items()
    }


def run_contingencies(
    config: ExperimentConfig, runs_dir: Path = Path("runs"), sensitivity: bool = False
) -> Path:
    """The contingencies of 2024 with a frozen config, on the test period (`EVALUATION_PERIOD`), written to
    ``runs_dir/<name>.contingencies/``: ``contingencies.json``, ``config.yaml`` (the period is the test
    period, so `tune` refuses it) and ``code_version.json``. Only `nox-ml contingencies` calls this."""
    name = f"{config.name.removesuffix('.test').removesuffix(SUFFIX)}{SUFFIX}"
    test = config.model_copy(
        update={"name": name, "period": Period(start=EVALUATION_PERIOD[0], end=EVALUATION_PERIOD[1])}
    )
    episodes = contingencies.read_episodes(config.data_dir / "raw" / contingencies.EPISODES_FILE)
    inputs = load_inputs(
        test.data_dir, test.period.start.isoformat(), test.period.end.isoformat(), test.simat_hours
    )
    result = {
        "model": test.model.name,
        "frozen_on": {"start": config.period.start.isoformat(), "end": config.period.end.isoformat()},
        "period": {"start": test.period.start.isoformat(), "end": test.period.end.isoformat()},
        "level": test.placebo.level,
        "scenarios": contingency_effect(inputs, test.model.build, episodes, test.placebo, sensitivity),
    }
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(test.model_dump(mode="json"), sort_keys=False))
    (out / "contingencies.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def headline(result: dict[str, Any]) -> str:
    """The ratios and placebos of each scenario in a few lines, for the terminal."""
    lines = []
    for name, s in result["scenarios"].items():
        bounds = "" if s["lo"] is None else f" ({s['lo']:.2f}-{s['hi']:.2f})"
        lines.append(
            f"{name}: contingency / normal {s['ratio']:.2f}{bounds} on {len(s['days']['event'])} days"
        )
        for kind, p in s["placebos"].items():
            text = "no pool" if p is None else f"{p['center']:.2f} ({p['lo']:.2f}-{p['hi']:.2f})"
            lines.append(f"  placebo {kind}: {text}")
    return "\n".join(lines)
