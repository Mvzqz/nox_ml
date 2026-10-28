# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Did the emission fall on the days with contingency measures, or on a set of calendar days (school holidays,
year-end)? Any model of the registry, with placebos.

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
`experiment.run_on_test_period`, and nothing here is reachable from `tune`. `run_calendar` runs on the
period of the config or on the test period; the event days are the requested calendar days and the
contingency days are left out of the normal ones.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm

from nox_ml.data import calendar, contingencies
from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import BACKGROUND_STATION, HOLIDAYS, SIGMA_THETA, U_MIN
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
CALENDAR_SUFFIX = ".calendar-"  # + label: runs/<name>.calendar-<label>/
DETECTION_SUFFIX = ".detection"
DETECTION_POWER = 0.80  # the usual power of a detection limit
EXTRAPOLATED_DAYS = (20, 60, 120, 250)  # a month of business days, a season, half a year, a year
PIXEL_BACKGROUND_QUANTILE = 0.10  # of an hour's TEMPO columns: the part of the column the city does not emit


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
    return _fake_ratios(inputs, make_model, groups.normal, pool, len(groups.event), refits, seed)


def _fake_ratios(
    inputs: Inputs,
    make_model: Callable[[], Model],
    normal: pd.DatetimeIndex,
    pool: pd.DatetimeIndex,
    n_fake: int,
    refits: int,
    seed: int,
) -> np.ndarray:
    """Ratio of `n_fake` days drawn from `pool` over the rest of `normal`, once per refit."""
    if n_fake > len(pool) or n_fake >= len(normal):
        raise ValueError(
            f"placebo needs {n_fake} fake days from a pool of {len(pool)}, "
            f"with more than {n_fake} normal days left (has {len(normal)})"
        )
    rng = np.random.default_rng(seed)
    days = inputs.on_days(normal)  # once: `on_days` starts an empty Jacobian cache
    return np.array(
        [
            _fit_ratio(days, make_model, pool[rng.choice(len(pool), n_fake, replace=False)])[0]
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


def inject_drop(inputs: Inputs, days: pd.DatetimeIndex, drop: float) -> Inputs:
    """The inputs with the city's part of the observations lowered by `drop` (0.2: 20 %) on `days`: the
    station NOx above the background prior (`BACKGROUND_STATION`) and the TEMPO columns above the
    `PIXEL_BACKGROUND_QUANTILE` of their hour. A known emission drop added to real data, to measure the drop
    an analysis can detect. The Jacobians depend on where the receptors are, not on what they measured, so
    the cache is kept."""
    if not 0 <= drop < 1:
        raise ValueError(f"drop must be in [0, 1), got {drop}")
    selected = set(days)
    background = BACKGROUND_STATION[0]
    hours = []
    for hour in inputs.hours:
        if local_day(hour.hour) in selected:
            nox = background + (hour.nox - background) * (1 - drop)
            no2 = hour.no2
            if len(no2):
                floor = float(np.quantile(no2, PIXEL_BACKGROUND_QUANTILE))
                no2 = floor + (no2 - floor) * (1 - drop)
            hour = replace(hour, nox=nox, no2=no2)
        hours.append(hour)
    return replace(inputs, hours=hours)


def injection_recovery(
    inputs: Inputs, make_model: Callable[[], Model], groups: Groups, drops: Sequence[float]
) -> list[dict[str, Any]]:
    """For each injected drop on the event days, the contingency / normal ratio the model finds and the drop
    it recovers relative to the ratio without injection (``recovered`` = 1 - ratio / ratio at 0). A drop is
    detected when its interval stays below the ratio without injection. One fit per drop, plus the one
    without injection; the matrices of the fitted days are built once."""
    days = groups.event.union(groups.normal)
    rows = []
    for drop in (0.0, *drops):
        data = inject_drop(inputs, groups.event, drop).on_days(days) if drop else inputs.on_days(days)
        ratio, bounds = _fit_ratio(data, make_model, groups.event)
        rows.append(
            {
                "drop": drop,
                "ratio": ratio,
                "lo": None if bounds is None else bounds[0],
                "hi": None if bounds is None else bounds[1],
            }
        )
    base = rows[0]["ratio"]
    for row in rows:
        row["recovered"] = 1 - row["ratio"] / base
        row["detected"] = None if row["hi"] is None or not row["drop"] else bool(row["hi"] < base)
    return rows


def _require_emissions(make_model: Callable[[], Model]) -> None:
    if make_model().role != "model":
        raise ValueError("event analyses need a model that estimates emissions, not a reference")


def _daily(inputs: Inputs) -> pd.DataFrame:
    """The daily table of `normalized_days` with the baseline plume, for the ventilation of the days."""
    return normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)))


def contingency_effect(
    inputs: Inputs,
    make_model: Callable[[], Model],
    episodes: pd.DataFrame,
    config: Placebo,
    sensitivity: bool = False,
    inject: Sequence[float] = (),
    atypical: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Scenario ``measures`` (the days with measures, activation days left out) and, with `sensitivity`,
    ``all_active`` (every day with an active contingency). Each is `analyze`. Fits the model
    ``1 + 2 * config.refits`` times per scenario. With `inject`, the ``measures`` scenario also gets
    ``injection``: the drops it recovers when they are added to the data (`injection_recovery`).
    `atypical` days (e.g. school holidays) are neither event nor normal days: they would bias the reference
    (they are listed as left out)."""
    _require_emissions(make_model)
    active = contingencies.active_days(episodes)
    if atypical is not None:
        active = active.union(atypical)
    daily = _daily(inputs)
    requested = {"measures": contingencies.measure_days(episodes)}
    if sensitivity:
        requested["all_active"] = active
    result = {
        name: analyze(inputs, make_model, split_days(inputs, days, active), daily, config)
        for name, days in requested.items()
    }
    if inject:
        groups = split_days(inputs, requested["measures"], active)
        result["measures"]["injection"] = injection_recovery(inputs, make_model, groups, inject)
    return result


def run_contingencies(
    config: ExperimentConfig,
    runs_dir: Path = Path("runs"),
    sensitivity: bool = False,
    inject: Sequence[float] = (),
    atypical: pd.DatetimeIndex | None = None,
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
    left_out = calendar.atypical_days(test.period.start, test.period.end).union(
        pd.DatetimeIndex([]) if atypical is None else atypical
    )
    result = {
        "model": test.model.name,
        "frozen_on": {"start": config.period.start.isoformat(), "end": config.period.end.isoformat()},
        "period": {"start": test.period.start.isoformat(), "end": test.period.end.isoformat()},
        "level": test.placebo.level,
        "scenarios": contingency_effect(
            inputs, test.model.build, episodes, test.placebo, sensitivity, inject, left_out
        ),
        "atypical": day_list(left_out),
    }
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(test.model_dump(mode="json"), sort_keys=False))
    (out / "contingencies.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def calendar_effect(
    inputs: Inputs,
    make_model: Callable[[], Model],
    days: pd.DatetimeIndex,
    excluded: pd.DatetimeIndex,
    config: Placebo,
    inject: Sequence[float] = (),
) -> dict[str, Any]:
    """`analyze` with `days` (calendar days with less traffic expected) as the event days; `excluded` (the
    contingency days) are neither event nor normal days. With `inject`, also ``injection``, as for the
    contingencies. A real drop the analysis should see: its positive control."""
    _require_emissions(make_model)
    groups = split_days(inputs, days, days.union(excluded))
    result = analyze(inputs, make_model, groups, _daily(inputs), config)
    if inject:
        result["injection"] = injection_recovery(inputs, make_model, groups, inject)
    return result


def run_calendar(
    config: ExperimentConfig,
    days: pd.DatetimeIndex,
    label: str,
    runs_dir: Path = Path("runs"),
    test_period: bool = False,
    inject: Sequence[float] = (),
) -> Path:
    """`calendar_effect` of `days` on the period of `config` (or on the test period, `EVALUATION_PERIOD`),
    with the 2024 contingency days left out, written to ``runs_dir/<name>.calendar-<label>/``:
    ``calendar.json``, ``config.yaml`` and ``code_version.json``. Only `nox-ml calendar` calls this."""
    base = config.name.removesuffix(".test").split(CALENDAR_SUFFIX)[0]
    name = f"{base}{CALENDAR_SUFFIX}{label}"
    period = Period(start=EVALUATION_PERIOD[0], end=EVALUATION_PERIOD[1]) if test_period else config.period
    run = config.model_copy(update={"name": name, "period": period})
    episodes = contingencies.read_episodes(config.data_dir / "raw" / contingencies.EPISODES_FILE)
    inputs = load_inputs(
        run.data_dir, run.period.start.isoformat(), run.period.end.isoformat(), run.simat_hours
    )
    result = {
        "model": run.model.name,
        "label": label,
        "frozen_on": {"start": config.period.start.isoformat(), "end": config.period.end.isoformat()},
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "level": run.placebo.level,
        "scenarios": {
            label: calendar_effect(
                inputs,
                run.model.build,
                days,
                contingencies.active_days(episodes).union(calendar.atypical_days(period.start, period.end)),
                run.placebo,
                inject,
            )
        },
    }
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(run.model_dump(mode="json"), sort_keys=False))
    (out / "calendar.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def detection_curve(
    inputs: Inputs,
    make_model: Callable[[], Model],
    normal: pd.DatetimeIndex,
    counts: Sequence[int],
    config: Placebo,
    power: float = DETECTION_POWER,
) -> dict[str, Any]:
    """The smallest emission drop an event of k days can show, for each k of `counts`, from the placebo of k
    fake days drawn from `normal` (days where nothing changed).

    A drop d multiplies the ratio: it is detected when ``(1 - d) * r`` falls below the lower placebo bound
    ``lo``, with ``r`` a placebo ratio. So the drop detected with probability p is ``1 - lo / q_p``, with
    ``q_p`` the p quantile of the placebo ratios: ``mdc_half`` at p = 0.5 and ``mdc`` at p = `power`. The
    injection test supports the multiplicative form (the drops are recovered whole).

    ``cv`` is the day-to-day variation that fits the spread of the log ratios, ``sd = cv * sqrt(1/k +
    1/(n - k))`` with n normal days; ``extrapolated`` gives the drop for longer events against a reference of
    as many days (before and after), with normal quantiles: the rule for counts the data cannot hold."""
    rows = []
    for k in counts:
        ratios = _fake_ratios(inputs, make_model, normal, normal, k, config.refits, config.seed)
        lo, hi = interval(ratios, config.level)
        rows.append(
            {
                "days": k,
                "center": float(np.median(ratios)),
                "lo": lo,
                "hi": hi,
                "mdc_half": 1 - lo / float(np.median(ratios)),
                "mdc": 1 - lo / float(np.quantile(ratios, power)),
                "sd_log": float(np.std(np.log(ratios), ddof=1)),
            }
        )
    n = len(normal)
    scale = np.array([np.sqrt(1 / r["days"] + 1 / (n - r["days"])) for r in rows])
    sd = np.array([r["sd_log"] for r in rows])
    cv = float(scale @ sd / (scale @ scale))  # least squares through the origin
    z = float(norm.ppf(0.5 + config.level / 2) + norm.ppf(power))
    extrapolated = [
        {"days": k, "mdc": float(1 - np.exp(-z * cv * np.sqrt(2 / k)))} for k in EXTRAPOLATED_DAYS
    ]
    return {"n_normal": n, "power": power, "cv": cv, "rows": rows, "extrapolated": extrapolated}


def run_detection(
    config: ExperimentConfig,
    counts: Sequence[int],
    runs_dir: Path = Path("runs"),
    power: float = DETECTION_POWER,
    exclude: pd.DatetimeIndex | None = None,
    label: str | None = None,
) -> Path:
    """`detection_curve` on the business days of the period of `config` without contingency nor `exclude`
    (atypical periods, e.g. the year-end), written to ``runs_dir/<name>.detection[-<label>]/``:
    ``detection.json``, ``config.yaml`` and ``code_version.json``. Only `nox-ml detection` calls this."""
    _require_emissions(config.model.build)
    base = config.name.removesuffix(".test").split(DETECTION_SUFFIX)[0]
    name = f"{base}{DETECTION_SUFFIX}{f'-{label}' if label else ''}"
    exclude = pd.DatetimeIndex([]) if exclude is None else exclude
    run = config.model_copy(update={"name": name})
    episodes = contingencies.read_episodes(config.data_dir / "raw" / contingencies.EPISODES_FILE)
    inputs = load_inputs(
        run.data_dir, run.period.start.isoformat(), run.period.end.isoformat(), run.simat_hours
    )
    atypical = calendar.atypical_days(run.period.start, run.period.end)
    left_out = contingencies.active_days(episodes).union(exclude).union(atypical)
    normal = split_days(inputs, pd.DatetimeIndex([]), left_out).normal
    result = {
        "model": run.model.name,
        "period": {"start": run.period.start.isoformat(), "end": run.period.end.isoformat()},
        "excluded": day_list(exclude),
        "level": run.placebo.level,
        "refits": run.placebo.refits,
        **detection_curve(inputs, run.model.build, normal, counts, run.placebo, power),
    }
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(run.model_dump(mode="json"), sort_keys=False))
    (out / "detection.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def detection_headline(result: dict[str, Any]) -> str:
    """The curve in a few lines, for the terminal."""
    power = result["power"]
    lines = [f"days  placebo            drop seen half the time  drop seen {power:.0%} of the time"]
    for r in result["rows"]:
        bounds = f"{r['center']:.2f} ({r['lo']:.2f}-{r['hi']:.2f})"
        lines.append(f"{r['days']:>4}  {bounds:<17}  {r['mdc_half']:>23.0%}  {r['mdc']:>24.0%}")
    lines.append(f"day-to-day variation {result['cv']:.2f}; extrapolated, against as many days before:")
    lines.extend(f"{e['days']:>4}  {e['mdc']:.0%}" for e in result["extrapolated"])
    return "\n".join(lines)


def headline(result: dict[str, Any]) -> str:
    """The ratios and placebos of each scenario in a few lines, for the terminal."""
    lines = []
    for name, s in result["scenarios"].items():
        bounds = "" if s["lo"] is None else f" ({s['lo']:.2f}-{s['hi']:.2f})"
        lines.append(f"{name}: event / normal {s['ratio']:.2f}{bounds} on {len(s['days']['event'])} days")
        for kind, p in s["placebos"].items():
            text = "no pool" if p is None else f"{p['center']:.2f} ({p['lo']:.2f}-{p['hi']:.2f})"
            lines.append(f"  placebo {kind}: {text}")
        for row in s.get("injection", [])[1:]:
            seen = {True: "detected", False: "not detected", None: "no interval"}[row["detected"]]
            drop, ratio, recovered = row["drop"], row["ratio"], row["recovered"]
            lines.append(f"  injected {drop:.0%}: ratio {ratio:.2f}, recovered {recovered:.0%} ({seen})")
    return "\n".join(lines)
