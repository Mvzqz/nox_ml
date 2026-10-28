"""Atypical periods of the calendar: year-end and Easter."""

import pandas as pd

from nox_ml.data.calendar import atypical_days, easter_holidays, year_end


def test_the_year_end_spans_guadalupe_to_epiphany():
    days = year_end(2023)

    assert (days[0], days[-1]) == (pd.Timestamp("2023-12-12"), pd.Timestamp("2024-01-06"))


def test_easter_holidays_are_holy_week_and_the_week_after():
    days = easter_holidays(2024)  # Easter Sunday: 31 March

    assert (days[0], days[-1]) == (pd.Timestamp("2024-03-25"), pd.Timestamp("2024-04-07"))
    assert len(days) == 14


def test_a_window_gets_the_periods_that_touch_it_cut_to_the_window():
    days = atypical_days("2024-01-01", "2024-05-31")

    assert bool(days[0] == pd.Timestamp("2024-01-01"))  # the end of the 2023 year-end
    assert pd.Timestamp("2024-01-06") in days and pd.Timestamp("2024-01-08") not in days
    assert set(easter_holidays(2024)) <= set(days)
    assert bool(days[-1] == pd.Timestamp("2024-04-07"))


def test_a_normal_window_has_no_atypical_days():
    assert atypical_days("2023-11-01", "2023-11-30").empty
