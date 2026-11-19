# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
# pyright: reportOptionalOperand=false, reportReturnType=false, reportIndexIssue=false, reportOperatorIssue=false, reportGeneralTypeIssues=false
# (pandas and altair stubs infer unions; the smoke test covers the behavior)
# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""UX demo of every screen in docs/entregables/Interfaz.39.md.

Three kinds of numbers, labelled on each screen:
- **live**: runs the `nox-ml` command line in a subprocess (the app never imports nox_ml);
- **saved**: reads results exported under results/runs and notebooks/exploraciones;
- **notes**: figures copied from the knowledge notes, until their exploration exports them.

Run from the repository root: ``uv run streamlit run app/src/nox_app/main.py``
"""

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "results" / "runs"
EXPLORATIONS = ROOT / "notebooks" / "exploraciones"

# Seasons with TEMPO pixels in data/interim. Episodes need SIMAT (until 2024); measures also read OpenAQ.
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

VERDICTS = {
    "normal": ("Normal", "", "gray"),
    "weather_explains": ("El clima lo explica", "", "blue"),
    "weather_explains_part": ("El clima lo explica en parte", "", "blue"),
    "weather_does_not_explain": ("El clima no lo explica", "", "orange"),
}
# Runs made before the prudent verdict (PR #103) only carry the detailed one.
OLD_TO_PRUDENT = {"weather": "weather_explains", "emission": "weather_does_not_explain"}
RATIO_NAMES = {
    "concentration": "NOₓ en el aire",
    "weather": "Esperado solo por el clima",
    "emission": "Lo que salió de la ciudad (sin el clima)",
    "background": "Contaminación en toda la región (satélite)",
    "urban": "Contaminación sobre la ciudad (satélite)",
}
DESIGNS = {
    "a_contiguous": "Continuo",
    "b_alternate_days": "Días alternos",
    "c_alternate_weeks": "Semanas alternas",
    "d_two_week_blocks": "Bloques de dos semanas",
    "e_random_days": "Días al azar",
    "f_random_weeks": "Semanas al azar",
}
SEASON_LENGTH = {"feb–may": "feb a may, unos 3.5 meses", "nov–dic": "nov y dic, unos 2 meses"}
EVENT_COLORS = {
    "Contingencia": "#e76f51",
    "Festivo": "#8d99ae",
    "Fin de año": "#e9c46a",
    "Semana Santa": "#a7c957",
}
QC_TYPES = {
    "gap": "Hueco en una estación",
    "stuck": "Valor repetido (sensor pegado)",
    "network_outage": "Corte de toda la red",
    "network_step": "Salto de toda la red",
    "level_shift": "Cambio de nivel",
    "network_stuck": "Red con valores repetidos",
}
SOURCE = {
    "live": ":green-badge[En vivo · corre el sistema]",
    "saved": ":blue-badge[Resultado guardado]",
    "notes": ":orange-badge[Cifras de las notas]",
}
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DAY_ABBR = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
PAGES: dict[str, Any] = {}  # filled by main(): key -> st.Page
PAGE_KEYS = [
    "boletin",
    "episodio",
    "medida",
    "piloto",
    "ozono",
    "calidad",
    "zonas",
    "salud",
    "satelite",
    "metodo",
]


# ---------------------------------------------------------------- Helpers


def source(*kinds: str) -> None:
    st.markdown(" ".join(SOURCE[k] for k in kinds))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


@st.cache_data
def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def nox_ml() -> str:
    """The nox-ml executable of this environment."""
    local = Path(sys.executable).parent / "nox-ml"
    return str(local) if local.exists() else (shutil.which("nox-ml") or "nox-ml")


@st.cache_data(show_spinner=False)
def run_cli(args: tuple[str, ...]) -> tuple[int, str, str, dict[str, str]]:
    """Run `nox-ml <args> <out flag> <tmp>` from the repository root; return the code, stdout, stderr and the
    text of every file it wrote (relative path -> text)."""
    *cli, out_flag = args
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run(
            [nox_ml(), *cli, out_flag, tmp], cwd=ROOT, capture_output=True, text=True, timeout=900
        )
        files = {str(p.relative_to(tmp)): p.read_text() for p in Path(tmp).rglob("*") if p.is_file()}
    return done.returncode, done.stdout, done.stderr, files


def pct(ratio: float, digits: int = 0) -> str:
    return f"{ratio - 1:+.{digits}%}".replace("-", "−")


def metric(col, label: str, value: str, note: str = "", help: str | None = None) -> None:
    col.metric(label, value, note or None, delta_color="off", delta_arrow="off", help=help)


def change_chart(
    rows: pd.DataFrame, label: str, title: str = "Cambio frente a un día normal"
) -> alt.TopLevelMixin:
    """Percent change per row (point) with its interval (band) and a dashed line at 0 (no change)."""
    rows = rows.assign(change=rows["ratio"] - 1, lo_c=rows["lo"] - 1, hi_c=rows["hi"] - 1)
    base = alt.Chart(rows).encode(y=alt.Y(f"{label}:N", sort=None, title=None))
    band = base.mark_rule(strokeWidth=10, opacity=0.25).encode(
        x=alt.X("lo_c:Q", title=title, axis=alt.Axis(format="+%")), x2="hi_c:Q"
    )
    tooltip = [label, alt.Tooltip("change:Q", format="+.0%", title="cambio"),
               alt.Tooltip("lo_c:Q", format="+.0%", title="desde"), alt.Tooltip("hi_c:Q", format="+.0%", title="hasta")]  # fmt: skip
    point = base.mark_point(filled=True, size=140).encode(x="change:Q", tooltip=tooltip)
    zero = alt.Chart(pd.DataFrame({"x": [0.0]})).mark_rule(strokeDash=[4, 4]).encode(x="x:Q")
    return (band + point + zero).properties(height=44 * len(rows) + 40)


def show_chart(chart: alt.TopLevelMixin, **kwargs) -> None:
    """Draw a chart with full axis and legend labels (Altair cuts them at 180 px by default)."""
    chart = chart.configure_axis(labelLimit=0, labelFontSize=13, titleFontSize=13).configure_legend(
        labelLimit=0, labelFontSize=13
    )
    st.altair_chart(chart, **kwargs)


def go(page: str, **state) -> None:
    """Open another page with some of its inputs filled in."""
    st.session_state.update(state)
    st.switch_page(PAGES[page])


def season_of(day: date) -> str | None:
    return next((s for s, (a, b) in SEASONS.items() if a <= day.isoformat() <= b), None)


# ---------------------------------------------------------------- Calendar and period picker


@st.cache_data
def events() -> pd.DataFrame:
    e = pd.read_csv(RUNS / "demo" / "events.csv", parse_dates=["start", "end"])
    curated = [
        ("2023-12-11", "2023-12-15", "Ejemplo", "Semana estancada (el clima la explica)"),
        ("2023-12-18", "2023-12-22", "Ejemplo", "Semana antes de Navidad (el clima no la explica)"),
        ("2023-12-26", "2023-12-29", "Ejemplo", "Semana después de Navidad (normal)"),
    ]
    extra = pd.DataFrame(curated, columns=e.columns).astype(
        {"start": "datetime64[ns]", "end": "datetime64[ns]"}
    )
    return pd.concat([extra, e], ignore_index=True)


def calendar_chart(season: str, start: date, end: date, references: list[str] = ()) -> alt.TopLevelMixin:
    """Every day of the season as a cell (week × weekday), coloured by known event, with the chosen days
    outlined and the `references` (the normal days they were compared with) dotted."""
    a, b = (pd.Timestamp(d) for d in SEASONS[season])
    days = pd.DataFrame({"day": pd.date_range(a, b)})
    days["kind"] = "Día normal"
    days["name"] = ""
    for e in events()[lambda e: e["kind"] != "Ejemplo"].itertuples():
        hit = days["day"].between(e.start, e.end)
        days.loc[hit, "kind"], days.loc[hit, "name"] = e.kind, e.name
    days.loc[days["day"].dt.weekday >= 5, "kind"] = days["kind"].where(
        days["kind"] != "Día normal", "Fin de semana"
    )
    days["chosen"] = days["day"].between(pd.Timestamp(start), pd.Timestamp(end))
    days["reference"] = days["day"].isin(pd.to_datetime(list(references)))
    week = days["day"] - pd.to_timedelta(days["day"].dt.weekday, unit="D")
    days["week"] = week.dt.day.astype(str) + " " + week.dt.month.map(lambda m: MONTHS[m - 1])
    days["weekday"] = days["day"].dt.weekday.map(dict(enumerate(DAY_ABBR)))
    days["date"] = (
        days["weekday"]
        + " "
        + days["day"].dt.day.astype(str)
        + " "
        + days["day"].dt.month.map(lambda m: MONTHS[m - 1])
    )
    domain = ["Día normal", "Fin de semana", *EVENT_COLORS]
    colors = ["#eef1f4", "#d5dbe1", *EVENT_COLORS.values()]
    x = alt.X("week:O", sort=list(days["week"].unique()), title=None, axis=alt.Axis(labelAngle=-45))
    y = alt.Y("weekday:N", sort=DAY_ABBR, title=None)
    base = alt.Chart(days).encode(x=x, y=y)
    cells = base.mark_rect(cornerRadius=2).encode(
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(domain=domain, range=colors),
            legend=alt.Legend(title=None, orient="bottom"),
        ),
        stroke=alt.condition("datum.chosen", alt.value("#1d3557"), alt.value(None)),
        strokeWidth=alt.condition("datum.chosen", alt.value(2.5), alt.value(0)),
        tooltip=[
            alt.Tooltip("date:N", title="Día"),
            alt.Tooltip("kind:N", title="Tipo"),
            alt.Tooltip("name:N", title="Evento"),
        ],
    )
    if not len(references):
        return cells.properties(height=190)
    dots = base.transform_filter("datum.reference").mark_point(
        filled=True, size=45, color="#1d3557", opacity=0.9
    )
    return (cells + dots).properties(height=190)


def pick_period(
    key: str, seasons: list[str], default: tuple[str, date, date] | None = None
) -> tuple[str, date, date] | None:
    """Season, then a known event or days by hand, with the season's calendar. Fills from st.session_state
    ``prefill`` (set by another page) once."""
    prefill = st.session_state.pop("prefill", None)
    if prefill is None and f"{key}_season" not in st.session_state:
        prefill = default  # only on the first visit
    if prefill and prefill[0] in seasons:
        st.session_state[f"{key}_season"] = prefill[0]
        st.session_state[f"{key}_event"] = "Elegir días en el calendario"
        st.session_state[f"{key}_days"] = (prefill[1], prefill[2])
    c1, c2 = st.columns([1, 2])
    season = c1.selectbox("Temporada", seasons, key=f"{key}_season")
    a, b = (pd.Timestamp(d) for d in SEASONS[season])
    known = events()[lambda e: (e["end"] >= a) & (e["start"] <= b)]
    labels = {
        f"{e.name} · {e.start:%d %b}–{e.end:%d %b}": (max(e.start, a).date(), min(e.end, b).date())
        for e in known.itertuples()
    }
    choice = c2.selectbox("Evento conocido", ["Elegir días en el calendario", *labels], key=f"{key}_event",
                          help="Contingencias, festivos y periodos atípicos de la temporada.")  # fmt: skip
    if choice in labels:
        start, end = labels[choice]
    else:
        days_key = f"{key}_days"
        current = st.session_state.get(days_key)
        if not current or not all(a.date() <= d <= b.date() for d in current):
            st.session_state[days_key] = (a.date(), a.date() + timedelta(days=4))
        picked = st.date_input(
            "Días", min_value=a.date(), max_value=b.date(), key=days_key, format="DD/MM/YYYY"
        )
        if len(picked) != 2:
            st.info("Elige el último día.")
            return None
        start, end = picked
    show_chart(calendar_chart(season, start, end), width="stretch")
    return season, start, end


# ---------------------------------------------------------------- Boletín


def bulletin_page() -> None:
    weeks = read_json(RUNS / "demo" / "bulletin_2026-10.json")
    weeks = [w for w in weeks if "ratios" in w]
    completeness = read_csv(EXPLORATIONS / "network_qc" / "completeness_by_month.csv")
    october = completeness[(completeness["source"] == "OpenAQ") & (completeness["month"] == "2026-10")].iloc[
        0
    ]

    st.title("Boletín · octubre de 2026")
    st.caption("Se publica solo a mediados de cada mes. Resume qué pasó con la contaminación y por qué.")
    source("saved")

    unusual = sum(w["verdict"] != "normal" for w in weeks)
    c1, c2, c3 = st.columns(3)
    metric(
        c1,
        "Emisión del mes",
        "Sin cambio detectable",
        "el sistema ve cambios de ±30 % o más en una temporada",
    )
    metric(c2, "Semanas fuera de lo normal", f"{unusual} de {len(weeks)}", "comparadas con días normales")
    metric(
        c3,
        "Red de estaciones",
        f"{october['completeness']:.0%} de horas",
        f"{october['stations']} estaciones con datos",
    )

    st.subheader("Semanas del mes")
    st.caption(
        "Cada semana se compara con días normales del mismo día de la semana. Pulsa una para ver por qué."
    )
    for w in weeks:
        title, _, color = VERDICTS[w["verdict"]]
        r = w["ratios"]
        c = st.columns([2, 2, 2, 3, 2])
        c[0].markdown(f"**{date.fromisoformat(w['start']):%d %b}–{date.fromisoformat(w['end']):%d %b}**")
        c[1].markdown(f"Concentración **{pct(r['concentration'])}**")
        c[2].markdown(f"Clima {pct(r['weather'])}")
        c[3].markdown(
            f":{color}[{title}]" + (f" · {len(w['days'])} días con datos" if len(w["days"]) < 5 else "")
        )
        if c[4].button("Ver por qué", key=f"week_{w['start']}"):
            go("episodio", episode_saved=w)
    st.caption("La última semana de octubre todavía no tiene datos publicados (~2 semanas de retraso).")

    st.subheader("Emisión estimada por el satélite, semana a semana")
    daily = pd.read_csv(RUNS / "flux_divergence" / "2026-06-01_2026-10-31.csv", parse_dates=["day"])
    weekly = (
        daily[daily["kind"] == 0].set_index("day")["tau_4h"].resample("W-MON").mean().dropna().reset_index()
    )
    weekly["change"] = weekly["tau_4h"] / weekly["tau_4h"].mean() - 1
    y = alt.Y("change:Q", title="Frente a la media de la temporada", axis=alt.Axis(format="+%"))
    tooltip = [alt.Tooltip("day:T", title="Semana"), alt.Tooltip("change:Q", format="+.0%")]
    line = alt.Chart(weekly).mark_line(point=True).encode(x=alt.X("day:T", title=None), y=y, tooltip=tooltip)
    band = (
        alt.Chart(pd.DataFrame({"lo": [-0.15], "hi": [0.15]}))
        .mark_rect(opacity=0.12)
        .encode(y="lo:Q", y2="hi:Q")
    )
    show_chart((band + line).properties(height=220), width="stretch")
    st.caption(
        "Días hábiles de jun–oct 2026, solo con el satélite. La banda gris (±15 %) es la oscilación normal de semana a semana: un cambio dentro de ella no es señal."
    )

    st.subheader("Otras secciones")
    a, b = st.columns(2)
    with a.container(border=True):
        st.markdown("**Ozono:** en el centro, recortar NOₓ no baja el ozono.")
        st.page_link(PAGES["ozono"], label="Ver ozono", icon=":material/arrow_forward:")
    with b.container(border=True):
        st.markdown(
            f"**Calidad de las redes:** {october['completeness']:.0%} de las horas con dato en octubre."
        )
        st.page_link(PAGES["calidad"], label="Ver calidad de redes", icon=":material/arrow_forward:")
    table = pd.DataFrame(
        [{"semana": w["start"], "dias": len(w["days"]), "veredicto": VERDICTS[w["verdict"]][0],
          **{f"cambio_{k}": round(v - 1, 3) for k, v in w["ratios"].items() if v is not None}} for w in weeks]
    )  # fmt: skip
    st.download_button(
        "Descargar el boletín (CSV)",
        table.to_csv(index=False),
        "boletin_2026-10.csv",
        icon=":material/download:",
    )


# ---------------------------------------------------------------- Episodio


def verdict_of(result: dict) -> str:
    return (
        result["verdict"] if "detail" in result else OLD_TO_PRUDENT.get(result["verdict"], result["verdict"])
    )


def amount(ratio: float) -> str:
    """'59 % más', '20 % menos' or 'casi lo mismo' for a ratio against normal days."""
    change = ratio - 1
    if abs(change) < 0.05:
        return "casi lo mismo"
    return f"{abs(change) * 100:.0f} % {'más' if change > 0 else 'menos'}"


def episode_story(result: dict) -> str:
    """The verdict told with the episode's own numbers, for a reader who does not know what concentration,
    emission or regional background mean."""
    verdict, r = verdict_of(result), result["ratios"]
    air, weather = r["concentration"], r["weather"]
    up = air >= 1
    seen = (
        f"Esos días hubo **{amount(air)} NOₓ en el aire** que en un día normal"
        if abs(air - 1) >= 0.05
        else "Esos días hubo **casi el mismo NOₓ en el aire** que en un día normal"
    )
    by_weather = f"Solo por el viento y el aire de esos días esperaríamos {amount(weather)}"
    if verdict == "normal":
        text = [f"{seen}, y el viento y el aire también estuvieron como siempre. **Nada fuera de lo común.**"]
    elif verdict == "weather_explains":
        why = (
            "con poco viento y el aire quieto, la contaminación se junta aunque los coches y fábricas echen lo mismo de siempre"
            if up
            else "con más viento, la contaminación se dispersa aunque los coches y fábricas echen lo mismo de siempre"
        )
        text = [f"{seen}. **El clima basta para explicarlo:** {why}. {by_weather}."]
    elif verdict == "weather_explains_part":
        text = [
            f"{seen}. {by_weather}: **el clima explica una parte, no todo.**",
            "El resto puede venir de que se echó más contaminación (más coches, más actividad) o de contaminación que se fue juntando de días anteriores.",
        ]
    else:
        text = [
            f"{seen}. {by_weather}, así que **el clima no explica {'la subida' if up else 'la bajada'}.**",
            "Quedan dos explicaciones posibles: que se echó más contaminación (más coches, más actividad) o que se fue juntando de días anteriores. **Con estos datos no podemos saber cuál de las dos fue.**"
            if up
            else "Puede ser que se echó menos contaminación (menos coches, menos actividad) o que el aire limpio llegó de fuera. **Con estos datos no podemos saber cuál de las dos fue.**",
        ]
    if "background_up" in (result.get("notes") or []) and r.get("background") is not None:
        text.append(
            f"Una pista: el satélite vio **{amount(r['background'])} contaminación también fuera de la ciudad**, en toda la región. Cuando sube en toda la región, apunta a contaminación que se acumuló en el aire, no solo a lo que echó la ciudad esos días."
        )
    return "\n\n".join(text)


GLOSSARY = """
- **NOₓ:** gases que salen de los escapes de coches, camiones y fábricas. Irritan los pulmones y ayudan a formar ozono.
- **NOₓ en el aire (concentración):** cuánto NOₓ miden las estaciones en el aire que respiramos.
- **Lo que sale de la ciudad (emisión):** cuánto NOₓ echan los coches y fábricas. No es lo mismo que lo que hay en el aire.
- **El clima:** el viento y la altura del aire en que se mezcla la contaminación. Con viento, la contaminación se va; con aire quieto, se junta. Por eso un día puede haber mucho NOₓ en el aire aunque se haya echado lo mismo de siempre.
- **Contaminación en toda la región (fondo regional):** la que el satélite ve fuera de la ciudad. Si sube también ahí, la contaminación se está juntando sobre toda la zona, no solo en la ciudad.
- **Día normal:** un día del mismo día de la semana y la misma temporada, sin festivos ni contingencias.

Piénsalo como una tina: la llave es lo que sale de la ciudad, el agua en la tina es el NOₓ en el aire y el desagüe es el viento. La tina puede llenarse porque abrieron más la llave o porque se tapó el desagüe. Este diagnóstico te dice si el desagüe (el clima) basta para explicarlo.
"""


WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
LONG_EPISODE = 14  # days; longer periods mix the change into its own reference days


def short_date(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def weekdays_of(days: list[str]) -> str:
    """'de lunes a viernes', 'sábados y domingos' or 'lunes, miércoles y viernes'."""
    found = sorted({date.fromisoformat(d).weekday() for d in days})
    if len(found) >= 3 and found == list(range(found[0], found[-1] + 1)):
        return f"de {WEEKDAYS[found[0]]} a {WEEKDAYS[found[-1]]}"
    names = [WEEKDAYS[i] + ("" if WEEKDAYS[i].endswith("s") else "s") for i in found]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def comparison(result: dict, plain: bool = False) -> str:
    """What the episode was compared with, in one plain sentence (`plain`: without Streamlit colours)."""
    refs = result.get("references")
    if not refs:
        return (
            "**Comparado con:** días normales del mismo día de la semana, hasta 4 semanas antes y 4 después. "
            "No se usan contingencias, festivos ni fin de año."
        )
    text = (
        f"**Comparado con:** {len(refs)} días normales ({weekdays_of(result['days'])}, como los elegidos) "
        f"entre el {short_date(refs[0])} y el {short_date(refs[-1])}. "
        "Se buscan hasta 4 semanas antes y 4 después; no se usan contingencias, festivos ni fin de año."
    )
    warnings = []
    if len(refs) < 2 * len(result["days"]):
        warnings.append("Hay pocos días para comparar: el resultado es menos firme.")
    side = (
        "anteriores"
        if refs[-1] < result["days"][0]
        else "posteriores"
        if refs[0] > result["days"][-1]
        else None
    )
    if side:
        warnings.append(
            f"Todos los días de comparación son {side} a los elegidos: si la contaminación sube o baja con la "
            "temporada, ese cambio puede aparecer como parte del episodio."
        )
    for w in warnings:
        text += f"\n\n{w}" if plain else f"\n\n:orange[{w}]"
    return text


def episode_markdown(result: dict) -> str:
    title, _, _ = VERDICTS.get(verdict_of(result), (result["verdict"], "", ""))
    r, null = result["ratios"], result["null"]
    lines = [
        f"# Episodio del {result['days'][0]} al {result['days'][-1]}",
        "",
        f"## {title}",
        "",
        episode_story(result),
        "",
        comparison(result, plain=True),
        "",
    ]
    lines += ["| | Cambio | Rango de días normales |", "|---|---|---|"]
    lines += [
        f"| {RATIO_NAMES[k]} | {pct(v)} | {pct(null[k]['lo'])} a {pct(null[k]['hi'])} |"
        for k, v in r.items()
        if v is not None
    ]
    lines += ["", f"Referencia: días normales del mismo día de la semana del {result['data']['start']} al {result['data']['end']}.",
              "Fuente: estaciones de la red de monitoreo y satélite TEMPO."]  # fmt: skip
    return "\n".join(lines)


def show_episode(result: dict) -> None:
    title, _, color = VERDICTS.get(verdict_of(result), (result["verdict"], "", "gray"))
    st.markdown(f"## :{color}[{title.upper()}]")
    st.markdown(episode_story(result))
    st.markdown(comparison(result))
    start, end = date.fromisoformat(result["days"][0]), date.fromisoformat(result["days"][-1])
    season = season_of(start)
    if season and result.get("references"):
        with st.expander("¿Con qué días se comparó?"):
            show_chart(calendar_chart(season, start, end, result["references"]), width="stretch")
            st.caption(
                "**Borde oscuro:** los días elegidos. **Punto:** los días normales con los que se compararon."
            )
    with st.expander("¿Qué significa cada cosa?"):
        st.markdown(GLOSSARY)

    r, null = result["ratios"], result["null"]
    c1, c2, c3 = st.columns(3)
    metric(c1, "NOₓ en el aire", pct(r["concentration"]), "frente a un día normal",
           help="Lo que midieron las estaciones de la red de monitoreo.")  # fmt: skip
    metric(c2, "Esperado solo por el clima", pct(r["weather"]), "con lo que se echa siempre",
           help="Lo que habría en el aire si coches y fábricas echaran lo de siempre y solo cambiaran el viento y el aire de esos días.")  # fmt: skip
    if r.get("background") is not None:
        metric(c3, "Contaminación en toda la región", pct(r["background"]), "satélite, fuera de la ciudad")

    rows = pd.DataFrame(
        [
            {"Cociente": RATIO_NAMES[k], "ratio": v, "lo": null[k]["lo"], "hi": null[k]["hi"]}
            for k, v in r.items()
            if v is not None
        ]
    )
    with st.expander("¿Cómo se ve contra días normales?", expanded=True):
        show_chart(change_chart(rows, "Cociente"), width="stretch")
        st.caption(
            "**Punto:** esos días. **Barra gris:** cuánto varía en días normales. Si el punto queda fuera de su barra, es algo fuera de lo común."
        )

    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Exportar ficha (Markdown)", episode_markdown(result), "episodio.md", icon=":material/download:"
    )
    c2.download_button(
        "Datos (JSON)", json.dumps(result, indent=2), "episodio.json", icon=":material/data_object:"
    )
    if season and c3.button("¿Hubo una medida esos días? Evalúala", icon=":material/arrow_forward:"):
        go("medida", prefill=(season, start, end), measure_mode=MODES[1])


def episode_page() -> None:
    st.title("Episodio: ¿fue el clima?")
    st.markdown(
        "**¿Por qué una semana estuvo más (o menos) contaminada?** A veces es el clima (poco viento junta la contaminación) y a veces es que se echó más. Elige los días y te decimos si el clima basta para explicarlo. Si sabes que hubo una medida, usa **Evaluar medida**."
    )

    saved = st.session_state.pop("episode_saved", None)
    if saved:
        source("saved")
        st.caption(f"Semana del boletín: {saved['start']} a {saved['end']} (datos de OpenAQ).")
        show_episode(saved)
        st.divider()
        st.caption("Para diagnosticar otro periodo, elige abajo.")

    source("live")
    period = pick_period(
        "episode", SIMAT_SEASONS, default=("nov–dic 2023", date(2023, 12, 18), date(2023, 12, 22))
    )
    st.caption(
        "Por ahora, hasta dic 2024 (estaciones SIMAT); 2025 y 2026 llegan cuando el comando lea OpenAQ."
    )
    if period and (period[2] - period[1]).days + 1 > LONG_EPISODE:
        n = (period[2] - period[1]).days + 1
        st.warning(
            f"Elegiste {n} días. Este diagnóstico es para episodios cortos (hasta 2 semanas): se compara con días "
            "de las 4 semanas de alrededor, así que un cambio largo se mezcla con su propia comparación. "
            "Para un cambio que duró semanas o meses usa **Evaluar medida**."
        )
        if st.button("Evaluar como medida", icon=":material/arrow_forward:"):
            go("medida", prefill=period, measure_mode=MODES[1])
    if period is None or not st.button("Diagnosticar", type="primary"):
        return
    season, start, end = period
    with st.spinner("Comparando con días normales (~20 s la primera vez)…"):
        args = ("episode", "--days", f"{start}:{end}", "--data", ":".join(SEASONS[season]), "--label", "ep")
        code, out, err, files = run_cli((*args, "--runs-dir"))
    text = files.get("episodes/ep.json")
    if code or text is None:
        st.error(
            "No se pudo diagnosticar ese periodo: "
            + ((err or out).strip().splitlines() or ["sin detalle"])[-1]
        )
        return
    show_episode(json.loads(text))


# ---------------------------------------------------------------- Medida

SAVED_MEASURES = {
    "Confinamiento 2020, fase 2 (frente a 2019)": ("normalized_ratio.lockdown/lockdown.json", "phase2", None),
    "Confinamiento 2020, fase 3 (frente a 2019)": ("normalized_ratio.lockdown/lockdown.json", "phase3", None),
    "Contingencias con medidas, feb–may 2024": (
        "normalized_ratio.contingencies/contingencies.json",
        "measures",
        None,
    ),
    "Semana antes de Navidad 2023": (
        "normalized_ratio.calendar-pre_christmas/calendar.json",
        "pre_christmas",
        "pre_christmas",
    ),
}
MODES = ["Ejemplos ya calculados", "Mis fechas (en vivo, ~30 s)"]


def saved_measure(name: str) -> tuple[dict, dict | None]:
    file, key, episode = SAVED_MEASURES[name]
    data = read_json(RUNS / file)
    r = data["effect"][key]["did"] if "effect" in data else data["scenarios"][key]
    return r, read_json(RUNS / "episodes" / f"{episode}.json") if episode else None


def measure_verdict(lo: float, hi: float, episode: dict | None) -> tuple[str, str, str]:
    """Label, colour and explanation; a change is not credited to the measure when the episode check says the
    weather explains it or pollution accumulated over the region."""
    if lo <= 1 <= hi:
        return (
            "NO DETECTABLE",
            "gray",
            "El cambio cabe dentro de lo que varía la emisión en días normales. **No quiere decir que la medida no funcionó**: puede haber un cambio menor que el mínimo visible.",
        )
    if episode and (
        verdict_of(episode) in ("weather_explains", "weather_explains_part")
        or "background_up" in (episode.get("notes") or [])
    ):
        return (
            "CAMBIO NO ATRIBUIBLE A LA MEDIDA",
            "orange",
            "Lo que salió de la ciudad parece haber cambiado, pero esos días el clima lo explica o la contaminación subió también en toda la región. Puede ser contaminación que se juntó en el aire, no la medida.",
        )
    word = "BAJA" if hi < 1 else "SUBIDA"
    return (
        f"{word} DETECTADA",
        "green",
        "El cambio queda fuera de lo que varía la emisión en días normales, y el clima y el fondo regional no lo explican.",
    )


def episode_check(season: str, start: date, end: date) -> dict | None:
    if season not in SIMAT_SEASONS:
        return None
    args = ("episode", "--days", f"{start}:{end}", "--data", ":".join(SEASONS[season]), "--label", "ep")
    code, _, _, files = run_cli((*args, "--runs-dir"))
    return json.loads(files["episodes/ep.json"]) if code == 0 and "episodes/ep.json" in files else None


def parse_sheet(sheet: str) -> dict:
    """The numbers of a `ficha-medida` sheet (its Markdown is the contract of the command)."""
    num = r"([−+-]?\d+)%"
    found = {
        "change": re.search(r"descontado el clima \| " + num, sheet),
        "range": re.search(r"Rango compatible[^|]*\| " + num + r" a " + num, sheet),
        "mdc": re.search(r"bajas de (\d+)%", sheet),
        "claim": re.search(r"Cambio anunciado \| " + num + r": \*\*(\w+)\*\*", sheet),
        "days": re.search(r"Días evaluados: (\d+) días", sheet),
        "satellite": re.search(r"satélite TEMPO.*?cambio " + num + r", rango " + num + r" a " + num, sheet),
    }
    value = lambda s: int(s.replace("−", "-")) / 100  # noqa: E731
    out: dict = {}
    if found["change"]:
        out["change"] = value(found["change"].group(1))
    if found["range"]:
        out["lo"], out["hi"] = value(found["range"].group(1)), value(found["range"].group(2))
    if found["mdc"]:
        out["mdc"] = int(found["mdc"].group(1)) / 100
    if found["claim"]:
        out["claim"], out["claim_fits"] = value(found["claim"].group(1)), found["claim"].group(2) == "cabe"
    if found["days"]:
        out["days"] = int(found["days"].group(1))
    if found["satellite"]:
        out["satellite"] = tuple(value(found["satellite"].group(i)) for i in (1, 2, 3))
    return out


def measure_page() -> None:
    st.title("Evaluar una medida")
    st.markdown(
        "**¿Una medida cambió la emisión?** Sabes qué se hizo y cuándo: el sistema descuenta el clima y compara esos días con días normales. Si solo quieres saber por qué una semana estuvo sucia, usa **Episodio**."
    )
    if "measure_mode" in st.session_state:
        st.session_state["measure_mode_radio"] = st.session_state.pop("measure_mode")
    mode = st.radio("Modo", MODES, horizontal=True, key="measure_mode_radio")

    if mode == MODES[0]:
        source("saved")
        name = st.selectbox("Medida", list(SAVED_MEASURES))
        r, episode = saved_measure(name)
        label, color, explain = measure_verdict(r["lo"], r["hi"], episode)
        st.markdown(f"## :{color}[{label}]")
        st.markdown(explain)
        metric(
            st,
            "Cambio estimado de la emisión",
            pct(r["ratio"]),
            f"rango compatible {pct(r['lo'])} a {pct(r['hi'])}",
        )
        rows = pd.DataFrame([{"Medida": name, **{k: r[k] for k in ("ratio", "lo", "hi")}}])
        show_chart(change_chart(rows, "Medida", "Cambio de la emisión"), width="stretch")
        if episode and st.button("Ver el diagnóstico de esos días", icon=":material/arrow_forward:"):
            go("episodio", episode_saved={**episode, "start": episode["days"][0], "end": episode["days"][-1]})
        return

    source("live")
    title = st.text_input("Nombre de la medida", "Hoy No Circula sabatino")
    period = pick_period(
        "measure", list(SEASONS), default=("feb–may 2024", date(2024, 5, 14), date(2024, 5, 16))
    )
    claim = st.number_input(
        "Efecto anunciado (%; 0 si no hay)",
        -100,
        100,
        -20,
        step=5,
        help="Por ejemplo, −20 si se anunció que la emisión bajó 20 %.",
    )
    if period is None or not st.button("Evaluar", type="primary"):
        return
    season, start, end = period
    with st.spinner("Estimando con días normales al azar y revisando el clima de esos días (~45 s)…"):
        args = (
            "ficha-medida",
            "--days",
            f"{start}:{end}",
            "--data",
            ":".join(SEASONS[season]),
            "--title",
            title,
        )
        args += ("--claim", str(claim / 100)) if claim else ()
        code, out, err, files = run_cli((*args, "--out-dir"))
        episode = episode_check(season, start, end)
    sheet = next((t for p, t in files.items() if p.endswith(".md")), None)
    if code or sheet is None:
        st.error(
            "No se pudo evaluar ese periodo: " + ((err or out).strip().splitlines() or ["sin detalle"])[-1]
        )
        return
    s = parse_sheet(sheet)
    if "lo" not in s:
        st.markdown(sheet)
        return
    label, color, explain = measure_verdict(1 + s["lo"], 1 + s["hi"], episode)
    st.markdown(f"## :{color}[{label}]")
    st.markdown(explain)
    c1, c2, c3 = st.columns(3)
    metric(
        c1,
        "Cambio estimado de la emisión",
        pct(1 + s["change"]),
        f"rango compatible {pct(1 + s['lo'])} a {pct(1 + s['hi'])}",
    )
    if "mdc" in s:
        metric(
            c2,
            f"Lo mínimo visible con {s.get('days', '?')} días",
            f"−{s['mdc']:.0%}",
            "bajas menores pasan desapercibidas",
        )
    if "claim" in s:
        metric(
            c3,
            "Efecto anunciado",
            pct(1 + s["claim"]),
            "cabe en el rango" if s["claim_fits"] else "no cabe en el rango",
        )
        if s["claim_fits"]:
            st.info(
                f"**El {pct(1 + s['claim'])} anunciado no se puede confirmar ni descartar** con estos días: es compatible con lo medido, pero también lo sería no haber cambiado nada."
            )
        else:
            st.warning(
                f"**El {pct(1 + s['claim'])} anunciado no es compatible** con lo medido en estos días."
            )
    if "satellite" in s:
        change, lo, hi = s["satellite"]
        st.caption(
            f"Segunda opinión del satélite (sin estaciones): {pct(1 + change)}, rango {pct(1 + lo)} a {pct(1 + hi)}."
        )
    if episode is None:
        st.caption(
            "No se revisó el fondo regional: el diagnóstico de episodios aún no lee OpenAQ (2025 en adelante)."
        )

    with st.expander("Ficha completa"):
        st.markdown(sheet)
    c1, c2, c3 = st.columns(3)
    c1.download_button("Exportar ficha (Markdown)", sheet, "ficha_medida.md", icon=":material/download:")
    if episode and c2.button("Ver el diagnóstico de esos días", icon=":material/arrow_forward:"):
        go("episodio", episode_saved={**episode, "start": str(start), "end": str(end)})
    if c3.button("¿Cuántos días harían falta?", icon=":material/arrow_forward:"):
        go("piloto", pilot_season=season, pilot_effect=max(5, min(50, abs(claim) or 10)))


# ---------------------------------------------------------------- Piloto


@st.cache_data
def switchback() -> pd.DataFrame:
    d = pd.read_csv(RUNS / "switchback" / "switchback.csv")
    d = d[(d["drop"] == 0) & (d["estimator"] == "e7") & d["design"].isin(list(DESIGNS))].copy()
    d["Diseño"] = d["design"].map(DESIGNS)
    d["Temporada"] = d["season"].str[:2].map({"fm": "feb–may", "nd": "nov–dic"}) + " " + d["season"].str[2:]
    return d


def pilot_page() -> None:
    st.title("Planear un piloto")
    st.markdown("**¿Cuánto tiempo y con qué diseño hay que aplicar una medida para poder ver su efecto?**")
    source("saved", "live")

    if "pilot_effect" in st.session_state:
        st.session_state["pilot_effect_slider"] = st.session_state.pop("pilot_effect")
    from_measure = st.session_state.pop("pilot_season", None)
    if from_measure:
        st.session_state["pilot_kind"] = "nov–dic" if from_measure.startswith("nov") else "feb–may"
        st.session_state["pilot_live_season"] = from_measure

    c1, c2, c3 = st.columns(3)
    effect = c1.slider("Efecto esperado (baja de la emisión, %)", 5, 50, 10, key="pilot_effect_slider") / 100
    kind = c2.radio(
        "Temporada",
        list(SEASON_LENGTH),
        horizontal=True,
        key="pilot_kind",
        help="La de feb–may tiene menos estancamientos: se ve más.",
    )
    carry = c3.toggle(
        "El efecto dura más allá de la semana con medida",
        help="Si la gente no cambia su rutina de inmediato (arrastre del 50 %).",
    )

    d = switchback()
    d = d[d["Temporada"].str.startswith(kind) & (d["carryover"] == ("carry50" if carry else "none"))]
    mdd = d.groupby("Diseño")["mdd"].median()
    rows = pd.DataFrame({"Diseño": mdd.index, "mdd": mdd.to_numpy()}).sort_values("mdd")
    rows["Temporadas necesarias"] = [max(1, math.ceil((m / effect) ** 2)) for m in rows["mdd"]]
    best = rows.iloc[0]
    continuous = int(rows.set_index("Diseño").loc["Continuo", "Temporadas necesarias"])
    n = int(best["Temporadas necesarias"])
    st.markdown(
        f"### Con **{best['Diseño'].lower()}**: {n} {'temporada' if n == 1 else 'temporadas'} · continuo: {continuous}"
    )
    st.caption(f"Una temporada = {SEASON_LENGTH[kind]}, con la medida la mitad de los días.")

    bars = (
        alt.Chart(rows)
        .mark_bar()
        .encode(
            x=alt.X("mdd:Q", title="Baja mínima visible en una temporada", axis=alt.Axis(format="%")),
            y=alt.Y("Diseño:N", sort=None, title=None),
            color=alt.condition(alt.datum.mdd <= effect, alt.value("#2a9d8f"), alt.value("#c9ced6")),
            tooltip=[
                "Diseño",
                alt.Tooltip("mdd:Q", format=".0%", title="baja mínima"),
                "Temporadas necesarias",
            ],
        )
    )
    rule = alt.Chart(pd.DataFrame({"x": [effect]})).mark_rule(color="#d62828", strokeWidth=2).encode(x="x:Q")
    show_chart((bars + rule).properties(height=230), width="stretch")
    st.caption("Línea roja: tu efecto. Verde: se ve en una sola temporada.")

    with st.container(border=True):
        st.markdown(
            "**¿Por qué alternar ayuda?** La emisión sube y baja ±15 % de una semana a otra por causas que el clima no explica (una deriva lenta). "
            "Con la medida continua, esa deriva se confunde con el efecto. Alternando, cada semana con medida se compara con su vecina sin medida y la deriva se cancela."
        )
    if carry:
        st.warning(
            "Si el efecto dura más que la semana con medida, deja una semana de separación entre la semana con medida y la sin medida."
        )
    st.caption(
        "Temporadas necesarias ≈ (baja mínima ÷ efecto)²; supone temporadas parecidas. Fuente: simulación con eventos inyectados en 6 temporadas reales (exploración F1)."
    )
    st.download_button(
        "Exportar tabla (CSV)",
        rows.rename(columns={"mdd": "baja_minima_una_temporada"}).to_csv(index=False),
        "piloto.csv",
        icon=":material/download:",
    )
    with st.expander("Por temporada"):
        st.dataframe(d.pivot_table(index="Diseño", columns="Temporada", values="mdd").style.format("{:.0%}"))

    st.subheader("Segunda opinión: ficha de días (en vivo, ~75 s)")
    st.caption(
        "Calcula cuántos días hábiles hacen falta con la medida continua, desde la variación de una temporada concreta. Es más conservadora que la simulación."
    )
    season = st.selectbox("Temporada", list(SEASONS), index=1, key="pilot_live_season")
    if st.button("Calcular días necesarios"):
        with st.spinner("Midiendo la variación de la temporada (~75 s)…"):
            drops = sorted({round(effect, 2), 0.1, 0.2, 0.3})
            args = (
                "ficha-dias",
                "--data",
                ":".join(SEASONS[season]),
                *[x for v in drops for x in ("--drops", str(v))],
            )
            code, out, err, files = run_cli((*args, "--out-dir"))
        sheet = next((t for p, t in files.items() if p.endswith(".md")), None)
        if code or sheet is None:
            st.error("No se pudo calcular: " + ((err or out).strip().splitlines() or ["sin detalle"])[-1])
        else:
            with st.container(border=True):
                st.markdown(sheet)


# ---------------------------------------------------------------- Ozono


OZONE_SIGN = {"sube": [214, 40, 40], "igual": [108, 117, 125], "baja": [42, 157, 143]}
OZONE_REGIME = {"COV": ([123, 44, 191], "limitado por COV"), "transicion": ([242, 160, 40], "transición"),
                "NOx": ([58, 134, 255], "limitado por NOₓ")}  # fmt: skip
FNR_BBOX, FNR_CELL = (-99.4, 19.1), 0.05  # the grid of ozone_regime/hcho_no2_ratio.py


def ozone_map(stations: pd.DataFrame, year: str, show_grid: bool) -> pdk.Deck:
    """Base map, the satellite regime per grid cell and the stations coloured by their Sunday ozone change."""
    layers = []
    if show_grid:
        grid = read_csv(EXPLORATIONS / "ozone_regime" / "results" / "fnr_map.csv")
        grid = grid[grid["season"].astype(str) == year].copy()
        x0 = FNR_BBOX[0] + grid["ix"] * FNR_CELL
        y0 = FNR_BBOX[1] + grid["iy"] * FNR_CELL
        grid["polygon"] = [
            [[x, y], [x + FNR_CELL, y], [x + FNR_CELL, y + FNR_CELL], [x, y + FNR_CELL]]
            for x, y in zip(x0, y0, strict=True)
        ]
        grid["fill"] = grid["reg_Duncan2010"].map(lambda r: [*OZONE_REGIME[r][0], 70])
        grid["label"] = grid["reg_Duncan2010"].map(lambda r: OZONE_REGIME[r][1])
        grid["text"] = "Satélite: " + grid["label"] + " (cociente " + grid["fnr"].round(1).astype(str) + ")"
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                grid[["polygon", "fill", "text"]],
                get_polygon="polygon",
                get_fill_color="fill",
                stroked=False,
                pickable=True,
            )
        )
    st_ = stations.copy()
    st_["fill"] = st_["o3_sign"].map(lambda v: OZONE_SIGN.get(v, [173, 181, 189]))
    st_["text"] = (
        st_["station"] + ": ozono en domingo " + st_["cambio"].map(lambda c: pct(1 + c))
        + " · " + st_["Régimen (satélite)"].fillna("sin dato de satélite") + " · "
        + st_["km"].round(0).astype(int).astype(str) + " km al centro"
    )  # fmt: skip
    data = st_[["lon", "lat", "fill", "text", "station"]]
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data,
            get_position=["lon", "lat"],
            get_fill_color="fill",
            get_radius=900,
            radius_min_pixels=7,
            stroked=True,
            get_line_color=[255, 255, 255],
            line_width_min_pixels=2,
            pickable=True,
        )
    )
    layers.append(
        pdk.Layer(
            "TextLayer",
            data,
            get_position=["lon", "lat"],
            get_text="station",
            get_size=12,
            get_color=[33, 37, 41],
            get_pixel_offset=[0, -16],
        )
    )
    view = pdk.ViewState(latitude=19.42, longitude=-99.13, zoom=9.3)
    return pdk.Deck(layers=layers, initial_view_state=view, map_style="light", tooltip={"text": "{text}"})


def ozone_page() -> None:
    st.title("Ozono: ¿sirve recortar NOₓ?")
    source("saved", "notes")
    st.markdown(
        "En el **centro** de la ciudad, **no**: cuando el NOₓ baja (los domingos), el ozono queda igual o sube. El centro está limitado por compuestos orgánicos volátiles (COV); en la orilla, recortar NOₓ sí empieza a ayudar."
    )
    c1, c2, c3 = st.columns(3)
    metric(c1, "NOₓ en domingo", "−30 %", "frente a días hábiles")
    metric(c2, "Ozono máximo en domingo, centro", "+3 %", "periferia: 0 %")
    metric(c3, "Confinamiento 2020", "NOₓ −33 %", "ozono solo −2 a −4 %")

    year = st.radio("Temporada de ozono", ["2025", "2024"], horizontal=True)
    s = read_csv(EXPLORATIONS / "ozone_regime" / "results" / f"stations_fnr_{year}.csv").dropna(
        subset=["o3_sun"]
    )
    s["Ozono en domingo"] = s["o3_sign"].map({"sube": "sube", "igual": "igual", "baja": "baja"})
    s["cambio"] = s["o3_sun"] - 1
    regime = {"COV": "limitado por COV", "transicion": "transición", "NOx": "limitado por NOₓ"}
    s["Régimen (satélite)"] = s["regime"].map(regime)
    show_grid = st.toggle("Mostrar el régimen que ve el satélite", value=True)
    st.pydeck_chart(ozone_map(s, year, show_grid), height=520)
    legend = "**Estaciones (ozono máximo en domingo):** :red[● sube] · :gray[● igual] · :green[● baja]"
    if show_grid:
        legend += "  \n**Cuadros (satélite):** :violet[■ limitado por COV] · :orange[■ transición] · :blue[■ limitado por NOₓ]"
    st.markdown(legend)
    st.caption(
        "El domingo hay ~30 % menos NOₓ. Si en una estación el ozono **sube** ese día, recortar NOₓ ahí no lo baja. "
        "Los cuadros vienen del cociente formaldehído/NO₂ del satélite TEMPO (cuadros de ~5 km, umbrales de Duncan et al. 2010). "
        "Pasa el cursor sobre una estación o un cuadro para ver el detalle."
    )

    st.subheader("Qué implica para las contingencias")
    st.markdown(
        "Las 5–10 activaciones al año restringen vehículos (NOₓ). En el centro eso no baja el ozono; conviene sumar medidas sobre COV: **vapores de combustible, solventes, gas LP**."
    )
    st.caption(
        "Coincide con Vazquez Santiago et al. (2021, OMI). El cambio de régimen dentro de la temporada no está confirmado."
    )
    st.download_button(
        "Descargar estaciones (CSV)",
        s.to_csv(index=False),
        f"ozono_estaciones_{year}.csv",
        icon=":material/download:",
    )


# ---------------------------------------------------------------- Calidad de redes


def quality_page() -> None:
    st.title("Calidad de las redes")
    st.markdown(
        "**Para el operador de la red:** qué estaciones fallaron, cuándo, y qué se pierde en la copia pública (OpenAQ) frente a la oficial (SIMAT)."
    )
    source("saved")
    catalog = read_csv(EXPLORATIONS / "network_qc" / "catalog.csv")
    catalog = catalog[catalog["param"] == "NOX"].copy()
    completeness = read_csv(EXPLORATIONS / "network_qc" / "completeness_by_month.csv")
    completeness = completeness[completeness["month"] >= "2023-01"]

    outages = catalog[(catalog["type"] == "network_outage") & (catalog["status"] != "known")]
    c1, c2, c3 = st.columns(3)
    metric(
        c1,
        "Cortes de toda la red sin documentar",
        str(len(outages)),
        f"{outages['month'].min()} a {outages['month'].max()}",
    )
    both = completeness.pivot_table(index="month", columns="source", values="completeness").dropna()
    if len(both):
        metric(
            c2,
            "Horas que OpenAQ pierde frente a SIMAT",
            f"{1 - (both['OpenAQ'] / both['SIMAT']).mean():.0%}",
            "en los meses con ambas fuentes",
        )
    last = completeness[completeness["source"] == "OpenAQ"].iloc[-1]
    metric(
        c3,
        f"Último mes ({last['month']})",
        f"{last['completeness']:.0%} de horas",
        f"{last['stations']} estaciones",
    )

    line = (
        alt.Chart(completeness)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title=None),
            y=alt.Y(
                "completeness:Q",
                title="Horas con dato",
                axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0.5, 1]),
            ),
            color=alt.Color("source:N", title="Fuente"),
            tooltip=["month", "source", alt.Tooltip("completeness:Q", format=".0%"), "stations"],
        )
        .properties(height=220)
    )
    show_chart(line, width="stretch")

    st.subheader("Fallas por mes")
    months = sorted(catalog["month"].unique(), reverse=True)
    c1, c2 = st.columns([1, 2])
    month = c1.selectbox("Mes", months)
    only = c2.toggle("Solo las que afectan los análisis", value=True)
    rows = catalog[catalog["month"] == month]
    rows = rows[rows["relevant"]] if only else rows
    table = pd.DataFrame(
        {
            "Fuente": rows["source"],
            "Estación": rows["station"].replace({"ALL": "toda la red"}),
            "Falla": rows["type"].map(QC_TYPES).fillna(rows["type"]),
            "Desde": rows["start"].str[:16],
            "Hasta": rows["end"].str[:16],
            "Horas": rows["hours"],
            "Estado": rows["status"].map({"new": "nueva", "candidate": "por confirmar", "known": "conocida"}),
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button(
        f"Descargar fallas de {month} (CSV)",
        table.to_csv(index=False),
        f"fallas_{month}.csv",
        icon=":material/download:",
    )
    st.caption("Detectores de la exploración F7; entran a `nox-ml update` en la fase 1.")


# ---------------------------------------------------------------- Zonas, salud, satélite, método


def zones_page() -> None:
    st.title("Zonas e inventario")
    st.markdown(
        "**¿El inventario reparte bien la emisión vial?** El sistema estima qué parte de la emisión sale de cada zona. Es una señal para revisar el inventario, no una auditoría."
    )
    source("saved", "notes")
    st.markdown(
        "**Oriente** (Chalco, Ixtapaluca, Chimalhuacán, Texcoco y el oriente de Iztapalapa): ¿qué parte de la emisión vial de la ciudad?"
    )
    inv = read_csv(EXPLORATIONS / "inventory_east" / "out" / "inventory_compare.csv")
    moves = inv[inv["source"].str.startswith("MOVES 2016 (")]["east_share"]
    edgar = inv[inv["source"].str.contains("TRO")]["east_share"]
    flux = read_csv(EXPLORATIONS / "inventory_east" / "out" / "flux_zones_w1.csv")
    sat = flux[flux["layer"] == "tau4"]["east"]
    rows = pd.DataFrame(
        [
            ("Este sistema: inversión", 0.048, 0.095, "notas F4"),
            ("Este sistema: satélite", sat.min(), sat.max(), f"{len(sat)} temporadas"),
            ("Inventario MOVES-México 2016", moves.min(), moves.max(), "3 formas de repartir"),
            ("EDGAR (2018 y 2022)", edgar.min() - 0.002, edgar.max() + 0.002, "transporte por carretera"),
        ],
        columns=["Fuente", "lo", "hi", "nota"],
    )
    x = alt.X(
        "lo:Q",
        title="Parte de la emisión vial total",
        axis=alt.Axis(format="%"),
        scale=alt.Scale(domain=[0, 0.2]),
    )
    color = alt.condition(
        alt.FieldOneOfPredicate("Fuente", list(rows["Fuente"][:2])),
        alt.value("#2a9d8f"),
        alt.value("#8d99ae"),
    )
    tooltip = ["Fuente", alt.Tooltip("lo:Q", format=".0%"), alt.Tooltip("hi:Q", format=".0%"), "nota"]
    bars = (
        alt.Chart(rows)
        .mark_bar(height=18)
        .encode(x=x, x2="hi:Q", y=alt.Y("Fuente:N", sort=None, title=None), color=color, tooltip=tooltip)
    )
    show_chart(bars.properties(height=190), width="stretch")
    st.markdown(
        f"El sistema ve **menos** emisión en el oriente ({rows['lo'].iloc[:2].min():.0%}–{rows['hi'].iloc[:2].max():.0%}) que las fuentes oficiales ({rows['lo'].iloc[2:].min():.0%}–{rows['hi'].iloc[2:].max():.0%}). Vale la pena revisar el reparto del inventario en esa zona."
    )
    zones = flux[flux["layer"] == "tau4"][["season", "n_days", "SO", "S", "O", "Centro", "Norte", "Oriente"]]
    with st.expander("Reparto por zona y temporada (satélite)"):
        st.dataframe(
            zones.set_index("season").style.format(
                {c: "{:.0%}" for c in ["SO", "S", "O", "Centro", "Norte", "Oriente"]}
            )
        )
    st.download_button(
        "Descargar (CSV)", zones.to_csv(index=False), "zonas_satelite.csv", icon=":material/download:"
    )


def health_page() -> None:
    st.title("Salud (preliminar)")
    st.markdown(
        "**¿Cuánto está en juego?** Muertes y casos de asma infantil que se evitarían al año si bajara la emisión vial."
    )
    source("saved")
    st.warning(
        "Solo orden de magnitud: las funciones de riesgo y las tasas base aún no se verifican con la fuente primaria."
    )
    s = read_csv(EXPLORATIONS / "health" / "results" / "scenarios.csv")
    levels = sorted(int(v) for v in s["scenario_pct"].unique() if v > 0)
    drop = st.select_slider("Baja de la emisión vial (%)", levels, value=10)
    get = lambda m: s[(s["scenario_pct"] == drop) & (s["metric"] == m)].iloc[0]  # noqa: E731
    deaths, asthma, no2 = get("deaths"), get("asthma_cases"), get("dNO2_ppb")
    c1, c2, c3 = st.columns(3)
    metric(
        c1,
        "Muertes evitadas al año",
        f"~{deaths['p50']:,.0f}",
        f"rango {deaths['p05']:,.0f}–{deaths['p95']:,.0f}",
    )
    metric(
        c2,
        "Casos de asma infantil evitados",
        f"~{asthma['p50']:,.0f}",
        f"rango {asthma['p05']:,.0f}–{asthma['p95']:,.0f}",
    )
    metric(c3, "Baja del NO₂ promedio", f"{no2['p50']:.1f} ppb", f"rango {no2['p05']:.1f}–{no2['p95']:.1f}")
    st.caption("Simulador de la exploración F5: rango del 5 al 95 % de las simulaciones.")


def satellite_page() -> None:
    st.title("Segunda opinión del satélite")
    st.markdown(
        "**¿El satélite, sin usar las estaciones, ve lo mismo?** Emisión de sábado y domingo frente a días hábiles, temporada por temporada."
    )
    source("saved")
    rows = []
    for path in sorted((RUNS / "flux_divergence").glob("*.json")):
        ratios = read_json(path)["ratios"]["tau_4h"]
        window = tuple(path.stem.split("_"))
        season = next((s for s, w in SEASONS.items() if w == window), path.stem)
        for day, name in (("saturday", "sábado"), ("sunday", "domingo")):
            rows.append(
                {"Temporada": f"{season} · {name}", **{k: ratios[day][k] for k in ("ratio", "lo", "hi")}}
            )
    table = pd.DataFrame(rows)
    show_chart(change_chart(table, "Temporada", "Emisión frente a un día hábil"), width="stretch")
    st.caption(
        "Un domingo emite ~40–50 % menos; las estaciones dan −36 a −53 %. Coinciden sin compartir datos."
    )
    st.download_button(
        "Descargar (CSV)", table.to_csv(index=False), "satelite_fin_de_semana.csv", icon=":material/download:"
    )


def method_page() -> None:
    st.title("Datos y método")
    st.markdown(
        """
| Dato | Fuente | Resolución |
|---|---|---|
| NOₓ, NO₂ y ozono | SIMAT hasta 2024; desde 2025 las mismas estaciones vía OpenAQ | Horaria, ~24 estaciones |
| Columna de NO₂ y formaldehído | Satélite TEMPO (NASA) | Horaria de día, ~2 × 4.5 km |
| Viento, capa de mezcla | Aeropuertos (IEM), ERA5, MERRA-2 | Horaria |

**Validación:** confinamiento 2020 −50 % (esperado −40 a −60 %); placebo 0.95–1.11 en 4 temporadas no vistas; 5 % de falsas alarmas en 960 pruebas.

**Lo que no hace:** ver medidas de 5–10 % en una temporada, dar toneladas absolutas, separar autos de camiones, noche o tiempo real, pronosticar ozono.

**Reproducir:** el código está en el repositorio `nox_ml` y los datos versionados con DVC en DagsHub. Cada ficha exportada indica sus fechas y fuentes.
"""
    )
    st.info(
        "Conjunto de datos con DOI (Zenodo): en la fase 1. Mientras, cada pantalla tiene su botón de descarga."
    )


def main() -> None:
    st.set_page_config(page_title="NOx ZMVM · demo", layout="wide", page_icon=":material/air:")
    PAGES.update(
        boletin=st.Page(
            bulletin_page,
            title="Boletín del mes",
            url_path="boletin",
            default=True,
            icon=":material/newspaper:",
        ),
        episodio=st.Page(
            episode_page, title="Episodio: ¿fue el clima?", url_path="episodio", icon=":material/cloud:"
        ),
        medida=st.Page(measure_page, title="Evaluar medida", url_path="medida", icon=":material/rule:"),
        piloto=st.Page(pilot_page, title="Planear piloto", url_path="piloto", icon=":material/science:"),
        ozono=st.Page(ozone_page, title="Ozono", url_path="ozono", icon=":material/wb_sunny:"),
        calidad=st.Page(
            quality_page, title="Calidad de redes", url_path="calidad", icon=":material/sensors:"
        ),
        zonas=st.Page(zones_page, title="Zonas e inventario", url_path="zonas", icon=":material/map:"),
        salud=st.Page(health_page, title="Salud (preliminar)", url_path="salud", icon=":material/favorite:"),
        satelite=st.Page(
            satellite_page, title="Satélite", url_path="satelite", icon=":material/satellite_alt:"
        ),
        metodo=st.Page(method_page, title="Datos y método", url_path="metodo", icon=":material/info:"),
    )
    groups = {
        "Público": ["boletin", "episodio"],
        "Medidas": ["medida", "piloto"],
        "Temas": ["ozono", "calidad", "zonas", "salud", "satelite", "metodo"],
    }
    with st.sidebar:
        st.markdown("### ¿Fue el clima o fue la ciudad?")
        st.caption("Emisión de NOₓ de la ZMVM · demo de UX · equipo 39")
    st.navigation({g: [PAGES[k] for k in keys] for g, keys in groups.items()}).run()


if __name__ == "__main__":
    main()
