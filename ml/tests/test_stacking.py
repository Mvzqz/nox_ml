# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Nested convex stacking on the out-of-fold predictions of the base models (docs/models.md, section 10)."""

import numpy as np
import pandas as pd
import pytest

from nox_ml.validation import stacking

STATIONS = ["AAA", "BBB", "CCC", "DDD"]


def frames(seed: int = 0, n: int = 60):
    """Observed rows and the oof of three models: ``good`` is the truth plus little noise, ``bad`` is off by a
    lot, ``half`` shares the error of ``good`` at a different scale (so the optimum mixes them)."""
    rng = np.random.default_rng(seed)
    index = pd.MultiIndex.from_product([STATIONS, range(n)], names=["station", "utc"]).to_frame(index=False)
    truth = rng.gamma(4.0, 10.0, len(index))
    observed = index.rename(columns={"utc": "h"}).assign(obs=truth)
    oof = {
        "good": index.assign(nox_ppb_pred=truth + rng.normal(0, 1, len(index))),
        "bad": index.assign(nox_ppb_pred=truth * 0.5 + rng.normal(0, 8, len(index))),
        "high": index.assign(nox_ppb_pred=truth * 1.4 + rng.normal(0, 1, len(index))),
    }
    return observed, oof


@pytest.mark.parametrize("rule", sorted(stacking.RULES))
def test_weights_are_convex(rule):
    observed, oof = frames()

    weights = stacking.fit_weights(observed, oof, rule)

    assert (weights >= 0).all()
    assert weights.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("rule", sorted(stacking.RULES))
def test_nested_weights_are_convex_for_every_station(rule):
    observed, oof = frames()

    weights = stacking.nested_weights(observed, oof, rule)

    assert list(weights.index) == STATIONS
    assert (weights.to_numpy() >= 0).all()
    np.testing.assert_allclose(weights.sum(axis=1), 1.0)


def test_stacking_recovers_the_exact_mixture_and_drops_a_useless_model():
    rng = np.random.default_rng(1)
    a, b, noise = rng.uniform(5, 50, 200), rng.uniform(5, 50, 200), rng.normal(0, 30, 200)
    observed = 0.7 * a + 0.3 * b

    weights = stacking.stack_weights(np.c_[a, b, noise], observed)

    assert weights == pytest.approx([0.7, 0.3, 0.0], abs=1e-3)


def test_stacking_beats_the_worst_model_and_matches_the_best_one_when_it_is_exact():
    rng = np.random.default_rng(2)
    truth = rng.uniform(5, 50, 100)

    weights = stacking.stack_weights(np.c_[truth, truth * 2 + 5], truth)

    assert weights == pytest.approx([1.0, 0.0], abs=1e-3)


def test_likelihood_weights_favor_the_model_with_the_smaller_error():
    rng = np.random.default_rng(3)
    truth = rng.uniform(5, 50, 100)
    predictions = np.c_[truth + rng.normal(0, 2, 100), truth + rng.normal(0, 4, 100)]

    weights = stacking.likelihood_weights(predictions, truth)

    assert weights[0] > weights[1]
    assert weights.sum() == pytest.approx(1.0)


def test_the_weights_of_a_station_do_not_use_that_station():
    observed, oof = frames()
    scrambled_obs = observed.assign(obs=np.where(observed["station"] == "BBB", 1000.0, observed["obs"]))
    scrambled_oof = {
        name: frame.assign(nox_ppb_pred=np.where(frame["station"] == "BBB", -50.0, frame["nox_ppb_pred"]))
        for name, frame in oof.items()
    }

    base = stacking.nested_weights(observed, oof)
    changed = stacking.nested_weights(scrambled_obs, scrambled_oof)

    pd.testing.assert_series_equal(base.loc["BBB"], changed.loc["BBB"])
    assert not np.allclose(base.loc["AAA"], changed.loc["AAA"])  # the others do learn from BBB


def test_the_prediction_of_a_station_uses_the_weights_learned_without_it():
    observed, oof = frames()

    combined, weights = stacking.nested_oof(observed, oof)

    rows = combined[combined["station"] == "CCC"].merge(
        oof["good"], on=["station", "utc"], suffixes=("", "_g")
    )
    expected = sum(
        weights.loc["CCC", name]
        * oof[name].query("station == 'CCC'").sort_values("utc")["nox_ppb_pred"].to_numpy()
        for name in oof
    )
    np.testing.assert_allclose(rows.sort_values("utc")["nox_ppb_pred"].to_numpy(), expected)
    assert list(combined.columns) == ["station", "utc", "nox_ppb_pred"]
    assert len(combined) == len(observed)


def test_the_nested_ensemble_is_no_worse_than_its_worst_member():
    observed, oof = frames()

    combined, _ = stacking.nested_oof(observed, oof)

    worst = max(stacking.loo_rmse(observed, frame) for frame in oof.values())
    assert stacking.loo_rmse(observed, combined) < worst


def test_nested_stacking_needs_two_stations():
    observed, oof = frames()
    one = {name: frame[frame["station"] == "AAA"] for name, frame in oof.items()}

    with pytest.raises(ValueError, match="two stations"):
        stacking.nested_weights(observed[observed["station"] == "AAA"], one)


def test_models_without_rows_in_common_cannot_be_combined():
    observed, oof = frames()
    oof["bad"] = oof["bad"].assign(utc=oof["bad"]["utc"] + 10_000)

    with pytest.raises(ValueError, match="in common"):
        stacking.fit_weights(observed, oof)
