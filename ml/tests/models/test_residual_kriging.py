"""Regression-kriging: the base model plus the kriging of its residuals between stations."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from synthetic import synthetic_dataset

from nox_ml.models import residual_kriging
from nox_ml.models.ensemble import MemberConfig
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.residual_kriging import (
    RANGES_KM,
    ResidualKriging,
    ResidualKrigingParams,
    fit_shape,
    krige,
)

STATIONS = ["AAA", "BBB", "CCC"]


@pytest.fixture
def data(make_inputs):
    return synthetic_dataset(make_inputs()).data


def field(rng, xy, length_scale_km, n_hours):
    """Hourly draws of a Gaussian process with unit variance and the range, at `xy` (km)."""
    distance = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    k = np.exp(-0.5 * (distance / length_scale_km) ** 2) + 1e-8 * np.eye(len(xy))
    return rng.multivariate_normal(np.zeros(len(xy)), k, n_hours)


def test_the_pooled_fit_finds_the_range_of_the_field():
    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 60, (22, 2))
    draws = field(rng, xy, 12.0, 200) + rng.normal(0, 0.3, (200, 22))

    scale, nugget = fit_shape([(xy, d) for d in draws])

    assert scale in RANGES_KM and 8 <= scale <= 16
    assert 0.05 <= nugget <= 0.2  # noise variance 0.09 over a unit field


def test_kriging_a_smooth_field_beats_its_mean_and_far_away_returns_the_mean():
    rng = np.random.default_rng(1)
    xy = rng.uniform(0, 60, (23, 2))
    draws = 10 * field(rng, xy, 12.0, 100) + 5
    train, held = xy[1:], xy[:1]

    kriged = np.array([krige(train, d[1:], held, 12.0, 0.05)[0] for d in draws])
    far = krige(train, draws[0, 1:], np.array([[1e4, 1e4]]), 12.0, 0.05)[0]

    assert np.sqrt(np.mean((kriged - draws[:, 0]) ** 2)) < 0.6 * np.sqrt(
        np.mean((draws[:, 1:].mean(axis=1) - draws[:, 0]) ** 2)
    )
    assert far == pytest.approx(draws[0, 1:].mean())


def test_the_emissions_are_the_base_models(data):
    model = ResidualKriging().fit(data)

    expected = InversionPlume().fit(data).estimate_emissions().table
    pd.testing.assert_frame_equal(model.estimate_emissions().table, expected)


def test_the_held_out_station_is_never_read(data, monkeypatch):
    monkeypatch.setattr(residual_kriging, "MIN_STATIONS", 2)  # the fixture has three stations
    wild = replace(
        data,
        hours=[
            replace(h, nox=np.where(ids == "BBB", 1e4, h.nox))
            for h, ids in zip(data.hours, data.station_ids, strict=True)
        ],
    )
    params = ResidualKrigingParams(length_scale_km=5.0, nugget=0.1)

    calm = ResidualKriging(params).fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])
    got = ResidualKriging(params).fit(wild, exclude_stations=["BBB"]).predict_stations(wild, ["BBB"])

    pd.testing.assert_frame_equal(got, calm)
    base = InversionPlume().fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])
    assert not np.allclose(calm["nox_ppb_pred"], base["nox_ppb_pred"])  # the residuals were kriged


def test_with_too_few_training_stations_the_prediction_is_the_base_ones(data):
    held = ResidualKriging().fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])

    base = InversionPlume().fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])
    pd.testing.assert_frame_equal(held, base)


def test_a_given_shape_is_used_and_a_missing_one_is_fitted(data):
    fixed = ResidualKriging(ResidualKrigingParams(length_scale_km=5.0, nugget=0.1)).fit(data)
    fitted = ResidualKriging().fit(data)

    assert fixed.shape == (5.0, 0.1)
    assert fitted.shape is not None and fitted.shape[0] in RANGES_KM


def test_the_base_is_any_model_of_the_registry_but_an_ensemble():
    params = ResidualKrigingParams(base=MemberConfig(name="regularized_ls"))

    assert ResidualKriging(params)._base.name == "regularized_ls"
    with pytest.raises(ValueError, match="base model"):
        ResidualKrigingParams(base=MemberConfig(name="convex_ensemble"))
