import numpy as np
import pytest

from nox_ml.models.pinn.equation import EPS, GAMMA_CHECKS, exact


def crosswind_integral(gamma: float, along: float) -> float:
    a, c, field = exact(gamma)
    row = field[np.argmin(np.abs(a - along))]
    return float(row.sum() * (c[1] - c[0]))


@pytest.mark.parametrize("gamma", GAMMA_CHECKS)
def test_the_crosswind_integral_is_the_one_dimensional_decay_of_the_equation(gamma):
    """Integrating across the wind leaves F_A - eps F_AA + gamma F = delta(A): for A > 0 the integral is
    exp(r A) / sqrt(1 + 4 eps gamma) with r the negative root of eps r^2 - r - gamma = 0."""
    root = np.sqrt(1 + 4 * EPS * gamma)
    r = (1 - root) / (2 * EPS)

    assert crosswind_integral(gamma, 1.0) == pytest.approx(np.exp(r) / root, rel=0.01)
    assert crosswind_integral(gamma, 2.0) == pytest.approx(np.exp(2 * r) / root, rel=0.01)


def test_the_exact_field_is_positive_and_symmetric_across_the_wind():
    _, c, field = exact(0.25)

    assert (field > 0).all()
    np.testing.assert_allclose(field, field[:, ::-1], rtol=1e-9, atol=1e-12)
    assert c[0] == pytest.approx(-c[-1])


def test_a_shorter_lifetime_leaves_less_downwind():
    _, _, long_lived = exact(0.04)
    _, _, short_lived = exact(0.6)

    assert crosswind_integral(0.6, 2.0) < crosswind_integral(0.04, 2.0)
    assert short_lived.sum() < long_lived.sum()
