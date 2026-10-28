# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""X3: the PINN puff model averaged over several networks. The generic contract is `test_contract`, which runs
`SmallPinnSeeds` (the same class with small networks, so that it trains in seconds)."""

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import Field

from nox_ml.data.inputs import MAX_CACHED_TRANSPORTS, Inputs
from nox_ml.models import REGISTRY, EmissionEstimate, ModelParams
from nox_ml.models.ensemble import MemberConfig
from nox_ml.models.pinn.model import PinnPuff
from nox_ml.models.pinn.params import PinnPuffParams
from nox_ml.models.pinn.seeds import PinnSeeds, PinnSeedsParams

CONFIGS = Path(__file__).parents[3] / "configs" / "experiments"
STATIONS = ["AAA", "BBB", "CCC"]
TINY = {"layers": 2, "width": 16, "adam_steps": 20, "lbfgs_rounds": 1, "bootstrap_n": 20}
TINY_BASE = {"name": "pinn_puff", "params": TINY}


def small_params(seeds=(1, 2)) -> PinnSeedsParams:
    return PinnSeedsParams.model_validate({"base": TINY_BASE, "seeds": list(seeds)})


class SmallPinnSeedsParams(PinnSeedsParams):
    """Defaults of networks that train in seconds (the contract tests build models from the defaults)."""

    base: MemberConfig = Field(default_factory=lambda: MemberConfig.model_validate(TINY_BASE))
    seeds: list[int] = Field(default_factory=lambda: [1, 2])


class SmallPinnSeeds(PinnSeeds):
    Params: ClassVar[type[ModelParams]] = SmallPinnSeedsParams


def tiny_puff(seed: int) -> PinnPuff:
    return PinnPuff(PinnPuffParams(**TINY, seed=seed))


def estimate_table(estimate: EmissionEstimate) -> pd.DataFrame:
    return estimate.table.set_index(["zone", "day_type"])


# --- configuration ---------------------------------------------------------------------------------------


def test_it_is_registered_as_a_model_and_defaults_to_four_seeds_of_e5b_with_equal_weights():
    model = REGISTRY["pinn_seeds"]()

    assert REGISTRY["pinn_seeds"].role == "model"
    assert [m.params.seed for m in model._members] == [0, 1, 2, 3]
    assert all(isinstance(m, PinnPuff) for m in model._members)
    np.testing.assert_allclose(model.weights, 0.25)


def test_the_default_base_is_the_model_of_the_pinn_puff_config():
    config = yaml.safe_load((CONFIGS / "pinn_puff.yaml").read_text())["model"]
    expected = PinnPuffParams.model_validate(config["params"]).model_dump(mode="json")

    got = PinnSeedsParams().base

    assert got.name == config["name"]
    assert got.params == expected


def test_the_experiment_config_is_the_default_ensemble_of_the_pinn_puff_config():
    config = yaml.safe_load((CONFIGS / "pinn_seeds.yaml").read_text())
    puff = yaml.safe_load((CONFIGS / "pinn_puff.yaml").read_text())

    params = PinnSeedsParams.model_validate(config["model"]["params"])

    assert params == PinnSeedsParams()
    assert config["period"] == puff["period"] and config["placebo"] == puff["placebo"]


def test_each_member_is_the_base_with_its_own_seed():
    members = PinnSeedsParams().members()

    assert [m.params["seed"] for m in members] == [0, 1, 2, 3]
    assert {tuple((k, str(v)) for k, v in m.params.items() if k != "seed") for m in members} == {
        tuple((k, str(v)) for k, v in members[0].params.items() if k != "seed")
    }


def test_two_seeds_have_different_transport_keys():
    a, b = tiny_puff(1), tiny_puff(2)

    assert a.transport_key() != b.transport_key()


def test_more_seeds_than_the_jacobian_cache_holds_are_refused_with_a_clear_error():
    PinnSeedsParams(seeds=list(range(MAX_CACHED_TRANSPORTS)))  # exactly the capacity is fine

    with pytest.raises(
        ValueError, match=rf"{MAX_CACHED_TRANSPORTS + 1} seeds.*holds {MAX_CACHED_TRANSPORTS}"
    ):
        PinnSeedsParams(seeds=list(range(MAX_CACHED_TRANSPORTS + 1)))


@pytest.mark.parametrize(
    "update, match",
    [
        ({"seeds": []}, "at least 1"),
        ({"seeds": [1, 1]}, "distinct"),
        ({"base": {"name": "inversion_plume"}}, "PINN"),
        ({"base": {"name": "nope"}}, "unknown member"),
    ],
)
def test_seeds_must_be_distinct_and_the_base_a_pinn_model(update, match):
    with pytest.raises(ValueError, match=match):
        PinnSeedsParams.model_validate(update)


# --- behavior --------------------------------------------------------------------------------------------


@pytest.fixture
def inputs(make_inputs: Callable[..., Inputs]) -> Inputs:
    return make_inputs()


def test_one_seed_is_e5b_with_that_seed(inputs: Inputs):
    seeds = PinnSeeds(small_params(seeds=[3])).fit(inputs)
    alone = tiny_puff(3).fit(inputs)

    pd.testing.assert_frame_equal(
        seeds.predict_stations(inputs, STATIONS), alone.predict_stations(inputs, STATIONS)
    )
    got, expected = seeds.estimate_emissions(), alone.estimate_emissions()
    assert got.kind == expected.kind == "absolute"
    np.testing.assert_allclose(estimate_table(got)["mean"], estimate_table(expected)["mean"])
    np.testing.assert_allclose(estimate_table(got)["sd"], estimate_table(expected)["sd"])


def test_the_prediction_is_the_mean_of_the_networks(inputs: Inputs):
    model = PinnSeeds(small_params(seeds=[1, 2])).fit(inputs)

    first, second = (m.predict_stations(inputs, STATIONS)["nox_ppb_pred"].to_numpy() for m in model._members)

    np.testing.assert_allclose(
        model.predict_stations(inputs, STATIONS)["nox_ppb_pred"].to_numpy(), (first + second) / 2
    )


def test_emissions_are_absolute_and_the_sd_adds_the_dispersion_between_networks(inputs: Inputs):
    model = PinnSeeds(small_params(seeds=[1, 2])).fit(inputs)

    got = model.estimate_emissions().validate()

    members = [estimate_table(m.estimate_emissions()) for m in model._members]
    means = np.stack([t["mean"].to_numpy() for t in members])
    within = np.stack([t["sd"].to_numpy() ** 2 for t in members]).mean(axis=0)
    between = means.var(axis=0)
    table = estimate_table(got)
    assert got.kind == "absolute"
    np.testing.assert_allclose(table["mean"], means.mean(axis=0))
    assert (between > 0).all(), "the two networks must differ for this test to mean anything"
    np.testing.assert_allclose(table["sd"] ** 2, within + between)
    assert (table["sd"] ** 2 > within).all()


def test_the_level_is_shared_only_when_every_member_is_absolute():
    model = PinnSeeds(small_params(seeds=[1, 2]))
    absolute = EmissionEstimate("absolute", pd.DataFrame(columns=["zone", "day_type", "mean", "sd"]))
    relative = EmissionEstimate("relative", pd.DataFrame(columns=["zone", "day_type", "mean", "lo", "hi"]))

    assert model.shares_absolute_level([absolute, absolute])
    assert not model.shares_absolute_level([absolute, relative])
    assert tiny_puff(1).transport_key() != tiny_puff(2).transport_key()  # the contract rule would say no
