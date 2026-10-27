# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Ensemble-specific behavior: members as configs, convex weights and the absolute / relative rule.

The generic contract (fit, predict, leakage, emissions, run artifacts) is `test_contract`, which covers
`convex_ensemble`."""

import numpy as np
import pandas as pd
import pytest
from synthetic import Synthetic

from nox_ml.models import REGISTRY, EmissionEstimate
from nox_ml.models.ensemble import ConvexEnsemble, EnsembleParams, combine_absolute, combine_relative
from nox_ml.validation.experiment import ExperimentConfig

STATIONS = ["AAA", "BBB", "CCC"]
PLUME = {"name": "inversion_plume", "params": {"bootstrap_n": 5}}
LS = {"name": "regularized_ls", "params": {"bootstrap_n": 5}}


def ensemble(members: list[dict], weights: list[float] | None = None) -> ConvexEnsemble:
    return ConvexEnsemble(EnsembleParams.model_validate({"members": members, "weights": weights}))


def absolute(weekday: float, sunday: float, sd: float = 1.0) -> EmissionEstimate:
    rows = [(z, d, m, sd) for z in (0, 1) for d, m in (("weekday", weekday), ("sunday_holiday", sunday))]
    return EmissionEstimate("absolute", pd.DataFrame(rows, columns=["zone", "day_type", "mean", "sd"]))


def relative(sunday: float, half_width: float = 0.1) -> EmissionEstimate:
    rows = [
        (np.nan, "weekday", 1.0, 1.0, 1.0),
        (np.nan, "sunday_holiday", sunday, sunday - half_width, sunday + half_width),
    ]
    return EmissionEstimate("relative", pd.DataFrame(rows, columns=["zone", "day_type", "mean", "lo", "hi"]))


def test_the_ensemble_is_a_registered_model_that_estimates_emissions():
    assert REGISTRY["convex_ensemble"].role == "model"


def test_members_are_stored_as_experiment_configs_with_every_default_filled_in():
    config = ExperimentConfig.model_validate(
        {
            "name": "ens",
            "period": {"start": "2023-11-06", "end": "2023-11-19"},
            "model": {"name": "convex_ensemble", "params": {"members": [{"name": "rf_deweather"}, PLUME]}},
        }
    )

    members = config.model.params["members"]

    assert members[0]["name"] == "rf_deweather"
    assert "n_trees" in members[0]["params"] or len(members[0]["params"]) > 1
    assert members[1]["params"]["sigma_theta_deg"] == 15.0


@pytest.mark.parametrize(
    "members, match",
    [
        ([PLUME], "at least 2"),
        ([PLUME, {"name": "idw"}], "base model"),
        ([PLUME, {"name": "convex_ensemble"}], "base model"),
        ([PLUME, {"name": "nope"}], "unknown member"),
        ([PLUME, {"name": "regularized_ls", "params": {"alpha_typo": 1}}], "alpha_typo"),
    ],
)
def test_members_must_be_two_or_more_registered_base_models(members, match):
    with pytest.raises(ValueError, match=match):
        EnsembleParams.model_validate({"members": members})


@pytest.mark.parametrize("weights", [[0.5, 0.6], [1.5, -0.5], [1.0], [0.2, 0.3, 0.5]])
def test_weights_must_be_convex_and_one_per_member(weights):
    with pytest.raises(ValueError, match="weights"):
        EnsembleParams.model_validate({"members": [PLUME, LS], "weights": weights})


def test_no_weights_means_the_simple_average_of_the_predictions(synthetic: Synthetic):
    data = synthetic.data
    both = ensemble([PLUME, LS]).fit(data).predict_stations(data, STATIONS)
    a = ensemble([PLUME, LS]).fit(data)  # members fitted once more to get their own predictions
    first, second = (m.predict_stations(data, STATIONS) for m in a._members)

    expected = (first["nox_ppb_pred"].to_numpy() + second["nox_ppb_pred"].to_numpy()) / 2

    np.testing.assert_allclose(both["nox_ppb_pred"].to_numpy(), expected)


def test_a_weight_of_one_gives_that_member(synthetic: Synthetic):
    data = synthetic.data
    only_ls = ensemble([PLUME, LS], [0.0, 1.0]).fit(data).predict_stations(data, STATIONS)

    alone = REGISTRY["regularized_ls"](REGISTRY["regularized_ls"].Params(bootstrap_n=5)).fit(data)

    np.testing.assert_allclose(
        only_ls["nox_ppb_pred"].to_numpy(), alone.predict_stations(data, STATIONS)["nox_ppb_pred"].to_numpy()
    )


def test_members_with_the_same_transport_give_absolute_emissions_as_the_weighted_mean(synthetic: Synthetic):
    model = ensemble([PLUME, LS], [0.25, 0.75]).fit(synthetic.data)

    got = model.estimate_emissions()

    first, second = (m.estimate_emissions().table.set_index(["zone", "day_type"]) for m in model._members)
    assert got.kind == "absolute"
    expected = 0.25 * first["mean"] + 0.75 * second["mean"]
    np.testing.assert_allclose(
        got.table.set_index(["zone", "day_type"])["mean"].reindex(expected.index), expected
    )


def test_members_with_different_transports_give_relative_emissions(synthetic: Synthetic):
    wide = {"name": "inversion_plume", "params": {"bootstrap_n": 5, "sigma_theta_deg": 30.0}}

    got = ensemble([PLUME, wide]).fit(synthetic.data).estimate_emissions().validate()

    assert got.kind == "relative"
    assert got.table["zone"].isna().all()  # pooled over zones


def test_a_relative_member_makes_the_ensemble_relative(synthetic: Synthetic):
    got = ensemble([PLUME, {"name": "normalized_ratio"}]).fit(synthetic.data).estimate_emissions().validate()

    assert got.kind == "relative"


def test_absolute_combination_adds_the_disagreement_between_members_to_the_sd():
    estimates = [absolute(100, 60, sd=2.0), absolute(120, 80, sd=2.0)]

    got = combine_absolute(estimates, np.array([0.5, 0.5])).table.set_index(["zone", "day_type"])

    assert got.loc[(0, "weekday"), "mean"] == pytest.approx(110)
    assert got.loc[(0, "weekday"), "sd"] == pytest.approx(np.sqrt(2.0**2 + 10**2))


def test_relative_combination_averages_the_indices_and_their_bounds():
    got = combine_relative([relative(0.6), relative(0.8, half_width=0.2)], np.array([0.5, 0.5]))

    sunday = got.table[got.table["day_type"] == "sunday_holiday"].iloc[0]
    assert (sunday["mean"], sunday["lo"], sunday["hi"]) == pytest.approx((0.7, 0.55, 0.85))
    assert got.day_type_ratio("sunday_holiday") == pytest.approx(0.7)


def test_an_absolute_member_enters_a_relative_ensemble_as_its_sunday_over_weekday_index():
    got = combine_relative([absolute(100, 50), relative(0.7)], np.array([0.5, 0.5]))

    assert got.day_type_ratio("sunday_holiday") == pytest.approx(0.6)
    assert (got.table["lo"] <= got.table["hi"]).all()
