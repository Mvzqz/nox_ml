import numpy as np
import pandas as pd
import pytest

from nox_ml.validation.placebo import daily_table
from nox_ml.validation.stagnation import ols, relative_index, ventilation_slope

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
