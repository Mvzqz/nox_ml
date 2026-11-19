"""Every page of the demo that reads saved results renders without an error (the live pages need data/)."""

import pytest
from streamlit.testing.v1 import AppTest

SETUP = """
import streamlit as st
import nox_app.main as m
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
    app = AppTest.from_string(SETUP.replace("{page}", page), default_timeout=60).run()

    assert not app.exception
    assert not app.error


def test_a_change_with_regional_accumulation_is_not_credited_to_the_measure():
    app = AppTest.from_string(SETUP.replace("{page}", "measure_page"), default_timeout=60).run()
    app.selectbox[0].set_value("Semana antes de Navidad 2023").run()

    assert any("NO ATRIBUIBLE" in m.value for m in app.markdown)
