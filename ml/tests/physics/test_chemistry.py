import numpy as np
import pandas as pd
from hypothesis import given
from hypothesis import strategies as st
from numpy.testing import assert_allclose

from nox_ml.physics.chemistry import (
    F_NO2,
    K_OH_NO2,
    OH_REF,
    cos_zenith,
    j_o1d,
    lifetime_h,
    nox_loss_rate,
    oh_production,
    reference_production,
)

o3 = st.floats(1, 150)
temperature = st.floats(0, 35)
humidity = st.floats(5, 100)
LOCAL_NOON_UTC = 18


def _noon_lifetime_h(day: str, o3_ppb: float, tmp_c: float, rh: float, p_ref: float, b: float = 1.0) -> float:
    t = pd.DatetimeIndex([f"{day} {LOCAL_NOON_UTC}:00"])
    p = oh_production(j_o1d(cos_zenith(t)), [o3_ppb], [tmp_c], [rh])
    return float(lifetime_h(nox_loss_rate(p, p_ref, b=b))[0])


@given(
    may_day=st.integers(1, 31),
    december_day=st.integers(1, 31),
    o3_ppb=o3,
    tmp_c=temperature,
    rh=humidity,
    p_ref=st.floats(1e-4, 10),
    b=st.floats(0.3, 1.5),
)
def test_lifetime_is_longer_in_december_than_in_may(may_day, december_day, o3_ppb, tmp_c, rh, p_ref, b):
    may = _noon_lifetime_h(f"2024-05-{may_day:02d}", o3_ppb, tmp_c, rh, p_ref, b)
    december = _noon_lifetime_h(f"2023-12-{december_day:02d}", o3_ppb, tmp_c, rh, p_ref, b)
    assert december > may


def test_lifetime_matches_the_research_values_at_noon():
    # Values from scripts/vida_quimica.py (research-archive) with O3 = 60 ppb, 20 C, RH = 40 %.
    april = pd.date_range("2024-04-15", periods=24, freq="h")
    p = pd.Series(oh_production(j_o1d(cos_zenith(april)), 60.0, 20.0, 40.0), april)
    p_ref = reference_production(p)
    assert_allclose(_noon_lifetime_h("2024-05-15", 60, 20, 40, p_ref), 5.67635931, rtol=1e-7)
    assert_allclose(_noon_lifetime_h("2023-12-15", 60, 20, 40, p_ref), 11.50342721, rtol=1e-7)


def test_lifetime_at_the_reference_noon_follows_from_the_rate_constants():
    expected_h = 1 / (K_OH_NO2 * OH_REF * F_NO2) / 3600
    assert_allclose(lifetime_h(nox_loss_rate(1.0, 1.0)), expected_h)
    assert_allclose(expected_h, 5.8566, rtol=1e-4)


@given(day=st.integers(1, 365), year=st.sampled_from([2019, 2023, 2024]))
def test_cos_zenith_is_a_cosine(day, year):
    t = pd.date_range(
        pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=day - 1), periods=24, freq="h"
    )
    assert np.all(np.abs(cos_zenith(t)) <= 1.0)


@given(day=st.integers(0, 364))
def test_there_is_no_loss_at_night(day):
    t = pd.date_range("2024-01-01", periods=24, freq="h") + pd.Timedelta(days=day)
    night = t[(t - pd.Timedelta(hours=6)).hour <= 3]  # 00-03 local
    p = oh_production(j_o1d(cos_zenith(night)), 40.0, 15.0, 50.0)
    assert not nox_loss_rate(p, 1.0).any()
    assert np.isnan(lifetime_h(nox_loss_rate(p, 1.0))).all()


@given(cz=st.lists(st.floats(-1, 1), min_size=1, max_size=20))
def test_photolysis_is_nonnegative_and_zero_with_the_sun_down(cz):
    j = j_o1d(cz)
    assert np.all(j >= 0)
    assert not j[np.array(cz) <= 0.02].any()


@given(low=st.floats(0.02, 1), high=st.floats(0.02, 1))
def test_photolysis_grows_with_the_sun_height(low, high):
    lo, hi = sorted((low, high))
    assert j_o1d(lo) <= j_o1d(hi)


@given(o3_ppb=st.floats(-10, 150), tmp_c=temperature, rh=humidity)
def test_oh_production_treats_ozone_below_one_ppb_as_one(o3_ppb, tmp_c, rh):
    assert_allclose(oh_production(1e-5, o3_ppb, tmp_c, rh), oh_production(1e-5, max(o3_ppb, 1.0), tmp_c, rh))


@given(p=st.floats(0, 5), p_ref=st.floats(0.1, 5), extra_h=st.floats(1, 48))
def test_extra_loss_shortens_the_lifetime(p, p_ref, extra_h):
    k_extra = 1 / (extra_h * 3600)
    base = nox_loss_rate(p, p_ref)
    assert nox_loss_rate(p, p_ref, k_extra=k_extra) == base + k_extra


def test_reference_production_averages_local_noon_of_april_2024():
    t = pd.date_range("2024-03-30", "2024-05-02", freq="h")
    local = t - pd.Timedelta(hours=6)
    p = pd.Series(np.where((local.month == 4) & (local.hour == 12), 3.0, 100.0), t)
    assert reference_production(p) == 3.0
