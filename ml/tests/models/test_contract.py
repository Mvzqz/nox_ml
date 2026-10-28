# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Every registered model passes these (docs/models.md, section 8); a new one is tested once registered."""

import time
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import yaml
from synthetic import PLACEBO_TOLERANCE, TOLERANCE, Synthetic, synthetic_dataset
from ventilation_synthetic import ventilation_synthetic

from nox_ml.models import REGISTRY
from nox_ml.models.base import ABSOLUTE_COLUMNS, PREDICTION_COLUMNS, RELATIVE_COLUMNS
from nox_ml.validation import experiment
from nox_ml.validation.experiment import ExperimentConfig, Placebo, model_placebo, run_experiment

STATIONS = ["AAA", "BBB", "CCC"]
LEARN_FROM_WEATHER = {
    "rf_deweather",
    "gb_deweather",
}  # no forward model: judged on stations where weather sets the NOx


@pytest.fixture(params=sorted(REGISTRY))
def model_cls(request, monkeypatch):
    if request.param == "pinn_seeds":  # the default networks take minutes to train: same class, tiny networks
        from test_pinn_seeds import SmallPinnSeeds

        monkeypatch.setitem(REGISTRY, "pinn_seeds", SmallPinnSeeds)
    return REGISTRY[request.param]


@pytest.fixture
def own_synthetic(model_cls, make_inputs) -> Synthetic:
    """The fixture with observations simulated by the forward model of the model under test, when it has one
    (`transport()`): a model is judged on data from its own physics. Another physics moves the absolute
    level by 25-40 % (the cross twin of reports/pinn_prototipo.md), which is not a defect of the estimator.
    A model that learns concentration from the weather has no forward model and needs weeks of hours to
    learn it (two Sundays are fingerprinted by their wind, not separated from it): it gets 8 weeks of
    stations with known Sunday ratio (`ventilation_synthetic`)."""
    if model_cls.name in LEARN_FROM_WEATHER:
        return ventilation_synthetic()
    transport = getattr(model_cls(), "transport", None)
    return synthetic_dataset(make_inputs(), jacobian=transport() if transport else None)


def test_fits_and_predicts_on_the_fixture_in_under_30_seconds(model_cls, synthetic: Synthetic):
    start = time.perf_counter()

    model = model_cls().fit(synthetic.data)
    model.predict_stations(synthetic.data, STATIONS)
    if model.role == "model":
        model.estimate_emissions()

    assert time.perf_counter() - start < 30


def test_prediction_frame_has_the_contract_columns_and_a_value_for_every_station_row(
    model_cls, synthetic: Synthetic
):
    data = synthetic.data

    out = model_cls().fit(data).predict_stations(data, STATIONS)

    assert list(out.columns) == PREDICTION_COLUMNS
    assert len(out) == data.n_station_rows
    assert out["nox_ppb_pred"].notna().all()
    assert set(out["station"]) == set(STATIONS)


def test_predict_returns_only_the_requested_stations(model_cls, synthetic: Synthetic):
    out = model_cls().fit(synthetic.data).predict_stations(synthetic.data, ["BBB"])

    assert set(out["station"]) == {"BBB"}
    assert len(out) == len(synthetic.data.hours)


def test_same_seed_gives_identical_predictions(model_cls, synthetic: Synthetic):
    a = model_cls().fit(synthetic.data).predict_stations(synthetic.data, STATIONS)
    b = model_cls().fit(synthetic.data).predict_stations(synthetic.data, STATIONS)

    pd.testing.assert_frame_equal(a, b)


def test_fit_never_reads_the_excluded_station(model_cls, synthetic: Synthetic):
    data = synthetic.data
    rng = np.random.default_rng(0)
    scrambled = replace(
        data,
        hours=[
            replace(h, nox=np.where(ids == "BBB", rng.uniform(0, 500, len(ids)), h.nox))
            for h, ids in zip(data.hours, data.station_ids, strict=True)
        ],
    )

    a = model_cls().fit(data, exclude_stations=["BBB"])
    b = model_cls().fit(scrambled, exclude_stations=["BBB"])

    pd.testing.assert_frame_equal(
        a.predict_stations(data, ["AAA", "CCC"]), b.predict_stations(data, ["AAA", "CCC"])
    )
    if a.role == "model":
        pd.testing.assert_frame_equal(a.estimate_emissions().table, b.estimate_emissions().table)


def test_params_round_trip_through_yaml(model_cls):
    params = model_cls.Params()

    text = yaml.safe_dump(params.model_dump(mode="json"))

    assert model_cls.Params.model_validate(yaml.safe_load(text)) == params


def test_params_reject_unknown_fields(model_cls):
    with pytest.raises(ValueError, match="not_a_param"):
        model_cls.Params.model_validate({"not_a_param": 1})


def test_a_model_estimates_emissions_in_the_schema_of_its_kind(model_cls, synthetic: Synthetic):
    if model_cls.role != "model":
        pytest.skip("references only predict concentrations")

    estimate = model_cls().fit(synthetic.data).estimate_emissions().validate()

    columns = ABSOLUTE_COLUMNS if estimate.kind == "absolute" else RELATIVE_COLUMNS
    assert list(estimate.table.columns) == columns
    assert np.isfinite(estimate.table["mean"]).all()


def test_a_model_recovers_the_synthetic_emissions(model_cls, own_synthetic: Synthetic):
    synthetic = own_synthetic
    if model_cls.role != "model":
        pytest.skip("references only predict concentrations")

    estimate = model_cls().fit(synthetic.data).estimate_emissions()

    if estimate.kind == "absolute":
        for row in estimate.table.itertuples():
            assert row.mean == pytest.approx(synthetic.truth_t_yr[row.zone, row.day_type], rel=TOLERANCE)
    assert estimate.day_type_ratio("sunday_holiday") == pytest.approx(synthetic.sunday_ratio, rel=TOLERANCE)


def test_a_placebo_without_emission_change_is_centered_on_one(model_cls, own_synthetic: Synthetic):
    synthetic = own_synthetic
    if model_cls.role != "model":
        pytest.skip("references only predict concentrations")

    placebo = model_placebo(synthetic.data, model_cls, Placebo(refits=4))

    assert placebo["center"] == pytest.approx(1.0, abs=PLACEBO_TOLERANCE)


def test_the_run_writes_out_of_fold_predictions_never_made_with_the_held_out_station(
    model_cls, synthetic: Synthetic, tmp_path, monkeypatch
):
    monkeypatch.setattr(experiment, "load_inputs", lambda *args: synthetic.data)
    config = ExperimentConfig.model_validate(
        {
            "name": "contract",
            "period": {"start": "2023-11-06", "end": "2023-11-19"},
            "model": {"name": model_cls.name},
            "placebo": {"n": 20, "refits": 2},
        }
    )

    out = run_experiment(config, tmp_path)

    oof = pd.read_parquet(out / "oof.parquet")
    in_sample = model_cls().fit(synthetic.data).predict_stations(synthetic.data, STATIONS)
    assert list(oof.columns) == PREDICTION_COLUMNS
    assert len(oof) == synthetic.data.n_station_rows
    assert not oof.duplicated(["station", "utc"]).any()
    for station in STATIONS:
        fold = model_cls().fit(synthetic.data, exclude_stations=[station])
        expected = fold.predict_stations(synthetic.data, [station])["nox_ppb_pred"].to_numpy()
        got = oof[oof["station"] == station]["nox_ppb_pred"].to_numpy()
        held_in = in_sample[in_sample["station"] == station]["nox_ppb_pred"].to_numpy()
        np.testing.assert_allclose(got, expected)
        assert not np.allclose(got, held_in)  # an in-sample row would match the full fit
    assert (out / "emissions.parquet").exists() == (model_cls.role == "model")
