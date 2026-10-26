"""E4's solver: log-normal MAP with an analytic gradient and a Laplace covariance."""

import numpy as np
import pytest
from scipy.optimize import approx_fprime

from nox_ml.inversion.lognormal import hessian, log_prior, map_estimate, objective

MEAN = np.array([300.0, 1.0, 1.0, 1.0])
SD = np.array([300.0, 0.5, 0.5, 0.5])


def term(truth: np.ndarray, seed: int = 0):
    rng = np.random.default_rng(seed)
    k = rng.normal(size=(40, len(truth)))
    info = k.T @ k
    return info, info @ truth


def test_analytic_gradient_matches_finite_differences():
    info, gradient = term(np.array([400.0, 1.4, 0.6, 1.1]))
    prior = log_prior(MEAN, SD)
    eta = prior.mu + np.array([0.3, -0.2, 0.1, 0.4])

    analytic = objective(eta, info, gradient, prior)[1]
    numeric = np.asarray(approx_fprime(eta, lambda e: objective(e, info, gradient, prior)[0], 1e-6))

    np.testing.assert_allclose(analytic, numeric, rtol=1e-5, atol=1e-4)


def test_hessian_matches_finite_differences_of_the_gradient():
    info, gradient = term(np.array([400.0, 1.4, 0.6, 1.1]))
    prior = log_prior(MEAN, SD)
    eta = prior.mu + np.array([0.3, -0.2, 0.1, 0.4])

    numeric = np.array(
        [approx_fprime(eta, lambda e, i=i: objective(e, info, gradient, prior)[1][i], 1e-6) for i in range(4)]
    )

    np.testing.assert_allclose(hessian(eta, info, gradient, prior), numeric, rtol=1e-4, atol=1e-3)


def test_the_prior_has_the_mean_and_sd_it_was_given():
    prior = log_prior(MEAN, SD)

    mean = np.exp(prior.mu + prior.s**2 / 2)
    sd = mean * np.sqrt(np.expm1(prior.s**2))

    np.testing.assert_allclose(mean, MEAN)
    np.testing.assert_allclose(sd, SD)


def test_noiseless_informative_data_recover_the_truth():
    truth = np.array([400.0, 1.4, 0.6, 1.1])
    info, gradient = term(truth)

    fit = map_estimate(info * 1e4, gradient * 1e4, MEAN, SD)

    assert fit.converged
    np.testing.assert_allclose(fit.x, truth, rtol=1e-3)


def test_a_very_strong_prior_returns_the_prior_assumption():
    info, gradient = term(np.array([400.0, 1.4, 0.6, 1.1]))

    fit = map_estimate(info, gradient, MEAN, SD, sd_mult=1e-5)

    np.testing.assert_allclose(fit.x, MEAN, rtol=1e-2)


def test_emissions_are_positive_even_when_the_data_ask_for_negative_ones():
    info, gradient = term(np.array([400.0, -3.0, 0.6, 1.1]))

    fit = map_estimate(info, gradient, MEAN, SD)

    assert (fit.x > 0).all()


def test_laplace_covariance_is_symmetric_positive_definite_and_shrinks_with_more_data():
    truth = np.array([400.0, 1.4, 0.6, 1.1])
    info, gradient = term(truth)

    few = map_estimate(info, gradient, MEAN, SD)
    many = map_estimate(info * 100, gradient * 100, MEAN, SD)

    for fit in (few, many):
        np.testing.assert_allclose(fit.cov_eta, fit.cov_eta.T)
        assert np.linalg.eigvalsh(fit.cov_eta).min() > 0
    assert np.diag(many.cov_x).sum() < np.diag(few.cov_x).sum()
    assert fit.cov_x == pytest.approx(fit.cov_eta * np.outer(fit.x, fit.x))
