"""E3's solver: non-negative ridge on a quadratic data term, normalised by the prior."""

import numpy as np
import pandas as pd
import pytest

from nox_ml.inversion.normal_equations import DayEquations
from nox_ml.inversion.regularized import bootstrap_regularized, solve_regularized


def problem(truth: np.ndarray, seed: int = 0):
    """Noiseless data term of a well-conditioned linear model: its unconstrained minimum is `truth`."""
    rng = np.random.default_rng(seed)
    k = rng.normal(size=(40, len(truth)))
    info = k.T @ k
    return info, info @ truth


def test_without_penalty_noiseless_data_give_the_exact_emissions():
    truth = np.array([300.0, 1.2, 0.7, 1.5])
    info, gradient = problem(truth)

    x = solve_regularized(info, gradient, np.array([250.0, 1, 1, 1]), alpha=0)

    np.testing.assert_allclose(x, truth, rtol=1e-8)


def test_without_penalty_it_is_ordinary_least_squares_when_that_is_positive():
    rng = np.random.default_rng(1)
    k = rng.uniform(0.5, 1.5, size=(30, 3))
    y = k @ [2.0, 1.0, 3.0] + rng.normal(0, 0.1, 30)
    ols = np.linalg.lstsq(k, y, rcond=None)[0]
    assert (ols > 0).all()

    x = solve_regularized(k.T @ k, k.T @ y, np.ones(3), alpha=0)

    np.testing.assert_allclose(x, ols, rtol=1e-8)


@pytest.mark.parametrize("penalty", ["prior", "zero"])
def test_emissions_are_never_negative_when_the_data_ask_for_negative_ones(penalty):
    info, gradient = problem(np.array([300.0, -0.8, 0.7, 1.5]))

    x = solve_regularized(info, gradient, np.array([250.0, 1, 1, 1]), alpha=0.01, penalty=penalty)

    assert (x >= 0).all()
    assert x[1] == 0


def test_a_very_strong_penalty_returns_the_prior_assumption():
    info, gradient = problem(np.array([300.0, 2.0, 0.2, 1.5]))
    scale = np.array([250.0, 1, 1, 1])

    x = solve_regularized(info, gradient, scale, alpha=1e8, penalty="prior")

    np.testing.assert_allclose(x, scale, rtol=1e-4)


def test_a_very_strong_zero_penalty_shrinks_everything_to_zero():
    info, gradient = problem(np.array([300.0, 2.0, 0.2, 1.5]))

    x = solve_regularized(info, gradient, np.array([250.0, 1, 1, 1]), alpha=1e8, penalty="zero")

    assert (x / np.array([250.0, 1, 1, 1]) < 1e-2).all()


def test_a_parameter_the_data_do_not_see_stays_at_zero_without_penalty_and_at_the_prior_with_it():
    info, gradient = np.diag([4.0, 0.0]), np.array([4.0, 0.0])

    free = solve_regularized(info, gradient, np.ones(2), alpha=0)
    shrunk = solve_regularized(info, gradient, np.ones(2), alpha=0.5)

    assert free[0] == pytest.approx(1.0)
    assert shrunk[1] == pytest.approx(1.0)


def test_bootstrap_is_reproducible_and_one_row_per_replicate():
    truth = np.array([300.0, 1.2, 0.7, 1.5])
    info, gradient = problem(truth)
    days = DayEquations(
        pd.date_range("2023-11-01", periods=5),
        np.repeat(info[None] / 5, 5, axis=0),
        np.repeat(gradient[None] / 5, 5, axis=0),
    )
    zero = (np.zeros((4, 4)), np.zeros(4))
    args = (days, zero, np.array([250.0, 1, 1, 1]), 0.0, "prior", 6, 3)

    a, b = bootstrap_regularized(*args), bootstrap_regularized(*args)

    assert a.shape == (6, 4)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(
        a, truth * np.ones((6, 1)), rtol=1e-6
    )  # identical days: every draw is the truth
