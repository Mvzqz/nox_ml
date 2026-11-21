# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportReturnType=false
# ruff: noqa: E501  (chart specs read better unwrapped)
"""The four charts of context/UI_BUSINESS_CONTEXT.md, section 4: at most two variables (days and NOx); the
normal range, the weather and the atypical days go as background bands, dashed lines or quiet marks."""

import math
from collections.abc import Sequence
from datetime import date

import altair as alt
import pandas as pd

from nox_app import rules
from nox_app.common import (
    AMBER,
    BAND,
    BORDER,
    COBALT,
    COBALT_HOVER,
    DAY_ABBR,
    EVENT_COLORS,
    INK,
    MONTHS,
    MUTED,
    NORMAL_RANGE,
    OBSERVED_LINE,
    SAGE,
    events,
)

SPANISH_DAY = "date(datum.value) + ' ' + " + str(MONTHS) + "[month(datum.value)]"
OBSERVED, ADJUSTED = "NOₓ observado", "NOₓ sin el efecto del clima"
CHOSEN = "#DBE3F0"  # the chosen days: cobalt at 8 % over the page


# Legends, drawn as a list under each chart (common.show_legend): (swatch kind, colour, label, meaning).
def series_legend(highlight: bool = True) -> list[tuple[str, str, str, str]]:
    items = [
        ("line", OBSERVED_LINE, OBSERVED, "lo que miden las estaciones"),
        ("dash", COBALT, ADJUSTED, "descontando lo que hizo el viento"),
        ("band", NORMAL_RANGE, "Rango normal", "cuánto varía un día normal"),
        ("box", AMBER, "Día atípico", "feriado, fin de año, Semana Santa o contingencia"),
    ]
    return items + ([("box", CHOSEN, "Días elegidos", "el periodo que se diagnostica")] if highlight else [])


def calendar_legend(references: bool = False) -> list[tuple[str, str, str, str]]:
    items = [("box", BORDER, "Día normal", ""), ("box", BAND, "Fin de semana", "")]
    items += [("box", color, kind, "") for kind, color in EVENT_COLORS.items()]
    if references:
        items += [
            ("outline", COBALT, "Días elegidos", ""),
            ("dot", COBALT, "Día de comparación", "día normal con el que se comparó"),
        ]
    return items


def pilot_legend() -> list[tuple[str, str, str, str]]:
    return [
        ("box", BAND, "Línea base", "sin cambio (0 %)"),
        ("box", MUTED, "Meta esperada", "la baja propuesta"),
        ("box", SAGE, "Resultado: baja confirmada", "todo el rango está debajo de 0 %"),
        ("box", AMBER, "Resultado: incierto", "el rango cruza 0 %"),
        ("range", INK, "Rango del resultado", "valores compatibles con los datos"),
    ]


def strategy_legend() -> list[tuple[str, str, str, str]]:
    return [
        ("box", SAGE, rules.viability(1), "se ve en una temporada"),
        ("box", COBALT_HOVER, rules.viability(2), "hacen falta 2 o 3 temporadas"),
        ("box", BAND, rules.viability(4), "más de 3 temporadas"),
    ]


def time_series(
    table: pd.DataFrame,
    start: date | str,
    end: date | str,
    include_atypical: bool = False,
    pad: int = 28,
    height: int = 260,
    highlight: bool = True,
) -> alt.LayerChart:
    """Observed NOx (line) and NOx without the weather (dashed) against normal days, with the normal range of
    one day (grey band), the chosen days (shaded) and the atypical days (amber marks)."""
    a, b = pd.Timestamp(start), pd.Timestamp(end)
    t = table[table["day"].between(a - pd.Timedelta(days=pad), b + pd.Timedelta(days=pad))].copy()
    suffix = "_all" if include_atypical else ""
    lines = pd.concat(
        [t.assign(serie=OBSERVED, value=t[f"obs{suffix}"]), t.assign(serie=ADJUSTED, value=t[f"adj{suffix}"])]
    ).dropna(subset=["value"])
    x = alt.X("day:T", title=None, axis=alt.Axis(labelExpr=SPANISH_DAY, tickCount=8, grid=False))
    band = alt.Chart(t).mark_area(color=NORMAL_RANGE).encode(x=x, y="band_lo:Q", y2="band_hi:Q")
    chosen = (
        alt.Chart(pd.DataFrame({"a": [a], "b": [b + pd.Timedelta(days=1)]}))
        .mark_rect(color=COBALT, opacity=0.08)
        .encode(x="a:T", x2="b:T")
    )
    odd = events()[lambda e: (e["end"] >= t["day"].min()) & (e["start"] <= t["day"].max())].assign(
        stop=lambda e: e["end"] + pd.Timedelta(days=1)
    )
    marks = (
        alt.Chart(odd)
        .mark_rect(color=AMBER, opacity=0.2)
        .encode(x="start:T", x2="stop:T", tooltip=[alt.Tooltip("name:N", title="Día atípico")])
    )
    line = (
        alt.Chart(lines)
        .mark_line(strokeWidth=2)
        .encode(
            x=x,
            y=alt.Y("value:Q", title="Frente a un día normal", axis=alt.Axis(format="+%")),
            color=alt.Color(
                "serie:N",
                scale=alt.Scale(domain=[OBSERVED, ADJUSTED], range=[OBSERVED_LINE, COBALT]),
                legend=None,
            ),
            strokeDash=alt.StrokeDash(
                "serie:N", scale=alt.Scale(domain=[OBSERVED, ADJUSTED], range=[[1, 0], [5, 4]]), legend=None
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Día", format="%d/%m/%Y"),
                alt.Tooltip("serie:N", title="Serie"),
                alt.Tooltip("value:Q", title="Cambio", format="+.0%"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(color=BAND, strokeDash=[2, 2]).encode(y="y:Q")
    layers = [band, *([marks] if len(odd) else []), *([chosen] if highlight else []), zero, line]
    return alt.layer(*layers).properties(height=height)


def heatmap(
    start: date | str,
    end: date | str,
    chosen: tuple[date, date] | None = None,
    references: Sequence[str] = (),
) -> alt.LayerChart | alt.Chart:
    """Days of the week (Mon-Sun) against weeks, with weekends, holidays and contingencies coloured, the chosen
    days outlined and the days they were compared with dotted."""
    days = pd.DataFrame({"day": pd.date_range(start, end)})
    days["kind"], days["name"] = "Día normal", ""
    for e in events().itertuples():
        hit = days["day"].between(e.start, e.end)
        days.loc[hit, "kind"], days.loc[hit, "name"] = e.kind, e.name
    weekend = (days["day"].dt.weekday >= 5) & (days["kind"] == "Día normal")
    days.loc[weekend, "kind"] = "Fin de semana"
    a, b = (pd.Timestamp(x) for x in chosen) if chosen else (pd.NaT, pd.NaT)
    days["chosen"] = days["day"].between(a, b) if chosen else False
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
    domain, colors = (
        ["Día normal", "Fin de semana", *EVENT_COLORS],
        [BORDER, BAND, *EVENT_COLORS.values()],
    )
    base = alt.Chart(days).encode(
        x=alt.X("week:O", sort=list(days["week"].unique()), title="Semana del", axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            "weekday:N",
            sort=DAY_ABBR,
            title=None,
            axis=alt.Axis(labelOverlap=False, ticks=False, domain=False),
        ),
    )
    cells = base.mark_rect(cornerRadius=2).encode(
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(domain=domain, range=colors),
            legend=None,
        ),
        stroke=alt.condition("datum.chosen", alt.value(COBALT), alt.value("#FFFFFF")),
        strokeWidth=alt.condition("datum.chosen", alt.value(2.5), alt.value(2)),
        tooltip=[
            alt.Tooltip("date:N", title="Día"),
            alt.Tooltip("kind:N", title="Tipo"),
            alt.Tooltip("name:N", title="Evento"),
        ],
    )
    height = 7 * 28  # one 28 px row per weekday, so every label fits
    if not len(references):
        return cells.properties(height=height)
    dots = base.transform_filter("datum.reference").mark_point(
        filled=True, size=40, color=COBALT, opacity=0.9
    )
    return (cells + dots).properties(height=height)


def round_ticks(lo: float, hi: float) -> list[float]:
    """Axis ticks on round steps (2, 5 or 10 %) inside [lo, hi], always including 0."""
    step = next(s for s in (0.02, 0.05, 0.10, 0.20) if (hi - lo) / s <= 10)
    first = math.ceil(lo / step)
    return [round(i * step, 4) for i in range(first, math.floor(hi / step) + 1)]


def pilot_bars(target: float | None, result: dict | None) -> alt.LayerChart:
    """Baseline (0 %), target and real result with its range, as horizontal bars from 0: green when the whole
    range is a drop, amber when it crosses 0."""
    rows = [{"row": "Línea base", "value": 0.0, "color": BAND}]
    if target is not None:
        rows.append({"row": "Meta esperada", "value": target, "color": MUTED})
    if result is not None:
        color = SAGE if result["hi"] < 0 else AMBER if result["lo"] < 0 else BAND
        rows.append(
            {
                "row": "Resultado real",
                "value": result["change"],
                "lo": result["lo"],
                "hi": result["hi"],
                "color": color,
            }
        )
    d = pd.DataFrame(rows)
    d["label"] = d["value"].map(lambda v: "0 %" if v == 0 else f"{v * 100:+.0f} %".replace("-", "−"))
    ends = [0.0, *d["value"], *(([result["lo"], result["hi"]]) if result else [])]
    margin = 0.15 * (max(ends) - min(ends)) or 0.05
    y = alt.Y("row:N", sort=[r["row"] for r in rows], title=None, axis=alt.Axis(ticks=False, domain=False))
    x = alt.X(
        "value:Q",
        title="Cambio de la emisión",
        axis=alt.Axis(format="+%", grid=False, values=round_ticks(min(ends) - margin, max(ends) + margin)),
        scale=alt.Scale(domain=[min(ends) - margin, max(ends) + margin], nice=False),
    )
    bars = (
        alt.Chart(d[d["value"] != 0])
        .mark_bar(height=22, cornerRadius=2)
        .encode(x=x, x2=alt.X2(datum=0), y=y, color=alt.Color("color:N", scale=None))
    )
    baseline = (
        alt.Chart(d[d["row"] == "Línea base"]).mark_tick(color=MUTED, thickness=3, size=22).encode(x=x, y=y)
    )
    layers = [bars, baseline]
    if result is not None:
        ci = d[d["row"] == "Resultado real"]
        layers.append(alt.Chart(ci).mark_rule(color=INK, strokeWidth=2).encode(x="lo:Q", x2="hi:Q", y=y))
        layers.append(alt.Chart(ci).mark_tick(color=INK, thickness=2, size=16).encode(x="lo:Q", y=y))
        layers.append(alt.Chart(ci).mark_tick(color=INK, thickness=2, size=16).encode(x="hi:Q", y=y))
    layers.append(  # the value above the end of each bar, clear of the bar and of the range
        alt.Chart(d)
        .mark_text(align="center", baseline="bottom", dy=-14, fontSize=12, fontWeight=600, color=INK)
        .encode(x=x, y=y, text="label:N")
    )
    layers.append(
        alt.Chart(pd.DataFrame({"x": [0.0]})).mark_rule(color=MUTED, strokeDash=[3, 3]).encode(x="x:Q")
    )
    return alt.layer(*layers).properties(height=64 * len(rows) + 30)


def strategy_bars(rows: pd.DataFrame, cap: int = 6) -> alt.LayerChart:
    """Seasons each design needs, coloured by viability: green in one season, blue in two or three, grey beyond."""
    d = rows.assign(
        shown=rows["seasons"].clip(upper=cap),
        label=rows["seasons"].map(lambda n: f"{n}" if n <= cap else f"más de {cap}"),
    )
    d["viability"] = d["seasons"].map(rules.viability)
    domain = [rules.viability(1), rules.viability(2), rules.viability(cap + 1)]
    y = alt.Y("Diseño:N", sort=None, title=None)
    bars = (
        alt.Chart(d)
        .mark_bar(height=20)
        .encode(
            x=alt.X(
                "shown:Q",
                title="Temporadas necesarias",
                scale=alt.Scale(domain=[0, cap]),
                axis=alt.Axis(tickMinStep=1),
            ),
            y=y,
            color=alt.Color(
                "viability:N",
                scale=alt.Scale(domain=domain, range=[SAGE, COBALT_HOVER, BAND]),
                legend=None,
            ),
            tooltip=["Diseño", alt.Tooltip("label:N", title="Temporadas")],
        )
    )
    text = (
        alt.Chart(d)
        .mark_text(align="left", dx=5, fontSize=12, color=INK)
        .encode(x="shown:Q", y=y, text="label:N")
    )
    return (bars + text).properties(height=34 * len(d) + 40)
