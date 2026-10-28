"""Atypical periods: business days whose activity is not that of a normal business day.

A normal business day is the reference of every ratio (Sunday / weekday, event / normal). Two recurring
periods are not normal and move it:

- **year-end**, from the Virgin of Guadalupe (12 December) to the Epiphany (6 January). In nov-dec 2023 its
  business days had 75 % more afternoon NOx with usual ventilation, while the traffic of the same dates in
  2018 was that of a normal day (Infovial): an accumulation the models take for emission
  (`context/knowledge/sesgo_domingo.md`). Without them the Sunday / weekday of the estimators rises from
  0.53-0.56 to 0.63-0.75;
- **Easter**, Holy Week and the week after (the school holidays), from the Monday before Easter to the Sunday
  after it.

Holidays are already Sundays (`inversion.linear.HOLIDAYS`); these periods add the business days around them.
"""

from datetime import date, timedelta

import pandas as pd
from dateutil.easter import easter

YEAR_END = ((12, 12), (1, 6))  # (month, day) of the first and the last day, across the new year


def year_end(year: int) -> pd.DatetimeIndex:
    """The year-end period that starts in December of `year`."""
    (m0, d0), (m1, d1) = YEAR_END
    return pd.date_range(date(year, m0, d0), date(year + 1, m1, d1), freq="D")


def easter_holidays(year: int) -> pd.DatetimeIndex:
    """Holy Week and the week after Easter Sunday of `year`, Monday to Sunday."""
    sunday = easter(year)
    return pd.date_range(sunday - timedelta(days=6), sunday + timedelta(days=7), freq="D")


def atypical_days(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Every day of an atypical period between `start` and `end` (inclusive)."""
    first, last = pd.Timestamp(pd.Timestamp(start).date()), pd.Timestamp(pd.Timestamp(end).date())
    days: set[pd.Timestamp] = set()
    for year in range(int(first.year) - 1, int(last.year) + 1):
        days.update(year_end(year))
        days.update(easter_holidays(year))
    return pd.DatetimeIndex(sorted(d for d in days if first <= d <= last))
