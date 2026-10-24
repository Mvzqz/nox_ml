import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

from nox_ml.inversion.linear import (
    BACKGROUND_STATION,
    SIGMA_STATION,
    background_mean,
    hour_systems,
    invert,
    solve,
)

N_REGIONS = 2


def systems_of(inputs):
    return hour_systems(inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)


def test_an_hour_with_weight_two_counts_as_the_hour_repeated(make_inputs):
    inputs = make_inputs()
    weights = [2.0 if k % 5 == 0 else 1.0 for k in range(len(inputs.hours))]
    repeated = [h for h, w in zip(inputs.hours, weights, strict=True) for _ in range(int(w))]

    weighted = solve(systems_of(inputs), inputs.points, N_REGIONS, weights)
    expected = invert(repeated, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)

    assert_allclose(weighted.mean, expected.mean, rtol=1e-9)
    assert_allclose(weighted.cov, expected.cov, rtol=1e-9)


def test_an_hour_with_weight_zero_is_left_out(make_inputs):
    inputs = make_inputs()
    weights = [0.0 if k < 6 else 1.0 for k in range(len(inputs.hours))]

    weighted = solve(systems_of(inputs), inputs.points, N_REGIONS, weights)
    expected = invert(inputs.hours[6:], inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)

    assert_allclose(weighted.mean, expected.mean, rtol=1e-9)


def test_hour_systems_remember_the_local_day_and_the_day_type(make_inputs):
    systems = systems_of(make_inputs())

    assert systems[0].day == pd.Timestamp("2023-11-06")  # a Monday
    assert [s.kind for s in systems[:1]] == [0]
    assert {s.kind for s in systems if s.day == pd.Timestamp("2023-11-11")} == {1}  # Saturday
    assert {s.kind for s in systems if s.day == pd.Timestamp("2023-11-12")} == {2}  # Sunday


def test_background_mean_matches_the_background_unknown_of_the_joint_solution():
    """Solve for the sources and the background together (the research way); the background mean equals
    `background_mean` of the residuals of the sources found."""
    rng = np.random.default_rng(1)
    n, p = 9, 2
    k, y = rng.normal(size=(n, p)), 20 + rng.normal(size=n)
    prior_mean, prior_sd = np.array([1.0, 2.0]), np.array([0.5, 0.8])
    mean_b, sd_b = BACKGROUND_STATION
    design = np.c_[k, np.ones(n)]
    precision = np.diag(1 / np.r_[prior_sd, sd_b] ** 2) + design.T @ design / SIGMA_STATION**2
    rhs = np.r_[prior_mean / prior_sd**2, mean_b / sd_b**2] + design.T @ y / SIGMA_STATION**2
    joint = np.linalg.solve(precision, rhs)

    b = background_mean(y - k @ joint[:p], SIGMA_STATION, BACKGROUND_STATION)

    assert b == pytest.approx(joint[p])


def test_background_mean_without_rows_is_the_prior_mean():
    assert background_mean(np.zeros(0), SIGMA_STATION, BACKGROUND_STATION) == BACKGROUND_STATION[0]


def test_state_has_the_points_and_the_road_factors_of_the_day_type(make_inputs):
    inputs = make_inputs()
    post = invert(inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)

    assert_allclose(post.state(2), np.r_[post.mean[0], post.road_factors()[2]])
    assert len(post.state(0)) == 1 + N_REGIONS
