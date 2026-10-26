"""R1 (idw) and R2 (kriging): concentration references."""

from dataclasses import replace

import numpy as np
import pytest
from synthetic import synthetic_dataset

from nox_ml.models.references import Idw, IdwParams, Kriging, KrigingParams
from nox_ml.validation import loo

STATIONS = ["AAA", "BBB", "CCC"]


@pytest.fixture
def data(make_inputs):
    return synthetic_dataset(make_inputs()).data


def constant_field(data, value=42.0):
    return replace(data, hours=[replace(h, nox=np.full_like(h.nox, value)) for h in data.hours])


def test_references_estimate_no_emissions(data):
    with pytest.raises(NotImplementedError):
        Idw().fit(data).estimate_emissions()


def test_idw_of_a_held_out_station_is_the_idw_of_the_loo(data):
    rows = loo.station_rows(data)
    expected = loo.idw_and_hybrid(rows, np.zeros(len(rows)), "BBB", data.station_xy)["idw"].to_numpy()

    got = Idw().fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])

    np.testing.assert_allclose(got["nox_ppb_pred"].to_numpy(), expected)


def test_idw_far_from_every_other_station_is_their_mean_weighted_by_inverse_squared_distance(data):
    hour, ids = data.hours[0], data.station_ids[0]
    held = ids == "BBB"
    near = np.hypot(
        hour.stations.x[~held] - hour.stations.x[held], hour.stations.y[~held] - hour.stations.y[held]
    )
    w = 1 / np.maximum(near / 1000, 0.5) ** 2

    got = Idw().fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])

    assert got["nox_ppb_pred"].iloc[0] == pytest.approx(w @ hour.nox[~held] / w.sum())


def test_idw_params_change_the_weights(data):
    flat = Idw(IdwParams(power=1e-6)).fit(data, exclude_stations=["BBB"]).predict_stations(data, ["BBB"])

    hour, ids = data.hours[0], data.station_ids[0]
    assert flat["nox_ppb_pred"].iloc[0] == pytest.approx(hour.nox[ids != "BBB"].mean(), rel=1e-4)


def test_an_hour_where_only_the_excluded_station_reports_gets_no_prediction(data):
    only = replace(
        data,
        hours=[
            replace(
                data.hours[0],
                stations=replace(
                    data.hours[0].stations, x=data.hours[0].stations.x[:1], y=data.hours[0].stations.y[:1]
                ),
                nox=data.hours[0].nox[:1],
            ),
            *data.hours[1:],
        ],
        station_ids=[data.station_ids[0][:1], *data.station_ids[1:]],
    )
    held = only.station_ids[0][0]

    for model in (Idw(), Kriging()):
        out = model.fit(only, exclude_stations=[held]).predict_stations(only, [held])
        assert only.hours[0].hour not in set(out["utc"])


def test_kriging_in_a_constant_field_predicts_the_constant(data):
    field = constant_field(data)

    out = Kriging().fit(field, exclude_stations=["BBB"]).predict_stations(field, ["BBB"])

    np.testing.assert_allclose(out["nox_ppb_pred"], 42.0)


def test_kriging_at_a_known_station_without_noise_gives_its_value(data):
    out = Kriging(KrigingParams(nugget=1e-9)).fit(data).predict_stations(data, STATIONS)

    hour = data.hours[0]
    first = out[out["utc"] == hour.hour].set_index("station")["nox_ppb_pred"]
    for station, observed in zip(data.station_ids[0], hour.nox, strict=True):
        assert float(first.loc[station]) == pytest.approx(observed, abs=1e-3)


def test_kriging_far_from_the_stations_goes_back_to_the_mean_of_the_hour(data):
    near = Kriging(KrigingParams(length_scale_km=1e-3)).fit(data, exclude_stations=["BBB"])

    out = near.predict_stations(data, ["BBB"])

    hour, ids = data.hours[0], data.station_ids[0]
    assert out["nox_ppb_pred"].iloc[0] == pytest.approx(hour.nox[ids != "BBB"].mean(), rel=1e-3)
