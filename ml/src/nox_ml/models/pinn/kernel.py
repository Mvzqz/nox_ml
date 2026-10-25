"""The network that learns the plume kernel ``F(A, C, gamma)`` with physics only (no data).

Migrated from `scripts/pinn/kernel.py` (research-archive). The loss is the residual of the equation of
`nox_ml.models.pinn.equation` (relative to the local value, since the far tail sums many cells) plus
``F = 0`` 10 km upwind and 40 km to the side. Adam alone stalls at a relative error of 10-20 % with respect to
the exact solution; rounds of L-BFGS bring it to 4-7 %. CPU, one thread (the result then does not
depend on the machine's load).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import torch

from nox_ml.models.pinn.equation import (
    A_RANGE,
    C_MAX,
    EPS,
    GAMMA_CHECKS,
    GAMMA_RANGE,
    SOURCE_SIGMA,
    exact,
)
from nox_ml.models.pinn.params import PinnParams
from nox_ml.models.pinn.transport import KernelTable

BOUNDARY_WEIGHT = 10.0
REL_FLOOR = 0.05  # the residual is divided by F + this, so it counts in proportion to the value
ADAM_POINTS, ADAM_BOUNDARY_POINTS = 2048, 512
LBFGS_POINTS, LBFGS_BOUNDARY_POINTS, LBFGS_ITERATIONS = 6000, 1024, 60
LR_DECAY = 100.0  # the rate ends at learning_rate / LR_DECAY
TABLE_STEP = 0.02  # spacing of the evaluation table in A and C (units of L)
TABLE_GAMMAS = 16

Progress = Callable[[str], None]
Points = tuple[torch.Tensor, torch.Tensor, torch.Tensor]


class KernelNet(torch.nn.Module):
    """``F(A, C, gamma) = exp(net(A, C^2, log gamma))``: positive and symmetric in ``C``."""

    def __init__(self, layers: int = 4, width: int = 64):
        super().__init__()
        modules: list[torch.nn.Module] = []
        size = 3
        for _ in range(layers):
            modules += [torch.nn.Linear(size, width), torch.nn.Tanh()]
            size = width
        modules.append(torch.nn.Linear(size, 1))
        self.net = torch.nn.Sequential(*modules)

    def forward(self, a: torch.Tensor, c: torch.Tensor, gamma: torch.Tensor) -> torch.Tensor:
        log_gamma = torch.log(gamma) - np.log(0.15)
        z = torch.stack([(a - 2) / 3, c**2 / 4 - 1, log_gamma], -1)
        return torch.exp(self.net(z).squeeze(-1))


@dataclass
class TrainedKernel:
    """A trained network, the parameters that made it and how the training went (``log`` rows:
    phase, step or round, loss, seconds)."""

    net: KernelNet
    params: PinnParams
    log: list[tuple[str, int, float, float]] = field(default_factory=list)
    seconds: float = 0.0
    validation: dict[str, dict[str, float]] = field(default_factory=dict)  # `validate`, by gamma

    @cached_property
    def table(self) -> KernelTable:
        """The network tabulated for evaluation (built once, shared by every fit that uses this kernel)."""
        return build_table(self.net)


@contextmanager
def one_thread() -> Iterator[None]:
    """Run with a single torch thread and restore the previous setting."""
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def source(a: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
    return torch.exp(-(a**2 + c**2) / (2 * SOURCE_SIGMA**2)) / (2 * np.pi * SOURCE_SIGMA**2)


def residual(
    net: KernelNet, a: torch.Tensor, c: torch.Tensor, gamma: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Residual of the equation at the points, and the value of the network there."""
    a = a.detach().requires_grad_(True)
    c = c.detach().requires_grad_(True)
    f = net(a, c, gamma)
    fa, fc = torch.autograd.grad(f.sum(), (a, c), create_graph=True)
    faa = torch.autograd.grad(fa.sum(), a, create_graph=True)[0]
    fcc = torch.autograd.grad(fc.sum(), c, create_graph=True)[0]
    return fa - EPS * (faa + fcc) + gamma * f - source(a, c), f


def random_gamma(n: int, gen: torch.Generator) -> torch.Tensor:
    """Log-uniform in `GAMMA_RANGE`."""
    low, high = np.log(GAMMA_RANGE[0]), np.log(GAMMA_RANGE[1])
    return torch.exp(low + torch.rand(n, generator=gen) * (high - low))


def collocation(n: int, gen: torch.Generator) -> Points:
    """Points of the interior: 40 % near the source, 30 % in the plume, 30 % uniform."""
    n_near, n_plume = int(0.4 * n), int(0.3 * n)
    n_uniform = n - n_near - n_plume
    a = torch.cat(
        [
            torch.randn(n_near, generator=gen) * 0.35,
            torch.rand(n_plume, generator=gen) * 5.0,
            A_RANGE[0] + torch.rand(n_uniform, generator=gen) * (A_RANGE[1] - A_RANGE[0]),
        ]
    )
    plume_a = a[n_near : n_near + n_plume].clamp(min=0)
    c = torch.cat(
        [
            torch.randn(n_near, generator=gen) * 0.35,
            torch.randn(n_plume, generator=gen) * (0.2 + 0.5 * torch.sqrt(plume_a + 0.1)),
            (torch.rand(n_uniform, generator=gen) * 2 - 1) * C_MAX,
        ]
    )
    return a.clamp(*A_RANGE), c.clamp(-C_MAX, C_MAX), random_gamma(n, gen)


def boundary(n: int, gen: torch.Generator) -> Points:
    """Points 10 km upwind and 40 km to the side, where ``F`` must vanish (the exit at 50 km is free)."""
    t = torch.rand(n, generator=gen)
    upwind = torch.rand(n, generator=gen) < 0.5
    a = torch.where(upwind, torch.full_like(t, A_RANGE[0]), A_RANGE[0] + t * (A_RANGE[1] - A_RANGE[0]))
    side = torch.sign(torch.rand(n, generator=gen) - 0.5) * C_MAX
    c = torch.where(upwind, (t * 2 - 1) * C_MAX, side)
    return a, c, random_gamma(n, gen)


def loss(net: KernelNet, interior: Points, edge: Points, physics_weight: float) -> torch.Tensor:
    """Equation residual (relative to the local value) times `physics_weight` plus the boundary term."""
    r, f = residual(net, *interior)
    equation_term = ((r / (f.detach() + REL_FLOOR)) ** 2).mean()
    return physics_weight * equation_term + BOUNDARY_WEIGHT * net(*edge).pow(2).mean()


def lbfgs_round(net: KernelNet, interior: Points, edge: Points, physics_weight: float) -> float:
    """One L-BFGS round on fixed points; returns the loss at its start."""
    optimizer = torch.optim.LBFGS(
        net.parameters(),
        lr=1.0,
        max_iter=LBFGS_ITERATIONS,
        history_size=50,
        line_search_fn="strong_wolfe",
    )

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        value = loss(net, interior, edge, physics_weight)
        value.backward()
        return value

    return optimizer.step(closure).item()


def train_kernel(params: PinnParams, progress: Progress | None = None) -> TrainedKernel:
    """Train the network with Adam on fresh points each step, then refine with L-BFGS rounds on fixed
    points (renewed every round). Deterministic given ``params.seed``. `progress` receives a line every
    100 Adam steps and every L-BFGS round."""
    say = progress or (lambda _line: None)
    with one_thread():
        torch.manual_seed(params.seed)
        gen = torch.Generator().manual_seed(params.seed)
        net = KernelNet(params.layers, params.width)
        log: list[tuple[str, int, float, float]] = []
        start = time.time()

        steps = params.adam_steps
        opt = torch.optim.Adam(net.parameters(), lr=params.learning_rate)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            opt, max(steps, 1), eta_min=params.learning_rate / LR_DECAY
        )
        for k in range(steps):
            opt.zero_grad()
            value = loss(
                net, collocation(ADAM_POINTS, gen), boundary(ADAM_BOUNDARY_POINTS, gen), params.physics_weight
            )
            value.backward()
            opt.step()
            sched.step()
            if k % 100 == 0 or k == steps - 1:
                log.append(("adam", k, value.item(), time.time() - start))
                say(f"adam step {k:5d}  loss {value.item():.3e}  {time.time() - start:.0f} s")

        gen = torch.Generator().manual_seed(params.seed + 1)
        for r in range(params.lbfgs_rounds):
            interior = collocation(LBFGS_POINTS, gen)
            edge = boundary(LBFGS_BOUNDARY_POINTS, gen)
            value = lbfgs_round(net, interior, edge, params.physics_weight)
            log.append(("lbfgs", r, value, time.time() - start))
            say(f"lbfgs round {r:3d}  loss {value:.3e}  {time.time() - start:.0f} s")
        net.eval()
    seconds = time.time() - start
    return TrainedKernel(net, params, log, seconds, validate(net))


def evaluate(net: KernelNet, a: np.ndarray, c: np.ndarray, gamma: float | np.ndarray) -> np.ndarray:
    """Network values at points `a`, `c` (units of L) for one `gamma` (or one per point)."""
    ta = torch.as_tensor(np.asarray(a, dtype=np.float32).ravel())
    tc = torch.as_tensor(np.asarray(c, dtype=np.float32).ravel())
    tg = torch.as_tensor(np.broadcast_to(np.asarray(gamma, dtype=np.float32), ta.shape).copy())
    with torch.no_grad():
        return net(ta, tc, tg).numpy().reshape(np.shape(a))


def validate(net: KernelNet, gammas: tuple[float, ...] = GAMMA_CHECKS) -> dict[str, dict[str, float]]:
    """Error against the exact solution at each of `gammas`, in the window ``-0.5 <= A <= 4``,
    ``|C| <= 2.5`` (5 km upwind to 40 km downwind), where the exact value is above 5 % of its maximum:
    ``median_rel_error`` and ``p90_rel_error`` of the plume, ``mass_error`` (sum over the window) and the
    value on the centerline 5 and 20 km from the source, of the network and of the exact solution."""
    out = {}
    for gamma in gammas:
        a, c, f_exact = exact(gamma)
        in_a, in_c = (a >= -0.5) & (a <= 4.0), np.abs(c) <= 2.5
        aa, cc = np.meshgrid(a[in_a][::5], c[in_c][::5], indexing="ij")
        exact_window = f_exact[np.ix_(in_a, in_c)][::5, ::5]
        net_window = evaluate(net, aa, cc, gamma)
        big = exact_window > 0.05 * exact_window.max()
        rel = np.abs(net_window - exact_window)[big] / exact_window[big]
        row_5, row_20 = np.argmin(np.abs(aa[:, 0] - 0.5)), np.argmin(np.abs(aa[:, 0] - 2.0))
        center = np.argmin(np.abs(cc[0]))
        out[f"{gamma}"] = {
            "median_rel_error": float(np.median(rel)),
            "p90_rel_error": float(np.percentile(rel, 90)),
            "mass_error": float(net_window.sum() / exact_window.sum() - 1),
            "center_5km": float(net_window[row_5, center]),
            "exact_5km": float(exact_window[row_5, center]),
            "center_20km": float(net_window[row_20, center]),
            "exact_20km": float(exact_window[row_20, center]),
        }
    return out


def build_table(net: KernelNet) -> KernelTable:
    """The network on a grid, for fast evaluation (bilinear interpolation in A and C, linear in log gamma)."""
    a = np.arange(A_RANGE[0], A_RANGE[1] + 1e-9, TABLE_STEP)
    c = np.arange(0, C_MAX + 1e-9, TABLE_STEP)
    gammas = np.exp(np.linspace(np.log(GAMMA_RANGE[0]), np.log(GAMMA_RANGE[1]), TABLE_GAMMAS))
    aa, cc = np.meshgrid(a, c, indexing="ij")
    values = np.stack([evaluate(net, aa, cc, g) for g in gammas]).astype(np.float32)
    return KernelTable(a, c, gammas, values)
