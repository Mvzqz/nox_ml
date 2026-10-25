"""Shared fixtures: small synthetic hourly series with a known emission change."""

from collections.abc import Callable

import numpy as np
import pandas as pd
import pytest
from hypothesis import settings

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.jacobian import Receptors
from nox_ml.inversion.linear import HourData

# No per-example time limit: run time depends on the machine (CI, laptops, cloud sessions), and a
# deadline only makes property tests fail at random without finding a bug.
settings.register_profile("nox", deadline=None)
settings.load_profile("nox")

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


STATIONS = {"AAA": (0.0, 0.0), "BBB": (6000.0, 1000.0), "CCC": (2000.0, 7000.0)}


def small_inputs(sunday_scale: float = 1.0, seed: int = 0) -> Inputs:
    """Two weeks (2023-11-06 to 11-19, local 12-17 h) at three stations, one point source and six road
    cells in two regions. NOx is noise around 30 ppb, times ``sunday_scale`` on Sundays."""
    rng = np.random.default_rng(seed)
    zones = pd.DataFrame(
        {
            "x": [-3000.0, 0.0, 3000.0, 6000.0, 1000.0, 4000.0],
            "y": [-1000.0, 2000.0, 5000.0, 1000.0, 8000.0, -2000.0],
            "weight": [400.0, 300.0, 200.0, 300.0, 100.0, 200.0],
            "region": [0, 0, 0, 1, 1, 1],
        }
    )
    points = pd.DataFrame({"name": ["P0"], "x": [8000.0], "y": [4000.0], "prior": [100.0], "sd": [100.0]})
    xy = pd.DataFrame(STATIONS, index=["x", "y"]).T
    hours, ids = [], []
    for day in pd.date_range("2023-11-06", periods=14):
        for utc_hour in range(18, 24):  # 12-17 h local
            wind = (float(rng.uniform(-3, 3)), float(rng.uniform(-3, 3)))
            scale = sunday_scale if day.day_of_week == 6 else 1.0
            n = len(STATIONS)
            hours.append(
                HourData(
                    hour=day + pd.Timedelta(hours=utc_hour),
                    wind=wind,
                    pbl=800.0,
                    stations=Receptors(xy["x"].to_numpy(), xy["y"].to_numpy()),
                    nox=scale * (30 + 5 * rng.normal(size=n)),
                    pixels=Receptors(np.array([1000.0, 5000.0]), np.array([2000.0, 3000.0])),
                    no2=scale * (8e15 + 1e15 * rng.normal(size=2)),
                )
            )
            ids.append(np.array(list(STATIONS)))
    return Inputs(hours, ids, xy, zones, points, 0.7, n_regions=2)


@pytest.fixture
def make_inputs() -> Callable[..., Inputs]:
    return small_inputs
