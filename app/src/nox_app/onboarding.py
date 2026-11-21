# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""The dismissible "¿Qué es NOx?" walkthrough: three steps, shown on at most two visits or until dismissed,
remembered in the browser's localStorage, and reopened from the header."""

import streamlit as st
from streamlit.components import v2 as components

STORAGE_KEY = "nox_onboarding"
MAX_VIEWS = 2

# Runs in the browser. Once per browser session (sessionStorage), counts a view unless dismissed or already
# shown MAX_VIEWS times, and tells Python whether to open the walkthrough; writes the dismissal it is sent.
JS = f"""
export default function(component) {{
    const {{ data, setStateValue }} = component;
    const KEY = "{STORAGE_KEY}";
    let saved = {{ views: 0, dismissed: false }};
    try {{ saved = Object.assign(saved, JSON.parse(window.localStorage.getItem(KEY) || "{{}}")); }} catch (e) {{}}
    const save = () => {{ try {{ window.localStorage.setItem(KEY, JSON.stringify(saved)); }} catch (e) {{}} }};
    if (data && data.dismiss && !saved.dismissed) {{ saved.dismissed = true; save(); }}
    let counted = false;
    try {{ counted = window.sessionStorage.getItem(KEY + "_counted") === "1"; }} catch (e) {{}}
    if (!counted) {{
        const show = !saved.dismissed && saved.views < {MAX_VIEWS};
        if (show) {{ saved.views += 1; save(); }}
        try {{ window.sessionStorage.setItem(KEY + "_counted", "1"); }} catch (e) {{}}
        setStateValue("show", show);
    }}
}}
"""

STEPS = [
    (
        "1. Por qué importa el NOₓ en la Ciudad de México",
        """Los **óxidos de nitrógeno (NOₓ)** son gases que salen sobre todo de los escapes de coches, camiones y autobuses, y también de la industria.

- Irritan las vías respiratorias.
- Con el sol, ayudan a formar **ozono** y **partículas finas**, los dos contaminantes que más activan contingencias en la ciudad.

Por eso medir cuánto NOₓ se emite, y si una medida lo reduce, ayuda a decidir qué funciona.""",
    ),
    (
        "2. Las dos secciones de la herramienta",
        """**Emisiones (consulta):** el boletín de cada mes dice cómo estuvo el NOₓ semana a semana y si algún cambio se explica por el clima. Desde cualquier semana puedes abrir **¿Fue el clima?** para ver el detalle.

**Planes y Pilotos (gestión):** para diseñar un piloto (cuánto tiempo medir y cómo), darle seguimiento y leer su evaluación: el impacto real frente a la meta propuesta.""",
    ),
    (
        "3. Clima, feriados y desfase de datos",
        """- **Clima:** con poco viento la contaminación se acumula aunque se emita lo mismo. Por eso siempre mostramos el NOₓ observado y el NOₓ **sin el efecto del clima**.
- **Feriados y días atípicos** (Semana Santa, fin de año, contingencias) se apartan de la comparación por defecto. Puedes incluirlos con un interruptor, y en los pilotos verás las dos lecturas.
- **Desfase:** los datos de las estaciones llegan con unas **2 semanas** de retraso. Un piloto que acaba de terminar aparece como *Sin datos suficientes aún* hasta que llegan.""",
    ),
]


@st.cache_resource
def _storage():
    return components.component("nox_onboarding_storage", js=JS)


def storage() -> None:
    """Mount the invisible localStorage bridge; open the walkthrough on the visits it allows."""
    result = _storage()(
        key="onboarding_storage",
        data={"dismiss": st.session_state.get("onboarding_dismissed", False)},
        default={"show": False},
        on_show_change=lambda: None,
        height=0,
    )
    if getattr(result, "show", False) and not st.session_state.get("onboarding_seen"):
        st.session_state["onboarding_seen"] = True
        st.session_state["onboarding_open"] = True


def reopen() -> None:
    st.session_state["onboarding_open"] = True
    st.session_state["onboarding_step"] = 0


@st.dialog("¿Qué es NOₓ?", width="large")
def walkthrough() -> None:
    step = st.session_state.setdefault("onboarding_step", 0)
    title, body = STEPS[step]
    st.progress((step + 1) / len(STEPS), text=f"Paso {step + 1} de {len(STEPS)}")
    st.subheader(title)
    st.markdown(body)
    c1, c2, c3 = st.columns([1, 1, 2])
    if step > 0 and c1.button("Anterior", key="onboarding_back"):
        st.session_state["onboarding_step"] = step - 1
        st.rerun(scope="fragment")
    if step < len(STEPS) - 1:
        if c2.button("Siguiente", type="primary", key="onboarding_next"):
            st.session_state["onboarding_step"] = step + 1
            st.rerun(scope="fragment")
    elif c2.button("Entendido", type="primary", key="onboarding_done"):
        st.session_state["onboarding_step"] = 0
        st.rerun()
    if c3.button("No volver a mostrar", key="onboarding_dismiss"):
        st.session_state["onboarding_dismissed"] = True
        st.session_state["onboarding_step"] = 0
        st.rerun()
    st.caption("Puedes volver a abrir esta guía con el botón **¿Qué es NOₓ?** de arriba.")


def show() -> None:
    """Open the walkthrough when the storage bridge or the header button asked for it."""
    if st.session_state.pop("onboarding_open", False):
        walkthrough()
