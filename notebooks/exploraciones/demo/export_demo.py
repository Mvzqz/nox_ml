# pyright: reportReturnType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportArgumentType=false
# pyright: reportOperatorIssue=false, reportIndexIssue=false
"""Export what the app (app/src/nox_app) reads from results/runs/demo.

- ``events.csv``: the atypical events of 2019 to 2027 (ozone contingencies, holidays, year-end, Easter);
- ``series/<start>_<end>.csv``: per day of each season, the observed NOx and the NOx without the weather
  (observed over modeled with the usual emission), both over the same weekday of the normal days within four
  weeks; with the atypical days left out of those days (the default baseline) and kept in (``_all``);
- ``bulletins.json``: the weekly episodes of the monthly bulletins of June to October 2026, which the
  `episode` command cannot run yet (it does not read the OpenAQ tables), each with both baselines;
- ``episodes.json``: three example episodes of December 2023, each with both baselines.

Run from the repository root: ``uv run python notebooks/exploraciones/demo/export_demo.py``.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import calendar, contingencies
from nox_ml.data.inputs import DEFAULT_SOURCES, load_inputs, openaq_sources
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import HOLIDAYS, SIGMA_THETA, U_MIN
from nox_ml.validation.episodes import diagnose_episode, tempo_parts
from nox_ml.validation.experiment import normalized_days
from nox_ml.validation.placebo import reference_days

OUT = Path("results/runs/demo")
EVENTS = ("2019-01-01", "2027-12-31")  # from the 2020 lockdown to the pilots scheduled for 2027
SEASONS = [
    ("2023-11-01", "2023-12-31"),
    ("2024-02-15", "2024-05-31"),
    ("2024-06-01", "2024-10-31"),
    ("2024-11-01", "2024-12-31"),
    ("2025-02-15", "2025-05-31"),
    ("2025-06-01", "2025-10-31"),
    ("2025-11-01", "2025-12-31"),
    ("2026-02-15", "2026-05-31"),
    ("2026-06-01", "2026-10-31"),
]
BULLETIN_SEASON = ("2026-06-01", "2026-10-31")
EXAMPLES = {
    "stagnant_week": ("2023-12-11", "2023-12-15", "Semana estancada"),
    "pre_christmas": ("2023-12-18", "2023-12-22", "Semana antes de Navidad"),
    "post_christmas": ("2023-12-26", "2023-12-29", "Semana después de Navidad"),
}
BAND = (0.05, 0.95)  # of the observed change of normal days: the "normal range" of one day


def known_events() -> pd.DataFrame:
    rows = []
    for e in contingencies.read_episodes(Path("data/raw") / contingencies.EPISODES_FILE).itertuples():
        rows.append((e.activation, e.suspension, "Contingencia", f"Contingencia por ozono #{e.episode}"))
    rows += [
        (pd.Timestamp(h), pd.Timestamp(h), "Festivo", f"Festivo del {pd.Timestamp(h):%d/%m/%Y}")
        for h in HOLIDAYS
    ]
    for year in range(int(EVENTS[0][:4]), int(EVENTS[1][:4]) + 1):
        year_end, easter = calendar.year_end(year), calendar.easter_holidays(year)
        rows.append((year_end[0], year_end[-1], "Fin de año", f"Guadalupe–Reyes {year}"))
        rows.append((easter[0], easter[-1], "Semana Santa", f"Semana Santa y Pascua {year}"))
    events = pd.DataFrame(rows, columns=["start", "end", "kind", "name"]).sort_values("start")
    return events[events["start"].between(*EVENTS)]


def atypical(start: str, end: str) -> set:
    """Year-end, Easter, holidays and contingency days: left out of the default baseline."""
    episodes = contingencies.read_episodes(Path("data/raw") / contingencies.EPISODES_FILE)
    days = set(calendar.atypical_days(start, end)) | set(contingencies.active_days(episodes))
    days |= {pd.Timestamp(h) for h in HOLIDAYS}
    return {d for d in days if pd.Timestamp(start) <= d <= pd.Timestamp(end)}


def season_data(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    after = pd.Timestamp(end) + pd.Timedelta(days=1)
    sources = openaq_sources(start, f"{after:%Y-%m-%d}") if start >= "2025-01-01" else DEFAULT_SOURCES
    inputs = load_inputs(Path("data"), start, end, (12, 17), sources)
    return normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN))), tempo_parts(
        inputs
    )


def series(daily: pd.DataFrame, odd: set) -> pd.DataFrame:
    """Observed and weather-free NOx change of each day over its reference days, with both baselines."""
    rate, model = daily["obs"] / daily["hours"], daily["model"] / daily["hours"]
    rows = []
    for day in daily.index:
        row = {"day": day.date().isoformat(), "atypical": day in odd}
        for suffix, excluded in (("", odd | {day}), ("_all", {day})):
            refs = reference_days(daily, day, excluded)
            if refs:
                obs = rate[day] / rate[refs].mean()
                row[f"obs{suffix}"] = obs - 1
                row[f"adj{suffix}"] = obs / (model[day] / model[refs].mean()) - 1
        rows.append(row)
    table = pd.DataFrame(rows)
    normal = table.loc[~table["atypical"], "obs"].dropna()
    table["band_lo"], table["band_hi"] = normal.quantile(BAND[0]), normal.quantile(BAND[1])
    return table


def clean(result: dict) -> dict:
    result = json.loads(json.dumps(result, default=str))
    result["ratios"] = {
        k: v if v is not None and np.isfinite(v) else None for k, v in result["ratios"].items()
    }
    return result


def both_baselines(daily: pd.DataFrame, tempo: pd.DataFrame, days: pd.DatetimeIndex, odd: set) -> dict:
    """The diagnosis of `days` with the atypical days out of the baseline (default) and in it."""
    out = {}
    for name, excluded in (("default", odd - set(days)), ("with_atypical", set())):
        try:
            out[name] = clean(diagnose_episode(daily, tempo, days, excluded))
        except ValueError as error:
            out[name] = {"error": str(error)}
    return out


def bulletins(daily: pd.DataFrame, tempo: pd.DataFrame, odd: set) -> list[dict]:
    """One bulletin per month: its Monday-to-Friday weeks."""
    months = []
    for month in pd.period_range(*BULLETIN_SEASON, freq="M"):
        weeks = []
        for monday in pd.date_range(month.start_time, month.end_time, freq="W-MON"):
            days = pd.date_range(monday, monday + pd.Timedelta(days=4))
            weeks.append(
                {
                    "start": f"{days[0]:%Y-%m-%d}",
                    "end": f"{days[-1]:%Y-%m-%d}",
                    **both_baselines(daily, tempo, days, odd),
                }
            )
        months.append(
            {
                "month": f"{month}",
                "data": dict(zip(("start", "end"), BULLETIN_SEASON, strict=True)),
                "weeks": weeks,
            }
        )
    return months


if __name__ == "__main__":
    (OUT / "series").mkdir(parents=True, exist_ok=True)
    events = known_events()
    events.assign(start=events["start"].dt.date, end=events["end"].dt.date).to_csv(
        OUT / "events.csv", index=False
    )
    examples = {}
    for start, end in SEASONS:
        odd = atypical(start, end)
        daily, tempo = season_data(start, end)
        series(daily, odd).to_csv(OUT / "series" / f"{start}_{end}.csv", index=False, float_format="%.4g")
        print("series", start, end, len(daily), flush=True)
        if (start, end) == BULLETIN_SEASON:
            months = bulletins(daily, tempo, odd)
            (OUT / "bulletins.json").write_text(json.dumps(months, indent=1) + "\n")
            for m in months:
                print(m["month"], [w["default"].get("verdict", "sin datos") for w in m["weeks"]], flush=True)
        for label, (a, b, title) in EXAMPLES.items():
            if start <= a <= end:
                result = both_baselines(daily, tempo, pd.date_range(a, b), odd)
                examples[label] = {"title": title, "data": {"start": start, "end": end}, **result}
    (OUT / "episodes.json").write_text(json.dumps(examples, indent=1) + "\n")
