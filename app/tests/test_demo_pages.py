"""Every page of the demo that reads saved results renders without an error (the live pages need data/)."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
SETUP = """
import streamlit as st
import nox_app.main as m
m.live = lambda: {live}
m.PAGES.update({n: st.Page(lambda: None, title=n, url_path=n) for n in m.PAGE_KEYS})
m.{page}()
"""
SAVED_PAGES = [
    "bulletin_page",
    "measure_page",
    "pilot_page",
    "ozone_page",
    "quality_page",
    "zones_page",
    "health_page",
    "satellite_page",
    "method_page",
]


@pytest.mark.parametrize("page", SAVED_PAGES)
def test_page_renders(page):
    app = AppTest.from_string(
        SETUP.replace("{page}", page).replace("{live}", "True"), default_timeout=60
    ).run()

    assert not app.exception
    assert not app.error


def test_a_change_with_regional_accumulation_is_not_credited_to_the_measure():
    app = AppTest.from_string(
        SETUP.replace("{page}", "measure_page").replace("{live}", "True"), default_timeout=60
    ).run()
    app.selectbox[0].set_value("Semana antes de Navidad 2023").run()

    assert any("NO ATRIBUIBLE" in m.value for m in app.markdown)


@pytest.mark.parametrize("page", ["episode_page", *SAVED_PAGES])
def test_without_the_system_every_page_shows_saved_results(page):
    """The online demo installs only the app: no nox-ml command and no data/."""
    app = AppTest.from_string(
        SETUP.replace("{page}", page).replace("{live}", "False"), default_timeout=60
    ).run()

    assert not app.exception
    assert not app.error


@pytest.mark.parametrize("live", ["True", "False"])
def test_a_bulletin_week_opens_its_episode(live):
    """'Ver por qué' stores the week and opens the episode page, which online also shows an example below."""
    week = json.loads((ROOT / "results/runs/demo/bulletin_2026-10.json").read_text())[0]
    app = AppTest.from_string(
        SETUP.replace("{page}", "episode_page").replace("{live}", live), default_timeout=60
    )
    app.session_state["episode_saved"] = week

    app.run()

    assert not app.exception
    assert not app.error
