# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""The sheets: each question with its estimator, the verdict against the placebo, the days a measure needs."""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy.stats import norm
from test_events import BUSINESS_MEASURES, make_model, scaled
from ventilation_synthetic import ventilation_inputs

from nox_ml.models import REGISTRY
from nox_ml.validation import products
from nox_ml.validation.experiment import Placebo

WEEK = pd.date_range("2023-11-27", "2023-12-01")  # Monday to Friday, no contingency nor atypical day
PLACEBO = Placebo(refits=40, seed=2, level=0.90)


@pytest.fixture(scope="module")
def base():
    # the emission varies 15 % from one day to the next, as in the real data
    inputs = ventilation_inputs(n_days=56, sunday=1.0, noise=0.1)
    days = pd.date_range("2023-11-06", periods=56)
    return scaled(inputs, dict(zip(days, np.random.default_rng(4).lognormal(0, 0.15, 56), strict=True)))


def sheet(inputs, **kwargs):
    return products.measure_result(inputs, make_model, WEEK, BUSINESS_MEASURES, PLACEBO, **kwargs)


def test_every_question_has_a_registered_estimator_with_a_config():
    for question, name in products.ESTIMATORS.items():
        assert name in REGISTRY
        assert products.estimator(question)().name == name


def test_a_large_drop_is_detected_and_no_change_is_not(base):
    dropped = sheet(scaled(base, dict.fromkeys(WEEK, 0.5)))
    unchanged = sheet(base)

    assert dropped["verdict"] == "decrease" and dropped["change"] < -0.25
    assert unchanged["verdict"] == "undetectable"
    low, high = unchanged["range"]
    assert low < 0 < high
    assert 0 < unchanged["detectable_drop"] < 1


def test_a_claim_fits_when_it_is_in_the_range(base):
    result = sheet(base, claim=0.0)

    assert result["claim"] == {"change": 0.0, "fits": True}
    assert sheet(base, claim=-0.9)["claim"]["fits"] is False


def test_the_verdict_reads_the_ratio_against_the_placebo():
    assert products.verdict(0.7, 0.8, 1.2) == "decrease"
    assert products.verdict(1.3, 0.8, 1.2) == "increase"
    assert products.verdict(0.9, 0.8, 1.2) == "undetectable"


@given(st.floats(0.02, 0.6), st.floats(0.1, 0.8))
def test_the_days_needed_invert_the_extrapolated_detection(drop, cv):
    k = products.days_needed(drop, cv)

    z = norm.ppf(0.95) + norm.ppf(products.POWER)
    assert 1 - np.exp(-z * cv * np.sqrt(2 / k)) <= drop + 1e-9  # k days are enough
    if k > 1:
        assert 1 - np.exp(-z * cv * np.sqrt(2 / (k - 1))) > drop - 1e-9  # one day fewer is not


def test_the_sheets_say_the_verdict_the_range_and_the_claim(base):
    text = products.render_measure(sheet(base, claim=-0.3), "Prueba", ("2023-11-06", "2023-12-31"))

    assert text.startswith("# Prueba") and "No se detecta" in text and "Cambio anunciado" in text
    days = products.render_days([(0.1, 120)], 0.46, ("2023-11-01", "2023-12-31"))
    assert "| 10% | 120 (unas 24 semanas) |" in days


def test_a_measure_as_long_as_the_reference_uses_the_extrapolated_spread(base):
    long = pd.date_range(
        "2023-11-13", "2023-12-31"
    )  # most business days: fewer normal ones than measure days

    result = products.measure_result(
        scaled(base, dict.fromkeys(long, 0.5)), make_model, long, BUSINESS_MEASURES, PLACEBO
    )

    assert result["method"] == "extrapolated"
    assert result["n_days"] >= result["days"]["n_normal"]
    assert result["verdict"] == "decrease"
    low, high = result["range"]
    assert low < result["change"] < high and 0 < result["detectable_drop"] < 1


def test_a_measure_in_an_atypical_period_carries_a_warning(base):
    year_end = pd.date_range("2023-12-18", "2023-12-22")

    result = products.measure_result(base, make_model, year_end, BUSINESS_MEASURES, PLACEBO)

    assert result["atypical_share"] == 1.0
    assert "Advertencia" in products.render_measure(result, "Fin de año", ("2023-11-06", "2023-12-31"))
    assert sheet(base)["atypical_share"] == 0.0


def test_a_few_atypical_days_get_a_note_not_a_warning(base):
    result = products.measure_result(base, make_model, WEEK, BUSINESS_MEASURES, PLACEBO) | {
        "atypical_share": 0.2
    }

    text = products.render_measure(result, "Prueba", ("2023-11-06", "2023-12-31"))

    assert "Nota: 20%" in text and "Advertencia" not in text


def test_two_equal_seasons_keep_the_change_and_narrow_the_range():
    season = {"change": -0.2, "range": (-0.35, -0.02), "n_days": 9, "atypical_share": 0.0}

    one = products.combine_seasons([season])
    two = products.combine_seasons([season, season], claim=-0.2)

    assert two["change"] == pytest.approx(-0.2) and two["weights"] == [0.5, 0.5]
    assert two["range"][1] - two["range"][0] < one["range"][1] - one["range"][0]
    assert two["detectable_drop"] < one["detectable_drop"]
    assert two["claim"] == {"change": -0.2, "fits": True}
    text = products.render_seasons(
        [season, season], two, "Dos temporadas", [("2023-11-01", "2023-12-31"), ("2024-11-01", "2024-12-31")]
    )
    assert "18 días hábiles en 2 temporadas" in text and "| 2024-11-01 a 2024-12-31 | 9 |" in text


def test_seasons_after_2024_read_openaq():
    assert products.sources_for("2024-11-01", "2024-12-31").wind == "network"
    later = products.sources_for("2025-02-15", "2025-05-31")
    assert later.simat_nox == "openaq_nox_2025-02-15_2025-06-01.parquet" and later.wind == "airports"
