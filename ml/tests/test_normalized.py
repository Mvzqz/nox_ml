import numpy as np
import pandas as pd
import pytest

from nox_ml.inversion.normalized import (
    bootstrap_ratio,
    day_type,
    difference_in_differences,
    interval,
    local_day,
    ratio,
)


def two_periods(make_hourly, drop=1.0, weather=1.0, noise=0.03, seed=0):
    """Hourly table of period 0 (reference) and period 1 (emission x ``drop``, ventilation x ``weather``)."""
    base = make_hourly(n_days=60, noise=noise, seed=seed)
    after = make_hourly(
        n_days=60,
        emission={d: drop for d in pd.date_range("2024-02-01", periods=60)},
        noise=noise,
        seed=seed + 1,
    )
    after["model"] *= weather
    after["obs"] *= weather
    after["day"] += pd.Timedelta(days=60)
    return pd.concat([base.assign(group=0), after.assign(group=1)], ignore_index=True)


def test_ratio_recovers_a_known_35_percent_drop(make_hourly):
    df = two_periods(make_hourly, drop=0.65)

    assert ratio(df, 0, 1) == pytest.approx(0.65, abs=0.03)


def test_ratio_discounts_weather_that_moves_concentration(make_hourly):
    # period 1 is 1.5x more stagnant, which cancels most of the 35 % drop in the raw concentration
    df = two_periods(make_hourly, drop=0.65, weather=1.5)
    raw = df[df.group == 1].obs.mean() / df[df.group == 0].obs.mean()

    assert raw == pytest.approx(0.65 * 1.5, abs=0.1)
    assert ratio(df, 0, 1) == pytest.approx(0.65, abs=0.03)


def test_ratio_is_nan_when_a_group_is_absent(make_hourly):
    df = two_periods(make_hourly)

    assert np.isnan(ratio(df, 0, 7))


def test_bootstrap_of_a_placebo_is_centered_on_one(make_hourly):
    df = two_periods(make_hourly, drop=1.0)

    samples = bootstrap_ratio(df, 0, 1, 400, np.random.default_rng(1))
    lo, hi = interval(samples)

    assert np.median(samples) == pytest.approx(1.0, abs=0.02)
    assert lo < 1.0 < hi


def test_bootstrap_interval_covers_a_known_drop(make_hourly):
    df = two_periods(make_hourly, drop=0.65)

    lo, hi = interval(bootstrap_ratio(df, 0, 1, 400, np.random.default_rng(1)))

    assert lo < 0.65 < hi
    assert hi - lo < 0.15


def test_bootstrap_is_reproducible_with_the_same_seed(make_hourly):
    df = two_periods(make_hourly, drop=0.8)

    a = bootstrap_ratio(df, 0, 1, 50, np.random.default_rng(3))
    b = bootstrap_ratio(df, 0, 1, 50, np.random.default_rng(3))

    np.testing.assert_array_equal(a, b)


def test_bootstrap_is_nan_when_a_group_is_absent(make_hourly):
    df = two_periods(make_hourly)

    assert np.isnan(bootstrap_ratio(df, 0, 7, 20, np.random.default_rng(0))).all()


def test_interval_ignores_nan_and_follows_the_level():
    samples = np.r_[np.arange(101.0), np.nan]

    assert interval(samples) == pytest.approx((5.0, 95.0))
    assert interval(samples, level=0.5) == pytest.approx((25.0, 75.0))


def test_difference_in_differences_removes_a_shared_seasonal_bias():
    rng = np.random.default_rng(0)
    control = np.full(100, 0.9)  # season alone lowers the index to 0.9 with no emission change
    target = 0.65 * control

    did = difference_in_differences(target, control, rng)

    np.testing.assert_allclose(did, 0.65)


def test_day_type_marks_sundays_and_holidays_apart_from_weekdays_and_saturdays():
    days = pd.date_range("2024-03-14", periods=7)  # Thursday ... Wednesday
    holidays = ["2024-03-18"]  # a Monday

    assert day_type(days, holidays).tolist() == [0, 0, 1, 2, 2, 0, 0]


def test_local_day_shifts_utc_to_mexico_city_time():
    utc = pd.Series(pd.to_datetime(["2024-03-15 05:59", "2024-03-15 06:00"]))

    assert local_day(utc).tolist() == pd.to_datetime(["2024-03-14", "2024-03-15"]).tolist()
    assert local_day(pd.DatetimeIndex(utc)).tolist() == pd.to_datetime(["2024-03-14", "2024-03-15"]).tolist()
