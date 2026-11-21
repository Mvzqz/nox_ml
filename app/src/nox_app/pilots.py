# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false
# pyright: reportOptionalSubscript=false, reportReturnType=false
# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Section 2, Planes y Pilotos (planner): the history of pilots planned with the app, their life cycle,
report and log, and the planner of new pilots. Only pilots designed here are evaluated: a measure applied
before did not follow the app's design rules."""

import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from nox_app import charts, rules
from nox_app.common import (
    RUNS,
    add_pilot,
    event_tuples,
    go,
    is_planner,
    new_pilot_id,
    pct,
    period_label,
    pilot,
    pilots,
    read_csv,
    short_date,
    today,
)
from nox_app.design import ICONS, kpi, page_header, show_chart, show_legend

VERDICT_COLORS = {
    rules.CONFIRMED: "green",
    rules.NO_CHANGE: "gray",
    rules.INCONCLUSIVE: "orange",
    rules.INSUFFICIENT: "orange",
}
STATUS_ICONS = {rules.WAITING: ICONS["caution"], rules.PRELIMINARY: ICONS["caution"]}
STATUS_COLORS = {rules.DRAFT: "gray", rules.SCHEDULED: "blue", rules.RUNNING: "blue", rules.WAITING: "orange",
                 rules.PRELIMINARY: "orange", rules.CONSOLIDATED: "green"}  # fmt: skip
EVALUATED = (rules.PRELIMINARY, rules.CONSOLIDATED)
DESIGNS = {"a_contiguous": "Continuo", "b_alternate_days": "Días alternos", "c_alternate_weeks": "Semanas alternas",
           "d_two_week_blocks": "Bloques de dos semanas", "e_random_days": "Días al azar", "f_random_weeks": "Semanas al azar"}  # fmt: skip
SEASON_LENGTH = {"feb–may": "feb a may, unos 3.5 meses", "nov–dic": "nov y dic, unos 2 meses"}
HEALTH = (
    "Menos NOₓ significa menos exposición a un gas que irrita las vías respiratorias y que ayuda a formar ozono y "
    "partículas finas. El beneficio es mayor para niñas y niños, personas mayores y personas con asma. "
    "Este reporte no cuantifica ese beneficio."
)


def verdict_of(p: dict) -> str | None:
    """The verdict once the pilot has been evaluated, None before."""
    return (
        rules.verdict(p.get("result"), p.get("target"), p.get("coverage"))
        if rules.status(p, today()) in EVALUATED
        else None
    )


def badge(text: str, color: str) -> str:
    return f":{color}-badge[{text}]"


def status_badge(state: str) -> str:
    icon = STATUS_ICONS.get(state)
    return badge(f"{icon} {state}" if icon else state, STATUS_COLORS[state])


def verdict_heading(v: str) -> str:
    return f"### :{VERDICT_COLORS[v]}[{v}]"


def mock_badge(p: dict) -> str:
    return " " + badge("Ejemplo simulado", "gray") if p.get("mock") else ""


def weeks_of(p: dict) -> float:
    return ((date.fromisoformat(p["end"]) - date.fromisoformat(p["start"])).days + 1) / 7


# ---------------------------------------------------------------- history


def compact_period(start: str | None, end: str | None) -> str:
    """'1 jun – 24 jul 2026': the year once when both dates share it, so the table column stays narrow."""
    if not (start and end) or start[:4] != end[:4]:
        return period_label(start, end)
    return f"{short_date(start)[:-5]} – {short_date(end)}"


HISTORY_COLUMNS = [3, 2.2, 0.7, 1.9, 1]  # pilot (name and dates), status, target, verdict, button


def history_row(p: dict, key: str) -> None:
    """One pilot: its name, status and verdict as coloured badges, and a button to open its report."""
    c = st.columns(HISTORY_COLUMNS, vertical_alignment="center")
    c[0].markdown(f"**{p['name']}**  \n:gray[{compact_period(p.get('start'), p.get('end'))}]")
    c[1].markdown(status_badge(rules.status(p, today())))
    c[2].markdown(pct(p["target"]) if p.get("target") is not None else "—")
    v = verdict_of(p)
    c[3].markdown(badge(v.split(" — ")[0], VERDICT_COLORS[v]) if v else ":gray[—]")  # the short name
    if c[4].button("Abrir", key=f"{key}_open_{p['id']}", icon=":material/arrow_forward:"):
        go("pilotos", pilot_id=p["id"])


def pilot_history(key: str) -> None:
    """Every pilot in one list, with filters; each row opens its report, like the bulletin history."""
    c1, c2 = st.columns([2, 1.6])
    statuses = c1.multiselect("Estado", rules.STATUSES, key=f"{key}_status", placeholder="Todos")
    text = c2.text_input("Buscar", key=f"{key}_text", placeholder="Nombre del piloto")
    rows = [
        p for p in pilots()
        if (not statuses or rules.status(p, today()) in statuses) and text.lower() in p["name"].lower()
    ]  # fmt: skip
    if not rows:
        st.info("Ningún piloto cumple esos filtros.")
        return
    with st.container(border=True, key=f"card_{key}_history"):
        head = st.columns(HISTORY_COLUMNS)
        for col, name in zip(head, ["Piloto y fechas", "Estado", "Meta", "Veredicto", ""], strict=True):
            col.caption(f"**{name}**" if name else "")
        for p in rows:
            history_row(p, key)


def latest_evaluated() -> dict | None:
    done = [p for p in pilots() if rules.status(p, today()) in EVALUATED]
    return max(done, key=lambda p: p["end"]) if done else None


def pilot_hero() -> None:
    p = latest_evaluated()
    if p is None:
        st.info("Todavía no hay pilotos evaluados.")
        return
    v = verdict_of(p)
    st.markdown(
        f"**{p['name']}** · {period_label(p['start'], p['end'])}  \n{status_badge(rules.status(p, today()))}{mock_badge(p)}"
    )
    st.markdown(verdict_heading(v))
    show_chart(charts.pilot_bars(p.get("target"), p.get("result")))
    show_legend(charts.pilot_legend())
    if st.button("Ver reporte del piloto", key="hero_pilot", icon=":material/arrow_forward:"):
        go("pilotos", pilot_id=p["id"])


# ---------------------------------------------------------------- one pilot


def key_messages(p: dict, v: str) -> list[tuple[str, str]]:
    """'Mensajes clave para toma de decisiones': NOx evidence and qualitative health co-benefits."""
    r, target = p.get("result"), p.get("target")
    goal = f"la meta de {pct(target)}" if target is not None else None
    if v == rules.CONFIRMED:
        evidence = f"La emisión de NOₓ bajó {pct(r['change'])}: entre {pct(r['hi'])} y {pct(r['lo'])}."
        if goal:
            evidence += f" {'Alcanzó' if r['change'] <= target else 'Se acercó a'} {goal}."
    elif v == rules.INCONCLUSIVE:
        evidence = f"El resultado ({pct(r['change'])}, rango {pct(r['lo'])} a {pct(r['hi'])}) es compatible tanto con {goal} como con ningún cambio."
        if extra := rules.extension_weeks(r, target, weeks_of(p)):
            evidence += f" Extender el piloto unas **{extra} semanas** más permitiría distinguirlos."
    elif v == rules.NO_CHANGE:
        evidence = f"No se detectó un cambio en la emisión de NOₓ (rango {pct(r['lo'])} a {pct(r['hi'])})"
        evidence += f", y el rango descarta {goal}." if goal else "."
    else:
        cov = p.get("coverage")
        evidence = (f"No hay veredicto: las estaciones tuvieron datos el {cov:.0%} de las horas, menos del 50 % necesario." if cov is not None
                    else "No hay veredicto: todavía no hay resultado.")  # fmt: skip
    health = (
        HEALTH if v == rules.CONFIRMED else "Si una reducción se confirma: " + HEALTH[0].lower() + HEALTH[1:]
    )
    return [
        ("Evidencia de NOₓ", evidence),
        ("Co-beneficios en salud", health),
    ]


def double_reading(p: dict) -> str | None:
    """When the pilot crosses atypical days: the verdict leaves them out; a note gives the reading with them."""
    if not p.get("start"):
        return None
    names = rules.atypical_in(p["start"], p["end"], event_tuples())
    if not names:
        return None
    unique = ", ".join(dict.fromkeys(names))
    other = p.get("result_with_atypical")
    if rules.status(p, today()) not in EVALUATED:
        return f"Este piloto cruza días atípicos ({unique}). Su evaluación los dejará fuera y añadirá una nota con la lectura que los incluye."
    if other is None:
        return f"El veredicto deja fuera los días atípicos ({unique}). La lectura que los incluye no está calculada para este resultado."
    with_them = rules.verdict(other, p.get("target"), p.get("coverage"))
    return (f"**Incluyendo los días atípicos** ({unique}): cambio {pct(other['change'])}, rango {pct(other['lo'])} a {pct(other['hi'])}, "
            f"que se leería como «{with_them}». El veredicto principal los deja fuera porque esos días se emite distinto por razones ajenas al piloto.")  # fmt: skip


def coverage_note(p: dict) -> None:
    level, cov = rules.coverage_level(p.get("coverage")), p.get("coverage")
    if cov is None:
        return
    if level == "valid":
        st.caption(f"Cobertura de estaciones: {cov:.0%} de las horas (válida, 75 % o más).")
    elif level == "preliminary":
        st.warning(
            f"**Resultado preliminar:** las estaciones tuvieron datos el {cov:.0%} de las horas (entre 50 % y 74 %). Tómalo con cautela."
        )
    else:
        st.error(
            f"**Datos insuficientes:** las estaciones tuvieron datos solo el {cov:.0%} de las horas (menos de 50 %). No se emite veredicto."
        )


def report_markdown(p: dict, v: str) -> str:
    lines = [f"# Reporte de piloto: {p['name']}", "", f"- Fechas: {period_label(p.get('start'), p.get('end'))}",
             f"- Estado: {rules.status(p, today())}", f"- Meta propuesta: {pct(p['target']) if p.get('target') is not None else 'sin meta'}"]  # fmt: skip
    if r := p.get("result"):
        lines.append(f"- Impacto real detectado: {pct(r['change'])} (rango {pct(r['lo'])} a {pct(r['hi'])})")
    if p.get("coverage") is not None:
        lines.append(f"- Cobertura de estaciones: {p['coverage']:.0%}")
    lines += ["", f"## Veredicto: {v}", ""]
    if note := double_reading(p):
        lines += [note.replace("**", ""), ""]
    lines += ["## Mensajes clave para toma de decisiones", ""]
    lines += [f"- **{title}:** {text.replace('**', '')}" for title, text in key_messages(p, v)]
    if p.get("mock"):
        lines += ["", "_Ejemplo con datos simulados._"]
    return "\n".join(lines)


def edit_dates(p: dict) -> None:
    """Dates can change while the pilot is a draft or scheduled; after it starts, only a variant can."""
    if not rules.dates_editable(p, today()):
        st.caption(
            f"**Fechas:** {period_label(p['start'], p['end'])}. No se pueden cambiar porque el piloto ya empezó; usa **Duplicar** para crear una variante."
        )
        return
    if not is_planner():
        st.caption(f"**Fechas:** {period_label(p.get('start'), p.get('end'))}")
        return
    with st.form(f"dates_{p['id']}", border=False):
        first = today() + timedelta(days=1)
        value = (date.fromisoformat(p["start"]), date.fromisoformat(p["end"])) if p.get("start") else ()
        value = value if value and value[0] >= first else ()
        picked = st.date_input("Fechas del piloto", value=value, min_value=first, format="DD/MM/YYYY")
        if st.form_submit_button("Guardar fechas") and len(picked) == 2:
            p.update(start=picked[0].isoformat(), end=picked[1].isoformat(), draft=False)
            st.rerun()


def pilot_detail(p: dict) -> None:
    state = rules.status(p, today())
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    c1.markdown(f"## {p['name']}")
    c1.markdown(f"{status_badge(state)}{mock_badge(p)}")
    if is_planner() and c2.button("Duplicar piloto", icon=ICONS["duplicate"], key=f"dup_{p['id']}"):
        copy = rules.duplicate(p, new_pilot_id(), today())
        add_pilot(copy)
        go("pilotos", pilot_id=copy["id"])
    if p.get("description"):
        st.markdown(p["description"])
    edit_dates(p)
    if p.get("design"):
        st.caption(
            f"**Diseño:** {p['design']}"
            + (f" · **Meta:** {pct(p['target'])}" if p.get("target") is not None else " · sin meta")
        )

    if state == rules.WAITING:
        st.info(
            f"El piloto terminó el {short_date(p['end'])}. Los datos de las estaciones llegan con unas 2 semanas de retraso: la evaluación estará lista hacia el {short_date(date.fromisoformat(p['end']) + rules.DATA_LAG)}."
        )
    elif state in (rules.RUNNING, rules.SCHEDULED, rules.DRAFT):
        st.info({rules.RUNNING: "El piloto está en curso. Se evaluará unas 2 semanas después de terminar, cuando lleguen los datos.",
                 rules.SCHEDULED: f"El piloto empieza el {short_date(p['start'])}." if p.get("start") else "",
                 rules.DRAFT: "Borrador: fija las fechas para programarlo."}[state])  # fmt: skip
    if note := double_reading(p):
        st.markdown(f":orange[{ICONS['calendar']}] {note}")

    v = verdict_of(p)
    if v is not None:
        st.divider()
        st.subheader("Reporte del piloto")
        st.markdown(verdict_heading(v))
        if state == rules.PRELIMINARY and rules.coverage_level(p.get("coverage")) == "valid":
            st.caption(
                "Evaluación preliminar: se consolida unas 6 semanas después de terminar, cuando se validan los datos tardíos."
            )
        coverage_note(p)
        if v != rules.INSUFFICIENT:
            r = p["result"]
            c1, c2 = st.columns(2)
            impact = "below" if r["hi"] < 0 else "above" if r["lo"] > 0 else "normal"
            kpi(c1, "Impacto real detectado", pct(r["change"]), f"rango {pct(r['lo'])} a {pct(r['hi'])}", status=impact,
                text={"below": "Baja confirmada", "above": "Subida", "normal": "Incierto: el rango cruza 0 %"}[impact])  # fmt: skip
            kpi(c2, "Meta propuesta", pct(p["target"]) if p.get("target") is not None else "Sin meta",
                "la baja que se esperaba lograr")  # fmt: skip
            show_chart(charts.pilot_bars(p.get("target"), r))
            show_legend(charts.pilot_legend())
        st.markdown("#### Mensajes clave para toma de decisiones")
        for title, text in key_messages(p, v):
            st.markdown(f"**{title}.** {text}")
        st.download_button(
            "Exportar reporte (Markdown)",
            report_markdown(p, v),
            f"piloto_{p['id']}.md",
            icon=":material/download:",
            key=f"report_{p['id']}",
        )
    if p.get("mock"):
        st.caption(":gray[Ejemplo con datos simulados para mostrar el flujo; no es un piloto real.]")


def pilots_page() -> None:
    page_header(
        "Planes y Pilotos",
        "Seguimiento y evaluación de los pilotos planeados con esta herramienta: el impacto real frente a la meta.",
    )
    if (wanted := st.session_state.pop("pilot_id", None)) is not None:
        st.session_state["pilot_open"] = wanted
    open_id = st.session_state.get("pilot_open")
    p = pilot(open_id) if open_id else None
    if p is not None:
        if st.button("← Todos los pilotos", key="back_to_list"):
            st.session_state.pop("pilot_open")
            st.rerun()
        pilot_detail(p)
        return
    if is_planner() and st.button("Planear un piloto nuevo", type="primary", icon=":material/add:"):
        go("planear")
    pilot_history("pilots_page")


# ---------------------------------------------------------------- planner


@st.cache_data
def switchback() -> pd.DataFrame:
    d = read_csv(RUNS / "switchback" / "switchback.csv")
    d = d[(d["drop"] == 0) & (d["estimator"] == "e7") & d["design"].isin(list(DESIGNS))].copy()
    d["Diseño"] = d["design"].map(DESIGNS)
    d["Temporada"] = d["season"].str[:2].map({"fm": "feb–may", "nd": "nov–dic"}) + " " + d["season"].str[2:]
    return d


def strategies(effect: float, kind: str, carry: bool) -> pd.DataFrame:
    """Seasons each design needs to see `effect` (the median smallest visible drop over the simulated seasons)."""
    d = switchback()
    d = d[d["Temporada"].str.startswith(kind) & (d["carryover"] == ("carry50" if carry else "none"))]
    mdd = d.groupby("Diseño")["mdd"].median().sort_values()
    rows = pd.DataFrame({"Diseño": mdd.index, "mdd": mdd.to_numpy()})
    rows["seasons"] = [max(1, math.ceil((m / effect) ** 2)) for m in rows["mdd"]]
    return rows


def planning_page() -> None:
    page_header(
        "Planear un piloto",
        "Cuánto tiempo y con qué diseño aplicar una medida para poder ver su efecto en la emisión de NOₓ.",
    )
    plan_new()


def plan_new() -> None:
    st.markdown("**¿Cuánto tiempo y con qué diseño hay que aplicar una medida para poder ver su efecto?**")
    name = st.text_input("Nombre del piloto", "Nuevo piloto", key="plan_name")
    c1, c2, c3 = st.columns(3)
    effect = c1.slider("Meta: baja esperada de la emisión (%)", 5, 50, 10, key="plan_effect") / 100
    kind = c2.radio(
        "Temporada",
        list(SEASON_LENGTH),
        horizontal=True,
        key="plan_kind",
        help="La de feb–may tiene menos estancamientos: se ve más.",
    )
    carry = c3.toggle(
        "El efecto dura más allá de la semana con medida",
        key="plan_carry",
        help="Si la gente no cambia su rutina de inmediato.",
    )

    rows = strategies(effect, kind, carry)
    best = rows.iloc[0]
    n = int(best["seasons"])
    st.markdown(
        f"### Mejor diseño: **{best['Diseño'].lower()}**, {n} {'temporada' if n == 1 else 'temporadas'} ({rules.viability(n).lower()})"
    )
    show_chart(charts.strategy_bars(rows))
    show_legend(charts.strategy_legend())
    st.caption(f"Una temporada = {SEASON_LENGTH[kind]}.")
    if carry:
        st.warning(
            "Si el efecto dura más que la semana con medida, deja una semana de separación entre la semana con medida y la sin medida."
        )

    with st.expander("Detalles técnicos"):
        st.markdown(
            "- **Temporadas necesarias** ≈ (baja mínima visible en una temporada ÷ meta)², redondeado hacia arriba.\n"
            "- La baja mínima visible sale de una simulación con efectos inyectados en temporadas reales (exploración F1): mediana entre temporadas.\n"
            "- **¿Por qué alternar ayuda?** La emisión sube y baja ±15 % de una semana a otra por causas que el clima no explica. Con la medida continua esa deriva se confunde con el efecto; alternando, cada semana con medida se compara con su vecina sin medida."
        )
        st.dataframe(
            rows.rename(columns={"mdd": "Baja mínima visible", "seasons": "Temporadas"}).style.format(
                {"Baja mínima visible": "{:.0%}"}
            ),
            hide_index=True,
        )

    design = st.selectbox("Diseño elegido", list(rows["Diseño"]), key="plan_design")
    picked = st.date_input("Fechas (opcional)", value=(), min_value=today() + timedelta(days=1), format="DD/MM/YYYY", key="plan_dates",
                           help="Sin fechas se guarda como borrador.")  # fmt: skip
    if st.button("Guardar piloto", type="primary", key="plan_save"):
        dated = len(picked) == 2
        p = {"id": new_pilot_id(), "name": name, "created": today().isoformat(), "design": design,
             "target": -effect, "draft": not dated, "start": picked[0].isoformat() if dated else None,
             "end": picked[1].isoformat() if dated else None}  # fmt: skip
        add_pilot(p)
        go("pilotos", pilot_id=p["id"])
