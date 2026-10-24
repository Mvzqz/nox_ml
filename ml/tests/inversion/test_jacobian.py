from dataclasses import replace
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import (
    Receptors,
    Sources,
    jacobian_hour_puff,
    road_emission_profile,
    standard_transport,
)
from nox_ml.physics.puff import MAX_AGE_H, TRAFFIC_PROFILE

REFERENCE = Path(__file__).parents[1] / "fixtures" / "jacobian_reference.npz"
T0 = cast(pd.Timestamp, pd.Timestamp("2024-03-01 00:00"))
PBL = 1100.0
NO_LOSS = pd.Series(dtype=float)


def ts(text: str) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(text))


def receptors(x, y) -> Receptors:
    return Receptors(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(y, float)))


# --- reproduces the research output ---------------------------------------------------------------------

reference = np.load(REFERENCE)


@pytest.mark.regression
@pytest.mark.parametrize("k", range(len(reference["targets"])), ids=list(reference["targets"]))
def test_jacobian_reproduces_the_research_output_within_1e_9(k):
    """Scene and expected matrices from `puffs_cdmx.jacobian_puff_mx` of research-archive, standard
    configuration (`ml/tests/fixtures/make_jacobian_reference.py`): all three day types, a night hour, an
    hour without TEMPO, an hour without stations and puffs older than the wind record."""
    ref = reference
    hours = pd.date_range(str(ref["t0"]), periods=len(ref["u"]), freq="h")
    wind = pd.DataFrame({"u": ref["u"], "v": ref["v"]}, index=hours)
    infovial = {d: dict(enumerate(ref["infovial"][d])) for d in range(3)}
    transport = standard_transport(
        wind,
        pd.Series(ref["loss_rate"], hours),
        road_emission_profile(infovial, [str(d) for d in ref["holidays"]]),
    )
    sources = Sources(
        ref["point_x"],
        ref["point_y"],
        ref["cell_x"],
        ref["cell_y"],
        ref["cell_prior"],
        ref["cell_zone"],
        n_zones=4,
    )
    n_st = 5 if ref["stations_present"][k] else 0
    n_px = 7 if ref["pixels_present"][k] else 0
    h = ts(str(ref["targets"][k]))

    got = jacobian_hour_puff(
        h,
        (float(wind.loc[h, "u"]), float(wind.loc[h, "v"])),
        float(ref["pbl"][hours.get_loc(h)]),
        transport,
        sources,
        receptors(ref["station_x"][:n_st], ref["station_y"][:n_st]),
        receptors(ref["pixel_x"][:n_px], ref["pixel_y"][:n_px]),
        float(ref["ratio"]),
    )

    assert_allclose(got.stations, ref[f"stations_{k}"], rtol=1e-9, atol=0)
    assert_allclose(got.pixels, ref[f"pixels_{k}"], rtol=1e-9, atol=0)
    assert got.stations.shape == (n_st, 3 + 4)
    assert got.pixels.shape == (n_px, 3 + 4)


# --- properties -----------------------------------------------------------------------------------------


def _wind(u: float, v: float, hours: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {"u": np.full(hours, u), "v": np.full(hours, v)}, index=pd.date_range(T0, periods=hours, freq="h")
    )


def _jacobian(
    sources: Sources,
    stations: Receptors,
    pixels: Receptors | None = None,
    wind=(3.0, 0.0),
    loss: pd.Series = NO_LOSS,
    max_age_h: int = MAX_AGE_H,
):
    transport = replace(standard_transport(_wind(*wind), loss, lambda _h: 1.0), max_age_h=max_age_h)
    pixels = receptors([], []) if pixels is None else pixels
    h = cast(pd.Timestamp, T0 + pd.Timedelta(hours=25))
    return jacobian_hour_puff(h, wind, PBL, transport, sources, stations, pixels, 0.8)


def _scene(n_zones: int = 3, empty: int | None = None, prior_scale: float = 1.0) -> Sources:
    """One point source at the origin and 12 road cells around it, spread over `n_zones` zones."""
    rng = np.random.default_rng(3)
    zone = np.arange(12) % n_zones
    if empty is not None:
        zone = np.where(zone == empty, (empty + 1) % n_zones, zone)
    return Sources(
        np.array([0.0]),
        np.array([0.0]),
        rng.uniform(-6_000, 6_000, 12),
        rng.uniform(-6_000, 6_000, 12),
        rng.uniform(5, 50, 12) * prior_scale,
        zone,
        n_zones,
    )


NEAR = receptors([2_000.0, 5_000.0, 9_000.0], [500.0, -300.0, 1_000.0])


@given(scale=st.floats(0.01, 100))
def test_jacobian_is_linear_in_the_emission(scale):
    base = _jacobian(_scene(), NEAR, NEAR)
    scaled = _jacobian(_scene(prior_scale=scale), NEAR, NEAR)

    zones = slice(1, None)  # columns after the point source
    assert_allclose(scaled.stations[:, zones], scale * base.stations[:, zones], rtol=1e-12)
    assert_allclose(scaled.pixels[:, zones], scale * base.pixels[:, zones], rtol=1e-12)
    assert_allclose(scaled.stations[:, 0], base.stations[:, 0], rtol=1e-12)  # per t/yr, independent of priors


def test_a_zone_is_the_sum_of_its_cells():
    """Superposition: the zone column equals the columns of its cells computed one by one."""
    sources = _scene(n_zones=1)
    whole = _jacobian(sources, NEAR, NEAR)
    parts = [
        _jacobian(
            replace(
                sources,
                cell_x=sources.cell_x[[i]],
                cell_y=sources.cell_y[[i]],
                cell_prior=sources.cell_prior[[i]],
                cell_zone=sources.cell_zone[[i]],
            ),
            NEAR,
            NEAR,
        )
        for i in range(len(sources.cell_x))
    ]

    assert_allclose(whole.stations[:, 1], sum(p.stations[:, 1] for p in parts), rtol=1e-12)
    assert_allclose(whole.pixels[:, 1], sum(p.pixels[:, 1] for p in parts), rtol=1e-12)


@given(angle=st.floats(0, 2 * np.pi), distance=st.floats(500, 10_000))
def test_plume_gives_nothing_upwind_and_something_downwind(angle, distance):
    """Without puffs only the plume of the last hour is left: strictly zero upwind of the source."""
    wind = (3 * np.cos(angle), 3 * np.sin(angle))
    along = np.array([np.cos(angle), np.sin(angle)])
    sources = replace(_scene(), cell_x=np.array([0.0]), cell_y=np.array([0.0]), cell_prior=np.array([10.0]))
    sources = replace(sources, cell_zone=np.array([0]), n_zones=1)
    upwind = receptors(*(-distance * along))
    downwind = receptors(*(distance * along))

    up = _jacobian(sources, upwind, upwind, wind, max_age_h=0)
    down = _jacobian(sources, downwind, downwind, wind, max_age_h=0)

    assert not up.stations.any() and not up.pixels.any()
    assert (down.stations > 0).all() and (down.pixels > 0).all()


@given(angle=st.floats(0, 2 * np.pi), distance=st.floats(500, 10_000))
def test_puffs_reach_less_upwind_than_downwind_at_the_same_distance(angle, distance):
    """The wind-direction spread (30 degrees) leaves a tail upwind, but always smaller than downwind."""
    wind = (3 * np.cos(angle), 3 * np.sin(angle))
    along = np.array([np.cos(angle), np.sin(angle)])
    sources = _scene()
    upwind = receptors(*(-distance * along))
    downwind = receptors(*(distance * along))

    up = _jacobian(sources, upwind, upwind, wind)
    down = _jacobian(sources, downwind, downwind, wind)

    assert (up.stations[0, :1] < down.stations[0, :1]).all()  # the point source at the origin
    assert (up.pixels[0, :1] < down.pixels[0, :1]).all()


@given(empty=st.integers(0, 3))
def test_columns_of_a_zone_without_cells_are_zero(empty):
    sources = _scene(n_zones=4, empty=empty)

    jac = _jacobian(sources, NEAR, NEAR)

    column = 1 + empty
    assert not jac.stations[:, column].any() and not jac.pixels[:, column].any()
    other = [c for c in range(1, 5) if c != column]
    assert (jac.stations[:, other] > 0).all() and (jac.pixels[:, other] > 0).all()


def test_matrix_has_a_row_per_receptor_and_a_column_per_point_source_and_zone():
    jac = _jacobian(_scene(n_zones=5), NEAR, receptors([1_000.0], [0.0]))

    assert jac.stations.shape == (3, 1 + 5)
    assert jac.pixels.shape == (1, 1 + 5)


def test_an_hour_without_receptors_has_empty_rows():
    jac = _jacobian(_scene(), receptors([], []), receptors([], []))

    assert jac.stations.shape == (0, 1 + 3) and jac.pixels.shape == (0, 1 + 3)


def test_faster_chemical_loss_lowers_every_contribution():
    sources = _scene()
    hours = pd.date_range(T0 - pd.Timedelta(days=1), periods=80, freq="h")

    slow = _jacobian(sources, NEAR, NEAR, loss=pd.Series(1e-5, hours))
    fast = _jacobian(sources, NEAR, NEAR, loss=pd.Series(1e-4, hours))

    assert (fast.stations < slow.stations).all() and (fast.pixels < slow.pixels).all()


# --- transport and road profile -------------------------------------------------------------------------


def test_standard_transport_follows_24_h_puffs_with_the_loss_series():
    k = 2e-5  # 1/s
    hours = pd.date_range(T0 - pd.Timedelta(days=1), periods=80, freq="h")

    transport = standard_transport(_wind(1.0, 0.0), pd.Series(k, hours), lambda _h: 1.0)

    assert transport.max_age_h == 24
    assert_allclose(transport.survival(10.0, 14.0, 4.0), np.exp(-k * 3600 * 4), rtol=1e-9)


INFOVIAL = {
    0: dict.fromkeys(range(24), 0.5),
    1: dict.fromkeys(range(24), 0.4),
    2: dict.fromkeys(range(24), 0.3),
}


def test_road_profile_is_the_typical_profile_during_the_day_whatever_the_day_type():
    profile = road_emission_profile(INFOVIAL)

    assert profile(ts("2024-03-02 14:00")) == TRAFFIC_PROFILE[8]  # Saturday 08:00 local
    assert profile(ts("2024-03-03 14:00")) == TRAFFIC_PROFILE[8]  # Sunday


def test_road_profile_outside_the_day_uses_the_infovial_profile_of_the_local_day_type():
    profile = road_emission_profile(INFOVIAL, holidays=["2024-03-04"])

    assert profile(ts("2024-03-01 08:00")) == 0.5  # Friday 02:00 local
    assert profile(ts("2024-03-02 08:00")) == 0.4  # Saturday
    assert profile(ts("2024-03-03 08:00")) == 0.3  # Sunday
    assert profile(ts("2024-03-04 08:00")) == 0.3  # holiday Monday
    assert (
        profile(ts("2024-03-02 03:00")) == 0.5
    )  # Friday 21:00 local: the local day decides, not the UTC one
