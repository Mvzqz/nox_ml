# pyright: reportReturnType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportArgumentType=false
"""Export what the UX demo (app/src/nox_app/main.py) reads from results/runs/demo.

- ``events.csv``: the known events of each season (ozone contingencies, holidays, year-end, Easter);
- ``bulletin_2026-10.json``: the weekly episodes of the October 2026 bulletin, which the `episode` command
  cannot run yet (it does not read the OpenAQ tables).

Run from the repository root: ``uv run python notebooks/exploraciones/demo/export_demo.py``.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import calendar, contingencies
from nox_ml.data.inputs import load_inputs, openaq_sources
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import HOLIDAYS, SIGMA_THETA, U_MIN
from nox_ml.validation.episodes import diagnose_episode, tempo_parts
from nox_ml.validation.experiment import normalized_days

OUT = Path("results/runs/demo")
FIRST, LAST = "2023-11-01", "2026-10-31"  # the seasons with TEMPO pixels
START, END = "2026-06-01", "2026-10-31"  # the season of the bulletin
WEEKS = [
    ("2026-09-28", "2026-10-02"),
    ("2026-10-05", "2026-10-09"),
    ("2026-10-12", "2026-10-16"),
    ("2026-10-19", "2026-10-23"),
    ("2026-10-26", "2026-10-30"),
]


def known_events() -> pd.DataFrame:
    rows = []
    for e in contingencies.read_episodes(Path("data/raw") / contingencies.EPISODES_FILE).itertuples():
        rows.append((e.activation, e.suspension, "Contingencia", f"Contingencia por ozono #{e.episode}"))
    rows += [(pd.Timestamp(h), pd.Timestamp(h), "Festivo", "Día festivo") for h in HOLIDAYS]
    for year in range(2023, 2027):
        year_end, easter = calendar.year_end(year), calendar.easter_holidays(year)
        rows.append((year_end[0], year_end[-1], "Fin de año", f"Guadalupe–Reyes {year}"))
        rows.append((easter[0], easter[-1], "Semana Santa", f"Semana Santa y Pascua {year}"))
    events = pd.DataFrame(rows, columns=["start", "end", "kind", "name"]).sort_values("start")
    return events[events["start"].between(FIRST, LAST)]


def bulletin() -> list[dict]:
    inputs = load_inputs(Path("data"), START, END, (12, 17), openaq_sources(START, "2026-11-01"))
    daily = normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)))
    tempo = tempo_parts(inputs)
    atypical = set(calendar.atypical_days(START, END))
    weeks = []
    for a, b in WEEKS:
        days = pd.date_range(a, b)
        try:
            result = diagnose_episode(daily, tempo, days, atypical - set(days))
        except ValueError as error:
            weeks.append({"start": a, "end": b, "error": str(error)})
            continue
        result = json.loads(json.dumps(result, default=str))
        result["ratios"] = {
            k: v if v is not None and np.isfinite(v) else None for k, v in result["ratios"].items()
        }
        weeks.append({**result, "start": a, "end": b, "data": {"start": START, "end": END}})
    return weeks


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    events = known_events()
    events.assign(start=events["start"].dt.date, end=events["end"].dt.date).to_csv(
        OUT / "events.csv", index=False
    )
    weeks = bulletin()
    (OUT / "bulletin_2026-10.json").write_text(json.dumps(weeks, indent=2) + "\n")
    for w in weeks:
        print(w["start"], w.get("verdict", w.get("error")), w.get("notes"))
