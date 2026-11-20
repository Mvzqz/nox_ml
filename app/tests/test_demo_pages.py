# ruff: noqa: E501  (test tables read better unwrapped)
"""Every page renders for each role, with and without the full system, and the flows between them work."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from nox_app.common import short_date

ROOT = Path(__file__).resolve().parents[2]
SETUP = """
import streamlit as st
from nox_app import common, emissions, home, pilots
emissions.live = pilots.live = lambda: {live}
st.session_state.setdefault("_role", "{role}")
common.PAGES.update({n: st.Page(lambda: None, title=n, url_path=n) for n in common.PAGE_KEYS})
{page}()
"""
PAGES = {
    "viewer": ["home.home_page", "emissions.bulletin_page", "emissions.episode_page"],
    "planner": ["home.home_page", "emissions.bulletin_page", "emissions.episode_page", "pilots.pilots_page", "pilots.planning_page"],
}  # fmt: skip
CASES = [(role, page, live) for role, pages in PAGES.items() for page in pages for live in ("True", "False")]


def app(page: str, role: str = "planner", live: str = "False", **state) -> AppTest:
    test = AppTest.from_string(
        SETUP.replace("{page}", page).replace("{role}", role).replace("{live}", live), default_timeout=60
    )
    for key, value in state.items():
        test.session_state[key] = value
    return test.run()


def ok(test: AppTest) -> bool:
    """No exception; error boxes are allowed only where the page means them (a blocked verdict)."""
    return not test.exception and all("Datos insuficientes" in e.value for e in test.error)


@pytest.mark.parametrize(("role", "page", "live"), CASES)
def test_page_renders(role, page, live):
    assert ok(app(page, role, live))


def test_a_viewer_does_not_see_the_pilots_section():
    planner, viewer = app("home.home_page", "planner"), app("home.home_page", "viewer")

    assert "2. Planes y Pilotos" in [h.value for h in planner.header]
    assert "2. Planes y Pilotos" not in [h.value for h in viewer.header]


def test_a_bulletin_week_opens_its_diagnosis_with_its_dates():
    bulletin = json.loads((ROOT / "results/runs/demo/bulletins.json").read_text())[-2]  # September 2026
    week = next(w for w in bulletin["weeks"] if w["default"].get("verdict", "normal") != "normal")

    episode = app("emissions.episode_page", episode_week={"month": bulletin["month"], "start": week["start"]})

    assert ok(episode)
    expected = f"{short_date(week['start'])[:-5]} – {short_date(week['end'])}"
    assert episode.selectbox(key="episode_bulletin_week").value == expected
    assert any("NO LO EXPLICA" in m.value or "LO EXPLICA" in m.value for m in episode.markdown)


def test_the_baseline_switch_reads_the_diagnosis_with_atypical_days():
    episode = app("emissions.episode_page")
    episode.toggle(key="baseline_with_atypical").set_value(True).run()

    assert ok(episode)
    assert any("incluye feriados" in m.value for m in episode.markdown)


@pytest.mark.parametrize("pilot_id", ["m01", "m02", "m03", "m04", "m05", "m06", "m07", "r01", "r02", "r03"])
def test_every_saved_pilot_opens(pilot_id):
    assert ok(app("pilots.pilots_page", pilot_id=pilot_id))


def test_a_pilot_that_crosses_a_holiday_gives_both_readings_and_its_key_messages():
    page = app("pilots.pilots_page", pilot_id="m02")
    text = " ".join(m.value for m in page.markdown)

    assert "Incluyendo los días atípicos" in text
    assert "Mensajes clave para toma de decisiones" in text
    assert "Inconcluyente" in text and "Extender el piloto" in text


def test_low_coverage_blocks_the_verdict():
    page = app("pilots.pilots_page", pilot_id="m03")

    assert any("Datos insuficientes" in e.value for e in page.error)


def test_duplicating_a_started_pilot_makes_an_editable_draft():
    page = app("pilots.pilots_page", pilot_id="m01")
    assert not page.date_input  # dates fixed once started
    page.button(key="dup_m01").click().run()

    copy = page.session_state["pilots"][0]
    assert copy["draft"] and copy["name"].endswith("(variante)")
    variant = app("pilots.pilots_page", pilot_id=copy["id"], pilots=page.session_state["pilots"])
    assert variant.date_input


def test_a_note_is_added_to_the_log():
    page = app("pilots.pilots_page", pilot_id="m05")
    page.text_area[0].set_value("Reunión con la Alcaldía.")
    page.button(key="FormSubmitter:note_m05-Agregar nota").click().run()

    notes = next(p for p in page.session_state["pilots"] if p["id"] == "m05")["notes"]
    assert notes[-1]["text"] == "Reunión con la Alcaldía."


def test_the_planner_saves_a_draft_without_dates():
    page = app("pilots.planning_page")
    page.button(key="plan_save").click().run()

    saved = page.session_state["pilots"][0]
    assert saved["draft"] and saved["origin"] == "Planificado" and saved["target"] == -0.10
