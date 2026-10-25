from dataclasses import replace

import numpy as np
import pandas as pd
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import Receptors
from nox_ml.inversion.linear import hour_systems, solve, traffic_constraints
from nox_ml.models.inversion_plume import InversionPlume, InversionPlumeParams

N_REGIONS = 2


def systems_of(inputs, **kwargs):
    return hour_systems(inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS, **kwargs)


def test_a_tempo_error_without_limit_leaves_the_pixels_out(make_inputs):
    inputs = make_inputs()
    no_pixel = Receptors(np.zeros(0), np.zeros(0))
    without_pixels = [replace(h, pixels=no_pixel, no2=np.zeros(0)) for h in inputs.hours]

    huge = systems_of(inputs, tempo_sigma_mult=1e9)
    stations_only = hour_systems(without_pixels, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)

    for with_error, no_pixels in zip(huge, stations_only, strict=True):
        assert_allclose(with_error.info, no_pixels.info, rtol=1e-8, atol=1e-12)
        assert_allclose(with_error.gradient, no_pixels.gradient, rtol=1e-8, atol=1e-12)


def test_the_traffic_constraint_sets_the_road_totals_of_the_day_types():
    prior = np.array([700.0, 500.0])  # t/yr of each region
    points = pd.DataFrame({"name": ["P0"], "x": [0.0], "y": [0.0], "prior": [100.0], "sd": [100.0]})

    free = solve([], points, N_REGIONS)
    held = solve([], points, N_REGIONS, constraints=traffic_constraints(prior, 1, sd=1e-3))

    free_totals = free.road_factors() @ prior
    held_totals = held.road_factors() @ prior
    assert_allclose(free_totals / free_totals[0], 1.0)  # no data and no constraint: the prior
    assert_allclose(held_totals[1] / held_totals[0], 0.87, rtol=1e-3)  # Saturday
    assert_allclose(held_totals[2] / held_totals[0], 0.69, rtol=1e-3)  # Sunday or holiday


def test_the_baseline_has_no_traffic_constraint(make_inputs):
    inputs = make_inputs()
    model = InversionPlume()

    assert isinstance(model.params, InversionPlumeParams)
    assert model.params.tempo_sigma_mult == 1.0
    assert model.params.traffic_constraint is False
    assert model.constraints(inputs) == []


def day_total(table: pd.DataFrame, day_type: str) -> float:
    return float(table.loc[table["day_type"] == day_type, "mean"].sum())


def test_a_model_with_the_traffic_constraint_gives_the_sunday_ratio_of_the_traffic(make_inputs):
    inputs = make_inputs()
    params = InversionPlumeParams.model_validate(
        {"traffic_constraint": True, "traffic_sd": 1e-3, "bootstrap_n": 2}
    )

    table = InversionPlume(params).fit(inputs).estimate_emissions().table
    weekday = day_total(table, "weekday")

    assert_allclose(day_total(table, "sunday_holiday") / weekday, 0.69, rtol=1e-2)
    assert_allclose(day_total(table, "saturday") / weekday, 0.87, rtol=1e-2)
