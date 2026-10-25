import json

import numpy as np
import pytest
import torch
from numpy.testing import assert_allclose, assert_array_equal
from pinn_kernel_fixture import reference_kernel

from nox_ml.models.pinn import cache as cache_module
from nox_ml.models.pinn.cache import KernelCache
from nox_ml.models.pinn.equation import EPS, GAMMA_CHECKS
from nox_ml.models.pinn.kernel import (
    KernelNet,
    boundary,
    build_table,
    collocation,
    evaluate,
    residual,
    source,
    train_kernel,
    validate,
)
from nox_ml.models.pinn.params import PinnParams

TINY = PinnParams(layers=2, width=16, adam_steps=30, lbfgs_rounds=1)


# --- the research validation: the trained network against the exact solution ---------------------------


@pytest.mark.regression
@pytest.mark.parametrize("gamma", GAMMA_CHECKS)
def test_the_trained_kernel_is_within_the_research_error_of_the_exact_solution(gamma):
    """`reports/pinn_prototipo.md`: median relative error of 4-7 % over the plume (3.5-6.6 % there) and a mass
    within 7 % at four typical values of gamma."""
    row = validate(reference_kernel().net, (gamma,))[f"{gamma}"]

    assert row["median_rel_error"] < 0.07
    assert abs(row["mass_error"]) < 0.07
    assert row["center_20km"] == pytest.approx(row["exact_20km"], rel=0.10)


# --- the equation and the sampling ---------------------------------------------------------------------


class Known(torch.nn.Module):
    """F = exp(0.5 A) (1 + 0.1 C^2): a function with known derivatives, to check that the residual applies the
    equation."""

    def forward(self, a, c, gamma):
        return torch.exp(0.5 * a) * (1 + 0.1 * c**2)


def test_the_residual_is_the_advection_diffusion_operator_minus_the_source():
    a, c, gamma = torch.tensor([0.3, 1.0]), torch.tensor([0.2, -0.4]), torch.tensor([0.1, 0.5])

    r, f = residual(Known(), a, c, gamma)  # type: ignore[arg-type]

    # F_A = F / 2, F_AA = F / 4, F_CC = 0.2 exp(A / 2)
    operator = (0.5 - EPS * 0.25 + gamma) * f - EPS * 0.2 * torch.exp(0.5 * a)
    assert_allclose(r.detach().numpy(), (operator - source(a, c)).detach().numpy(), rtol=1e-5)


def test_the_residual_uses_the_diffusion_it_is_given():
    a, c, gamma = torch.tensor([0.3]), torch.tensor([0.2]), torch.tensor([0.1])

    default, f = residual(Known(), a, c, gamma)  # type: ignore[arg-type]
    wider, _ = residual(Known(), a, c, gamma, 0.3)  # type: ignore[arg-type]

    # F_AA + F_CC = (1/4 F + 0.2 exp(A / 2)): the residual drops by (eps' - eps) times it
    laplacian = 0.25 * f + 0.2 * torch.exp(0.5 * a)
    assert_allclose((default - wider).detach().numpy(), ((0.3 - EPS) * laplacian).detach().numpy(), rtol=1e-5)


def test_training_validates_against_the_exact_solution_of_its_own_diffusivity(tmp_path):
    wide = PinnParams(**{**TINY.model_dump(), "kappa": 3000.0})

    kernel = KernelCache(tmp_path).get(wide)

    assert kernel.validation == validate(kernel.net, kappa=3000.0)
    assert kernel.validation != validate(kernel.net)
    assert wide.training_key() != TINY.training_key()
    assert KernelCache(tmp_path).load(TINY) is None  # a different kappa is a different entry


def test_the_source_has_unit_mass():
    grid = torch.linspace(-1.5, 1.5, 601)
    aa, cc = torch.meshgrid(grid, grid, indexing="ij")

    assert float(source(aa, cc).sum() * (grid[1] - grid[0]) ** 2) == pytest.approx(1.0, rel=1e-3)


def test_collocation_and_boundary_points_stay_inside_the_domain_and_the_gamma_range():
    gen = torch.Generator().manual_seed(0)

    for a, c, gamma in (collocation(500, gen), boundary(500, gen)):
        assert float(a.min()) >= -1.0 and float(a.max()) <= 5.0
        assert float(c.abs().max()) <= 4.0
        assert float(gamma.min()) >= 0.03 and float(gamma.max()) <= 0.75


def test_the_network_is_positive_and_symmetric_across_the_wind():
    net = KernelNet(2, 8)
    a, c = np.linspace(-1, 5, 50), np.linspace(0, 3, 50)

    left, right = evaluate(net, a, c, 0.2), evaluate(net, a, -c, 0.2)

    assert (left > 0).all()
    assert_allclose(left, right)


# --- training ------------------------------------------------------------------------------------------


def weights(kernel):
    return torch.cat([p.detach().ravel() for p in kernel.net.parameters()]).numpy()


def test_training_is_deterministic_given_the_seed():
    assert_array_equal(weights(train_kernel(TINY)), weights(train_kernel(TINY)))


def test_a_different_seed_trains_a_different_network():
    other = PinnParams(layers=2, width=16, adam_steps=30, lbfgs_rounds=1, seed=1)

    assert not np.allclose(weights(train_kernel(TINY)), weights(train_kernel(other)))


def test_training_lowers_the_loss_and_logs_every_phase():
    kernel = train_kernel(PinnParams(layers=2, width=16, learning_rate=1e-2, adam_steps=100, lbfgs_rounds=2))

    adam = [loss for phase, _, loss, _ in kernel.log if phase == "adam"]
    lbfgs = [loss for phase, _, loss, _ in kernel.log if phase == "lbfgs"]
    assert adam[-1] < adam[0] / 2
    assert lbfgs[-1] < adam[-1]
    assert len(lbfgs) == 2
    assert kernel.seconds > 0


def test_training_reports_progress_and_restores_the_thread_count():
    lines: list[str] = []
    before = torch.get_num_threads()

    train_kernel(TINY, lines.append)

    assert any(line.startswith("adam step") for line in lines) and any(
        line.startswith("lbfgs") for line in lines
    )
    assert torch.get_num_threads() == before


def test_a_network_with_no_training_steps_is_still_a_valid_kernel():
    kernel = train_kernel(PinnParams(layers=1, width=4, adam_steps=0, lbfgs_rounds=0))

    assert np.isfinite(list(kernel.validation["0.25"].values())).all()


# --- the table -----------------------------------------------------------------------------------------


def test_the_table_is_the_network_at_its_nodes_and_close_to_it_between_them():
    net = reference_kernel().net
    table = build_table(net)
    k = 7
    a, c = table.a[::40], table.c[::25]
    aa, cc = np.meshgrid(a, c, indexing="ij")

    at_nodes = np.array([table(aa[:, j], cc[:, j], float(table.gamma[k])) for j in range(aa.shape[1])]).T
    assert_allclose(at_nodes, evaluate(net, aa, cc, float(table.gamma[k])), rtol=2e-4)

    a_mid, c_mid = np.array([0.713, 1.987, 3.31]), np.array([0.337, 0.9, 1.45])
    between = table(a_mid, c_mid, 0.2)
    assert_allclose(between, evaluate(net, a_mid, c_mid, 0.2), rtol=0.02)


# --- the cache -----------------------------------------------------------------------------------------


def test_the_cache_trains_once_and_reloads_the_same_network(tmp_path, monkeypatch):
    calls = []

    def counting(params, progress=None):
        calls.append(params)
        return train_kernel(params)

    monkeypatch.setattr(cache_module, "train_kernel", counting)
    cache = KernelCache(tmp_path / "kernels")

    first = cache.get(TINY)
    second = cache.get(TINY)

    assert len(calls) == 1
    assert_array_equal(weights(first), weights(second))
    assert second.validation == first.validation
    assert second.log == first.log


def test_the_cache_keeps_the_parameters_and_the_validation_next_to_the_weights(tmp_path):
    cache = KernelCache(tmp_path)
    cache.get(TINY)

    info = json.loads(cache.info_path(TINY).read_text())

    assert info["params"] == TINY.model_dump()
    assert set(info["validation"]) == {f"{g}" for g in GAMMA_CHECKS}
    assert info["training_key"] == TINY.training_key()


def test_changing_only_the_transport_fields_reuses_the_cached_network(tmp_path):
    cache = KernelCache(tmp_path)
    cache.get(TINY)

    reused = cache.load(PinnParams(**{**TINY.model_dump(), "tau_h": 6.0, "u_min": 2.0}))

    assert reused is not None
    assert reused.params.tau_h == 6.0


def test_a_network_that_was_never_trained_is_not_in_the_cache(tmp_path):
    assert KernelCache(tmp_path).load(TINY) is None
