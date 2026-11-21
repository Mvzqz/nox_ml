"""Home: 1. Emisiones (latest bulletin and history) and, for planners, 2. Planes y Pilotos (latest pilot and
the unified history)."""

import streamlit as st

from nox_app import emissions, pilots
from nox_app.common import bulletins, go, is_planner


def home_page() -> None:
    st.title("Monitor de NOₓ · Ciudad de México")

    st.header("1. Emisiones", divider="blue")
    latest = bulletins()[0]
    with st.container(border=True, key="card_bulletin"):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        c1.markdown(f"#### Último boletín · {emissions.month_title(latest['month'])}")
        if c2.button("Abrir boletín", type="primary", key="home_bulletin", icon=":material/arrow_forward:"):
            go("boletin", bulletin_month=latest["month"])
        emissions.bulletin_hero(latest, compact=True)
    with st.expander("Historial de boletines"):
        emissions.bulletin_history()

    if is_planner():
        with st.container(key="sage_home"):
            pilots_section()


def pilots_section() -> None:
    st.header("2. Planes y Pilotos", divider="green")
    with st.container(border=True, key="card_pilot"):
        st.markdown("#### Último piloto evaluado")
        st.caption("Impacto real frente a la meta.")
        pilots.pilot_hero()
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    c1.markdown("**Historial de pilotos**")
    if c2.button("Planear un piloto", type="primary", key="home_plan", icon=":material/add:"):
        go("planear")
    pilots.pilot_history("home")
