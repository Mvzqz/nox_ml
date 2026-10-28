from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

import nox_ml.inversion.jacobian as jacobian_module
from nox_ml.data.inputs import MAX_CACHED_TRANSPORTS
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import hour_systems, solve
from nox_ml.models.inversion_plume import InversionPlume, InversionPlumeParams
from nox_ml.models.inversion_puff import InversionPuff, InversionPuffParams
from nox_ml.time import local_day
from nox_ml.validation.loo import leave_one_out

N_REGIONS = 2
SIGMA_THETA = np.deg2rad(15.0)


def rebuilt_systems(inputs, held_out):
    """Reference: the systems built from the hours without the station, no cache involved."""
    return hour_systems(
        inputs.without_stations([held_out]), inputs.zones, inputs.points, inputs.no2_nox_ratio, N_REGIONS
    )


def test_cached_systems_without_a_station_equal_the_rebuilt_ones(make_inputs):
    inputs = make_inputs()
    inputs.jacobians(*plume_transport(SIGMA_THETA, 1.0))  # fill the cache with every station

    cached = hour_systems(
        inputs.without_stations(["BBB"]),
        inputs.zones,
        inputs.points,
        inputs.no2_nox_ratio,
        N_REGIONS,
        jacobians=inputs.jacobians_without_stations(["BBB"], *plume_transport(SIGMA_THETA, 1.0)),
    )

    for a, b in zip(cached, rebuilt_systems(inputs, "BBB"), strict=True):
        assert_allclose(a.info, b.info, rtol=1e-9)
        assert_allclose(a.gradient, b.gradient, rtol=1e-9)
        assert_allclose(a.jacobian.stations, b.jacobian.stations, rtol=1e-9)


@pytest.mark.parametrize("station", ["AAA", "BBB", "CCC"])
def test_cached_leave_one_out_fit_equals_the_rebuilt_one(make_inputs, station):
    inputs = make_inputs()
    InversionPlume().fit(inputs)  # the cache is warm, as after a full fit

    cached = InversionPlume().fit(inputs, exclude_stations=[station])._state[2]
    systems = rebuilt_systems(inputs, station)
    rebuilt = solve(systems, inputs.points, N_REGIONS)

    assert_allclose(cached.mean, rebuilt.mean, rtol=1e-9)
    assert_allclose(cached.cov, rebuilt.cov, rtol=1e-9)


def test_cached_leave_one_out_table_equals_the_one_with_a_fresh_cache_per_fold(make_inputs):
    inputs = make_inputs()
    fresh = make_inputs()

    class Fresh:
        """A model that starts every fold from inputs without cache."""

        def __init__(self):
            self.model = InversionPlume()

        def fit(self, data, *, exclude_stations=()):
            self.model.fit(replace(data, jacobian_cache={}), exclude_stations=exclude_stations)
            return self

        def predict_stations(self, data, stations):
            return self.model.predict_stations(replace(data, jacobian_cache={}), stations)

    cached_table, cached_oof = leave_one_out(inputs, InversionPlume)
    fresh_table, fresh_oof = leave_one_out(fresh, Fresh)  # pyright: ignore[reportArgumentType]

    assert_allclose(cached_table.to_numpy(), fresh_table.to_numpy(), rtol=1e-9)
    assert_allclose(cached_oof["nox_ppb_pred"], fresh_oof["nox_ppb_pred"], rtol=1e-9)


def test_leave_one_out_builds_the_jacobians_once_per_transport_config(make_inputs, monkeypatch):
    inputs = make_inputs()
    calls = []
    original = jacobian_module.jacobian_hour_plume
    monkeypatch.setattr(
        jacobian_module, "jacobian_hour_plume", lambda *a, **k: calls.append(1) or original(*a, **k)
    )

    leave_one_out(inputs, InversionPlume)  # 3 held-out stations, one fit and one prediction each

    assert len(calls) == len(inputs.hours)


def test_another_transport_config_gets_its_own_jacobians(make_inputs):
    inputs = make_inputs()
    base = InversionPlume().fit(inputs)._state[2]

    wider = InversionPlume(InversionPlumeParams.model_validate({"sigma_theta_deg": 30})).fit(inputs)._state[2]

    assert len(inputs.jacobian_cache) == 2
    assert not np.allclose(base.mean, wider.mean)


def test_the_cache_keeps_a_bounded_number_of_configs(make_inputs):
    inputs = make_inputs()

    u_mins = 1.0 + 0.1 * np.arange(MAX_CACHED_TRANSPORTS + 2)
    for u_min in u_mins:
        inputs.jacobians(*plume_transport(SIGMA_THETA, float(u_min)))

    assert len(inputs.jacobian_cache) == MAX_CACHED_TRANSPORTS
    assert plume_transport(SIGMA_THETA, float(u_mins[0]))[0] not in inputs.jacobian_cache  # the oldest left


def test_relabeling_days_shares_the_cache_and_selecting_days_does_not(make_inputs):
    inputs = make_inputs()
    inputs.jacobians(*plume_transport(SIGMA_THETA, 1.0))

    assert inputs.with_day_kinds({}).jacobian_cache is inputs.jacobian_cache
    assert inputs.on_days([inputs.hours[0].hour.normalize()]).jacobian_cache == {}


def with_wind_history(inputs):
    """The inputs with the hourly wind of the whole period, as `load_inputs` gives them: every hour of the
    days and the day before, so the puffs of the first afternoon have a history."""
    rng = np.random.default_rng(3)
    index = pd.date_range(
        inputs.hours[0].hour.normalize() - pd.Timedelta(days=1), inputs.hours[-1].hour, freq="h"
    )
    wind = pd.DataFrame(
        {"u": rng.uniform(-3, 3, len(index)), "v": rng.uniform(-3, 3, len(index))}, index=index
    )
    for h in inputs.hours:
        wind.loc[h.hour] = h.wind
    return replace(inputs, wind=wind)


TRANSPORTS = {
    "plume": lambda: plume_transport(SIGMA_THETA, 1.0),
    "puff": lambda: (lambda m: (m.transport_key(), m.transport()))(
        InversionPuff(InversionPuffParams(lifetime="fixed"))
    ),
}


@pytest.mark.parametrize("transport", sorted(TRANSPORTS))
def test_a_subset_of_days_keeps_the_cached_matrices_of_its_hours_and_they_are_exact(make_inputs, transport):
    inputs = with_wind_history(make_inputs())
    key, fn = TRANSPORTS[transport]()
    full = inputs.jacobians(key, fn)
    days = pd.DatetimeIndex(sorted({local_day(h.hour) for h in inputs.hours}))[::3]

    subset = inputs.on_days(days)
    rebuilt = replace(subset, jacobian_cache={}).jacobians(key, fn)

    assert key in subset.jacobian_cache  # nothing rebuilt
    kept = subset.jacobian_cache[key]
    assert len(kept) == len(subset.hours) < len(full)
    for a, b in zip(kept, rebuilt, strict=True):
        assert_allclose(a.stations, b.stations, rtol=1e-12)
        assert_allclose(a.pixels, b.pixels, rtol=1e-12)


def test_without_the_wind_history_a_subset_of_days_starts_an_empty_cache(make_inputs):
    inputs = make_inputs()
    inputs.jacobians(*plume_transport(SIGMA_THETA, 1.0))

    assert inputs.on_days([local_day(inputs.hours[0].hour)]).jacobian_cache == {}
