import numpy as np
import pandas as pd
import pytest

from nox_ml.validation.placebo import daily_table, placebo
from nox_ml.validation.stagnation import (
    geometric_mean,
    index_by_quartile,
    ols,
    poorly_ventilated_mask,
    relative_index,
    stagnant_index,
    ventilation_quartile,
    ventilation_slope,
)

DAYS = [pd.Timestamp("2024-03-12") + pd.Timedelta(days=7 * k) for k in range(8)]  # all Tuesdays


def daily(make_hourly, power=1.0):
    """Daily table with observations ``model ** power``; power 1 means the model gets the weather right."""
    hourly = make_hourly(noise=0.0, seed=5)
    hourly["obs"] = hourly.model**power
    return daily_table(hourly)


def test_relative_index_is_one_when_observations_equal_the_model(make_hourly):
    d = daily(make_hourly)

    rel = relative_index(d, DAYS, set(DAYS))

    assert len(rel) == len(DAYS)
    np.testing.assert_allclose(rel.to_numpy(), 1.0)


def test_relative_index_skips_days_without_references(make_hourly):
    d = daily(make_hourly)

    assert relative_index(d, DAYS, excluded=set(d.index)).empty


def test_ols_recovers_exact_coefficients_with_a_perfect_fit():
    x = pd.DataFrame({"a": np.arange(10.0), "b": np.arange(10.0) ** 2})
    y = 2.0 + 3.0 * x.a - 0.5 * x.b

    beta, t, r2 = ols(y + np.sin(np.arange(10.0)) * 1e-9, x)

    assert beta["const"] == pytest.approx(2.0)
    assert beta["a"] == pytest.approx(3.0)
    assert beta["b"] == pytest.approx(-0.5)
    assert r2 == pytest.approx(1.0)
    assert abs(t["a"]) > 1e3


def test_ventilation_slope_is_zero_when_the_model_gets_the_weather_right(make_hourly):
    d = daily(make_hourly, power=1.0)

    slope, _, n = ventilation_slope(d, DAYS, set(DAYS))

    assert slope == pytest.approx(0.0, abs=1e-9)
    assert n == len(DAYS)


def test_ventilation_slope_detects_a_model_that_misjudges_the_weather(make_hourly):
    # observations respond 1.5x as strongly to stagnation as the model says: log(index) grows with it
    d = daily(make_hourly, power=1.5)

    slope, t, _ = ventilation_slope(d, DAYS, set(DAYS))

    assert slope == pytest.approx(0.5, abs=0.15)
    assert t > 3


def test_ventilation_quartile_puts_the_most_stagnant_days_in_zero():
    ventilation = pd.Series(np.arange(1.0, 41.0), index=pd.date_range("2024-03-01", periods=40))

    q = ventilation_quartile(ventilation)

    assert q.value_counts().to_dict() == {0: 10, 1: 10, 2: 10, 3: 10}
    assert (q.iloc[:10] == 0).all()
    assert (q.iloc[-10:] == 3).all()


def test_geometric_mean_is_the_exponential_of_the_mean_log():
    assert geometric_mean([0.5, 2.0]) == pytest.approx(1.0)
    assert geometric_mean(pd.Series([2.0, 8.0])) == pytest.approx(4.0)


def test_index_by_quartile_is_one_everywhere_when_observations_equal_the_model(make_hourly):
    d = daily(make_hourly)
    rel = relative_index(d, list(d.index), excluded=set())
    quartile = ventilation_quartile(1 / d.stagnation)

    np.testing.assert_allclose(index_by_quartile(rel, quartile), 1.0)


def test_index_by_quartile_shows_a_model_that_misjudges_stagnant_days(make_hourly):
    # observations respond 1.5x as strongly to stagnation as the model says: stagnant days read above 1
    d = daily(make_hourly, power=1.5)
    rel = relative_index(d, list(d.index), excluded=set())
    quartile = ventilation_quartile(1 / d.stagnation)

    by_quartile = index_by_quartile(rel, quartile)

    assert by_quartile[0] > 1.1 > 0.9 > by_quartile[3]
    assert by_quartile == sorted(by_quartile, reverse=True)


def test_stagnant_index_counts_the_days_of_the_most_stagnant_quartile(make_hourly):
    d = daily(make_hourly)
    rel = relative_index(d, list(d.index), excluded=set())
    quartile = ventilation_quartile(1 / d.stagnation)

    index, _, n = stagnant_index(rel, quartile, n_boot=10)

    assert n == (quartile.reindex(rel.index) == 0).sum()
    assert index == pytest.approx(1.0)


def test_stagnant_index_interval_brackets_the_estimate(make_hourly):
    d = daily(make_hourly, power=1.5)
    rel = relative_index(d, list(d.index), excluded=set())
    quartile = ventilation_quartile(1 / d.stagnation)

    index, (low, high), _ = stagnant_index(rel, quartile)

    assert low < index < high


def test_poorly_ventilated_mask_keeps_days_at_least_as_stagnant_as_the_event_days(make_hourly):
    d = daily(make_hourly)
    events = list(d.stagnation.sort_values().index[-20:])  # the 20 most stagnant days

    mask = poorly_ventilated_mask(d, events)

    floor = d.loc[events, "stagnation"].quantile(0.25)
    assert (d.stagnation[mask] >= floor).all()
    assert (d.stagnation[~mask] < floor).all()
    assert set(events[5:]) <= set(d.index[mask])  # at most a quarter of the event days fall below the floor


def test_placebo_on_poorly_ventilated_days_is_centered_on_one(make_hourly):
    d = daily_table(make_hourly(n_days=240, noise=0.0, seed=5).assign(obs=lambda x: x.model))
    events = list(d.stagnation.sort_values().index[-60:][::7])  # 8 days among the 60 most stagnant

    samples = placebo(d, events, poorly_ventilated_mask(d, events), 100, np.random.default_rng(0))

    assert len(samples) > 50
    assert np.median(samples) == pytest.approx(1.0, abs=1e-9)
