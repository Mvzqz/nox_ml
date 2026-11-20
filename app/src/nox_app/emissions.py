# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOptionalSubscript=false
# pyright: reportReturnType=false, reportIndexIssue=false
# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Section 1, Emisiones (read only): the monthly bulletins and "¿Fue el clima?" for a week or any period.

Bulletins are neutral: they diagnose, they do not recommend."""

import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from nox_app import charts
from nox_app.common import (
    MONTH_NAMES,
    OFFLINE,
    SEASONS,
    SIMAT_SEASONS,
    bulletins,
    cli_error,
    coverage,
    events,
    example_episodes,
    go,
    keep,
    live,
    metric,
    pct,
    run_cli,
    season_of,
    series,
    short_date,
    show_chart,
)

VERDICTS = {
    "normal": ("Normal", "gray"),
    "weather_explains": ("El clima lo explica", "blue"),
    "weather_explains_part": ("El clima lo explica en parte", "blue"),
    "weather_does_not_explain": ("El clima no lo explica", "orange"),
}
OLD_TO_PRUDENT = {"weather": "weather_explains", "emission": "weather_does_not_explain"}
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
LONG_EPISODE = 14  # days; longer periods mix the change into its own reference days
BASELINE_KEY = "baseline_with_atypical"
GLOSSARY = """
- **NOₓ:** gases que salen de los escapes de coches, camiones y fábricas. Irritan los pulmones y ayudan a formar ozono.
- **NOₓ observado (concentración):** cuánto NOₓ miden las estaciones en el aire que respiramos.
- **NOₓ sin el efecto del clima (emisión):** lo observado, descontando lo que hizo el viento. Se acerca a cuánto NOₓ echaron coches y fábricas.
- **El clima:** el viento y la altura del aire en que se mezcla la contaminación. Con viento la contaminación se va; con aire quieto se junta, aunque se emita lo mismo.
- **Contaminación en toda la región:** la que el satélite ve fuera de la ciudad. Si sube también ahí, la contaminación se está juntando sobre toda la zona.
- **Día normal:** un día del mismo día de la semana, hasta 4 semanas antes o después. Por defecto no cuenta feriados, fin de año, Semana Santa ni contingencias.
"""


def month_title(month: str) -> str:
    year, m = month.split("-")
    return f"{MONTH_NAMES[int(m) - 1].capitalize()} de {year}"


def with_atypical() -> bool:
    return st.session_state.get(f"_{BASELINE_KEY}", False)


def baseline_toggle(disabled: bool = False) -> bool:
    """Atypical days out of the baseline by default; the same switch on every page of this section."""
    st.session_state[BASELINE_KEY] = with_atypical()
    return st.toggle(
        "Incluir días atípicos en la comparación",
        key=BASELINE_KEY,
        on_change=keep,
        args=(BASELINE_KEY,),
        disabled=disabled,
        help="Por defecto, los días normales de comparación no incluyen feriados, fin de año, Semana Santa ni contingencias.",
    )


def variant(diagnosis: dict) -> dict:
    """The diagnosis with the baseline the switch asks for (the default when the other was not computed)."""
    return diagnosis.get("with_atypical" if with_atypical() else "default") or diagnosis["default"]


def verdict_of(result: dict) -> str:
    return (
        result["verdict"] if "detail" in result else OLD_TO_PRUDENT.get(result["verdict"], result["verdict"])
    )


# ---------------------------------------------------------------- Boletín


def month_summary(bulletin: dict) -> dict:
    """Mean observed and weather-free change of the month's days, its coverage and its atypical weeks."""
    season = season_of(bulletin["data"]["start"])
    t = series(season)
    days = t[t["day"].dt.strftime("%Y-%m") == bulletin["month"]]
    suffix = "_all" if with_atypical() else ""
    weeks = [w for w in bulletin["weeks"] if "ratios" in variant(w)]
    odd = [w for w in weeks if verdict_of(variant(w)) != "normal"]
    start = f"{bulletin['month']}-01"
    return {
        "observed": float(days[f"obs{suffix}"].mean()),
        "adjusted": float(days[f"adj{suffix}"].mean()),
        "coverage": coverage(start, start),
        "weeks": len(weeks),
        "odd": len(odd),
        "season": season,
    }


def bulletin_hero(bulletin: dict, compact: bool = False) -> None:
    s = month_summary(bulletin)
    c1, c2, c3 = st.columns(3)
    metric(c1, "NOₓ observado", pct(s["observed"]), "frente a días normales",
           help="Promedio de los días del mes, cada uno frente a días normales del mismo día de la semana.")  # fmt: skip
    metric(c2, "NOₓ sin el efecto del clima", pct(s["adjusted"]), "lo que el clima no explica",
           help="Lo observado, descontando lo que hizo el viento: se acerca a la emisión.")  # fmt: skip
    metric(c3, "Semanas fuera de lo común", f"{s['odd']} de {s['weeks']}",
           f"cobertura de la red {s['coverage']:.0%}" if s["coverage"] else "")  # fmt: skip
    first = date.fromisoformat(f"{bulletin['month']}-01")
    last = (pd.Timestamp(first) + pd.offsets.MonthEnd(0)).date()
    show_chart(
        charts.time_series(
            series(s["season"]),
            first,
            last,
            with_atypical(),
            pad=0,
            height=180 if compact else 240,
            highlight=False,
        )
    )


def week_row(week: dict, key: str) -> None:
    result = variant(week)
    c = st.columns([2, 1.2, 1.2, 2, 1.6], vertical_alignment="center")
    c[0].markdown(f"**{short_date(week['start'])[:-5]} – {short_date(week['end'])}**")
    if "ratios" not in result:
        c[3].markdown(":gray[Sin datos de la red esa semana]")
        return
    title, color = VERDICTS[verdict_of(result)]
    c[1].markdown(f"Observado {pct(result['ratios']['concentration'] - 1)}")
    c[2].markdown(f"Por clima {pct(result['ratios']['weather'] - 1)}")
    c[3].markdown(f":{color}-badge[{title}]")
    odd = verdict_of(result) != "normal"
    if c[4].button(
        "¿Fue el clima?", key=key, type="primary" if odd else "secondary", icon=":material/arrow_forward:"
    ):
        go("episodio", episode_week={"month": week["month"], "start": week["start"]})


def bulletin_page() -> None:
    months = bulletins()
    titles = {m["month"]: month_title(m["month"]) for m in months}
    if "bulletin_month" in st.session_state:
        st.session_state["bulletin_select"] = st.session_state.pop("bulletin_month")
    month = st.selectbox("Boletín", list(titles), format_func=titles.get, key="bulletin_select")
    bulletin = next(m for m in months if m["month"] == month)
    st.title(f"Boletín de NOₓ · {titles[month]}")
    st.caption(
        "Diagnóstico neutral de cómo estuvo el NOₓ y por qué. Datos de la red de monitoreo (OpenAQ) y del satélite TEMPO."
    )
    baseline_toggle()
    bulletin_hero(bulletin)
    st.caption(
        "**Línea continua:** NOₓ observado. **Punteada:** sin el efecto del clima. **Banda gris:** cuánto varía un día normal. **Marcas ámbar:** días atípicos."
    )

    st.subheader("Semanas del mes")
    st.caption("Las semanas resaltadas salieron de lo común: ábrelas para ver si el clima lo explica.")
    for i, week in enumerate(bulletin["weeks"]):
        week_row({**week, "month": month}, key=f"week_{month}_{i}")

    first = date.fromisoformat(f"{month}-01")
    with st.expander("Calendario del mes"):
        show_chart(charts.heatmap(first, (pd.Timestamp(first) + pd.offsets.MonthEnd(0)).date()))
    rows = [
        {"semana": w["start"], "veredicto": VERDICTS[verdict_of(variant(w))][0] if "ratios" in variant(w) else "sin datos",
         "nox_observado": variant(w).get("ratios", {}).get("concentration"), "esperado_por_clima": variant(w).get("ratios", {}).get("weather")}
        for w in bulletin["weeks"]
    ]  # fmt: skip
    st.download_button(
        "Descargar semanas (CSV)",
        pd.DataFrame(rows).to_csv(index=False),
        f"boletin_{month}.csv",
        icon=":material/download:",
    )


def bulletin_history() -> None:
    """Every bulletin, newest first, with a link to open it."""
    for m in bulletins():
        weeks = [w for w in m["weeks"] if "ratios" in variant(w)]
        odd = sum(verdict_of(variant(w)) != "normal" for w in weeks)
        c = st.columns([2, 3, 1.2], vertical_alignment="center")
        c[0].markdown(f"**{month_title(m['month'])}**")
        c[1].markdown(
            f"{odd} de {len(weeks)} semanas fuera de lo común" if odd else f"{len(weeks)} semanas normales"
        )
        if c[2].button("Abrir", key=f"history_{m['month']}", icon=":material/arrow_forward:"):
            go("boletin", bulletin_month=m["month"])


# ---------------------------------------------------------------- ¿Fue el clima?


def amount(ratio: float) -> str:
    change = ratio - 1
    if abs(change) < 0.05:
        return "casi lo mismo"
    return f"{abs(change) * 100:.0f} % {'más' if change > 0 else 'menos'}"


def story(result: dict) -> str:
    """The verdict told with the episode's own numbers, for a reader without a technical background."""
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
        text = [
            f"{seen}, un cambio que cabe en lo que varía de un día normal a otro. **Nada fuera de lo común.**"
        ]
    elif verdict == "weather_explains":
        why = (
            "con poco viento y el aire quieto, la contaminación se junta aunque se emita lo mismo de siempre"
            if up
            else "con más viento, la contaminación se dispersa aunque se emita lo mismo de siempre"
        )
        text = [f"{seen}. **El clima basta para explicarlo:** {why}. {by_weather}."]
    elif verdict == "weather_explains_part":
        text = [f"{seen}. {by_weather}: **el clima explica una parte, no todo.**",
                "El resto puede venir de más emisión (más tráfico, más actividad) o de contaminación que se fue juntando de días anteriores."]  # fmt: skip
    else:
        text = [
            f"{seen}. {by_weather}, así que **el clima no explica {'la subida' if up else 'la bajada'}.**",
            "Quedan dos explicaciones posibles: más emisión (más tráfico, más actividad) o contaminación que se fue juntando de días anteriores. **Con estos datos no se puede saber cuál de las dos fue.**"
            if up
            else "Puede ser menos emisión (menos tráfico, menos actividad) o aire limpio que llegó de fuera. **Con estos datos no se puede saber cuál de las dos fue.**",
        ]
    if "background_up" in (result.get("notes") or []) and r.get("background") is not None:
        text.append(
            f"Una pista: el satélite vio **{amount(r['background'])} contaminación también fuera de la ciudad**. Cuando sube en toda la región, apunta a contaminación acumulada en el aire, no solo a lo que se emitió en la ciudad esos días."
        )
    return "\n\n".join(text)


def weekdays_of(days: list[str]) -> str:
    found = sorted({date.fromisoformat(d).weekday() for d in days})
    if len(found) >= 3 and found == list(range(found[0], found[-1] + 1)):
        return f"de {WEEKDAYS[found[0]]} a {WEEKDAYS[found[-1]]}"
    names = [WEEKDAYS[i] + ("" if WEEKDAYS[i].endswith("s") else "s") for i in found]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def comparison(result: dict, included: bool, plain: bool = False) -> str:
    """What the days were compared with, in one plain sentence, with warnings when the comparison is weak."""
    refs = result.get("references")
    rule = (
        "incluye feriados y días atípicos"
        if included
        else "no se usan feriados, fin de año, Semana Santa ni contingencias"
    )
    if not refs:
        return f"**Comparado con:** días normales del mismo día de la semana, hasta 4 semanas antes y 4 después; {rule}."
    text = (
        f"**Comparado con:** {len(refs)} días ({weekdays_of(result['days'])}, como los elegidos) "
        f"entre el {short_date(refs[0])} y el {short_date(refs[-1])}. Se buscan hasta 4 semanas antes y 4 después; {rule}."
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
            f"Todos los días de comparación son {side} a los elegidos: si el NOₓ sube o baja con la temporada, ese cambio puede aparecer como parte del episodio."
        )
    for w in warnings:
        text += f"\n\n{w}" if plain else f"\n\n:orange[{w}]"
    return text


def markdown(result: dict, included: bool) -> str:
    title = VERDICTS[verdict_of(result)][0]
    r = result["ratios"]
    lines = [f"# ¿Fue el clima? {short_date(result['days'][0])} – {short_date(result['days'][-1])}", "", f"## {title}", "",
             story(result), "", comparison(result, included, plain=True), "",
             f"- NOₓ observado: {pct(r['concentration'] - 1)}", f"- Esperado solo por el clima: {pct(r['weather'] - 1)}"]  # fmt: skip
    if r.get("background") is not None:
        lines.append(f"- Contaminación en toda la región (satélite): {pct(r['background'] - 1)}")
    lines += ["", "Fuente: estaciones de la red de monitoreo y satélite TEMPO."]
    return "\n".join(lines)


def show_diagnosis(diagnosis: dict, key: str) -> None:
    """One diagnosis (``default`` and, when computed, ``with_atypical`` baselines)."""
    baseline_toggle(disabled="with_atypical" not in diagnosis)
    if "with_atypical" not in diagnosis:
        st.caption("El cálculo en vivo siempre aparta los días atípicos de la comparación.")
    result = variant(diagnosis)
    if "ratios" not in result:
        st.warning("No hay datos de la red de monitoreo para esos días.")
        return
    included = with_atypical() and "with_atypical" in diagnosis
    title, color = VERDICTS[verdict_of(result)]
    st.markdown(f"## :{color}[{title.upper()}]")
    st.markdown(story(result))

    r = result["ratios"]
    c1, c2, c3 = st.columns(3)
    metric(
        c1,
        "NOₓ observado",
        pct(r["concentration"] - 1),
        "frente a días normales",
        help="Lo que midieron las estaciones.",
    )
    metric(c2, "Esperado solo por el clima", pct(r["weather"] - 1), "con la emisión de siempre",
           help="Lo que habría en el aire si se emitiera lo de siempre y solo cambiaran el viento y el aire de esos días.")  # fmt: skip
    if r.get("background") is not None:
        metric(
            c3, "Contaminación en toda la región", pct(r["background"] - 1), "satélite, fuera de la ciudad"
        )

    start, end = date.fromisoformat(result["days"][0]), date.fromisoformat(result["days"][-1])
    season = season_of(start)
    if season:
        show_chart(charts.time_series(series(season), start, end, included))
        st.caption(
            "**Línea continua:** NOₓ observado. **Punteada:** sin el efecto del clima. **Banda gris:** cuánto varía un día normal. **Zona azul:** los días elegidos. **Marcas ámbar:** días atípicos."
        )
    st.markdown(comparison(result, included))
    if season and result.get("references"):
        with st.expander("¿Con qué días se comparó?"):
            a, b = SEASONS[season]
            lo, hi = (
                max(date.fromisoformat(a), start - timedelta(days=35)),
                min(date.fromisoformat(b), end + timedelta(days=35)),
            )
            show_chart(charts.heatmap(lo, hi, (start, end), result["references"]))
            st.caption(
                "**Borde oscuro:** los días elegidos. **Punto:** los días normales con los que se compararon."
            )
    with st.expander("¿Qué significa cada cosa?"):
        st.markdown(GLOSSARY)
    c1, c2, _ = st.columns(3)
    c1.download_button(
        "Exportar ficha (Markdown)",
        markdown(result, included),
        "fue_el_clima.md",
        icon=":material/download:",
        key=f"{key}_md",
    )
    c2.download_button(
        "Datos (JSON)",
        json.dumps(result, indent=2),
        "fue_el_clima.json",
        icon=":material/data_object:",
        key=f"{key}_json",
    )


def bulletin_weeks() -> dict[str, dict]:
    """Every week of every bulletin, by label."""
    return {
        f"{short_date(w['start'])[:-5]} – {short_date(w['end'])}": {**w, "month": m["month"]}
        for m in bulletins()
        for w in m["weeks"]
    }


SOURCES = ["Una semana de los boletines", "Ejemplos de diciembre de 2023", "Otro periodo (en vivo)"]


def episode_page() -> None:
    st.title("¿Fue el clima?")
    st.markdown(
        "**¿Por qué una semana tuvo más (o menos) NOₓ?** A veces es el clima, porque con poco viento la contaminación se junta, y a veces cambió la emisión. Elige los días y te decimos si el clima basta para explicarlo."
    )

    weeks = bulletin_weeks()
    if wanted := st.session_state.pop("episode_week", None):  # opened from a bulletin week
        st.session_state["episode_source"] = SOURCES[0]
        st.session_state["episode_bulletin_week"] = next(
            k for k, w in weeks.items() if w["start"] == wanted["start"]
        )
    sources = SOURCES if live() else SOURCES[:2]
    source = st.radio("¿Qué días?", sources, horizontal=True, key="episode_source")

    if source == SOURCES[0]:
        label = st.selectbox("Semana", list(weeks), key="episode_bulletin_week")
        week = weeks[label]
        st.caption(f"Del boletín de {month_title(week['month']).lower()}.")
        show_diagnosis(week, key="bulletin")
    elif source == SOURCES[1]:
        examples = example_episodes()
        name = st.selectbox("Ejemplo", list(examples), format_func=lambda k: examples[k]["title"])
        show_diagnosis(examples[name], key="example")
        if not live():
            st.info(OFFLINE)
    else:
        live_period()


def pick_period(key: str, seasons: list[str]) -> tuple[str, date, date] | None:
    """A season and its days, picked by hand or from its known events."""
    c1, c2 = st.columns([1, 2])
    season = c1.selectbox("Temporada", seasons, key=f"{key}_season")
    a, b = (pd.Timestamp(d) for d in SEASONS[season])
    known = events()[lambda e: (e["end"] >= a) & (e["start"] <= b)]
    labels = {
        f"{e.name} · {short_date(e.start.date())}": (max(e.start, a).date(), min(e.end, b).date())
        for e in known.itertuples()
    }
    choice = c2.selectbox("Evento conocido", ["Elegir días a mano", *labels], key=f"{key}_event")
    if choice in labels:
        return season, *labels[choice]
    days_key = f"{key}_days"
    current = st.session_state.get(days_key)
    if not current or not all(a.date() <= d <= b.date() for d in current):
        st.session_state[days_key] = (a.date(), a.date() + timedelta(days=4))
    picked = st.date_input("Días", min_value=a.date(), max_value=b.date(), key=days_key, format="DD/MM/YYYY")
    if len(picked) != 2:
        st.info("Elige el último día.")
        return None
    return season, picked[0], picked[1]


def live_period() -> None:
    period = pick_period("episode", SIMAT_SEASONS)
    st.caption(
        "En vivo, hasta diciembre de 2024 (estaciones de SIMAT). Las semanas de 2025 y 2026 están en los boletines."
    )
    if period and (period[2] - period[1]).days + 1 > LONG_EPISODE:
        st.warning(
            "Este diagnóstico es para episodios cortos (hasta 2 semanas): se compara con días de las 4 semanas de alrededor, así que un cambio largo se mezcla con su propia comparación."
        )
    if period is None or not st.button("Diagnosticar", type="primary"):
        return
    season, start, end = period
    with st.spinner("Comparando con días normales (~20 s la primera vez)…"):
        args = ("episode", "--days", f"{start}:{end}", "--data", ":".join(SEASONS[season]), "--label", "ep")
        code, out, err, files = run_cli((*args, "--runs-dir"))
    text = files.get("episodes/ep.json")
    if code or text is None:
        st.error("No se pudo diagnosticar ese periodo: " + cli_error(code, out, err))
        return
    show_diagnosis({"default": json.loads(text)}, key="live")
