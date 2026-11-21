# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportReturnType=false
# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Paths, saved results, the live command line, the user's role and page links, shared by every page."""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "results" / "runs"
DEMO = RUNS / "demo"
EXPLORATIONS = ROOT / "notebooks" / "exploraciones"

# Seasons with TEMPO pixels in data/interim. Live episodes need SIMAT (until 2024).
SEASONS = {
    "nov–dic 2023": ("2023-11-01", "2023-12-31"),
    "feb–may 2024": ("2024-02-15", "2024-05-31"),
    "jun–oct 2024": ("2024-06-01", "2024-10-31"),
    "nov–dic 2024": ("2024-11-01", "2024-12-31"),
    "feb–may 2025": ("2025-02-15", "2025-05-31"),
    "jun–oct 2025": ("2025-06-01", "2025-10-31"),
    "nov–dic 2025": ("2025-11-01", "2025-12-31"),
    "feb–may 2026": ("2026-02-15", "2026-05-31"),
    "jun–oct 2026": ("2026-06-01", "2026-10-31"),
}
SIMAT_SEASONS = [s for s, (_, end) in SEASONS.items() if end <= "2024-12-31"]
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]  # fmt: skip
DAY_ABBR = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
# Brand palette (context/UI_BUSINESS_CONTEXT.md, section 5); the Streamlit theme is in .streamlit/config.toml.
COBALT, COBALT_HOVER = "#1E3A8A", "#1D4ED8"  # structure, navigation and section 1 (Emisiones)
SAGE, SAGE_HOVER = "#0F766E", "#115E59"  # section 2 (Pilotos) and confirmed drops
AMBER = "#D97706"  # holidays, atypical weather and preliminary states
INK, MUTED, BORDER, BAND = "#0F172A", "#475569", "#E2E8F0", "#CBD5E1"
OBSERVED_LINE = "#0D9488"  # observed NOx: a vivid teal of the sage family, apart from the cobalt dashed line
NORMAL_RANGE = "#E6EBF1"  # the normal-range band, solid so the legend shows the same colour as the chart
BODY_FONT = "Public Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
# Icons (section 7): Material Symbols Outlined, thin (FILL 0, wght 400, opsz 20) and small (16-20 px), as
# quiet accents in headings, badges and states. Streamlit ships the Rounded set; STYLE swaps the font.
ICONS = {
    "emissions": ":material/air:",
    "weather": ":material/partly_cloudy_day:",
    "calendar": ":material/calendar_today:",
    "pilots": ":material/science:",
    "duplicate": ":material/content_copy:",
    "caution": ":material/data_alert:",
}
# Calendar events are all "caution": shades of amber, darker for the stronger anomalies.
EVENT_COLORS = {
    "Contingencia": "#92400E",
    "Festivo": AMBER,
    "Fin de año": "#F59E0B",
    "Semana Santa": "#FCD34D",
}
# Streamlit has one primary colour: section 2 containers (key "sage...") turn their primary buttons sage, and
# containers keyed "card..." become white cards on the slate background. Typography (section 6): the fonts are in
# the theme; headings get the -0.02em tracking and numbers tabular figures here.
STYLE = f"""<style>
@import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20,400,0,0&display=block");
[data-testid="stIconMaterial"], span[role="img"][aria-label$=" icon"] {{
  /* Outlined from Google Fonts; if that request is blocked, the Rounded set Streamlit bundles, never the icon's
     name as plain text */
  font-family: "Material Symbols Outlined", "Material Symbols Rounded" !important;
  font-variation-settings: "FILL" 0, "wght" 400, "opsz" 20;
}}
:is(h1, h2, h3, h4) :is([data-testid="stIconMaterial"], span[role="img"][aria-label$=" icon"]) {{
  font-size: 20px !important; vertical-align: middle !important; margin-right: 4px;
}}
button[kind="primary"]:hover {{ background-color: {COBALT_HOVER}; border-color: {COBALT_HOVER}; }}
[class*="st-key-sage"] button[kind="primary"] {{ background-color: {SAGE}; border-color: {SAGE}; }}
[class*="st-key-sage"] button[kind="primary"]:hover {{ background-color: {SAGE_HOVER}; border-color: {SAGE_HOVER}; }}
[class*="st-key-card"] {{ background-color: #FFFFFF; }}
h1, h2, h3, h4, h5, h6 {{ letter-spacing: -0.02em; }}
[data-testid="stMetricValue"], [data-testid="stMetricDelta"], [data-testid="stDataFrame"], [data-testid="stTable"],
.stMarkdown, [data-testid="stCaptionContainer"] {{ font-variant-numeric: tabular-nums; }}
</style>"""

VIEWER, PLANNER = "viewer", "planner"
ROLES = {VIEWER: "Consulta (viewer)", PLANNER: "Planeación (planner)"}
PAGES: dict[str, Any] = {}  # filled by main(): key -> st.Page
PAGE_KEYS = ["inicio", "boletin", "episodio", "pilotos", "planear"]
OFFLINE = (
    "En la versión en línea solo están los **resultados ya calculados**: calcular periodos nuevos necesita el "
    "sistema completo y sus datos (~3 GB)."
)


def today() -> date:
    return date.today()


def keep(widget_key: str) -> None:
    """Copy a widget's value to ``_<key>``: Streamlit drops widget state when the page changes, so values
    shared across pages (the role, the baseline switch) live in their own keys."""
    st.session_state[f"_{widget_key}"] = st.session_state[widget_key]


def role() -> str:
    return st.session_state.get("_role", VIEWER)


def is_planner() -> bool:
    return role() == PLANNER


def go(page: str, **state) -> None:
    """Open another page with some of its inputs filled in."""
    st.session_state.update(state)
    st.switch_page(PAGES[page])


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


@st.cache_data
def read_csv(path: Path, dates: tuple[str, ...] = ()) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=list(dates))


def pct(change: float, digits: int = 0) -> str:
    """'+12 %' or '−8 %' (a real minus sign) for a relative change."""
    return f"{change * 100:+.{digits}f}\u00a0%".replace("-", "−")  # non-breaking: "+33" and "%" stay together


def short_date(day: str | date) -> str:
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def period_label(start: str | date | None, end: str | date | None) -> str:
    return f"{short_date(start)} – {short_date(end)}" if start and end else "Sin fechas"


def metric(col, label: str, value: str, note: str = "", help: str | None = None) -> None:
    col.metric(label, value, note or None, delta_color="off", delta_arrow="off", help=help)


def show_chart(chart: alt.TopLevelMixin, **kwargs) -> None:
    """Draw a chart with full axis and legend labels (Altair cuts them at 180 px by default) on a transparent
    background, so it sits on the page or on a white card alike."""
    chart = (
        chart.configure(background="transparent", font=BODY_FONT)
        .configure_axis(labelLimit=0, labelFontSize=12, titleFontSize=12)
        .configure_legend(labelLimit=0, labelFontSize=12)
    )
    st.altair_chart(chart, width="stretch", **kwargs)


# A swatch per kind of mark, drawn with CSS (st.html strips SVG) in a 22 x 14 px box next to its meaning.
SWATCHES = {
    "box": "width:16px;height:12px;border-radius:2px;background:{c}",
    "band": "width:22px;height:10px;border-radius:1px;background:{c}",
    "line": "width:22px;height:0;border-top:3px solid {c}",
    "dash": "width:22px;height:0;border-top:3px dashed {c}",
    "outline": "width:14px;height:10px;border-radius:2px;background:#FFFFFF;border:2.5px solid {c}",
    "dot": "width:9px;height:9px;border-radius:50%;background:{c}",
    "range": "width:20px;height:10px;border-left:2px solid {c};border-right:2px solid {c};"
    "background:linear-gradient({c},{c}) center/100% 2px no-repeat",
}


def legend_html(items: list[tuple[str, str, str, str]]) -> str:
    """A legend as a list: one row per (swatch kind, colour, label, meaning), wrapping into columns."""
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;padding:4px 0">'
        f'<span style="flex:none;width:22px;display:flex;justify-content:center" aria-hidden="true">'
        f'<span style="display:block;box-sizing:border-box;{SWATCHES[kind].format(c=color)}"></span></span>'
        f'<span><strong style="color:{INK}">{label}</strong>'
        f"{f'<span style=color:{MUTED}> · {meaning}</span>' if meaning else ''}</span></div>"
        for kind, color, label, meaning in items
    )
    return (
        f'<div role="list" aria-label="Leyenda" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));'
        f'column-gap:24px;font-size:0.875rem;line-height:1.3;border-top:1px solid {BORDER};padding-top:6px;margin-bottom:8px">{rows}</div>'
    )


def show_legend(items: list[tuple[str, str, str, str]]) -> None:
    st.html(legend_html(items))


def season_of(day: date | str) -> str | None:
    iso = day if isinstance(day, str) else day.isoformat()
    return next((s for s, (a, b) in SEASONS.items() if a <= iso <= b), None)


# ---------------------------------------------------------------- saved results


@st.cache_data
def events() -> pd.DataFrame:
    """Holidays, year-end, Easter and ozone contingencies (results/runs/demo/events.csv)."""
    return pd.read_csv(DEMO / "events.csv", parse_dates=["start", "end"])


def event_tuples() -> list[tuple[date, date, str, str]]:
    return [(e.start.date(), e.end.date(), e.kind, e.name) for e in events().itertuples()]


@st.cache_data
def series(season: str) -> pd.DataFrame:
    """Daily observed and weather-free NOx change of a season, with the normal range of one day."""
    a, b = SEASONS[season]
    return pd.read_csv(DEMO / "series" / f"{a}_{b}.csv", parse_dates=["day"])


@st.cache_data
def bulletins() -> list[dict]:
    """The monthly bulletins, newest first."""
    return sorted(read_json(DEMO / "bulletins.json"), key=lambda m: m["month"], reverse=True)


@st.cache_data
def example_episodes() -> dict[str, dict]:
    return read_json(DEMO / "episodes.json")


@st.cache_data
def coverage_by_month() -> pd.DataFrame:
    """Share of station hours with NOx per month: SIMAT until 2024, OpenAQ after."""
    c = pd.read_csv(EXPLORATIONS / "network_qc" / "completeness_by_month.csv")
    return c[
        ((c["source"] == "SIMAT") & (c["month"] <= "2024-12"))
        | ((c["source"] == "OpenAQ") & (c["month"] > "2024-12"))
    ]


def coverage(start: str, end: str) -> float | None:
    """Mean coverage of the months of a period, None when no month is in the table."""
    months = pd.period_range(start, end, freq="M").astype(str)
    c = coverage_by_month().set_index("month")["completeness"]
    found = c.reindex(months).dropna()
    return float(found.mean()) if len(found) else None


# ---------------------------------------------------------------- pilots (session store)


def pilots() -> list[dict]:
    """Every pilot of this session: the saved ones plus those created, duplicated or annotated here. There is
    no backend: changes last until the page is reloaded."""
    if "pilots" not in st.session_state:
        st.session_state["pilots"] = copy.deepcopy(read_json(DEMO / "pilots.json"))
    return st.session_state["pilots"]


def pilot(pilot_id: str) -> dict | None:
    return next((p for p in pilots() if p["id"] == pilot_id), None)


def add_pilot(p: dict) -> None:
    pilots().insert(0, p)


def new_pilot_id() -> str:
    return f"p{len(pilots()) + 1:03d}"


# ---------------------------------------------------------------- live command line


def nox_ml() -> str | None:
    """The nox-ml executable of this environment, or None (e.g. the online demo, which installs only the app)."""
    local = Path(sys.executable).parent / "nox-ml"
    return str(local) if local.exists() else shutil.which("nox-ml")


def live() -> bool:
    """Whether new periods can be computed here: the nox-ml command and the station and satellite data."""
    return nox_ml() is not None and (ROOT / "data" / "interim").is_dir()


@st.cache_data(show_spinner=False)
def run_cli(args: tuple[str, ...]) -> tuple[int, str, str, dict[str, str]]:
    """Run `nox-ml <args> <out flag> <tmp>` from the repository root; return the code, stdout, stderr and the
    text of every file it wrote (relative path -> text)."""
    *cli, out_flag = args
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run(
            [nox_ml() or "nox-ml", *cli, out_flag, tmp], cwd=ROOT, capture_output=True, text=True, timeout=900
        )
        files = {str(p.relative_to(tmp)): p.read_text() for p in Path(tmp).rglob("*") if p.is_file()}
    return done.returncode, done.stdout, done.stderr, files


def cli_error(code: int, out: str, err: str) -> str:
    return ((err or out).strip().splitlines() or ["sin detalle"])[-1]
