import numpy as np
import pandas as pd
import pytest

from nox_ml.inversion.linear import hour_systems, invert
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.validation.loo import (
    idw_and_hybrid,
    leave_one_out,
    predict_pixels,
    station_rows,
    summarize,
)

N_REGIONS = 2


def fit(inputs):
    systems = hour_systems(inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)
    post = invert(inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS)
    return systems, post


def test_station_rows_follow_the_order_of_the_hours(make_inputs):
    inputs = make_inputs()

    rows = station_rows(inputs)

    assert len(rows) == inputs.n_station_rows
    assert rows["station"].iloc[:3].tolist() == ["AAA", "BBB", "CCC"]
    assert rows["h"].iloc[0] == inputs.hours[0].hour
    assert rows["obs"].iloc[4] == inputs.hours[1].nox[1]


def test_idw_weights_the_other_stations_by_inverse_squared_distance_and_adds_it_to_the_residuals():
    xy = pd.DataFrame({"x": [0.0, 1000.0, 0.0], "y": [0.0, 0.0, 2000.0]}, index=["A", "B", "C"])
    h = pd.Timestamp("2023-11-01 18:00")
    rows = pd.DataFrame({"h": [h] * 3, "station": ["A", "B", "C"], "obs": [10.0, 20.0, 40.0]})
    model = np.array([12.0, 15.0, 30.0])  # residuals of B and C: 5 and 10

    out = idw_and_hybrid(rows, model, "A", xy)

    w = np.array([1 / 1**2, 1 / 2**2])  # B at 1 km, C at 2 km
    assert out["obs"].tolist() == [10.0]
    assert out["model"].tolist() == [12.0]
    assert out["idw"].iloc[0] == pytest.approx(w @ [20.0, 40.0] / w.sum())
    assert out["hybrid"].iloc[0] == pytest.approx(12.0 + w @ [5.0, 10.0] / w.sum())


def test_idw_treats_a_station_closer_than_half_a_km_as_if_it_were_at_half_a_km():
    xy = pd.DataFrame({"x": [0.0, 100.0, 500.0], "y": [0.0, 0.0, 0.0]}, index=["A", "B", "C"])
    h = pd.Timestamp("2023-11-01 18:00")
    rows = pd.DataFrame({"h": [h] * 3, "station": ["A", "B", "C"], "obs": [0.0, 10.0, 30.0]})

    out = idw_and_hybrid(rows, np.zeros(3), "A", xy)

    assert out["idw"].iloc[0] == pytest.approx(20.0)  # equal weights


def test_idw_drops_the_hours_where_the_station_is_alone():
    xy = pd.DataFrame({"x": [0.0, 1000.0], "y": [0.0, 0.0]}, index=["A", "B"])
    t = [pd.Timestamp("2023-11-01 18:00"), pd.Timestamp("2023-11-01 19:00")]
    rows = pd.DataFrame({"h": [t[0], t[0], t[1]], "station": ["A", "B", "A"], "obs": [1.0, 2.0, 3.0]})

    out = idw_and_hybrid(rows, np.zeros(3), "A", xy)

    assert out["obs"].tolist() == [1.0]


def test_the_excluded_station_does_not_enter_the_background_of_the_others(make_inputs):
    inputs = make_inputs()
    changed = make_inputs()
    for hour in changed.hours:
        hour.nox[1] += 50.0  # BBB reads 50 ppb more
    others = ["AAA", "CCC"]

    same = InversionPlume().fit(inputs, exclude_stations=["BBB"]).predict_stations(changed, others)
    reference = InversionPlume().fit(inputs, exclude_stations=["BBB"]).predict_stations(inputs, others)
    other = InversionPlume().fit(inputs).predict_stations(changed, others)

    np.testing.assert_allclose(same["nox_ppb_pred"], reference["nox_ppb_pred"])
    assert np.all(other["nox_ppb_pred"] > reference["nox_ppb_pred"])


def test_predict_pixels_returns_one_value_per_pixel(make_inputs):
    inputs = make_inputs()
    systems, post = fit(inputs)

    model, observed = predict_pixels(inputs, systems, post)

    assert len(model) == len(observed) == inputs.n_pixels
    assert np.all(np.isfinite(model))


def test_leave_one_out_has_one_row_per_station_with_its_observations(make_inputs):
    inputs = make_inputs()

    table, _ = leave_one_out(inputs, InversionPlume)

    assert table.index.tolist() == ["AAA", "BBB", "CCC"]
    assert table["n"].tolist() == [len(inputs.hours)] * 3
    assert np.all(np.isfinite(table.to_numpy(float)))


def test_leave_one_out_predicts_every_held_out_row_with_a_model_that_never_saw_the_station(make_inputs):
    inputs = make_inputs()

    _, oof = leave_one_out(inputs, InversionPlume)

    assert len(oof) == inputs.n_station_rows
    for station in ["AAA", "BBB", "CCC"]:
        alone = InversionPlume().fit(inputs, exclude_stations=[station]).predict_stations(inputs, [station])
        mine = oof[oof["station"] == station].reset_index(drop=True)
        np.testing.assert_allclose(mine["nox_ppb_pred"], alone["nox_ppb_pred"])


def test_summarize_pools_by_rows_and_splits_bias_from_the_hour_to_hour_error():
    table = pd.DataFrame(
        {
            "n": [1, 3],
            "rmse_model": [5.0, 10.0],
            "bias_model": [3.0, -6.0],
            "rmse_idw": [4.0, 12.0],
            "bias_idw": [0.0, 0.0],
            "rmse_hybrid": [4.0, 9.0],
            "bias_hybrid": [4.0, 0.0],
        },
        index=["AAA", "BBB"],
    )

    s = summarize(table)

    assert s["rmse"]["model"] == pytest.approx(np.sqrt((1 * 25 + 3 * 100) / 4))
    assert s["bias"]["model"] == pytest.approx(np.sqrt((1 * 9 + 3 * 36) / 4))
    assert s["hourly"]["model"] == pytest.approx(np.sqrt((1 * 16 + 3 * 64) / 4))
    assert s["hourly"]["hybrid"] == pytest.approx(np.sqrt((0 + 3 * 81) / 4))  # AAA: 4 ** 2 - 4 ** 2
    assert s["hybrid_beats_idw"] == 1  # BBB only
    assert s["model_beats_idw"] == 1  # BBB only
    assert s["n_stations"] == 2
