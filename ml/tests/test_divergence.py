# pyright: reportArgumentType=false
"""The flux divergence of TEMPO columns: the city emission of a scan and the day-type ratios of the days."""

import numpy as np
import pandas as pd
import pytest

from nox_ml.inversion.jacobian import Receptors
from nox_ml.inversion.linear import HourData
from nox_ml.validation import divergence

CELL = divergence.CELL_M


def scan(column, wind=(2.0, 0.0), n=12, per_cell=3):
    """An hour whose pixels fill an n x n grid of cells, `per_cell` pixels per cell, with the column
    `column(x, y)` (molecules/cm2)."""
    centers = (np.arange(n) + 0.5) * CELL
    x, y = (a.ravel() for a in np.meshgrid(centers, centers))
    x, y = np.repeat(x, per_cell), np.repeat(y, per_cell)
    empty = Receptors(np.zeros(0), np.zeros(0))
    return HourData(
        pd.Timestamp("2023-11-06 19:00"), wind, 1000.0, empty, np.zeros(0), Receptors(x, y), column(x, y)
    )


def test_a_uniform_column_in_a_uniform_wind_emits_nothing():
    hour = scan(lambda x, y: np.full_like(x, 4e15))

    result = divergence.scan_emission(hour, divergence.Grid.over([hour]), 1.0, (np.inf,))

    assert result is not None
    assert result["tau_infh"] == pytest.approx(0.0, abs=1e-6)


def test_a_column_that_grows_downwind_emits_wind_times_slope_in_every_cell():
    slope = 1e15 / CELL  # molecules/cm2 per m
    hour = scan(lambda x, y: 1e15 + slope * x, wind=(3.0, 0.0))
    grid = divergence.Grid.over([hour])

    result = divergence.scan_emission(hour, grid, 1.0, (np.inf,))

    interior = (grid.nx - 2) * (grid.ny - 2)
    per_cell = 3.0 * slope  # u (m/s) times the slope (molecules/cm2 per m)
    assert result is not None
    assert result["tau_infh"] == pytest.approx(per_cell * interior, rel=1e-6)


def test_a_scan_that_covers_little_of_the_city_is_left_out():
    hour = scan(lambda x, y: np.full_like(x, 4e15))
    grid = divergence.Grid.over([hour])
    sparse = HourData(hour.hour, hour.wind, hour.pbl, hour.stations, hour.nox,
                      Receptors(hour.pixels.x[:20], hour.pixels.y[:20]), hour.no2[:20])  # fmt: skip

    assert divergence.scan_emission(sparse, grid, 1.0) is None


def test_sundays_at_half_the_weekday_emission_give_a_ratio_of_one_half():
    days = pd.date_range("2023-11-06", periods=21)
    kinds = np.where(days.day_of_week == 6, 2, np.where(days.day_of_week == 5, 1, 0))
    emission = np.where(kinds == 2, 5.0, 10.0) * np.random.default_rng(0).uniform(0.99, 1.01, len(days))
    daily = pd.DataFrame({"tau_2h": emission, "kind": kinds}, index=days)

    ratios = divergence.day_type_ratios(daily, n_boot=200)

    sunday = ratios["tau_2h"]["sunday"]
    assert sunday["ratio"] == pytest.approx(0.5, abs=0.01)
    assert sunday["lo"] < sunday["ratio"] < sunday["hi"]
    assert sunday["n_days"] == 3 and ratios["tau_2h"]["n_weekdays"] == 15


def test_the_placebo_of_a_steady_series_is_centered_on_one_and_detects_its_noise():
    days = pd.date_range("2023-11-06", periods=60)
    daily = pd.Series(np.random.default_rng(1).lognormal(np.log(10.0), 0.1, len(days)), index=days)

    result = divergence.placebo(daily, days[:50], draws=500)

    assert result["n_normal"] == 50
    nine = next(r for r in result["rows"] if r["days"] == 9)
    assert nine["center"] == pytest.approx(1.0, abs=0.02)
    assert nine["lo"] < 1 < nine["hi"]
    assert result["cv"] == pytest.approx(0.1, rel=0.3)
    assert 0 < nine["mdc"] < 0.25
