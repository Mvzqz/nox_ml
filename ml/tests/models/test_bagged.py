# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""X1: bagging of an inversion. The generic contract is `test_contract`, which runs `SmallBagged` (the same
class with a fixed-lifetime E2 and two bags, since the default base needs the OH loss rate of the inputs)."""

from collections.abc import Callable
from typing import ClassVar

import numpy as np
import pytest
from pydantic import Field

from nox_ml.data.inputs import Inputs
from nox_ml.models import REGISTRY, EmissionEstimate, ModelParams
from nox_ml.models import bagged as bagged_module
from nox_ml.models.bagged import BaggedInversion, BaggedInversionParams
from nox_ml.models.ensemble import MemberConfig
from nox_ml.models.inversion_plume import block_draw
from nox_ml.models.inversion_puff import InversionPuff, InversionPuffParams

STATIONS = ["AAA", "BBB", "CCC"]
TINY_BASE = {"name": "inversion_puff", "params": {"lifetime": "fixed", "bootstrap_n": 5}}


class SmallBaggedParams(BaggedInversionParams):
    base: MemberConfig = Field(default_factory=lambda: MemberConfig.model_validate(TINY_BASE))
    n_bags: int = 2


class SmallBagged(BaggedInversion):
    Params: ClassVar[type[ModelParams]] = SmallBaggedParams


def small_bagged(n_bags: int = 3, block_days: int = 1, seed: int = 0) -> BaggedInversion:
    return BaggedInversion(
        BaggedInversionParams(
            base=MemberConfig.model_validate(TINY_BASE), n_bags=n_bags, block_days=block_days, seed=seed
        )
    )


def base_puff() -> InversionPuff:
    return InversionPuff(InversionPuffParams.model_validate(TINY_BASE["params"]))


def test_block_draw_draws_as_many_days_as_there_are():
    rng = np.random.default_rng(0)
    for block in (1, 3):
        counts = block_draw(14, block, rng)
        assert counts.sum() == 14
        assert len(counts) == 14


def test_the_bags_are_the_base_model_on_resampled_days(make_inputs: Callable[..., Inputs]):
    data: Inputs = make_inputs()
    bagged = small_bagged(n_bags=3).fit(data)

    assert len(bagged._members) == 3
    means = [member._state[2].mean for member in bagged._members]
    assert not np.allclose(means[0], means[1]), "different draws of the days must give different posteriors"
    assert {m.transport_key() for m in bagged._members} == {base_puff().transport_key()}


def test_one_bag_without_resampling_is_the_base(make_inputs: Callable[..., Inputs], monkeypatch):
    """With every day counted once, each bag solves exactly the base's system: the predictions are equal."""
    data: Inputs = make_inputs()
    monkeypatch.setattr(bagged_module, "block_draw", lambda n, block, rng: np.ones(n, dtype=int))

    base = base_puff().fit(data).predict_stations(data, STATIONS)
    bagged = small_bagged(n_bags=2).fit(data).predict_stations(data, STATIONS)

    assert np.allclose(base["nox_ppb_pred"].to_numpy(), bagged["nox_ppb_pred"].to_numpy())


def test_same_seed_same_bags(make_inputs: Callable[..., Inputs]):
    data: Inputs = make_inputs()
    first = small_bagged(seed=4).fit(data).estimate_emissions().table
    second = small_bagged(seed=4).fit(data).estimate_emissions().table
    other = small_bagged(seed=5).fit(data).estimate_emissions().table

    assert first.equals(second)
    assert not first["sd"].equals(other["sd"])


def test_emissions_are_absolute_with_the_spread_between_bags(make_inputs: Callable[..., Inputs]):
    data: Inputs = make_inputs()
    estimate: EmissionEstimate = small_bagged(n_bags=4).fit(data).estimate_emissions()

    assert estimate.kind == "absolute"
    assert (estimate.table["sd"] > 0).all()


def test_the_base_must_be_an_inversion():
    with pytest.raises(ValueError, match="base must be an inversion"):
        BaggedInversionParams(base=MemberConfig.model_validate({"name": "rf_deweather"}))


def test_it_is_registered_under_its_name():
    assert REGISTRY["bagged_inversion"] is BaggedInversion
