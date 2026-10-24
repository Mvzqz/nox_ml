from typing import cast

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.testing import assert_allclose

from nox_ml.physics.plume import U_MIN
from nox_ml.physics.puff import (
    TRAFFIC_PROFILE,
    Trajectories,
    cumulative_loss,
    fixed_lifetime,
    puffs,
    road_profile,
    variable_lifetime,
)

T0 = cast(pd.Timestamp, pd.Timestamp("2024-03-01 00:00"))
PBL = 1100.0
SOURCE = (np.array([0.0]), np.array([0.0]))


def _wind(u, v, hours: int = 30) -> pd.DataFrame:
    idx = pd.date_range(T0, periods=hours, freq="h")
    return pd.DataFrame({"u": np.broadcast_to(u, hours), "v": np.broadcast_to(v, hours)}, index=idx)


def _field(traj, xr, yr, t_target, *, xs=SOURCE[0], ys=SOURCE[1], weights=lambda _t: 1.0, **kwargs):
    return puffs(
        xs, ys, np.asarray(xr, float), np.asarray(yr, float), traj, t_target, PBL, weights, 0.0, **kwargs
    )


# --- puffs do not move without wind ---------------------------------------------------------------------


@given(t_from=st.floats(0, 10), span=st.floats(0, 15))
def test_puffs_do_not_move_without_wind(t_from, span):
    traj = Trajectories.from_wind(_wind(0.0, 0.0))
    dx, dy, distance = traj.between(t_from, t_from + span)
    assert dx == 0.0 and dy == 0.0
    assert_allclose(
        distance, U_MIN * 3600 * span, rtol=1e-9, atol=1e-6
    )  # they still spread, at the floor speed


@given(radius=st.floats(100, 20_000), angle=st.floats(0, 2 * np.pi), other=st.floats(0, 2 * np.pi))
def test_puff_field_without_wind_is_symmetric_around_the_source(radius, angle, other):
    traj = Trajectories.from_wind(_wind(0.0, 0.0))
    xr = radius * np.cos([angle, other])
    yr = radius * np.sin([angle, other])
    g, c = _field(traj, xr, yr, 20.5, max_age_h=3)
    assert_allclose(g[0], g[1], rtol=1e-9)
    assert_allclose(c[0], c[1], rtol=1e-9)


@given(near=st.floats(0, 20_000), far=st.floats(0, 20_000), angle=st.floats(0, 2 * np.pi))
def test_puff_field_without_wind_peaks_at_the_source(near, far, angle):
    traj = Trajectories.from_wind(_wind(0.0, 0.0))
    near, far = sorted((near, far))
    xr, yr = np.array([near, far]) * np.cos(angle), np.array([near, far]) * np.sin(angle)
    _, c = _field(traj, xr, yr, 20.5, max_age_h=3)
    assert c[0, 0] >= c[1, 0]


@given(u=st.floats(-8, 8), v=st.floats(-8, 8), hours=st.integers(2, 10))
def test_puffs_move_with_the_wind_of_the_domain(u, v, hours):
    traj = Trajectories.from_wind(_wind(u, v))
    dx, dy, distance = traj.between(5.0, 5.0 + hours)
    assert_allclose([dx, dy], [u * 3600 * hours, v * 3600 * hours], atol=1e-6)
    assert distance >= np.hypot(dx, dy) - 1e-6  # the floor can only lengthen the path


# --- the wind floor -------------------------------------------------------------------------------------


@given(u=st.floats(-1.4, 1.4), v=st.floats(-1.4, 1.4))
def test_distance_travelled_per_hour_respects_the_wind_floor(u, v):
    traj = Trajectories.from_wind(_wind(u, v))
    assert np.all(np.diff(traj.cs) >= U_MIN * 3600 - 1e-6)


# --- mass conservation and linearity --------------------------------------------------------------------

GRID = np.arange(-240e3, 240e3, 4_000.0)
GX, GY = (a.ravel() for a in np.meshgrid(GRID, GRID))
CELL_AREA = 4_000.0**2


@given(
    u=st.floats(-3, 3),
    v=st.floats(-3, 3),
    max_age_h=st.integers(1, 2),
    source=st.tuples(st.floats(-5e3, 5e3), st.floats(-5e3, 5e3)),
)
@settings(max_examples=25, deadline=None)
def test_puffs_conserve_mass_without_chemistry(u, v, max_age_h, source):
    traj = Trajectories.from_wind(_wind(u, v))
    _, c = _field(
        traj,
        GX,
        GY,
        6.5,
        xs=np.array([source[0]]),
        ys=np.array([source[1]]),
        survival=fixed_lifetime(np.inf),
        max_age_h=max_age_h,
    )
    assert_allclose(c.sum() * CELL_AREA, max_age_h * 3600.0, rtol=1e-4)  # g released at 1 g/s


@given(tau_h=st.floats(1, 48), u=st.floats(-3, 3), v=st.floats(-3, 3))
@settings(max_examples=15, deadline=None)
def test_puff_mass_lost_is_what_the_chemistry_removes(tau_h, u, v):
    traj = Trajectories.from_wind(_wind(u, v))
    _, c = _field(traj, GX, GY, 6.5, survival=fixed_lifetime(tau_h), max_age_h=2)
    ages = 1 + (np.arange(2 * 4) + 0.5) / 4
    assert_allclose(c.sum() * CELL_AREA, (900.0 * np.exp(-ages / tau_h)).sum(), rtol=1e-4)


@given(
    emission=st.floats(0, 1e3),
    other=st.floats(0, 1e3),
    u=st.floats(-6, 6),
    v=st.floats(-6, 6),
    tau_h=st.floats(1, 48),
)
@settings(max_examples=30, deadline=None)
def test_puff_concentration_is_linear_in_emission(emission, other, u, v, tau_h):
    traj = Trajectories.from_wind(_wind(u, v))
    xr, yr = np.array([-4_000.0, 2_000.0, 9_000.0]), np.array([1_000.0, -6_000.0, 3_000.0])
    options = {"survival": fixed_lifetime(tau_h), "max_age_h": 3}
    unit = _field(traj, xr, yr, 20.5, **options)
    first = _field(traj, xr, yr, 20.5, weights=lambda _t: emission, **options)
    both = _field(traj, xr, yr, 20.5, weights=lambda _t: emission + other, **options)
    second = _field(traj, xr, yr, 20.5, weights=lambda _t: other, **options)
    for i in range(2):
        assert_allclose(first[i], emission * unit[i], rtol=1e-9, atol=1e-30)
        assert_allclose(both[i], first[i] + second[i], rtol=1e-9, atol=1e-30)


@given(u=st.floats(-6, 6), v=st.floats(-6, 6))
@settings(max_examples=20, deadline=None)
def test_puff_sources_contribute_independently(u, v):
    traj = Trajectories.from_wind(_wind(u, v))
    xs, ys = np.array([-3e3, 1e3, 8e3]), np.array([2e3, -4e3, 0.0])
    xr, yr = np.array([0.0, 5e3]), np.array([0.0, -2e3])
    g_all, _ = _field(traj, xr, yr, 20.5, xs=xs, ys=ys, max_age_h=3)
    for j in range(3):
        g_one, _ = _field(traj, xr, yr, 20.5, xs=xs[[j]], ys=ys[[j]], max_age_h=3)
        assert_allclose(g_all[:, j], g_one[:, 0], rtol=1e-9)


def test_mixing_in_the_boundary_layer_limits_the_ground_level_concentration():
    traj = Trajectories.from_wind(_wind(3.0, 0.0))
    g, c = _field(traj, [20e3], [0.0], 20.5, max_age_h=6)
    low = puffs(
        *SOURCE, np.array([20e3]), np.array([0.0]), traj, 20.5, 200.0, lambda _t: 1.0, 0.0, max_age_h=6
    )[0]
    assert low[0, 0] > g[0, 0]
    assert c[0, 0] > 0


def test_puffs_reproduce_the_research_reference_value():
    # Value from scripts/puff.py (research-archive): 3 m/s from the west, receiver 30 km downwind, 6 h of
    # history, boundary layer 1,000 m.
    traj = Trajectories.from_wind(_wind(3.0, 0.0))
    g, c = puffs(
        *SOURCE, np.array([30e3]), np.array([0.0]), traj, 25.5, 1_000.0, lambda _t: 1.0, 0.0, max_age_h=6
    )
    assert_allclose(g[0, 0], 3.68898031e-09, rtol=1e-7)
    assert_allclose(c[0, 0], 3.68898031e-06, rtol=1e-7)


# --- trajectories, chemistry and profile ----------------------------------------------------------------


def test_short_wind_gaps_are_interpolated_and_long_ones_are_calm():
    wind = _wind(6.0, 0.0, hours=8).drop(_wind(6.0, 0.0, hours=8).index[1:6])  # five missing hours
    steps = np.diff(Trajectories.from_wind(wind).cx) / 3600
    assert_allclose(steps, [6.0, 6.0, 6.0, 6.0, 0.0, 0.0, 6.0, 6.0], atol=1e-9)  # 3 interpolated, then calm


def test_times_are_measured_in_hours_from_the_first_wind():
    traj = Trajectories.from_wind(_wind(1.0, 1.0))
    assert traj.t(cast(pd.Timestamp, T0 + pd.Timedelta(hours=7, minutes=30))) == 7.5


@given(tau_h=st.floats(0.5, 100), age=st.floats(0, 100))
def test_fixed_lifetime_decays_exponentially(tau_h, age):
    surviving = fixed_lifetime(tau_h)(0.0, age, age)
    assert 0 < surviving <= 1
    assert_allclose(surviving, np.exp(-age / tau_h))


@given(k=st.floats(0, 1e-3), t_rel=st.floats(0, 20), age=st.floats(0, 20))
def test_variable_lifetime_with_constant_loss_matches_exponential_decay(k, t_rel, age):
    traj = Trajectories.from_wind(_wind(1.0, 0.0, hours=48))
    loss = pd.Series(k, index=pd.date_range(T0 - pd.Timedelta(hours=5), periods=60, freq="h"))
    surviving = variable_lifetime(cumulative_loss(loss, traj))(t_rel, t_rel + age, age)
    assert_allclose(surviving, np.exp(-k * 3600 * age), rtol=1e-9)


def test_cumulative_loss_without_data_means_no_loss():
    traj = Trajectories.from_wind(_wind(1.0, 0.0, hours=10))
    lam = cumulative_loss(pd.Series(dtype=float), traj)
    assert not lam.any()
    assert variable_lifetime(lam)(1.0, 8.0, 7.0) == 1.0


def test_road_profile_uses_local_hours_and_is_one_outside_the_profile():
    traj = Trajectories.from_wind(_wind(1.0, 0.0))
    weight = road_profile(traj)
    assert weight(14.2) == TRAFFIC_PROFILE[8]  # 14:00 UTC is 08:00 local
    assert weight(5.0) == 1.0  # 05:00 UTC is 23:00 local
    assert road_profile(traj, profile={8: 2.0})(14.0) == 2.0
