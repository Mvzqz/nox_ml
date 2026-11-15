# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Why was an episode high (or low)? Weather, emission or regional background, against normal days.

The episode days are compared with reference days of the same weekday within four weeks (`placebo.estimate`):

- **concentration**: observed station NOx per hour, episode over reference;
- **weather**: NOx modeled with the prior emission (the baseline plume), the effect of ventilation alone;
- **emission**: concentration over weather, the meteorology-normalized estimator (E7's family);
- **background**: the low end of the TEMPO columns of each hour (`events.PIXEL_BACKGROUND_QUANTILE`), the part
  of the column the city does not emit; it rises when pollution accumulates over the region for days;
- **urban**: the mean TEMPO column above that background, the part the city adds; it rises with the emission
  (and with stagnation, which is why it only separates emission from accumulation when the weather is usual).

Each ratio gets a null interval from fake episodes with the same weekdays drawn from normal days
(`placebo.placebo`), and the verdict reads them together. The emission estimator has no background term: when
the background rose too, a rise of the emission can be accumulation: with usual weather, the urban part of the
column tells regional accumulation from the city's, but not accumulation over the city from emission. In the
week before Christmas 2023 it said emission while the traffic of those dates (Infovial 2018) was normal.

The headline verdict is therefore the prudent one (`prudent_verdict`): it says whether the weather explains
the episode and never claims an emission change; the detailed reading (`verdict`) is kept under ``detail``. On
52 episodes of known cause (context/knowledge/validacion_episodios.md) the prudent verdict halved the false
emission claims in weeks without an emission change (18 % to 9 %) and stopped blaming the weather for
holidays.
"""

from collections.abc import Collection, Iterator, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nox_ml.data import calendar, contingencies
from nox_ml.data.inputs import Inputs, load_inputs
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import SIGMA_THETA, U_MIN
from nox_ml.inversion.normalized import interval
from nox_ml.time import local_day
from nox_ml.validation.events import PIXEL_BACKGROUND_QUANTILE
from nox_ml.validation.experiment import normalized_days
from nox_ml.validation.placebo import estimate, fake_event_sets, reference_days

N_FAKE = 500  # fake episodes per null interval
LEVEL = 0.95  # of the null intervals: at 0.90 one normal episode in ten looked unusual


def tempo_parts(inputs: Inputs, quantile: float = PIXEL_BACKGROUND_QUANTILE) -> pd.DataFrame:
    """Daily means over the hours with TEMPO pixels (molecules/cm2) of the regional ``background`` (the
    `quantile` of the columns of the hour) and of the ``urban`` part (the mean column above it)."""
    rows = []
    for h in inputs.hours:
        if len(h.no2):
            floor = float(np.quantile(h.no2, quantile))
            rows.append((local_day(h.hour), floor, float(h.no2.mean()) - floor))
    table = pd.DataFrame(rows, columns=["day", "background", "urban"])
    return table.groupby("day")[["background", "urban"]].mean()


RATIOS = ("concentration", "weather", "emission", "background", "urban")


def tempo_ratio(part: pd.Series, d: pd.DataFrame, days: Sequence, excluded: Collection) -> float:
    """Mean of a daily TEMPO `part` on `days` over that of their reference days (NaN without data)."""
    refs = [r for day in days for r in reference_days(d, day, excluded)]
    event, ref = part.reindex(list(days)).mean(), part.reindex(refs).mean()
    return float(event / ref) if ref > 0 else float("nan")


def _ratios(d: pd.DataFrame, tempo: pd.DataFrame, days: Sequence, excluded: Collection) -> dict[str, float]:
    est = estimate(d, days, excluded)
    if est is None:
        return {}
    return {
        "concentration": float(est["concentration"]),
        "weather": float(est["meteorology"]),
        "emission": float(est["emission"]),
        "background": tempo_ratio(tempo["background"], d, days, excluded),
        "urban": tempo_ratio(tempo["urban"], d, days, excluded),
    }


def _null(
    d: pd.DataFrame, tempo: pd.DataFrame, sets: Iterator[tuple[list, set]], level: float
) -> dict[str, dict[str, float]]:
    draws = [_ratios(d, tempo, fake, excluded) for fake, excluded in sets]
    out = {}
    for name in RATIOS:
        values = np.array([draw[name] for draw in draws if draw], float)
        lo, hi = interval(values, level)
        out[name] = {"lo": lo, "hi": hi, "n": int(np.isfinite(values).sum())}
    return out


def verdict(ratios: dict[str, float], null: dict[str, dict[str, float]]) -> tuple[str, list[str]]:
    """``emission``, ``weather``, ``both``, ``emission_or_accumulation``, ``accumulation`` or ``normal``, and
    notes that qualify it.

    A ratio is unusual when it leaves its null interval. An unusual rise of the emission with an unusual rise
    of the background is ambiguous (the estimator has no background term); with usual weather the urban part
    of the TEMPO column separates it: ``emission`` (note ``background_up``) when the urban part rose too,
    ``accumulation`` when it did not, ``emission_or_accumulation`` when the weather is unusual. An unusual
    emission against an unusual weather (opposite directions) is ``weather``, with the note
    ``emission_against_weather``: the normalization likely over-corrects the ventilation, a known bias on
    strongly stagnant days. Both unusual in the same direction is ``both``; only the emission, ``emission``.
    A usual emission with an unusual concentration is ``weather`` when the weather ratio is unusual in the
    same direction and ``unexplained`` when it is not (a holiday: concentration and emission down, weather
    usual); ``accumulation`` when only the background is unusual, and ``normal`` otherwise."""

    def unusual(name: str) -> bool:
        return _side(ratios, null, name) != 0

    log_e, log_w = np.log(ratios["emission"]), np.log(ratios["weather"])
    if unusual("emission"):
        if unusual("background") and ratios["background"] > 1 and log_e > 0:
            if unusual("weather"):
                return "emission_or_accumulation", []
            if unusual("urban") and ratios["urban"] > 1:
                return "emission", ["background_up"]
            return "accumulation", []
        if unusual("weather"):
            if np.sign(log_e) != np.sign(log_w):
                return "weather", ["emission_against_weather"]
            return "both", []
        return "emission", []
    concentration = _side(ratios, null, "concentration")
    if concentration:
        return ("weather" if _side(ratios, null, "weather") == concentration else "unexplained"), []
    return ("accumulation" if unusual("background") else "normal"), []


def _side(ratios: dict[str, float], null: dict[str, dict[str, float]], name: str) -> int:
    """+1 above its null interval, -1 below, 0 inside or without data."""
    value, lo, hi = ratios[name], null[name]["lo"], null[name]["hi"]
    if not np.isfinite(value) or lo <= value <= hi:
        return 0
    return 1 if value > hi else -1


def prudent_verdict(ratios: dict[str, float], null: dict[str, dict[str, float]]) -> tuple[str, list[str]]:
    """``normal`` (the concentration is usual), ``weather_explains`` (the weather ratio is unusual in the
    direction of the concentration), ``weather_explains_part`` (the emission ratio is too) or
    ``weather_does_not_explain``, with the note ``background_up`` when the regional background rose.

    It never claims an emission change: the null intervals hold single days, not weeks, so they miss the slow
    drift (±15 %) and the emission ratio of a week leaves them about one time in six without any change."""
    notes = ["background_up"] if _side(ratios, null, "background") > 0 else []
    concentration = _side(ratios, null, "concentration")
    if not concentration:
        return "normal", notes
    if _side(ratios, null, "weather") != concentration:
        return "weather_does_not_explain", notes
    part = _side(ratios, null, "emission") == concentration
    return ("weather_explains_part" if part else "weather_explains"), notes


def diagnose_episode(
    d: pd.DataFrame,
    tempo: pd.DataFrame,
    days: pd.DatetimeIndex,
    excluded: Collection = (),
    n_fake: int = N_FAKE,
    level: float = LEVEL,
    seed: int = 0,
) -> dict[str, Any]:
    """The ratios of the episode `days` (rows of the daily table `d`; `tempo` from `tempo_parts`), their
    null intervals, the share of the log change of the concentration due to weather and to emission, and the
    `verdict`. `excluded` (e.g. contingency days) are neither references nor fake days."""
    days = pd.DatetimeIndex([x for x in days if x in d.index])
    if days.empty:
        raise ValueError("no episode day has data")
    real = set(days) | set(excluded)
    ratios = _ratios(d, tempo, list(days), real)
    if not ratios:
        raise ValueError("no episode day has reference days")
    pool = ~d.index.isin(list(real))
    sets = fake_event_sets(d, list(days), pool, n_fake, np.random.default_rng(seed), real)
    null = _null(d, tempo, sets, level)
    log_c = np.log(ratios["concentration"])
    shares = (
        {
            "weather": float(np.log(ratios["weather"]) / log_c),
            "emission": float(np.log(ratios["emission"]) / log_c),
        }
        if abs(log_c) > 1e-9
        else None
    )
    label, notes = prudent_verdict(ratios, null)
    detail, detail_notes = verdict(ratios, null)
    return {
        "days": [x.date().isoformat() for x in days],
        "ratios": ratios,
        "null": null,
        "shares": shares,
        "verdict": label,
        "notes": notes,
        "detail": {"verdict": detail, "notes": detail_notes},
        "level": level,
    }


def headline(result: dict[str, Any]) -> str:
    """The diagnosis in a few lines, for the terminal."""
    lines = [f"{len(result['days'])} days, {result['days'][0]} to {result['days'][-1]}"]
    for name, value in result["ratios"].items():
        null = result["null"][name]
        lines.append(f"  {name:<13} {value:.2f}   normal days {null['lo']:.2f}-{null['hi']:.2f}")
    if result["shares"]:
        weather, emission = result["shares"]["weather"], result["shares"]["emission"]
        lines.append(f"  share of the change: weather {weather:.0%}, emission {emission:.0%}")
    lines.append(f"  verdict: {_labelled(result['verdict'], result['notes'])}")
    detail = result["detail"]
    lines.append(f"  detail (not a claim on the emission): {_labelled(detail['verdict'], detail['notes'])}")
    return "\n".join(lines)


def _labelled(label: str, notes: list[str]) -> str:
    return label + (f" ({', '.join(notes)})" if notes else "")


def run_episode(
    data_dir: Path, start: str, end: str, days: pd.DatetimeIndex, seed: int = 0
) -> dict[str, Any]:
    """`diagnose_episode` of `days` with the data of the local days `start` to `end` (a window with TEMPO
    pixels), the contingency days of 2024 kept out of the references. Only `nox-ml episode` calls this."""
    inputs = load_inputs(data_dir, start, end)
    daily = normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)))
    episodes = contingencies.read_episodes(data_dir / "raw" / contingencies.EPISODES_FILE)
    atypical = calendar.atypical_days(start, end)
    excluded = (set(contingencies.active_days(episodes)) | set(atypical)) - set(days)
    result = diagnose_episode(daily, tempo_parts(inputs), days, excluded, seed=seed)
    return {"data": {"start": start, "end": end}, **result}
