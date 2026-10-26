"""Tests for the normalized relative emission estimator."""

import pytest
from synthetic import synthetic_dataset


def test_normalized_ratio_recovers_synthetic_sunday_change(make_inputs):
    from nox_ml.models.normalized_ratio import NormalizedRatio

    synthetic = synthetic_dataset(make_inputs())
    model = NormalizedRatio().fit(synthetic.data)

    estimate = model.estimate_emissions().validate()

    assert estimate.kind == "relative"
    assert estimate.day_type_ratio("weekday") == pytest.approx(1.0)
    assert estimate.day_type_ratio("sunday_holiday") == pytest.approx(synthetic.sunday_ratio, rel=0.15)


def test_predict_stations_respects_requested_stations(make_inputs):
    from nox_ml.models.normalized_ratio import NormalizedRatio

    data = synthetic_dataset(make_inputs()).data

    model = NormalizedRatio().fit(
        data,
        exclude_stations=["BBB"],
    )

    predictions = model.predict_stations(data, ["BBB"])

    assert list(predictions.columns) == [
        "station",
        "utc",
        "nox_ppb_pred",
    ]
    assert not predictions.empty
    assert set(predictions["station"]) == {"BBB"}
    assert predictions["nox_ppb_pred"].notna().all()


def test_excluded_station_does_not_affect_training(make_inputs):
    from dataclasses import replace

    import numpy as np
    import pandas as pd

    from nox_ml.models.normalized_ratio import NormalizedRatio

    data = synthetic_dataset(make_inputs()).data

    rng = np.random.default_rng(42)
    altered_hours = []

    for hour, ids in zip(data.hours, data.station_ids, strict=True):
        changed_nox = np.where(
            ids == "BBB",
            rng.uniform(100, 500, size=len(ids)),
            hour.nox,
        )
        altered_hours.append(replace(hour, nox=changed_nox))

    altered = replace(data, hours=altered_hours)

    original = NormalizedRatio().fit(data, exclude_stations=["BBB"])
    modified = NormalizedRatio().fit(altered, exclude_stations=["BBB"])

    pd.testing.assert_frame_equal(
        original.estimate_emissions().table,
        modified.estimate_emissions().table,
    )

    pd.testing.assert_frame_equal(
        original.predict_stations(data, ["AAA", "CCC"]),
        modified.predict_stations(altered, ["AAA", "CCC"]),
    )
