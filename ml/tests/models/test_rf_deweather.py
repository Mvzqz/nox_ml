# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Meteorological normalization with a random forest: features and the index on known answers."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from ventilation_synthetic import ventilation_inputs

from nox_ml.models.rf_deweather import RfDeweather, RfDeweatherParams, hour_table, ventilation_features

FAST = RfDeweatherParams(n_estimators=100, bootstrap_n=5)  # the answer does not need more, and tests are fast


def hours(utc: list[str], u=3.0, v=0.0, pbl=1000.0) -> pd.DataFrame:
    stamps = pd.to_datetime(utc)
    return pd.DataFrame({"utc": stamps, "u": u, "v": v, "pbl": pbl})


def observed_ratio(model: RfDeweather, data, background: float = 5.0) -> float:
    """Sunday over weekday of the mean NOx above the background, with no weather adjustment."""
    rows = model._rows(data, None)
    above = rows.groupby("day_type")["nox"].mean() - background
    return float(above[2] / above[0])


def test_sunday_emitting_half_gives_an_index_near_half():
    data = ventilation_inputs(sunday=0.5)

    estimate = RfDeweather(FAST).fit(data).estimate_emissions().validate()

    assert estimate.day_type_ratio("sunday_holiday") == pytest.approx(0.5, rel=0.15)
    assert estimate.day_type_ratio("saturday") == pytest.approx(0.75, rel=0.15)


def test_the_weekday_is_the_reference_of_the_index_and_the_interval_holds_the_estimate():
    estimate = RfDeweather(FAST).fit(ventilation_inputs()).estimate_emissions()

    weekday = estimate.table.set_index("day_type").loc["weekday"]
    sunday = estimate.table.set_index("day_type").loc["sunday_holiday"]
    assert (weekday["mean"], weekday["lo"], weekday["hi"]) == (1.0, 1.0, 1.0)
    assert sunday["lo"] <= sunday["mean"] <= sunday["hi"]
    assert estimate.table["zone"].isna().all()


def test_weather_that_depends_on_the_day_type_does_not_drive_the_index():
    # same emission every day, but Sundays are mostly stagnant: they look dirtier, with no change to find
    data = ventilation_inputs(sunday=1.0, stagnant_on_sunday=0.9)
    model = RfDeweather(FAST).fit(data)

    index = model.estimate_emissions().day_type_ratio("sunday_holiday")

    assert observed_ratio(model, data) > 1.25
    assert index == pytest.approx(1.0, abs=0.1)


def test_the_prediction_is_in_ppb_and_close_to_the_observations():
    data = ventilation_inputs()
    model = RfDeweather(FAST).fit(data)

    pred = model.predict_stations(data, ["AAA", "BBB", "CCC"])

    observed = np.concatenate([h.nox for h in data.hours])
    assert pred["nox_ppb_pred"].mean() == pytest.approx(observed.mean(), rel=0.1)


def test_a_station_never_seen_in_the_fit_is_predicted_from_the_others():
    data = ventilation_inputs()
    model = RfDeweather(FAST).fit(data, exclude_stations=["BBB"])

    pred = model.predict_stations(data, ["BBB"])

    assert len(pred) == len(data.hours)
    assert pred["nox_ppb_pred"].notna().all()
    assert not any(column == "station_BBB" for column in model._matrix(model._rows(data, None)))


def test_the_previous_hours_of_the_ventilation_are_summed_when_all_are_present():
    table = hours([f"2023-11-06 {h:02d}:00" for h in range(12, 20)])

    out = ventilation_features(table)

    assert out["ventilation"].iloc[7] == 3000.0
    assert out["ventilation_3h"].iloc[7] == 3 * 3000.0
    assert out["ventilation_6h"].iloc[7] == 6 * 3000.0


def test_hours_missing_before_the_window_are_filled_with_the_mean_of_those_present():
    table = hours(["2023-11-06 18:00", "2023-11-06 19:00"]).assign(u=[1.0, 3.0])

    out = ventilation_features(table)

    assert out["ventilation_3h"].iloc[0] == 3 * 1000.0  # nothing before: the current hour
    assert out["ventilation_3h"].iloc[1] == 3 * 1000.0  # only the first hour before: its value


def test_wind_direction_is_continuous_across_north():
    data = ventilation_inputs(n_days=1)
    winds = [(0.02, 1.0), (-0.02, 1.0)]  # just east and just west of north, 2 degrees apart
    a, b = (hour_table(replace(data, hours=[replace(data.hours[0], wind=wind)])).iloc[0] for wind in winds)

    assert abs(a["wind_sin"] - b["wind_sin"]) < 0.001
    assert abs(a["wind_cos"] - b["wind_cos"]) < 0.04


def test_hour_of_the_day_is_a_circle():
    data = ventilation_inputs(n_days=1)

    table = hour_table(data)
    local = (np.array([h.hour.hour for h in data.hours]) - 6) % 24

    assert np.allclose(np.hypot(table["hour_sin"], table["hour_cos"]), 1.0)
    assert table["hour_cos"].to_numpy()[local == 12] == pytest.approx(-1.0)


def test_a_relabeled_day_changes_the_day_type_of_its_rows():
    data = ventilation_inputs(n_days=7)
    monday = pd.Timestamp("2023-11-06")

    relabeled = data.with_day_kinds({monday: 2})

    before, after = hour_table(data)["day_type"], hour_table(relabeled)["day_type"]
    assert (before.iloc[:6] == 0).all()
    assert (after.iloc[:6] == 2).all()
    assert (before.iloc[6:] == after.iloc[6:]).all()


def test_unfitted_model_asks_to_be_fitted():
    with pytest.raises(RuntimeError, match="fit the model first"):
        RfDeweather().estimate_emissions()


def test_params_reject_a_fraction_of_features_above_one():
    with pytest.raises(ValueError, match="max_features"):
        RfDeweatherParams(max_features=1.5)
