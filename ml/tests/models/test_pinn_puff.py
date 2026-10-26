# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""E5b: the puff transport with the kernel of the PINN. The transport tests use the table of the exact
solution, so they need no torch and no training."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from exact_table import exact_table
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import Receptors, Sources, Transport, jacobian_hour_puff
from nox_ml.inversion.linear import History, HistoryTransport, hour_jacobians, road_sources
from nox_ml.models import REGISTRY
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.pinn.model import PinnPlume, PinnPuff
from nox_ml.models.pinn.params import PinnParams, PinnPuffParams
from nox_ml.models.pinn.puff import PinnPuffTransport, jacobian_hour_pinn_puff, radial_profile
from nox_ml.models.pinn.transport import jacobian_hour_pinn
from nox_ml.physics.puff import Trajectories, fixed_lifetime, local_hour_profile
from nox_ml.validation.experiment import read_config

CONFIGS = Path(__file__).parents[3] / "configs" / "experiments"
TABLE = exact_table()
TAU_H, U_MIN, PBL = 12.0, 2.0, 1000.0
T0 = pd.Timestamp("2024-03-01")
H = T0 + pd.Timedelta(hours=30)


def wind_series(u: float, v: float = 0.0, hours: int = 40) -> pd.DataFrame:
    return pd.DataFrame(
        {"u": np.full(hours, u), "v": np.full(hours, v)}, index=pd.date_range(T0, periods=hours, freq="h")
    )


def puff_transport(wind: pd.DataFrame, tau_h: float = TAU_H, max_age_h: int = 24) -> Transport:
    return Transport(Trajectories.from_wind(wind, U_MIN), fixed_lifetime(tau_h), lambda _h: 1.0, max_age_h)


def scene() -> tuple[Sources, Receptors, Receptors]:
    sources = Sources(
        point_x=np.array([0.0]),
        point_y=np.array([0.0]),
        cell_x=np.array([-2000.0, 1000.0]),
        cell_y=np.array([500.0, -500.0]),
        cell_prior=np.array([400.0, 100.0]),
        cell_zone=np.array([0, 1]),
        n_zones=2,
    )
    stations = Receptors(np.array([5000.0, 9000.0, 15_000.0]), np.array([0.0, 500.0, -1500.0]))
    return sources, stations, Receptors(np.array([20_000.0]), np.array([0.0]))


def pinn_puff(transport: Transport, wind=(3.0, 0.0), tau_h: float = TAU_H):
    sources, stations, pixels = scene()
    return jacobian_hour_pinn_puff(
        H, wind, PBL, transport, sources, stations, pixels, 0.7, TABLE, tau_h, U_MIN
    )


# --- the shape of a puff -------------------------------------------------------------------------------


@pytest.mark.parametrize("dist", [8_000.0, 30_000.0, 120_000.0])
def test_a_puff_keeps_its_unit_mass_wherever_it_has_travelled_even_beyond_the_table(dist):
    profile = radial_profile(TABLE, dist, dist / 3 / 3600, TAU_H)
    r = np.linspace(0, 100_000, 20_001)

    mass = np.trapezoid(profile(r) * 2 * np.pi * r, r)

    assert mass == pytest.approx(1.0, rel=0.02)


def test_a_puff_spreads_as_it_travels():
    near, far = (radial_profile(TABLE, d, d / 3 / 3600, TAU_H) for d in (8_000.0, 40_000.0))

    assert near(np.array([0.0]))[0] > far(np.array([0.0]))[0]


# --- the single puff without age is the PINN plume -----------------------------------------------------


def test_a_single_puff_without_age_is_the_jacobian_of_pinn_plume():
    sources, _, _ = scene()
    near = Receptors(
        np.array([5000.0, 7000.0]), np.array([0.0, 500.0])
    )  # all within 10.8 km, the hour's reach

    got = jacobian_hour_pinn_puff(
        H, (3.0, 0.0), PBL, puff_transport(wind_series(3.0), max_age_h=0), sources, near, near, 0.7,
        TABLE, TAU_H, U_MIN,
    )  # fmt: skip
    plume = jacobian_hour_pinn((3.0, 0.0), PBL, sources, near, near, 0.7, TABLE, TAU_H, U_MIN)

    assert_allclose(got.stations, plume.stations, rtol=1e-6)  # the table is float32
    assert_allclose(got.pixels, plume.pixels, rtol=1e-6)  # the table is float32


def test_the_plume_of_the_last_hour_stops_where_the_wind_has_not_carried_the_emission():
    out = pinn_puff(puff_transport(wind_series(3.0), max_age_h=0))

    assert (out.stations[0] > 0).all()  # 5 km
    assert_allclose(out.stations[2], 0.0)  # 15 km away, the hour only reached 10.8 km
    assert_allclose(out.pixels, 0.0)


# --- the puffs of the previous hours -------------------------------------------------------------------


def test_the_puffs_of_the_previous_hours_deliver_what_the_last_hour_has_not_reached():
    with_puffs = pinn_puff(puff_transport(wind_series(3.0)))
    last_hour = pinn_puff(puff_transport(wind_series(3.0), max_age_h=0))

    assert (with_puffs.stations[2] > last_hour.stations[2]).all()
    assert (with_puffs.pixels > last_hour.pixels).all()
    assert (with_puffs.stations >= last_hour.stations).all()


def test_the_puffs_remember_the_wind_of_the_hours_before_and_not_only_the_current_one():
    east_then_calm = wind_series(3.0)
    east_then_calm.iloc[30:] = (0.0, 0.0)
    north_then_east = wind_series(3.0)
    north_then_east.iloc[:30] = (0.0, 3.0)

    kept = pinn_puff(puff_transport(east_then_calm), wind=(0.0, 0.0))  # the hour itself is calm
    moved = pinn_puff(puff_transport(north_then_east))

    assert kept.stations.sum() > 0  # the puffs still travel east
    assert moved.stations[:2, 0].sum() < pinn_puff(puff_transport(wind_series(3.0))).stations[:2, 0].sum()


def test_a_shorter_lifetime_lowers_what_the_old_puffs_deliver():
    long_lived = pinn_puff(puff_transport(wind_series(3.0), tau_h=12.0), tau_h=12.0)
    short_lived = pinn_puff(puff_transport(wind_series(3.0), tau_h=3.0), tau_h=3.0)

    assert (short_lived.stations[2] < long_lived.stations[2]).all()


def test_a_zone_column_is_linear_in_the_prior_of_its_cells():
    sources, stations, pixels = scene()
    transport = puff_transport(wind_series(3.0))
    doubled = replace(sources, cell_prior=2 * sources.cell_prior)

    once = pinn_puff(transport)
    twice = jacobian_hour_pinn_puff(
        H, (3.0, 0.0), PBL, transport, doubled, stations, pixels, 0.7, TABLE, TAU_H, U_MIN
    )

    assert_allclose(twice.stations[:, 1:], 2 * once.stations[:, 1:])
    assert_allclose(twice.stations[:, 0], once.stations[:, 0])


def test_the_road_profile_scales_the_old_puffs_by_their_release_time():
    transport = puff_transport(wind_series(3.0))
    halved = replace(transport, road_profile=lambda _h: 0.5)

    full, half = pinn_puff(transport), pinn_puff(halved)

    assert_allclose(half.stations[:, 1:], full.stations[:, 1:] / 2)  # every road puff and the last hour halve
    assert_allclose(half.stations[:, 0], full.stations[:, 0])  # the point source has no profile


def test_a_receptor_without_stations_gives_empty_rows():
    sources, _, pixels = scene()
    transport = puff_transport(wind_series(3.0))

    out = jacobian_hour_pinn_puff(
        H, (3.0, 0.0), PBL, transport, sources, Receptors(np.array([]), np.array([])), pixels, 0.7,
        TABLE, TAU_H, U_MIN,
    )  # fmt: skip

    assert out.stations.shape == (0, sources.n_columns)
    assert out.pixels.shape == (1, sources.n_columns)


# --- it follows the Gaussian puffs within the error of the kernel ---------------------------------------


def test_the_full_jacobian_is_close_to_the_gaussian_puffs_where_the_kernel_is_calibrated():
    """The kernel matches the 30 degree Briggs plume within a factor 1.7 between 5 and 20 km
    (test_pinn_transport); the puffs add up pieces of it, so they keep that agreement."""
    sources, stations, pixels = scene()
    transport = puff_transport(wind_series(3.0))

    gaussian = jacobian_hour_puff(H, (3.0, 0.0), PBL, transport, sources, stations, pixels, 0.7)
    learned = pinn_puff(transport)

    for got, expected in ((learned.stations, gaussian.stations), (learned.pixels, gaussian.pixels)):
        ratio = got[:, :2] / expected[:, :2]
        assert ((ratio > 1 / 1.7) & (ratio < 1.7)).all()
    total = learned.stations.sum() / gaussian.stations.sum()
    assert 0.8 < total < 1.25  # and the mass they deliver is the same to about 20 %


# --- the model -----------------------------------------------------------------------------------------


def test_the_model_is_registered_and_is_the_inversion_with_another_transport():
    assert REGISTRY["pinn_puff"] is PinnPuff
    assert (PinnPuff.name, PinnPuff.role) == ("pinn_puff", "model")
    assert issubclass(PinnPuff, InversionPlume) and not issubclass(PinnPuff, PinnPlume)
    assert PinnPuff.Params is PinnPuffParams


def test_the_puff_age_does_not_retrain_the_network():
    assert PinnPuffParams(max_age_h=6).training_key() == PinnParams().training_key()


def test_the_puff_yaml_is_the_pinn_plume_one_with_the_puff_model():
    plume, puff = read_config(CONFIGS / "pinn_plume.yaml"), read_config(CONFIGS / "pinn_puff.yaml")

    assert puff.model.name == "pinn_puff"
    assert PinnPuffParams.model_validate(puff.model.params) == PinnPuffParams(
        kernel_dir=".cache/pinn", u_min=2.0, lifetime="oh"
    )
    assert puff.model_copy(update={"name": "pinn_plume", "model": plume.model}) == plume


def test_the_transport_key_never_collides_with_the_plume_the_pinn_plume_or_other_puff_settings():
    keys = {
        "plume": InversionPlume().transport_key(),
        "pinn_plume": PinnPlume().transport_key(),
        "puff": PinnPuff().transport_key(),
        "age": PinnPuff(PinnPuffParams(max_age_h=12)).transport_key(),
        "lifetime": PinnPuff(PinnPuffParams(tau_h=6.0)).transport_key(),
        "floor": PinnPuff(PinnPuffParams(u_min=2.0)).transport_key(),
        "kernel": PinnPuff(PinnPuffParams(width=32)).transport_key(),
        "kappa": PinnPuff(PinnPuffParams(kappa=3000.0)).transport_key(),
    }

    assert len(set(keys.values())) == len(keys)
    assert PinnPuff().transport_key() == PinnPuff(PinnPuffParams()).transport_key()


def test_the_three_transports_keep_their_own_jacobians_in_the_cache(make_inputs):
    inputs = make_inputs()

    for model in (InversionPlume(), PinnPlume(), PinnPuff()):
        model.fit(inputs)

    assert len(inputs.jacobian_cache) == 3


def test_the_cache_gives_the_jacobians_the_transport_builds(make_inputs):
    inputs = make_inputs()
    model = PinnPuff()

    cached = inputs.jacobians(model.transport_key(), model.transport())
    built = hour_jacobians(
        inputs.hours, inputs.zones, inputs.points, inputs.no2_nox_ratio, inputs.n_regions,
        jacobian=model.transport(), history=History(),
    )  # fmt: skip

    for a, b in zip(cached, built, strict=True):
        assert_allclose(a.stations, b.stations)
        assert_allclose(a.pixels, b.pixels)


def test_the_model_reads_the_hourly_wind_of_the_inputs_when_it_has_it(make_inputs):
    inputs = make_inputs()
    hour = inputs.hours[40]
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    full = pd.DataFrame(
        {"u": 3.0, "v": 0.0},
        index=pd.date_range(inputs.hours[0].hour - pd.Timedelta(days=1), inputs.hours[-1].hour, freq="h"),
    )
    transport = PinnPuff().transport()

    own_winds = transport.for_hours(inputs.hours, History())(hour, sources, inputs.no2_nox_ratio)
    hourly_wind = transport.for_hours(inputs.hours, History(wind=full))(hour, sources, inputs.no2_nox_ratio)

    assert not np.allclose(own_winds.stations, hourly_wind.stations)


def test_the_transport_is_a_history_transport_that_the_plume_models_are_not():
    assert isinstance(PinnPuffTransport(TABLE, TAU_H, U_MIN, 24), HistoryTransport)
    assert not isinstance(PinnPlume().transport(), HistoryTransport)


# --- the survival of the puffs: fixed or from the OH loss ---------------------------------------------------


def hour_matrix(make_inputs, transport: PinnPuffTransport, history: History):
    inputs = make_inputs()
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    return transport.for_hours(inputs.hours, history)(inputs.hours[40], sources, inputs.no2_nox_ratio)


def hourly_history(make_inputs, loss_per_s: float | None) -> History:
    inputs = make_inputs()
    index = pd.date_range(inputs.hours[0].hour - pd.Timedelta(days=2), inputs.hours[-1].hour, freq="h")
    wind = pd.DataFrame({"u": 3.0, "v": 0.0}, index=index)
    return History(wind=wind, loss_rate=None if loss_per_s is None else pd.Series(loss_per_s, index))


def test_the_lifetime_is_fixed_by_default_and_the_loss_rate_of_the_inputs_is_then_ignored(make_inputs):
    assert PinnPuffParams().lifetime == "fixed"
    transport = PinnPuff().transport()
    assert transport.lifetime == "fixed"

    without = hour_matrix(make_inputs, transport, hourly_history(make_inputs, None))
    with_loss = hour_matrix(make_inputs, transport, hourly_history(make_inputs, 1e-3))

    assert np.array_equal(without.stations, with_loss.stations)
    assert np.array_equal(without.pixels, with_loss.pixels)


def test_the_fixed_lifetime_builds_the_matrix_of_the_puffs_with_a_fixed_survival(make_inputs):
    inputs = make_inputs()
    history = hourly_history(make_inputs, None)
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    hour = inputs.hours[40]
    transport = Transport(
        Trajectories.from_wind(history.wind, U_MIN), fixed_lifetime(TAU_H), local_hour_profile(), 24
    )

    own = PinnPuffTransport(TABLE, TAU_H, U_MIN, 24).for_hours(inputs.hours, history)(
        hour, sources, inputs.no2_nox_ratio
    )
    explicit = jacobian_hour_pinn_puff(
        hour.hour, hour.wind, hour.pbl, transport, sources, hour.stations, hour.pixels,
        inputs.no2_nox_ratio, TABLE, TAU_H, U_MIN,
    )  # fmt: skip

    assert np.array_equal(own.stations, explicit.stations)
    assert np.array_equal(own.pixels, explicit.pixels)


def test_a_constant_oh_loss_equal_to_the_fixed_lifetime_gives_the_fixed_matrix(make_inputs):
    fixed = PinnPuffTransport(TABLE, TAU_H, U_MIN, 24, "fixed")
    oh = PinnPuffTransport(TABLE, TAU_H, U_MIN, 24, "oh")

    a = hour_matrix(make_inputs, fixed, hourly_history(make_inputs, None))
    b = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (TAU_H * 3600)))

    assert_allclose(b.stations, a.stations, rtol=1e-9)
    assert_allclose(b.pixels, a.pixels, rtol=1e-9)


def test_a_stronger_oh_loss_lowers_what_the_old_puffs_deliver(make_inputs):
    oh = PinnPuffTransport(TABLE, TAU_H, U_MIN, 24, "oh")

    slow = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (12 * 3600)))
    fast = hour_matrix(make_inputs, oh, hourly_history(make_inputs, 1 / (2 * 3600)))

    assert (fast.stations <= slow.stations).all() and (fast.stations < slow.stations).any()


def test_the_oh_lifetime_without_a_loss_rate_in_the_inputs_says_so(make_inputs):
    oh = PinnPuff(PinnPuffParams(lifetime="oh")).transport()

    with pytest.raises(ValueError, match="loss_rate"):
        hour_matrix(make_inputs, oh, hourly_history(make_inputs, None))


def test_the_oh_lifetime_changes_the_transport_key_and_does_not_retrain_the_network():
    fixed, oh = PinnPuff(), PinnPuff(PinnPuffParams(lifetime="oh"))

    assert fixed.transport_key() != oh.transport_key()
    assert PinnPuffParams(lifetime="oh").training_key() == PinnParams().training_key()


def test_the_synthetic_inputs_have_no_chemistry_so_the_other_models_are_untouched(make_inputs):
    inputs = make_inputs()

    assert inputs.chemistry is None and inputs.loss_rate is None
