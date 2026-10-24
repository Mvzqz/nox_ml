import numpy as np
import pandas as pd
import pytest

from nox_ml.validation.placebo import (
    bootstrap_interval,
    daily_table,
    episodes,
    estimate,
    hourly_to_daily,
    placebo,
    reference_days,
)

EVENTS = list(pd.date_range("2024-03-12", periods=8, freq="9D"))  # every 9 days


def table(make_hourly, drop=1.0, stagnation=1.0, holidays=()):
    """Daily table whose event days have emission x ``drop`` and ventilation x ``stagnation``."""
    hourly = make_hourly(
        emission={d: drop for d in EVENTS}, model_scale={d: stagnation for d in EVENTS}, seed=2
    )
    return daily_table(hourly, holidays)


def test_daily_table_keeps_days_with_enough_hours_and_flags_holidays_as_sunday(make_hourly):
    hourly = make_hourly(n_days=10)
    hourly = hourly.drop(hourly[hourly.day == "2024-02-03"].index[2:])  # 2 hours left on a Saturday

    d = daily_table(hourly, holidays=["2024-02-05"])  # a Monday

    assert pd.Timestamp("2024-02-03") not in d.index
    assert d.loc["2024-02-05", "weekday"] == 6
    assert d.loc["2024-02-06", "weekday"] == 1
    assert d.hours.eq(6).all()
    assert d.stagnation.eq(d.model / 6).all()


def test_daily_table_averages_the_extra_columns(make_hourly):
    hourly = make_hourly(n_days=3).assign(pbl=100.0)

    assert daily_table(hourly, extras=["pbl"]).pbl.eq(100.0).all()


def test_hourly_to_daily_keeps_only_the_requested_local_hours():
    # UTC 17-22 h are 11-16 h local on the same day; UTC 05 h is 23 h local the day before
    h = pd.to_datetime(["2024-03-14 05:00"] + [f"2024-03-15 {x}:00" for x in range(17, 23)])
    hourly = pd.DataFrame({"h": h, "obs": 1.0, "model": 2.0})

    d = hourly_to_daily(hourly, (11, 16))

    assert d.index.tolist() == [pd.Timestamp("2024-03-15")]
    assert d.hours.iloc[0] == 6
    assert d.obs.iloc[0] == 6.0


def test_reference_days_share_the_weekday_stay_in_the_window_and_skip_excluded(make_hourly):
    d = table(make_hourly)
    day = EVENTS[0]

    refs = reference_days(d, day, excluded=set(EVENTS), window=28)

    assert refs, "expected at least one reference"
    assert all(r.day_of_week == day.day_of_week and abs((r - day).days) <= 28 for r in refs)
    assert not set(refs) & set(EVENTS)


def test_reference_days_of_a_holiday_are_sundays(make_hourly):
    d = table(make_hourly, holidays=["2024-03-12"])  # a Tuesday holiday

    holiday = EVENTS[0]  # 2024-03-12
    refs = reference_days(d, holiday, excluded={holiday})

    assert refs
    assert all(r.day_of_week == 6 for r in refs)


def test_estimate_recovers_a_known_35_percent_drop(make_hourly):
    d = table(make_hourly, drop=0.65)

    e = estimate(d, EVENTS, set(EVENTS))

    assert e is not None
    assert e["emission"] == pytest.approx(0.65, abs=0.05)


def test_estimate_separates_stagnant_weather_from_emission(make_hourly):
    # event days are 1.6x more stagnant: concentration looks unchanged but emission fell 35 %
    d = table(make_hourly, drop=0.65, stagnation=1.6)

    e = estimate(d, EVENTS, set(EVENTS))

    assert e is not None
    assert e["concentration"] == pytest.approx(0.65 * 1.6, abs=0.15)
    assert e["meteorology"] == pytest.approx(1.6, abs=0.2)
    assert e["emission"] == pytest.approx(0.65, abs=0.05)


def test_estimate_is_none_without_reference_days(make_hourly):
    d = table(make_hourly)

    assert estimate(d, EVENTS, excluded=set(d.index)) is None


def test_placebo_without_emission_change_is_centered_on_one(make_hourly):
    d = table(make_hourly, drop=1.0)
    pool = np.ones(len(d), dtype=bool)

    samples = placebo(d, EVENTS, pool, 200, np.random.default_rng(0))

    assert len(samples) == 200
    assert np.median(samples) == pytest.approx(1.0, abs=0.02)
    assert np.percentile(samples, 5) < 1.0 < np.percentile(samples, 95)


def test_placebo_pool_restricts_the_fake_days(make_hourly):
    d = table(make_hourly)
    only_march = np.asarray(pd.DatetimeIndex(d.index).month == 3)

    samples = placebo(d, EVENTS[:2], only_march, 20, np.random.default_rng(0))

    assert len(samples) == 20


def test_a_real_drop_falls_below_the_placebo_distribution(make_hourly):
    d = table(make_hourly, drop=0.65)
    samples = placebo(d, EVENTS, np.ones(len(d), dtype=bool), 200, np.random.default_rng(0))

    e = estimate(d, EVENTS, set(EVENTS))

    assert e is not None
    assert e["emission"] < np.percentile(samples, 5)


def test_placebo_is_empty_when_the_pool_has_no_days(make_hourly):
    d = table(make_hourly)

    assert len(placebo(d, EVENTS, np.zeros(len(d), dtype=bool), 5, np.random.default_rng(0))) == 0


def test_bootstrap_interval_covers_a_known_drop(make_hourly):
    d = table(make_hourly, drop=0.65)

    lo, hi = bootstrap_interval(d, EVENTS, set(EVENTS), 200, np.random.default_rng(0))

    assert lo < 0.65 < hi
    assert hi - lo < 0.2


def test_bootstrap_interval_is_nan_without_reference_days(make_hourly):
    d = table(make_hourly)

    lo, hi = bootstrap_interval(d, EVENTS, set(d.index), 10, np.random.default_rng(0))

    assert np.isnan(lo) and np.isnan(hi)


def test_episodes_group_consecutive_days():
    days = pd.to_datetime(["2024-03-01", "2024-03-02", "2024-03-05", "2024-03-09", "2024-03-10"])

    assert [len(e) for e in episodes(list(days))] == [2, 1, 2]
