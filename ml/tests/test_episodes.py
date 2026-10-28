"""Episode diagnosis: weather, emission or regional background, on daily tables with known causes."""

import json

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.validation import episodes
from nox_ml.validation.placebo import daily_table

DAYS = pd.date_range("2023-11-01", periods=84)
EPISODE = pd.date_range("2023-12-04", "2023-12-08")  # Monday to Friday


def table(weather=1.0, emission=1.0, background=1.0, urban=1.0, seed=0):
    """A daily table where the observed NOx is the modeled one (weather) times the emission and some noise,
    with the factors applied on the episode days, and the TEMPO background and urban parts of the days."""
    rng = np.random.default_rng(seed)
    model = rng.lognormal(np.log(30), 0.25, len(DAYS)) * 6
    obs = model * rng.lognormal(0, 0.08, len(DAYS))
    bg = rng.lognormal(np.log(2e15), 0.15, len(DAYS))
    city = rng.lognormal(np.log(6e15), 0.15, len(DAYS))
    on = DAYS.isin(EPISODE)
    obs[on] = model[on]  # no noise on the episode: the verdict sees only the imposed factors
    bg[on] = np.exp(np.log(bg[~on]).mean())
    city[on] = np.exp(np.log(city[~on]).mean()) * urban
    model[on] *= weather
    obs[on] *= weather * emission
    bg[on] *= background
    hourly = pd.DataFrame(
        {"day": DAYS.repeat(6), "obs": np.repeat(obs / 6, 6), "model": np.repeat(model / 6, 6)}
    )
    return daily_table(hourly), pd.DataFrame({"background": bg, "urban": city}, DAYS)


def diagnose(**factors):
    d, bg = table(**factors)
    return episodes.diagnose_episode(d, bg, EPISODE, n_fake=200)


@pytest.mark.parametrize(
    ("factors", "expected", "notes"),
    [
        ({}, "normal", []),
        ({"emission": 1.6}, "emission", []),
        ({"weather": 2.0}, "weather", []),
        ({"weather": 2.0, "emission": 1.5}, "both", []),
        ({"weather": 2.2, "emission": 0.65}, "weather", ["emission_against_weather"]),
        ({"emission": 1.6, "background": 2.0}, "accumulation", []),
        ({"emission": 1.6, "background": 2.0, "urban": 1.6}, "emission", ["background_up"]),
        ({"weather": 1.8, "emission": 1.6, "background": 2.0}, "emission_or_accumulation", []),
        ({"background": 2.0}, "accumulation", []),
    ],
)
def test_the_verdict_names_the_imposed_cause(factors, expected, notes):
    result = diagnose(**factors)

    assert (result["verdict"], result["notes"]) == (expected, notes)


def test_the_ratios_recover_the_factors_and_the_shares_add_up():
    result = diagnose(weather=1.5, emission=1.3)

    ratios = result["ratios"]
    assert ratios["weather"] == pytest.approx(1.5, rel=0.15)
    assert ratios["emission"] == pytest.approx(1.3, rel=0.1)
    assert ratios["concentration"] == pytest.approx(ratios["weather"] * ratios["emission"])
    assert result["shares"]["weather"] + result["shares"]["emission"] == pytest.approx(1.0)
    for name in episodes.RATIOS:
        assert result["null"][name]["lo"] < 1 < result["null"][name]["hi"]


def test_excluded_days_are_neither_references_nor_fake_days():
    d, bg = table(emission=1.6)
    wild = pd.date_range("2023-11-27", "2023-12-01")  # the week before: three times the NOx
    d.loc[wild, "obs"] *= 3

    calm = episodes.diagnose_episode(d, bg, EPISODE, excluded=wild, n_fake=100)

    assert calm["ratios"]["emission"] == pytest.approx(1.6, rel=0.1)


def test_an_episode_without_data_is_refused():
    d, bg = table()

    with pytest.raises(ValueError, match="no episode day"):
        episodes.diagnose_episode(d, bg, pd.date_range("2025-01-01", periods=3))


def test_the_command_writes_the_diagnosis(tmp_path, monkeypatch):
    asked = []

    def run(data_dir, start, end, days, seed):
        asked.append((start, end, len(days)))
        d, bg = table(emission=1.6)
        return {"data": {"start": start, "end": end}, **episodes.diagnose_episode(d, bg, EPISODE, n_fake=50)}

    monkeypatch.setattr(episodes, "run_episode", run)
    args = ["episode", "--days", "2023-12-04:2023-12-08", "--data", "2023-11-01:2023-12-31"]

    result = CliRunner().invoke(cli.app, [*args, "--runs-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert asked == [("2023-11-01", "2023-12-31", 5)]
    saved = json.loads((tmp_path / "episodes" / "2023-12-04_2023-12-08.json").read_text())
    assert saved["verdict"] == "emission" and "verdict: emission" in result.output
    assert CliRunner().invoke(cli.app, [*args[:3], "--data", "2023-11-01"]).exit_code == 2
