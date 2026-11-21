# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportReturnType=false
# ruff: noqa: E501  (CSS and user-facing Spanish strings read better unwrapped)
"""The app's visual system, in one place (context/UI_BUSINESS_CONTEXT.md, sections 4-7).

Every chart, KPI card, legend and page header takes its colours and styles from here, so a change made once
reaches the whole app:

- **Tokens**: the brand palette and, on top of it, colours with a meaning (above / within / below normal,
  atypical days) that KPI badges, chart marks and legend swatches share.
- **Charts**: one Altair style (fonts, axis contrast, line width, dash pattern, normal-range band).
- **Legends**: a list under each chart, one swatch per mark, dimmed when the mark has no data in the period.
- **KPIs**: one card per number, with a status badge that says how to read it.
- **Page**: the title with its one-line context and the "¿Qué es NOₓ?" button, and the page CSS.
"""

import re

import altair as alt
import streamlit as st

from nox_app import onboarding

# ---------------------------------------------------------------- tokens

# Brand (section 5). The Streamlit theme in .streamlit/config.toml repeats these values.
COBALT, COBALT_HOVER = "#1E3A8A", "#1D4ED8"  # structure, navigation, section 1 (Emisiones)
SAGE, SAGE_HOVER = "#0F766E", "#115E59"  # section 2 (Pilotos)
AMBER = "#D97706"  # calendar and caution
INK, MUTED, BORDER, BAND = "#0F172A", "#475569", "#E2E8F0", "#CBD5E1"
AXIS, GRID = "#334155", "#EEF2F6"  # chart text dark enough to read at 12 px; gridlines barely there
BODY_FONT = "Public Sans, Helvetica Neue, Helvetica, Arial, sans-serif"

# Meaning: the same colour says the same thing in a badge, a bar or a legend.
ABOVE = "#B42318"  # more NOx than normal (the theme's redColor)
NORMAL = MUTED  # within the normal range
BELOW = SAGE  # less NOx than normal, or a confirmed drop (the theme's greenColor)
ATYPICAL = AMBER  # holidays, year end, Holy Week, contingencies (the theme's orangeColor)
STATUS = {  # status -> (badge text, Streamlit colour name mapped to the token above by the theme)
    "above": ("Por encima de lo normal", "red"),
    "normal": ("Dentro de lo normal", "gray"),
    "below": ("Por debajo de lo normal", "green"),
}

# Series: solid for what was measured, dashed for what was computed (the series without the weather).
OBSERVED_COLOR, ADJUSTED_COLOR = COBALT_HOVER, INK
LINE_WIDTH, DASH = 2.5, [6, 4]
RANGE_FILL, RANGE_EDGE = (
    "#E6EBF1",
    BAND,
)  # the normal range: light fill with a fine edge, visible on any background
CHOSEN = "#DBE3F0"  # the days being diagnosed
# Calendar events are all "caution": shades of amber, darker for the stronger anomalies.
EVENT_COLORS = {
    "Contingencia": "#92400E",
    "Festivo": AMBER,
    "Fin de año": "#F59E0B",
    "Semana Santa": "#FCD34D",
}

# Icons (section 7): Material Symbols Outlined, as quiet accents in navigation, buttons and badges (not in
# headings). Streamlit bundles the Rounded set; STYLE swaps in Outlined and falls back to Rounded.
ICONS = {
    "emissions": ":material/air:",
    "weather": ":material/partly_cloudy_day:",
    "calendar": ":material/calendar_today:",
    "pilots": ":material/science:",
    "duplicate": ":material/content_copy:",
    "caution": ":material/data_alert:",
}


def status_of(value: float, lo: float, hi: float) -> str:
    """'above', 'normal' or 'below' the normal range [lo, hi]."""
    return "above" if value > hi else "below" if value < lo else "normal"


# ---------------------------------------------------------------- charts


def style_chart(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """The one look of every chart: transparent background, readable axes, quiet grid, full labels."""
    return (
        chart.configure(background="transparent", font=BODY_FONT)
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=AXIS, titleColor=AXIS, labelFontSize=12, titleFontSize=12, titleFontWeight=500,
            labelLimit=0, tickColor=BAND, domainColor=BAND, gridColor=GRID,
        )
        .configure_legend(labelLimit=0, labelFontSize=12, labelColor=AXIS)
    )  # fmt: skip


def show_chart(chart: alt.TopLevelMixin, **kwargs) -> None:
    st.altair_chart(style_chart(chart), width="stretch", **kwargs)


# ---------------------------------------------------------------- legends

# One swatch per kind of mark, drawn with CSS (st.html strips SVG), centred in a 22 x 14 px box.
SWATCHES = {
    "box": "width:16px;height:12px;border-radius:2px;background:{c}",
    "range": "width:22px;height:10px;background:{c};border-top:1px solid "
    + RANGE_EDGE
    + ";border-bottom:1px solid "
    + RANGE_EDGE,
    "line": "width:22px;height:0;border-top:3px solid {c}",
    "dash": f"width:22px;height:3px;background:repeating-linear-gradient(90deg,{{c}} 0 {DASH[0]}px,transparent {DASH[0]}px {sum(DASH)}px)",
    "outline": "width:14px;height:10px;border-radius:2px;background:#FFFFFF;border:2.5px solid {c}",
    "dot": "width:9px;height:9px;border-radius:50%;background:{c}",
    "interval": "width:20px;height:10px;border-left:2px solid {c};border-right:2px solid {c};background:linear-gradient({c},{c}) center/100% 2px no-repeat",
}


def legend_html(items: list[tuple]) -> str:  # (kind, colour, label, meaning) or (..., absent)
    """A legend as a list: one row per (swatch, colour, label, meaning[, absent]). An absent mark (nothing of
    it in the period) is dimmed and says so, instead of promising something the chart does not show."""
    rows = []
    for kind, color, label, meaning, *rest in items:
        absent = bool(rest and rest[0])
        text = "sin registros en este periodo" if absent else meaning
        rows.append(
            f'<div role="listitem" style="display:flex;align-items:center;gap:10px;padding:4px 0;opacity:{0.45 if absent else 1}">'
            f'<span style="flex:none;width:22px;display:flex;justify-content:center" aria-hidden="true">'
            f'<span style="display:block;box-sizing:border-box;{SWATCHES[kind].format(c=color)}"></span></span>'
            f'<span><strong style="color:{INK}">{label}</strong>'
            f"{f'<span style=color:{MUTED}> · {text}</span>' if text else ''}</span></div>"
        )
    return (
        '<div role="list" aria-label="Leyenda" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));'
        f'column-gap:24px;font-size:0.875rem;line-height:1.3;border-top:1px solid {BORDER};padding-top:6px;margin-bottom:8px">'
        + "".join(rows)
        + "</div>"
    )


def show_legend(items: list[tuple]) -> None:
    st.html(legend_html(items))


# ---------------------------------------------------------------- KPIs


def kpi(col, label: str, value: str, note: str = "", status: str | None = None, text: str | None = None,
        help: str | None = None) -> None:  # fmt: skip
    """One number in its own card: the value, a badge that says how to read it and a short note."""
    key = "card_kpi_" + re.sub(r"\W+", "_", label.lower()).strip("_")
    with col.container(border=True, key=key):
        st.metric(label, value, help=help)
        badge = ""
        if status:
            name, color = STATUS[status]
            badge = f":{color}-badge[{text or name}]"
        elif text:
            badge = f":blue-badge[{text}]"
        if badge:
            st.markdown(badge)
        if note:
            st.caption(note)


# ---------------------------------------------------------------- page


def page_header(title: str, subtitle: str = "") -> None:
    """The page title, one line of context under it and the walkthrough button beside it."""
    left, right = st.columns([5, 1], vertical_alignment="center")
    left.title(title)
    right.button(
        "¿Qué es NOₓ?", icon=":material/help:", on_click=onboarding.reopen, key="help_button", width="stretch"
    )
    if subtitle:
        st.markdown(f'<p class="nox-subtitle">{subtitle}</p>', unsafe_allow_html=True)


# Streamlit has one primary colour: section 2 containers (key "sage...") turn their primary buttons sage, and
# containers keyed "card..." become white cards on the slate background.
STYLE = f"""<style>
@import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20,400,0,0&display=block");

/* Icons (section 7): Outlined, thin and small; the Rounded set Streamlit bundles if Google Fonts is blocked. */
[data-testid="stIconMaterial"], span[role="img"][aria-label$=" icon"] {{
  font-family: "Material Symbols Outlined", "Material Symbols Rounded" !important;
  font-variation-settings: "FILL" 0, "wght" 400, "opsz" 20;
}}

/* Typography (section 6): fonts come from the theme; tracking on headings, tabular figures on numbers. */
h1, h2, h3, h4, h5, h6 {{ letter-spacing: -0.02em; }}
[data-testid="stMetricValue"], [data-testid="stMetricDelta"], [data-testid="stDataFrame"], [data-testid="stTable"],
.stMarkdown, [data-testid="stCaptionContainer"] {{ font-variant-numeric: tabular-nums; }}
.nox-subtitle {{ color: {MUTED}; font-size: 1.05rem; margin: -0.5rem 0 1rem; max-width: 60rem; }}

/* Layout: less empty space above the first screen. */
[data-testid="stMainBlockContainer"] {{ padding-top: 2.5rem; }}

/* Cards and section colours. */
[class*="st-key-card"] {{ background-color: #FFFFFF; }}
[class*="st-key-card_kpi"] [data-testid="stMetricValue"] {{ font-size: 2rem; }}
button[kind="primary"]:hover {{ background-color: {COBALT_HOVER}; border-color: {COBALT_HOVER}; }}
[class*="st-key-sage"] button[kind="primary"] {{ background-color: {SAGE}; border-color: {SAGE}; }}
[class*="st-key-sage"] button[kind="primary"]:hover {{ background-color: {SAGE_HOVER}; border-color: {SAGE_HOVER}; }}

/* Sidebar: sections read as headings, their pages sit indented under them. */
[data-testid="stNavSectionHeader"] {{
  margin-top: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em;
}}
[data-testid="stNavSectionHeader"] p {{ font-size: 0.75rem; font-weight: 700; color: {COBALT}; }}
[data-testid="stNavSectionHeader"] ~ [data-testid="stSidebarNavLinkContainer"] [data-testid="stSidebarNavLink"] {{
  margin-left: 0.75rem; border-left: 2px solid {BORDER}; border-radius: 0 6px 6px 0;
}}
</style>"""
