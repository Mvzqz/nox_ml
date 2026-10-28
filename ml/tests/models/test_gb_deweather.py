# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Gradient boosting deweathering: what changes against the forest (seed, dropped features, extremes)."""

import pytest
from pydantic import ValidationError
from ventilation_synthetic import ventilation_inputs

from nox_ml.models.gb_deweather import GbDeweather, GbDeweatherParams

FAST = GbDeweatherParams(max_iter=60, bootstrap_n=3, weather_samples=5)


def test_the_same_seed_gives_the_same_index_and_prediction():
    data = ventilation_inputs()

    first = GbDeweather(FAST).fit(data)
    second = GbDeweather(FAST).fit(data)

    assert first.estimate_emissions().table.equals(second.estimate_emissions().table)
    assert first.predict_stations(data, ["AAA"]).equals(second.predict_stations(data, ["AAA"]))


def test_drop_features_takes_those_columns_out_of_the_fit_and_the_deweathering():
    data = ventilation_inputs()
    dropped = ["doy_sin", "doy_cos", "ventilation_6h"]
    model = GbDeweather(FAST.model_copy(update={"drop_features": dropped})).fit(data)

    columns = set(model._matrix(model._rows(data, None)).columns)

    assert not columns & set(dropped)
    assert {"hour_sin", "ventilation", "day_type_weekday", "station_AAA"} <= columns
    assert model._forest is not None
    assert model._forest.n_features_in_ == len(columns)
    model.estimate_emissions().validate()  # the weather draws skip the dropped column


def test_the_default_keeps_every_feature():
    data = ventilation_inputs()
    model = GbDeweather(FAST).fit(data)

    columns = set(model._matrix(model._rows(data, None)).columns)

    assert {"doy_sin", "doy_cos", "ventilation_6h"} <= columns


def test_dropping_a_column_that_does_not_exist_is_an_error():
    data = ventilation_inputs()
    model = GbDeweather(FAST.model_copy(update={"drop_features": ["no_such_feature"]}))

    with pytest.raises(ValueError, match="no_such_feature"):
        model.fit(data)


def test_the_day_type_cannot_be_dropped():
    with pytest.raises(ValidationError, match="quantity under test"):
        GbDeweatherParams(drop_features=["day_type_sunday_holiday"])


@pytest.mark.parametrize(
    "extreme",
    [
        {"learning_rate": 1e-4, "max_iter": 1, "max_leaf_nodes": 2, "min_samples_leaf": 1},  # barely learns
        {"learning_rate": 1.0, "max_iter": 300, "max_leaf_nodes": 255, "min_samples_leaf": 1},  # interpolates
        {"min_samples_leaf": 10_000, "l2_regularization": 100.0},  # no leaf can be split
    ],
    ids=["underfit", "overfit", "no_split"],
)
def test_extreme_params_still_give_a_finite_index_and_prediction(extreme):
    data = ventilation_inputs()
    model = GbDeweather(FAST.model_copy(update=extreme)).fit(data)

    estimate = model.estimate_emissions().validate()
    pred = model.predict_stations(data, ["AAA"])

    assert estimate.table["mean"].notna().all()
    assert pred["nox_ppb_pred"].notna().all()
    assert model.n_params >= 1
