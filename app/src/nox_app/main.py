"""Monitor de NOx de la Ciudad de México: the operational app of context/UI_BUSINESS_CONTEXT.md.

Two sections by role: Emisiones (read only, every role) and Planes y Pilotos (planners). Numbers come from
results exported under results/runs/demo (the app never imports nox_ml) or, where the full system and its
data are installed, from the `nox-ml` command line run in a subprocess.

Run from the repository root: ``uv run streamlit run app/src/nox_app/main.py``
"""

import sys
from pathlib import Path

# Streamlit runs this file as a script (and Community Cloud installs only the requirements, not the package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from nox_app import emissions, home, onboarding, pilots
from nox_app.common import ICONS, PAGES, PLANNER, ROLES, STYLE, VIEWER, is_planner, keep


def header() -> None:
    """Demo role switch (no real accounts yet) and the button that reopens the walkthrough."""
    if "_role" not in st.session_state:
        st.session_state["_role"] = PLANNER if st.query_params.get("rol") == PLANNER else VIEWER
    st.session_state["role"] = st.session_state["_role"]
    st.sidebar.radio(
        "Rol (demo)",
        list(ROLES),
        format_func=ROLES.get,
        key="role",
        on_change=keep,
        args=("role",),
        help="Consulta solo ve Emisiones; Planeación también gestiona pilotos.",
    )
    _, right = st.columns([5, 1])
    right.button(
        "¿Qué es NOₓ?", icon=":material/help:", on_click=onboarding.reopen, key="help_button", width="stretch"
    )


def main() -> None:
    st.set_page_config(page_title="Monitor NOx CDMX", layout="wide", page_icon=":material/air:")
    st.html(STYLE)
    header()
    onboarding.storage()
    PAGES.update(
        inicio=st.Page(home.home_page, title="Inicio", icon=":material/home:", default=True),
        boletin=st.Page(
            emissions.bulletin_page, title="Boletines", url_path="boletin", icon=ICONS["emissions"]
        ),
        episodio=st.Page(
            emissions.episode_page, title="¿Fue el clima?", url_path="clima", icon=ICONS["weather"]
        ),
        pilotos=st.Page(pilots.pilots_page, title="Pilotos", url_path="pilotos", icon=ICONS["pilots"]),
        planear=st.Page(
            pilots.planning_page, title="Planear piloto", url_path="planear", icon=":material/edit_calendar:"
        ),
    )
    groups = {"": ["inicio"], "1. Emisiones": ["boletin", "episodio"]}
    if is_planner():
        groups["2. Planes y Pilotos"] = ["pilotos", "planear"]
    page = st.navigation({g: [PAGES[k] for k in keys] for g, keys in groups.items()})
    onboarding.show()
    section2 = page in (PAGES["pilotos"], PAGES["planear"])
    with st.container(key="sage_page" if section2 else "cobalt_page"):
        page.run()


if __name__ == "__main__":
    main()
