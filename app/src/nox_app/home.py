# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Home: 1. Emisiones (latest bulletin and history) and, for planners, 2. Planes y Pilotos (latest pilot and
the unified history)."""

import streamlit as st

from nox_app import emissions, pilots
from nox_app.common import bulletins, go, is_planner


def home_page() -> None:
    st.title("Monitor de NOₓ · Ciudad de México")

    st.header("1. Emisiones", divider="gray")
    latest = bulletins()[0]
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        c1.markdown(f"**Último boletín:** {emissions.month_title(latest['month'])}")
        if c2.button("Abrir boletín", type="primary", key="home_bulletin", icon=":material/arrow_forward:"):
            go("boletin", bulletin_month=latest["month"])
        emissions.bulletin_hero(latest, compact=True)
        st.caption(
            "**Línea continua:** NOₓ observado. **Punteada:** sin el efecto del clima. **Banda gris:** cuánto varía un día normal."
        )
    with st.expander("Historial de boletines"):
        emissions.bulletin_history()

    if not is_planner():
        return
    st.header("2. Planes y Pilotos", divider="gray")
    with st.container(border=True):
        st.markdown("**Último piloto evaluado:** impacto real frente a la meta")
        pilots.pilot_hero()
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    c1.markdown("**Historial de pilotos** (planificados y retrospectivos)")
    if c2.button("Planear un piloto", key="home_plan", icon=":material/add:"):
        go("planear")
    pilots.pilot_history("home")
