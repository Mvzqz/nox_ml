"""E2 `inversion_puff`: the puff transport of the inversion. The contract tests (`test_contract.py`) cover the
generic behavior; these cover what is specific to the puffs: their survival and their key."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import jacobian_hour_puff, standard_transport
from nox_ml.inversion.linear import History, road_sources
from nox_ml.models import REGISTRY
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.inversion_puff import InversionPuff, InversionPuffParams, PuffTransport
from nox_ml.physics.puff import local_hour_profile
from nox_ml.validation.loo import leave_one_out
from nox_ml.validation.tune import read_search, trials

TAU_H = 12.0


def hour_matrix(make_inputs, transport: PuffTransport, history: History):
    inputs = make_inputs()
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    return transport.for_hours(inputs.hours, history)(inputs.hours[40], sources, inputs.no2_nox_ratio)


def hourly_history(make_inputs, loss_per_s: float | None) -> History:
    inputs = make_inputs()
    index = pd.date_range(inputs.hours[0].hour - pd.Timedelta(days=2), inputs.hours[-1].hour, freq="h")
    wind = pd.DataFrame({"u": 3.0, "v": 0.0}, index=index)
    return History(wind=wind, loss_rate=None if loss_per_s is None else pd.Series(loss_per_s, index))


def test_e2_is_registered_and_its_default_lifetime_is_fixed():
    assert REGISTRY["inversion_puff"] is InversionPuff
    assert InversionPuffParams().lifetime == "fixed"


def test_the_oh_lifetime_without_a_loss_rate_in_the_inputs_says_so(make_inputs):
    oh = PuffTransport(max_age_h=24, lifetime="oh", tau_h=TAU_H)

    with pytest.raises(ValueError, match="loss_rate"):
        hour_matrix(make_inputs, oh, hourly_history(make_inputs, None))


def test_the_oh_matrix_is_the_standard_puff_matrix_of_the_research(make_inputs):
    """With the OH loss of the inputs, E2 builds the matrix of `jacobian_hour_puff` with `standard_transport`,
    the configuration verified against the research (`ml/tests/inversion/test_jacobian.py`)."""
    inputs = make_inputs()
    history = hourly_history(make_inputs, 1 / (TAU_H * 3600))
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    hour = inputs.hours[40]
    transport = standard_transport(history.wind, history.loss_rate, local_hour_profile())

    own = hour_matrix(make_inputs, PuffTransport(24, "oh", TAU_H), history)
    explicit = jacobian_hour_puff(
        hour.hour, hour.wind, hour.pbl, transport, sources, hour.stations, hour.pixels, inputs.no2_nox_ratio
    )

    assert np.array_equal(own.stations, explicit.stations)
    assert np.array_equal(own.pixels, explicit.pixels)


def test_a_constant_oh_loss_equal_to_the_fixed_lifetime_gives_the_fixed_matrix(make_inputs):
    fixed = PuffTransport(max_age_h=24, lifetime="fixed", tau_h=TAU_H)
    oh = PuffTransport(max_age_h=24, lifetime="oh", tau_h=TAU_H)

    a = hour_matrix(make_inputs, fixed, hourly_history(make_inputs, None))
    b = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (TAU_H * 3600)))

    assert_allclose(b.stations, a.stations, rtol=1e-9)
    assert_allclose(b.pixels, a.pixels, rtol=1e-9)


def test_a_stronger_oh_loss_lowers_what_the_old_puffs_deliver(make_inputs):
    oh = PuffTransport(max_age_h=24, lifetime="oh", tau_h=TAU_H)

    slow = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (12 * 3600)))
    fast = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (2 * 3600)))

    assert (fast.stations <= slow.stations).all() and (fast.stations < slow.stations).any()


def test_without_puffs_the_matrix_has_no_memory_of_the_wind_before_the_hour(make_inputs):
    """With no puffs (max_age_h = 0) the history is not read: the matrix is the last hour's plume alone."""
    inputs = make_inputs()
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    hour = inputs.hours[40]
    no_puffs = PuffTransport(max_age_h=0, lifetime="fixed", tau_h=TAU_H)

    a = no_puffs.for_hours(inputs.hours, hourly_history(make_inputs, None))(hour, sources, 0.7)
    b = no_puffs.for_hours(inputs.hours, History())(hour, sources, 0.7)

    assert_allclose(a.stations, b.stations, rtol=1e-12)


def test_the_puff_key_differs_from_the_plume_key_and_from_the_other_lifetimes():
    plume = InversionPlume().transport_key()
    fixed = InversionPuff().transport_key()
    oh = InversionPuff(InversionPuffParams(lifetime="oh")).transport_key()

    assert len({plume, fixed, oh}) == 3


def test_the_fixed_lifetime_takes_tau_h_into_its_key():
    a = InversionPuff(InversionPuffParams(tau_h=12.0)).transport_key()
    b = InversionPuff(InversionPuffParams(tau_h=6.0)).transport_key()

    assert a != b


# --- the cache of the Jacobians (`Inputs.jacobians`): the same numbers with or without it -------------


def test_cached_leave_one_out_fit_equals_the_fit_without_cache(make_inputs):
    inputs = make_inputs()
    InversionPuff().fit(inputs)  # the cache is warm, as after a full fit
    fresh = make_inputs()

    cached = InversionPuff().fit(inputs, exclude_stations=["BBB"])._state[2]
    rebuilt = InversionPuff().fit(replace(fresh, jacobian_cache={}), exclude_stations=["BBB"])._state[2]

    assert_allclose(cached.mean, rebuilt.mean, rtol=1e-9)
    assert_allclose(cached.cov, rebuilt.cov, rtol=1e-9)


def test_cached_leave_one_out_table_equals_the_one_with_a_fresh_cache_per_fold(make_inputs):
    inputs = make_inputs()
    fresh = make_inputs()

    class Fresh:
        """A model that starts every fold from inputs without cache."""

        def __init__(self):
            self.model = InversionPuff()

        def fit(self, data, *, exclude_stations=()):
            self.model.fit(replace(data, jacobian_cache={}), exclude_stations=exclude_stations)
            return self

        def predict_stations(self, data, stations):
            return self.model.predict_stations(replace(data, jacobian_cache={}), stations)

    cached_table, cached_oof = leave_one_out(inputs, InversionPuff)
    fresh_table, fresh_oof = leave_one_out(fresh, Fresh)  # pyright: ignore[reportArgumentType]

    assert_allclose(cached_table.to_numpy(), fresh_table.to_numpy(), rtol=1e-9)
    assert_allclose(cached_oof["nox_ppb_pred"], fresh_oof["nox_ppb_pred"], rtol=1e-9)


def test_each_puff_configuration_gets_its_own_jacobians(make_inputs):
    """Changing the age limit or the lifetime changes the matrix, so it must not reuse the cached one."""
    inputs = make_inputs()
    first = InversionPuff(InversionPuffParams(max_age_h=24))
    inputs.jacobians(first.transport_key(), first.transport())
    other = InversionPuff(InversionPuffParams(max_age_h=12))

    assert other.transport_key() not in inputs.jacobian_cache


# --- the tuning search (`nox-ml tune`) ---------------------------------------------------------------

SEARCH = Path(__file__).resolve().parents[3] / "configs" / "experiments" / "inversion_puff_tune.search.yaml"


def test_the_tuning_search_of_e2_is_valid_and_has_16_trials():
    space, base = read_search(SEARCH)

    assert base.model.name == "inversion_puff"
    assert len(trials(space, base)) == 16
