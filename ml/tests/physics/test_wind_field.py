"""The wind field of the stations and the trajectories of each source in it."""

import numpy as np
import pandas as pd
import pytest

from nox_ml.physics.puff import Trajectories, WindField

HOURS = pd.date_range("2023-11-06 12:00", periods=4, freq="h")
XY = pd.DataFrame({"x": [0.0, 20_000.0], "y": [0.0, 0.0]}, index=["W", "E"])


def station_wind(u_west, u_east, v=0.0):
    columns = pd.MultiIndex.from_product([["u", "v"], ["W", "E"]])
    return pd.DataFrame([[u_west, u_east, v, v]] * len(HOURS), index=HOURS, columns=columns)


def test_at_a_station_the_field_is_its_wind_and_between_them_a_weighted_mean():
    field = WindField.from_stations(station_wind(1.0, 3.0), XY)

    u, v = field.at(np.array([0.0, 10_000.0, 20_000.0]), np.zeros(3))

    assert u.shape == (len(HOURS), 3)
    assert u[0] == pytest.approx([1.0, 2.0, 3.0], abs=0.01)
    assert np.allclose(v, 0.0)


def test_an_hour_without_a_station_uses_the_others_and_without_any_is_calm():
    wind = station_wind(1.0, 3.0)
    wind.loc[HOURS[1] :, [("u", "E"), ("v", "E")]] = np.nan  # the east station stops (no gap to fill)
    wind.loc[HOURS[3], :] = np.nan

    u, _ = WindField.from_stations(wind, XY).at(np.array([20_000.0]), np.zeros(1))

    assert u[1, 0] == pytest.approx(1.0)  # the east station is out: the west one speaks for it
    assert u[3, 0] == 0.0  # the last hour has no station: calm


def test_each_source_moves_with_its_own_wind_and_a_uniform_field_is_the_domain_trajectory():
    field = WindField.from_stations(station_wind(1.0, 3.0), XY)
    sources_x, sources_y = np.array([0.0, 20_000.0]), np.zeros(2)

    traj = Trajectories.from_field(field, sources_x, sources_y)
    dx, dy, _ = traj.between(0.0, 2.0)

    assert dx == pytest.approx([7200.0, 21600.0], rel=0.01)  # two hours at 1 and 3 m/s
    assert dy == pytest.approx([0.0, 0.0])
    uniform = Trajectories.from_field(
        WindField.from_stations(station_wind(2.0, 2.0), XY), sources_x, sources_y
    )
    domain = Trajectories.from_wind(pd.DataFrame({"u": 2.0, "v": 0.0}, index=HOURS))
    assert uniform.between(0.5, 2.5)[0] == pytest.approx(domain.between(0.5, 2.5)[0])
