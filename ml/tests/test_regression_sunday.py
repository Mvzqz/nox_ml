from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, bootstrap_ratio, interval, ratio

SAMPLE = Path(__file__).parent / "fixtures" / "sunday_sample.csv"


@pytest.mark.regression
def test_sunday_to_weekday_ratio_matches_the_report():
    """Nov-Dec 2023 afternoons (sesgo_domingos.md): Sunday/weekday 0.65 (90 % CI 0.55-0.75), Saturday 0.89."""
    days = pd.read_csv(SAMPLE, parse_dates=["day"])

    sunday = ratio(days, WEEKDAY, SUNDAY_HOLIDAY)
    saturday = ratio(days, WEEKDAY, SATURDAY)
    lo, hi = interval(bootstrap_ratio(days, WEEKDAY, SUNDAY_HOLIDAY, 1000, np.random.default_rng(7)))

    assert sunday == pytest.approx(0.65, abs=0.01)
    assert saturday == pytest.approx(0.89, abs=0.01)
    assert lo == pytest.approx(0.55, abs=0.02)
    assert hi == pytest.approx(0.75, abs=0.02)
