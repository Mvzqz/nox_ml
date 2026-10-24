"""Shared fixtures: small synthetic hourly series with a known emission change."""

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest

HOURS = 6  # afternoon hours per day


def hourly_series(
    n_days: int = 120,
    emission: dict | None = None,
    model_scale: dict | None = None,
    noise: float = 0.03,
    seed: int = 0,
) -> pd.DataFrame:
    """Hourly ``obs`` and ``model`` from 2024-02-01 on.

    The model (NOx with fixed emission) is lognormal day to day, the weather. Observations are
    ``emission * model`` with multiplicative noise. ``emission`` and ``model_scale`` map a day (Timestamp)
    to a factor on the true emission and on the modeled ventilation; days not listed get 1.
    """
    rng = np.random.default_rng(seed)
    emission, model_scale = emission or {}, model_scale or {}
    rows = []
    for day in pd.date_range("2024-02-01", periods=n_days):
        daily = rng.lognormal(0, 0.3) * model_scale.get(day, 1.0)
        for hour in range(HOURS):
            model = daily * rng.lognormal(0, 0.1)
            obs = emission.get(day, 1.0) * model * rng.lognormal(0, noise)
            rows.append(
                {"h": day + pd.Timedelta(hours=6 + 12 + hour), "day": day, "obs": obs, "model": model}
            )
    return pd.DataFrame(rows)


@pytest.fixture
def make_hourly() -> Callable[..., pd.DataFrame]:
    return hourly_series
