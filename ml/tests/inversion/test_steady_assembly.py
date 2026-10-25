from functools import partial

import numpy as np
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import (
    HourJacobian,
    Receptors,
    Sources,
    jacobian_hour_plume,
    jacobian_hour_steady,
)
from nox_ml.inversion.linear import SIGMA_THETA, U_MIN, hour_systems
from nox_ml.physics.plume import MOLEC_CM2_PER_GM2, PPB_PER_GM3, T_PER_YR_TO_GS

RATIO = 0.7


def sources() -> Sources:
    return Sources(
        point_x=np.array([0.0, 1000.0]),
        point_y=np.array([0.0, 0.0]),
        cell_x=np.array([0.0, 0.0, 500.0]),
        cell_y=np.array([0.0, 1000.0, 0.0]),
        cell_prior=np.array([10.0, 20.0, 30.0]),
        cell_zone=np.array([0, 0, 2]),
        n_zones=3,
    )


def ones(xs, ys, xr, yr, extra_sy):
    shape = (len(xr), len(xs))
    return np.full(shape, 2.0), np.full(shape, 5.0)


def test_the_assembly_turns_a_response_into_points_then_zones_in_the_units_of_each_receptor():
    stations, pixels = Receptors(np.zeros(2), np.zeros(2)), Receptors(np.zeros(1), np.zeros(1))

    out = jacobian_hour_steady(ones, sources(), stations, pixels, RATIO)

    to_ppb, to_molec = T_PER_YR_TO_GS * PPB_PER_GM3, T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * RATIO
    assert_allclose(out.stations, np.tile([2, 2, 2 * 30, 0, 2 * 30], (2, 1)) * to_ppb)
    assert_allclose(out.pixels, np.tile([5, 5, 5 * 30, 0, 5 * 30], (1, 1)) * to_molec)


def test_the_response_sees_the_extra_spread_of_pixels_only():
    seen = []

    def spy(xs, ys, xr, yr, extra_sy):
        seen.append((len(xr), extra_sy))
        return ones(xs, ys, xr, yr, extra_sy)

    stations, pixels = Receptors(np.zeros(2), np.zeros(2)), Receptors(np.zeros(1), np.zeros(1))
    jacobian_hour_steady(spy, sources(), stations, pixels, RATIO)

    assert {(n, sy > 0) for n, sy in seen} == {(2, False), (1, True)}


def test_hour_systems_take_the_transport_they_are_given(make_inputs):
    inputs = make_inputs()
    winds = []

    def stub(wind, pbl, sources, stations, pixels, ratio):
        winds.append(wind)
        return HourJacobian(
            np.ones((len(stations.x), sources.n_columns)), np.ones((len(pixels.x), sources.n_columns))
        )

    systems = hour_systems(
        inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, inputs.n_regions, jacobian=stub
    )

    assert winds == [h.wind for h in inputs.hours]
    assert all((s.jacobian.stations == 1).all() for s in systems)


def test_the_default_transport_of_the_hour_systems_is_the_baseline_plume(make_inputs):
    inputs = make_inputs()
    args = (inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, inputs.n_regions)
    baseline = partial(jacobian_hour_plume, sigma_theta=SIGMA_THETA, u_min=U_MIN)

    default, explicit = hour_systems(*args), hour_systems(*args, jacobian=baseline)

    for a, b in zip(default, explicit, strict=True):
        assert_allclose(a.jacobian.stations, b.jacobian.stations)
        assert_allclose(a.info, b.info)


def test_the_plume_parameters_of_the_hour_systems_reach_the_jacobian(make_inputs):
    """`sigma_theta` and `u_min` used to be ignored in favor of the module constants."""
    inputs = make_inputs()
    args = (inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, inputs.n_regions)

    narrow = hour_systems(*args, sigma_theta=np.deg2rad(5.0))
    wide = hour_systems(*args, sigma_theta=np.deg2rad(45.0))

    assert not np.allclose(narrow[0].jacobian.stations, wide[0].jacobian.stations)
