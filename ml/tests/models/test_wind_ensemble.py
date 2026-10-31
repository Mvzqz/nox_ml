# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""X2: an ensemble of puff inversions over perturbed winds. The generic contract is `test_contract`, which
runs `SmallWindEnsemble`: the same class with a fixed-lifetime E2 and two members, since the default base
needs the OH loss rate of the inputs."""

from collections.abc import Callable
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest
from pydantic import Field

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import HourData
from nox_ml.models import REGISTRY, ModelParams
from nox_ml.models.ensemble import MemberConfig
from nox_ml.models.inversion_puff import InversionPuff, InversionPuffParams
from nox_ml.models.wind_ensemble import (
    WindEnsemble,
    WindEnsembleParams,
    WindMemberParams,
    WindPerturbation,
    perturbation_draws,
    perturbed_hour,
    perturbed_wind,
)

STATIONS = ["AAA", "BBB", "CCC"]
TINY_BASE = {"name": "inversion_puff", "params": {"lifetime": "fixed", "bootstrap_n": 5}}


class SmallWindEnsembleParams(WindEnsembleParams):
    """Small perturbations. The contract's synthetic truth has the unperturbed wind; with the default 30
    degrees
    the average over winds moves the levels of its 14 days by 10-15 % (the smoothing the ensemble is meant to
    give, reported in the notebook). The contract checks the machinery, not that smoothing."""

    base: MemberConfig = Field(default_factory=lambda: MemberConfig.model_validate(TINY_BASE))
    n_members: int = 2
    sigma_dir_deg: float = 2.0
    sigma_speed: float = 0.02
    sigma_pbl: float = 0.02


class SmallWindEnsemble(WindEnsemble):
    Params: ClassVar[type[ModelParams]] = SmallWindEnsembleParams


def small_ensemble(n_members: int = 3, sigma_dir_deg: float = 30.0, seed: int = 0) -> WindEnsemble:
    return WindEnsemble(
        WindEnsembleParams(
            base=MemberConfig.model_validate(TINY_BASE),
            n_members=n_members,
            sigma_dir_deg=sigma_dir_deg,
            sigma_speed=0.2,
            sigma_pbl=0.2,
            seed=seed,
        )
    )


def with_period_wind(data: Inputs) -> Inputs:
    """The inputs with the hourly wind of the whole period, as `load_inputs` gives them to the puffs."""
    stamps = pd.DatetimeIndex([h.hour for h in data.hours])
    index = pd.date_range(stamps.min().floor("D"), stamps.max() + pd.Timedelta(days=1), freq="h")
    rng = np.random.default_rng(11)
    wind = pd.DataFrame(rng.uniform(-3, 3, size=(len(index), 2)), columns=["u", "v"], index=index)
    return Inputs(
        data.hours,
        data.station_ids,
        data.station_xy,
        data.zones,
        data.points,
        data.no2_nox_ratio,
        data.n_regions,
        wind=wind,
    )


def test_the_draws_are_reproducible_from_the_seed():
    stamps = pd.date_range("2023-11-06", periods=48, freq="h")
    a = perturbation_draws(stamps, WindPerturbation(seed=3, sigma_dir_deg=20, sigma_speed=0.1, sigma_pbl=0.1))
    b = perturbation_draws(stamps, WindPerturbation(seed=3, sigma_dir_deg=20, sigma_speed=0.1, sigma_pbl=0.1))
    c = perturbation_draws(stamps, WindPerturbation(seed=4, sigma_dir_deg=20, sigma_speed=0.1, sigma_pbl=0.1))

    assert a.equals(b)
    assert not a.equals(c)


def test_the_hour_and_the_period_wind_get_the_same_perturbation():
    """An hour's wind is the same whether it comes from the hours or from the whole-period table, so the puffs
    are followed with the wind the hour itself was fitted with."""
    stamp = pd.Timestamp("2023-11-06 18:00")
    hour = HourData(
        hour=stamp,
        wind=(1.5, -2.0),
        pbl=800.0,
        stations=None,
        nox=np.array([]),
        pixels=None,
        no2=np.array([]),
    )
    period = pd.DataFrame(
        {"u": [1.5, 0.3], "v": [-2.0, 0.7]}, index=pd.DatetimeIndex([stamp, stamp.floor("D")])
    )
    draws = perturbation_draws(
        period.index.sort_values(), WindPerturbation(seed=9, sigma_dir_deg=30, sigma_speed=0.2, sigma_pbl=0.2)
    )

    from_hour = perturbed_hour(hour, draws)
    from_period = perturbed_wind(period, draws).loc[stamp]

    assert from_hour.wind == pytest.approx((from_period["u"], from_period["v"]))
    assert from_hour.pbl != hour.pbl, "the boundary layer height is perturbed too"


def test_zero_sigmas_give_the_base_model(make_inputs: Callable[..., Inputs]):
    data = make_inputs()
    base = InversionPuff(InversionPuffParams.model_validate(TINY_BASE["params"]))
    zero = WindEnsemble(
        WindEnsembleParams(
            base=MemberConfig.model_validate(TINY_BASE),
            n_members=2,
            sigma_dir_deg=0.0,
            sigma_speed=0.0,
            sigma_pbl=0.0,
        )
    )

    expected = base.fit(data).predict_stations(data, STATIONS)["nox_ppb_pred"].to_numpy()
    got = zero.fit(data).predict_stations(data, STATIONS)["nox_ppb_pred"].to_numpy()

    assert np.allclose(got, expected)


def test_members_have_their_own_transport_and_their_emissions_are_absolute(
    make_inputs: Callable[..., Inputs],
):
    data = with_period_wind(make_inputs())
    ensemble = small_ensemble(n_members=3).fit(data)

    keys = [member.transport_key() for member in ensemble._members]
    assert len(set(keys)) == 3, "each perturbation is its own transport in the Jacobian cache"
    assert len(data.jacobian_cache) == 3
    assert ensemble.estimate_emissions().kind == "absolute"


def test_without_the_period_wind_the_hours_are_the_history(make_inputs: Callable[..., Inputs]):
    """As the puff transport: with no whole-period wind, the winds of the fitted hours are followed."""
    data = make_inputs()
    ensemble = small_ensemble(n_members=2).fit(data)
    out = ensemble.predict_stations(data, STATIONS)

    assert out["nox_ppb_pred"].notna().all()


def test_a_perturbation_is_not_defined_with_the_stations_wind():
    with pytest.raises(ValueError, match="wind_field"):
        WindMemberParams.model_validate(
            {
                "wind_field": True,
                "perturbation": WindPerturbation(seed=1, sigma_dir_deg=10, sigma_speed=0.1, sigma_pbl=0.1),
            }
        )


def test_the_base_must_be_a_puff_inversion():
    with pytest.raises(ValueError, match="puff inversion"):
        WindEnsembleParams(base=MemberConfig.model_validate({"name": "inversion_plume"}))


def test_the_base_of_the_experiment_is_e2_without_the_field_wind():
    assert REGISTRY["wind_ensemble"] is WindEnsemble
    assert WindEnsembleParams().base.params.get("wind_field") in (None, False)
