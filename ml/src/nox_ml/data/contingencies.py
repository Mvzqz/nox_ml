# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Ozone contingency episodes of 2024 and the days they put in force.

``contingencias_ozono_2024_episodios.csv`` has one row per episode, with the local date (and, when the press
reported it, the hour) of the activation and of the suspension. Only the dates are used: the activation is
announced around 15:00 and the "Doble Hoy No Circula" starts at 05:00 the next day, so

- the **measure days** run from the day after the activation to the day of the suspension, inclusive
  (the suspension is usually at 15:00, but the morning of that day is still under the restrictions);
- the **activation day** has almost no restrictions in the 12-17 h window the models use, so it belongs to
  neither the contingency group nor the reference group;
- the **active days** are the activation day plus the measure days (the sensitivity analysis).

Days are naive local midnights, like the daily tables.
"""

from pathlib import Path

import pandas as pd

EPISODES_FILE = Path("contingencias") / "contingencias_ozono_2024_episodios.csv"
COLUMNS = ("episodio", "activacion_fecha", "suspension_fecha")


def read_episodes(path: Path) -> pd.DataFrame:
    """Episodes with columns ``episode``, ``activation`` and ``suspension`` (dates), sorted and checked.

    Raises ValueError if a column is missing, a suspension precedes its activation, or two episodes overlap.
    """
    raw = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"{path} lacks columns {missing}")
    episodes = pd.DataFrame(
        {
            "episode": raw["episodio"].astype(int),
            "activation": pd.to_datetime(raw["activacion_fecha"]),
            "suspension": pd.to_datetime(raw["suspension_fecha"]),
        }
    ).sort_values("activation", ignore_index=True)
    if (episodes["suspension"] < episodes["activation"]).any():
        raise ValueError(f"{path}: a suspension precedes its activation")
    if (episodes["activation"].iloc[1:].to_numpy() <= episodes["suspension"].iloc[:-1].to_numpy()).any():
        raise ValueError(f"{path}: episodes overlap")
    return episodes


def activation_days(episodes: pd.DataFrame) -> pd.DatetimeIndex:
    """Days of activation: left out of both groups of the analysis."""
    return pd.DatetimeIndex(episodes["activation"])


def measure_days(episodes: pd.DataFrame) -> pd.DatetimeIndex:
    """From the day after each activation to its suspension day, inclusive (none if both are the same day)."""
    days = [
        pd.date_range(row.activation + pd.Timedelta(days=1), row.suspension) for row in episodes.itertuples()
    ]
    return pd.DatetimeIndex(days[0].append(days[1:]) if days else [])


def active_days(episodes: pd.DataFrame) -> pd.DatetimeIndex:
    """Every day with an active contingency, the activation day included."""
    return activation_days(episodes).union(measure_days(episodes))
