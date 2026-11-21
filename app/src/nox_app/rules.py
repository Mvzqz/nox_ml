"""Business rules of the app (context/UI_BUSINESS_CONTEXT.md, section 3), without Streamlit.

Pilots are plain dicts (as in results/runs/demo/pilots.json): ``start``/``end`` ISO dates or None,
``target`` and ``result`` as relative changes (-0.10 is a 10 % drop), ``coverage`` as the share of station
hours with data.
"""

import math
from collections.abc import Iterable
from datetime import date, timedelta

DATA_LAG = timedelta(days=14)  # station data arrive about two weeks late
CONSOLIDATION = timedelta(days=45)  # after the end, a result stays preliminary while late data are validated
COVERAGE_VALID, COVERAGE_PRELIMINARY = 0.75, 0.50

DRAFT, SCHEDULED, RUNNING, WAITING = "Borrador", "Programado", "En curso", "Sin datos suficientes aún"
PRELIMINARY, CONSOLIDATED = "Evaluación preliminar", "Evaluado (Consolidado)"
STATUSES = [DRAFT, SCHEDULED, RUNNING, WAITING, PRELIMINARY, CONSOLIDATED]

CONFIRMED, NO_CHANGE = "Reducción confirmada", "Sin cambio detectable"
INCONCLUSIVE, INSUFFICIENT = "Inconcluyente — Extender piloto ayudaría", "Datos insuficientes"
VERDICTS = [CONFIRMED, NO_CHANGE, INCONCLUSIVE, INSUFFICIENT]


def as_date(value: str | date | None) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) else value


def day(value: str | date) -> date:
    return date.fromisoformat(value) if isinstance(value, str) else value


def coverage_level(coverage: float | None) -> str:
    """``valid`` (>= 75 %), ``preliminary`` (50-74 %) or ``insufficient`` (< 50 %, or unknown)."""
    if coverage is None or coverage < COVERAGE_PRELIMINARY:
        return "insufficient"
    return "valid" if coverage >= COVERAGE_VALID else "preliminary"


def status(pilot: dict, today: date) -> str:
    """Where the pilot is in its life cycle on `today`."""
    start, end = as_date(pilot.get("start")), as_date(pilot.get("end"))
    if pilot.get("draft") or start is None or end is None:
        return DRAFT
    if today < start:
        return SCHEDULED
    if today <= end:
        return RUNNING
    if today < end + DATA_LAG or pilot.get("result") is None:
        return WAITING
    if today < end + CONSOLIDATION or coverage_level(pilot.get("coverage")) != "valid":
        return PRELIMINARY
    return CONSOLIDATED


def dates_editable(pilot: dict, today: date) -> bool:
    """Dates are fixed once the pilot starts; a variant is made with `duplicate`."""
    return status(pilot, today) in (DRAFT, SCHEDULED)


def duplicate(pilot: dict, new_id: str, today: date) -> dict:
    """A draft copy with the same design and target, without dates (the planner sets new ones) or results."""
    copy = {k: v for k, v in pilot.items() if k not in ("result", "result_with_atypical", "coverage")}
    copy.update(
        id=new_id,
        name=f"{pilot['name']} (variante)",
        draft=True,
        start=None,
        end=None,
        created=today.isoformat(),
    )
    return copy


def verdict(result: dict | None, target: float | None, coverage: float | None) -> str:
    """Real impact against the target: a drop whose whole range is below 0 is confirmed; a range that
    crosses 0 and holds the target cannot tell them apart (longer would help); one that crosses 0 and rules
    the target out found no change. Below 50 % coverage, or without a result, there is no verdict."""
    if result is None or coverage_level(coverage) == "insufficient":
        return INSUFFICIENT
    if result["hi"] < 0:
        return CONFIRMED
    if target is not None and result["lo"] <= target <= result["hi"]:
        return INCONCLUSIVE
    return NO_CHANGE


def extension_weeks(result: dict, target: float, weeks: float) -> int | None:
    """Extra weeks for the range to tell the target from no change: the half-width shrinks with the square
    root of the duration, and must fall below the size of the target. None when it already does."""
    half = (result["hi"] - result["lo"]) / 2
    if not target or half <= abs(target):
        return None
    return math.ceil(weeks * (half / abs(target)) ** 2 - weeks)


def atypical_in(
    start: str | date, end: str | date, events: Iterable[tuple[date, date, str, str]]
) -> list[str]:
    """Names of the atypical events (holidays, year-end, Easter, contingencies) that overlap the period."""
    a, b = day(start), day(end)
    return [name for e_start, e_end, _, name in events if e_start <= b and e_end >= a]


def viability(seasons: int) -> str:
    """Strategy colour of the planner: green in one season, blue in two or three, grey beyond."""
    return "1 temporada" if seasons <= 1 else "2–3 temporadas" if seasons <= 3 else "Inviable (más de 3)"
