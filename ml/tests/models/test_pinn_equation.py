import numpy as np
import pytest

from nox_ml.models.pinn.equation import EPS, GAMMA_CHECKS, KAPPA_M, L_M, exact


def crosswind_integral(gamma: float, along: float, kappa: float = KAPPA_M) -> float:
    a, c, field = exact(gamma, kappa=kappa)
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


def test_the_default_diffusivity_is_the_research_one():
    assert KAPPA_M / L_M == EPS
    np.testing.assert_array_equal(exact(0.25)[2], exact(0.25, kappa=1500.0)[2])


@pytest.mark.parametrize("kappa", [500.0, 1500.0, 3000.0])
def test_the_exact_field_conserves_mass_for_any_diffusivity(kappa):
    """Without loss (gamma -> 0) every line across the wind downstream of the source carries the whole 1 g/s,
    however much the plume diffuses."""
    assert crosswind_integral(1e-9, 1.0, kappa) == pytest.approx(1.0, rel=0.01)
    assert crosswind_integral(1e-9, 3.0, kappa) == pytest.approx(1.0, rel=0.01)


@pytest.mark.parametrize("kappa", [500.0, 3000.0])
def test_the_crosswind_integral_follows_the_decay_of_the_equation_for_any_diffusivity(kappa):
    eps, gamma = kappa / L_M, 0.25
    root = np.sqrt(1 + 4 * eps * gamma)
    r = (1 - root) / (2 * eps)

    assert crosswind_integral(gamma, 2.0, kappa) == pytest.approx(np.exp(2 * r) / root, rel=0.01)


def test_a_larger_diffusivity_widens_the_plume_and_lowers_its_centerline():
    widths, centers = [], []
    for kappa in (500.0, 1500.0, 3000.0):
        a, c, field = exact(0.1, kappa=kappa)
        row = field[np.argmin(np.abs(a - 2.0))]
        widths.append(np.sqrt((row * c**2).sum() / row.sum()))
        centers.append(row.max())

    assert widths == sorted(widths) and centers == sorted(centers, reverse=True)
