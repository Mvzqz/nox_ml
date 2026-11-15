# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Ozone contingency episodes and the days they put in force.

``contingencias_ozono_<year>_episodios.csv`` (one file per year; `read_all` reads every one in the folder,
and a year without file is not covered, see `covers`) has one row per episode, with the local date (and, when
the press reported it, the hour) of the activation and of the suspension. Only the dates are used: the
activation is announced around 15:00 and the "Doble Hoy No Circula" starts at 05:00 the next day, so

- the **measure days** run from the day after the activation to the day of the suspension, inclusive
  (the suspension is usually at 15:00, but the morning of that day is still under the restrictions);
- the **activation day** has almost no restrictions in the 12-17 h window the models use, so it belongs to
  neither the contingency group nor the reference group;
- the **active days** are the activation day plus the measure days (the sensitivity analysis).

Days are naive local midnights, like the daily tables.
"""

from pathlib import Path

import pandas as pd

EPISODES_DIR = Path("contingencias")
EPISODES_PATTERN = "contingencias_ozono_{year}_episodios.csv"
EPISODES_FILE = EPISODES_DIR / EPISODES_PATTERN.format(year=2024)
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
    return _checked(episodes, path)


def _checked(episodes: pd.DataFrame, source: object) -> pd.DataFrame:
    if (episodes["suspension"] < episodes["activation"]).any():
        raise ValueError(f"{source}: a suspension precedes its activation")
    if (episodes["activation"].iloc[1:].to_numpy() <= episodes["suspension"].iloc[:-1].to_numpy()).any():
        raise ValueError(f"{source}: episodes overlap")
    return episodes


def read_all(directory: Path) -> pd.DataFrame:
    """The episodes of every ``contingencias_ozono_*_episodios.csv`` in `directory`, concatenated and checked
    like `read_episodes` (across files too). Empty, with the same columns, when there is no file."""
    files = sorted(directory.glob(EPISODES_PATTERN.format(year="*")))
    if not files:
        return pd.DataFrame(
            {
                "episode": pd.Series(dtype=int),
                "activation": pd.to_datetime([]),
                "suspension": pd.to_datetime([]),
            }
        )
    episodes = pd.concat([read_episodes(f) for f in files]).sort_values("activation", ignore_index=True)
    return _checked(episodes, directory)


def covers(directory: Path, start: str, end: str) -> bool:
    """Whether every year of the window `start`..`end` has its episodes file: a year without one is unknown,
    not a year without contingencies."""
    years = range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1)
    return all((directory / EPISODES_PATTERN.format(year=year)).exists() for year in years)


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
