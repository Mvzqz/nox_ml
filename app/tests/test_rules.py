"""Business rules of context/UI_BUSINESS_CONTEXT.md, section 3."""

from datetime import date

import pytest

from nox_app import rules

PILOT = {"name": "Piloto", "start": "2026-06-01", "end": "2026-07-24", "target": -0.10, "coverage": 0.86,
         "result": {"change": -0.12, "lo": -0.19, "hi": -0.05}}  # fmt: skip


@pytest.mark.parametrize(
    ("coverage", "level"),
    [
        (0.90, "valid"),
        (0.75, "valid"),
        (0.74, "preliminary"),
        (0.50, "preliminary"),
        (0.49, "insufficient"),
        (None, "insufficient"),
    ],
)
def test_coverage_thresholds(coverage, level):
    assert rules.coverage_level(coverage) == level


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 5, 31), rules.SCHEDULED),
        (date(2026, 6, 1), rules.RUNNING),
        (date(2026, 7, 24), rules.RUNNING),
        (date(2026, 8, 6), rules.WAITING),  # the data arrive about two weeks late
        (date(2026, 8, 7), rules.PRELIMINARY),
        (date(2026, 9, 7), rules.CONSOLIDATED),
    ],
)
def test_the_life_cycle_follows_the_dates_and_the_data_lag(today, expected):
    assert rules.status(PILOT, today) == expected


def test_a_pilot_without_dates_is_a_draft_and_one_without_valid_coverage_stays_preliminary():
    assert rules.status({**PILOT, "start": None, "end": None}, date(2026, 1, 1)) == rules.DRAFT
    assert rules.status({**PILOT, "coverage": 0.6}, date(2027, 1, 1)) == rules.PRELIMINARY


def test_a_finished_pilot_without_a_result_waits_for_data():
    assert rules.status({**PILOT, "result": None}, date(2027, 1, 1)) == rules.WAITING


def test_dates_are_fixed_once_the_pilot_starts():
    assert rules.dates_editable(PILOT, date(2026, 5, 31))
    assert not rules.dates_editable(PILOT, date(2026, 6, 1))


def test_a_duplicate_is_an_editable_draft_without_the_results_or_the_log():
    copy = rules.duplicate(
        {**PILOT, "notes": [{"date": "2026-06-01", "text": "x"}]}, "p9", date(2026, 11, 20)
    )

    assert copy["id"] == "p9" and copy["origin"] == rules.PLANNED and copy["draft"]
    assert "result" not in copy and "coverage" not in copy and copy["start"] is None
    assert [n["date"] for n in copy["notes"]] == ["2026-11-20"]
    assert rules.dates_editable(copy, date(2026, 11, 20))


@pytest.mark.parametrize(
    ("result", "target", "coverage", "expected"),
    [
        ({"lo": -0.19, "hi": -0.05}, -0.10, 0.86, rules.CONFIRMED),
        ({"lo": -0.14, "hi": 0.06}, -0.08, 0.81, rules.INCONCLUSIVE),  # holds both the target and no change
        ({"lo": -0.03, "hi": 0.06}, -0.10, 0.81, rules.NO_CHANGE),  # rules the target out
        ({"lo": -0.05, "hi": 0.28}, None, 0.82, rules.NO_CHANGE),
        ({"lo": -0.19, "hi": -0.05}, -0.10, 0.42, rules.INSUFFICIENT),  # coverage blocks the verdict
        (None, -0.10, 0.90, rules.INSUFFICIENT),
    ],
)
def test_the_verdict_compares_the_real_impact_with_the_target(result, target, coverage, expected):
    assert rules.verdict(result, target, coverage) == expected


def test_extending_helps_until_the_range_is_as_narrow_as_the_target():
    assert rules.extension_weeks({"lo": -0.14, "hi": 0.06}, -0.08, 6) == 4  # half-width 0.10 > 0.08
    assert rules.extension_weeks({"lo": -0.12, "hi": 0.04}, -0.08, 6) is None


def test_atypical_events_are_those_that_overlap_the_period():
    events = [(date(2026, 9, 16), date(2026, 9, 16), "Festivo", "16 de septiembre"),
              (date(2026, 12, 12), date(2027, 1, 6), "Fin de año", "Guadalupe–Reyes")]  # fmt: skip

    assert rules.atypical_in("2026-09-07", "2026-10-16", events) == ["16 de septiembre"]
    assert rules.atypical_in("2026-11-09", "2026-12-18", events) == ["Guadalupe–Reyes"]
    assert rules.atypical_in("2026-06-01", "2026-07-24", events) == []


@pytest.mark.parametrize(
    ("seasons", "label"), [(1, "1 temporada"), (3, "2–3 temporadas"), (4, "Inviable (más de 3)")]
)
def test_strategies_are_coloured_by_viability(seasons, label):
    assert rules.viability(seasons) == label
