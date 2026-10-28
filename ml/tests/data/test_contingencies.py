"""The 2024 contingency episodes and the days they put in force."""

import pandas as pd
import pytest

from nox_ml.data import contingencies

HEADER = "episodio,activacion_fecha,activacion_hora,suspension_fecha,suspension_hora,fuente\n"
# the 11 episodes of data/raw/contingencias/contingencias_ozono_2024_episodios.csv, without sources
EPISODES_2024 = [
    ("2024-02-22", "2024-02-25"),
    ("2024-03-06", "2024-03-07"),
    ("2024-03-23", "2024-03-24"),
    ("2024-04-30", "2024-05-01"),
    ("2024-05-03", "2024-05-04"),
    ("2024-05-09", "2024-05-10"),
    ("2024-05-13", "2024-05-16"),
    ("2024-05-18", "2024-05-19"),
    ("2024-05-22", "2024-05-24"),
    ("2024-05-25", "2024-05-26"),
    ("2024-05-30", "2024-05-31"),
]


def write(tmp_path, rows):
    path = tmp_path / "episodes.csv"
    lines = [f"{i},{a},,{s},,test" for i, (a, s) in enumerate(rows, 1)]
    path.write_text(HEADER + "\n".join(lines) + "\n")
    return path


def test_measure_days_run_from_the_day_after_the_activation_to_the_suspension_inclusive(tmp_path):
    episodes = contingencies.read_episodes(write(tmp_path, EPISODES_2024))

    measures = contingencies.measure_days(episodes)

    assert len(episodes) == 11 and len(measures) == 16
    assert measures[:4].strftime("%m-%d").tolist() == ["02-23", "02-24", "02-25", "03-07"]
    assert pd.Timestamp("2024-05-14") in measures and pd.Timestamp("2024-05-16") in measures
    assert not measures.isin(contingencies.activation_days(episodes)).any()


def test_active_days_add_the_activation_days_to_the_measure_days(tmp_path):
    episodes = contingencies.read_episodes(write(tmp_path, EPISODES_2024))

    active = contingencies.active_days(episodes)

    assert len(active) == 16 + 11
    assert active.is_monotonic_increasing and pd.Timestamp("2024-02-22") in active


def test_an_episode_suspended_on_its_activation_day_has_no_measure_day(tmp_path):
    episodes = contingencies.read_episodes(write(tmp_path, [("2024-03-06", "2024-03-06")]))

    assert len(contingencies.measure_days(episodes)) == 0
    assert list(contingencies.active_days(episodes)) == [pd.Timestamp("2024-03-06")]


def test_episodes_are_sorted_and_hours_may_be_missing(tmp_path):
    episodes = contingencies.read_episodes(write(tmp_path, EPISODES_2024[::-1]))

    assert episodes["activation"].is_monotonic_increasing


@pytest.mark.parametrize(
    "rows, message",
    [
        ([("2024-03-07", "2024-03-06")], "precedes"),
        ([("2024-03-06", "2024-03-10"), ("2024-03-10", "2024-03-12")], "overlap"),
    ],
)
def test_inconsistent_episodes_are_refused(tmp_path, rows, message):
    with pytest.raises(ValueError, match=message):
        contingencies.read_episodes(write(tmp_path, rows))


def test_a_file_without_the_episode_columns_is_refused(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("fecha\n2024-03-06\n")

    with pytest.raises(ValueError, match="lacks columns"):
        contingencies.read_episodes(path)
