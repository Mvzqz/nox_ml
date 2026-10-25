import numpy as np
import pytest
from exact_table import STEP, exact_table
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import Receptors, Sources
from nox_ml.models.pinn.equation import EPS, L_M, exact
from nox_ml.models.pinn.transport import column, jacobian_hour_pinn
from nox_ml.physics.plume import plume

TABLE = exact_table()
TAU_H, U_MIN = 12.0, 1.0


def col(dx, dy, u, v, tau_h=TAU_H):
    g, along = column(
        np.atleast_1d(np.asarray(dx, float)), np.atleast_1d(np.asarray(dy, float)), u, v, TABLE, tau_h, U_MIN
    )
    return g, along


def test_the_table_returns_the_values_it_was_built_from_at_its_nodes():
    a_idx, c_idx, g_idx = 150, 60, 7
    a, c, gamma = TABLE.a[a_idx], TABLE.c[c_idx], TABLE.gamma[g_idx]

    value = TABLE(np.array([a]), np.array([-c]), float(gamma))

    assert value[0] == pytest.approx(TABLE.values[g_idx, a_idx, c_idx], rel=1e-5)


def test_the_table_is_zero_outside_the_range_of_the_network():
    far_upwind = TABLE(np.array([-1.5, 5.5]), np.array([0.0, 0.0]), 0.2)
    far_side = TABLE(np.array([1.0]), np.array([4.5]), 0.2)

    assert_allclose([*far_upwind, *far_side], 0.0)


def test_the_crosswind_flux_of_the_column_is_the_mass_that_survives():
    """The column (g/m2 per 1 g/s) times the speed and integrated across the wind is the g/s that cross the
    line: exp(r x / L) / sqrt(1 + 4 eps gamma) for the equation of the kernel."""
    speed, tau_h = 3.0, 12.0
    gamma = L_M / (speed * tau_h * 3600)
    root = np.sqrt(1 + 4 * EPS * gamma)
    r = (1 - root) / (2 * EPS)
    across = np.arange(-30_000, 30_001, 100.0)

    for x in (10_000.0, 20_000.0):
        g, _ = col(np.full_like(across, x), across, speed, 0.0, tau_h)
        assert speed * g.sum() * 100 == pytest.approx(np.exp(r * x / L_M) / root, rel=0.01)


def test_a_larger_diffusivity_widens_the_plume_and_lowers_the_centerline_column():
    """Same kernel equation with kappa 500, 1500 and 3000 m: the column across the wind at 15 km is wider
    (second moment) and lower on the axis, and the mass that crosses (the integral) is the same."""
    across = np.arange(-30_000, 30_001, 100.0)
    widths, centers, fluxes = [], [], []
    for kappa in (500.0, 1500.0, 3000.0):
        g, _ = column(np.full_like(across, 15_000.0), across, 3.0, 0.0, exact_table(kappa), TAU_H, U_MIN)
        widths.append(np.sqrt((g * across**2).sum() / g.sum()))
        centers.append(g[across.size // 2])
        fluxes.append(g.sum())

    assert widths == sorted(widths) and centers == sorted(centers, reverse=True)
    assert_allclose(fluxes, fluxes[1], rtol=0.05)


@pytest.mark.parametrize("degrees", [0, 37, 90, 180, 251])
def test_the_column_does_not_depend_on_the_direction_of_the_wind(degrees):
    """The receptor is placed 5 km along and 1.5 km across the wind, whatever way it blows."""
    angle = np.deg2rad(degrees)
    u, v = 3.0 * np.cos(angle), 3.0 * np.sin(angle)
    dx = 5000.0 * np.cos(angle) - 1500.0 * np.sin(angle)
    dy = 5000.0 * np.sin(angle) + 1500.0 * np.cos(angle)

    rotated, _ = col(dx, dy, u, v)
    reference, _ = col(5000.0, 1500.0, 3.0, 0.0)

    assert_allclose(rotated, reference, rtol=1e-5)


def test_the_column_is_symmetric_across_the_wind():
    left, _ = col(8000.0, 2500.0, 2.0, 0.0)
    right, _ = col(8000.0, -2500.0, 2.0, 0.0)

    assert_allclose(left, right)


def test_a_slower_wind_leaves_a_larger_column_close_to_the_source():
    slow, _ = col(3000.0, 0.0, 1.5, 0.0)
    fast, _ = col(3000.0, 0.0, 6.0, 0.0)

    assert slow[0] > fast[0]


def test_a_shorter_lifetime_lowers_the_column_downwind():
    long_lived, _ = col(20_000.0, 0.0, 3.0, 0.0, tau_h=12.0)
    short_lived, _ = col(20_000.0, 0.0, 3.0, 0.0, tau_h=4.0)

    assert short_lived[0] < long_lived[0]


def test_there_is_no_plume_without_wind():
    g, _ = col([3000.0, -3000.0], [0.0, 1000.0], 0.0, 0.0)

    assert_allclose(g, 0.0)


@pytest.mark.parametrize("x", [5_000.0, 10_000.0, 20_000.0])
def test_the_centerline_column_is_of_the_order_of_the_plume_with_a_30_degree_spread(x):
    """The diffusivity kappa = 1,500 m stands for the meandering of a 30 degree wind spread (the research
    matched them at about 10 km): the two columns agree within a factor 1.7 between 5 and 20 km."""
    g, _ = col(x, 0.0, 3.0, 0.0)
    _, gaussian = plume(
        np.array([0.0]), np.array([0.0]), np.array([x]), np.array([0.0]), 3.0, 0.0, 1000.0,
        sigma_theta=np.deg2rad(30), u_min=U_MIN,
    )  # fmt: skip

    assert 1 / 1.7 < g[0] / gaussian[0, 0] < 1.7


# --- the Jacobian --------------------------------------------------------------------------------------


def scene(prior=(400.0, 100.0)) -> tuple[Sources, Receptors, Receptors]:
    sources = Sources(
        point_x=np.array([0.0]),
        point_y=np.array([0.0]),
        cell_x=np.array([-2000.0, 1000.0]),
        cell_y=np.array([500.0, -500.0]),
        cell_prior=np.array(prior),
        cell_zone=np.array([0, 1]),
        n_zones=3,
    )
    return (
        sources,
        Receptors(np.array([9000.0, 12_000.0]), np.array([500.0, -1500.0])),
        Receptors(np.array([15_000.0]), np.array([0.0])),
    )


def jac(sources, stations, pixels, wind=(3.0, 0.0), pbl=900.0, tau_h=TAU_H):
    return jacobian_hour_pinn(wind, pbl, sources, stations, pixels, 0.7, TABLE, tau_h, U_MIN)


def test_the_jacobian_has_the_columns_of_the_plume_jacobian_points_then_zones():
    sources, stations, pixels = scene()

    out = jac(sources, stations, pixels)

    assert out.stations.shape == (2, 1 + 3)
    assert out.pixels.shape == (1, 1 + 3)
    assert (out.stations[:, :3] > 0).all()
    assert_allclose(out.stations[:, 3], 0.0)  # a zone without cells has no column


def test_a_zone_column_is_linear_in_the_prior_of_its_cells():
    sources, stations, pixels = scene()
    doubled = scene(prior=(800.0, 200.0))[0]

    once, twice = jac(sources, stations, pixels), jac(doubled, stations, pixels)

    assert_allclose(twice.stations[:, 1:], 2 * once.stations[:, 1:])
    assert_allclose(twice.stations[:, 0], once.stations[:, 0])  # the point source is per 1 t/yr


def test_a_receptor_far_upwind_sees_nothing():
    sources, _, _ = scene()
    upwind = Receptors(np.array([-20_000.0]), np.array([0.0]))

    out = jac(sources, upwind, upwind)

    assert_allclose(out.stations, 0.0)
    assert_allclose(out.pixels, 0.0)


def test_absent_receptors_give_empty_blocks():
    sources, _, _ = scene()
    nobody = Receptors(np.empty(0), np.empty(0))

    out = jac(sources, nobody, nobody)

    assert out.stations.shape == (0, 4)
    assert out.pixels.shape == (0, 4)


def test_a_deeper_boundary_layer_dilutes_the_stations_but_not_the_column():
    sources, stations, pixels = scene()

    shallow, deep = jac(sources, stations, pixels, pbl=500.0), jac(sources, stations, pixels, pbl=3000.0)

    assert (deep.stations[:, :3] < shallow.stations[:, :3]).all()
    assert_allclose(deep.pixels, shallow.pixels)


def test_the_station_response_is_the_column_over_the_mixing_height_in_ppb():
    sources, stations, _ = scene()
    from nox_ml.physics.plume import PPB_PER_GM3, T_PER_YR_TO_GS, effective_height

    g, along = col(stations.x - sources.point_x[0], stations.y - sources.point_y[0], 3.0, 0.0)

    out = jac(sources, stations, Receptors(np.empty(0), np.empty(0)))

    assert_allclose(out.stations[:, 0], g / effective_height(along, 900.0) * T_PER_YR_TO_GS * PPB_PER_GM3)
    assert STEP == 0.02  # the table nodes of these tests
    assert exact(0.25)[0][1] - exact(0.25)[0][0] == pytest.approx(STEP)
