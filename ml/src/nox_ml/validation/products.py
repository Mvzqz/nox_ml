# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""What the system answers for someone outside the team: each question with the estimator that is validated
for it, written as a one-page sheet in Spanish (``context/knowledge/capacidades.md``).

Which estimator answers which question (`ESTIMATORS`):

- **a change of emission between periods** (a measure, a claim): the meteorology-normalized estimator (E7,
  ``normalized_ratio``). It is the one that measured the 2020 lockdown (-50 %, expected -40 to -60 %) with
  its 2019 placebo at 1; the inversions without TEMPO failed that placebo, and with TEMPO they carry a Sunday
  bias (``context/knowledge/sesgo_domingo.md``). It needs only the stations, so it also runs where TEMPO is
  missing;
- **the weekly cycle** (Sunday or Saturday over weekday): the deweathering boosting (X4, ``gb_deweather``),
  0.57 in nov-dec 2024, feb-may 2025 and nov-dec 2025 without the atypical periods, where the forest moved
  between 0.56 and 0.67 and the inversions fell to 0.36-0.47 in nov-dec 2025;
- **concentration where there is no station**: the regression-kriging on E5b (``residual_kriging``).

`measure_sheet` evaluates a set of days against normal days (`events.calendar_effect`) and reads the result
against the placebo: a change is detected when it leaves the range of fake events of as many days, and the
change the analysis can see is that of the placebo (`events.detection_curve`). With a claimed change it says
whether the claim fits. `days_sheet` answers how many business days a measure needs to show a given drop.
"""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from nox_ml.data import calendar, contingencies
from nox_ml.data.inputs import DEFAULT_SOURCES, Inputs, Sources, load_inputs, openaq_sources
from nox_ml.inversion.normalized import interval
from nox_ml.models import Model
from nox_ml.validation import events
from nox_ml.validation.experiment import Placebo, read_config

ESTIMATORS = {
    "change": "normalized_ratio",
    "weekly_cycle": "gb_deweather",
    "concentration": "residual_kriging",
}
CONFIGS = Path("configs/experiments")
POWER = events.DETECTION_POWER
LAST_SIMAT_YEAR = 2024  # the last year SIMAT has published its yearly tables
MOSTLY_ATYPICAL = 0.5  # share of atypical measure days from which the sheet warns instead of noting
# the placebo range widened in log around its center: with 9-day fake events in four seasons (960 injections
# of 0 and 20 %) it held the truth 88 % of the time at 90 %; widened by 5 %, 91 %, with 5 % false alarms
RANGE_WIDENING = 1.05
PLACEBO = Placebo(n=2000, seed=3, level=0.90, refits=200)  # E7 fits in a second: hundreds of fake events


def estimator(question: str, configs: Path = CONFIGS) -> Callable[[], Model]:
    """The builder of the model that answers `question` (a key of `ESTIMATORS`), as frozen in its config."""
    return read_config(configs / f"{ESTIMATORS[question]}.yaml").model.build


def station_sources(sources: Sources = DEFAULT_SOURCES) -> Sources:
    """`sources` without TEMPO: the estimator of changes reads only the stations."""
    return replace(sources, tempo=False)


def verdict(ratio: float, placebo_lo: float, placebo_hi: float) -> str:
    """``decrease``, ``increase`` or ``undetectable``: whether the ratio leaves the range of the placebo."""
    if ratio < placebo_lo:
        return "decrease"
    return "increase" if ratio > placebo_hi else "undetectable"


def measure_result(
    inputs: Inputs,
    make_model: Callable[[], Model],
    days: pd.DatetimeIndex,
    excluded: pd.DatetimeIndex,
    config: Placebo = PLACEBO,
    claim: float | None = None,
    power: float = POWER,
) -> dict[str, Any]:
    """The change of emission on `days` over the normal business days (ratio - 1), read for a sheet: its
    range (the ratio over the spread of fake events of as many days, the honest uncertainty: the intervals of
    the bootstrap of the estimator are narrower), the change the analysis can detect with `power`, the verdict
    and, with a `claim` (a fraction, -0.2 for a 20 % drop), whether the claim falls in the range.

    ``method`` says where the spread comes from: ``placebo``, fake events of as many days drawn from the
    normal days; or ``extrapolated`` when the measure has as many days as the reference or more (a sustained
    measure: months against weeks) and fake events of its length cannot be drawn. Then the day-to-day
    variation of the season (`events.detection_curve` on short fake events) gives a log-normal spread with sd
    ``cv sqrt(1/k + 1/n)`` for k measure days and n normal ones, the rule the detection curve follows."""
    groups = events.split_days(inputs, days, days.union(excluded))
    if groups.event.empty:
        raise ValueError("no day of the measure is a business day with data")
    k, n = len(groups.event), len(groups.normal)
    ratio, _ = events._fit_ratio(inputs.on_days(groups.event.union(groups.normal)), make_model, groups.event)
    if k < n - 1:
        method = "placebo"
        ratios = events._fake_ratios(
            inputs, make_model, groups.normal, groups.normal, k, config.refits, config.seed
        )
        center = float(np.median(ratios))
        lo, hi = (center * (bound / center) ** RANGE_WIDENING for bound in interval(ratios, config.level))
        detectable = 1 - lo / float(np.quantile(ratios, power))
    else:
        method = "extrapolated"
        short = [c for c in (3, 5, 9) if c < n // 2] or [1]
        cv = events.detection_curve(inputs, make_model, groups.normal, short, config, power)["cv"]
        sd = cv * np.sqrt(1 / k + 1 / n)
        center = 1.0
        lo, hi = (
            float(np.exp(-norm.ppf(0.5 + config.level / 2) * sd)),
            float(np.exp(norm.ppf(0.5 + config.level / 2) * sd)),
        )
        detectable = float(1 - np.exp(-(norm.ppf(0.5 + config.level / 2) + norm.ppf(power)) * sd))
    atypical = calendar.atypical_days(groups.event.min(), groups.event.max())
    out = {
        "method": method,
        "atypical_share": float(groups.event.isin(atypical).mean()),
        "n_days": k,
        "days": {"event": events.day_list(groups.event), "n_normal": n},
        "change": ratio - 1,
        "range": (ratio * center / hi - 1, ratio * center / lo - 1),
        "placebo": {"center": center, "lo": lo, "hi": hi},
        "detectable_drop": detectable,
        "verdict": verdict(ratio, lo, hi),  # the extrapolated spread is centered on 1
        "claim": None,
    }
    if claim is not None:
        low, high = out["range"]
        out["claim"] = {"change": claim, "fits": bool(low <= claim <= high)}
    return out


def combine_seasons(
    results: list[dict[str, Any]],
    level: float = PLACEBO.level,
    power: float = POWER,
    claim: float | None = None,
) -> dict:
    """One change from the `measure_result` of several seasons, each against its own normal days: the mean of
    their log ratios weighted by the inverse of their variance (each from its range, taken as normal in log
    at `level`), with its range, the drop the seasons together can detect with `power`, and the verdict."""
    z = float(norm.ppf(0.5 + level / 2))
    logs, variances = [], []
    for r in results:
        low, high = r["range"]
        sd = (np.log1p(high) - np.log1p(low)) / (2 * z)
        logs.append(np.log1p(r["change"]))
        variances.append(sd**2)
    weights = 1 / np.array(variances)
    mean = float(weights @ np.array(logs) / weights.sum())
    sd = float(np.sqrt(1 / weights.sum()))
    lo, hi = float(np.exp(-z * sd)), float(np.exp(z * sd))
    ratio = float(np.exp(mean))
    return {
        "n_seasons": len(results),
        "n_days": sum(r["n_days"] for r in results),
        "change": ratio - 1,
        "range": (ratio / hi - 1, ratio / lo - 1),
        "detectable_drop": float(1 - np.exp(-(z + norm.ppf(power)) * sd)),
        "verdict": verdict(ratio, lo, hi),
        "weights": [float(w) for w in weights / weights.sum()],
        "claim": None
        if claim is None
        else {"change": claim, "fits": bool(ratio / hi - 1 <= claim <= ratio / lo - 1)},
    }


def days_needed(drop: float, cv: float, level: float = 0.90, power: float = POWER) -> int:
    """Business days a measure needs, against a reference of as many days, to show a `drop` (0.1 for 10 %)
    with `power`, given the day-to-day variation `cv` of the season (`events.detection_curve`): the inverse
    of its extrapolation ``drop = 1 - exp(-z cv sqrt(2 / k))``."""
    z = float(norm.ppf(0.5 + level / 2) + norm.ppf(power))
    return int(np.ceil(2 * (z * cv / -np.log(1 - drop)) ** 2))


def sources_for(start: str, end: str) -> Sources:
    """SIMAT up to 2024; after it, the OpenAQ tables of the window (`openaq_sources`, its end exclusive)."""
    if pd.Timestamp(start).year <= LAST_SIMAT_YEAR:
        return DEFAULT_SOURCES
    after = (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()
    return openaq_sources(start, after)


def season_inputs(data_dir: Path, start: str, end: str, sources: Sources = DEFAULT_SOURCES) -> Inputs:
    return load_inputs(data_dir, start, end, (12, 17), station_sources(sources))


def reference_exclusions(data_dir: Path, start: str, end: str, days: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Days that are neither the event nor a normal reference: contingencies and atypical periods."""
    episodes = contingencies.read_episodes(data_dir / "raw" / contingencies.EPISODES_FILE)
    return contingencies.active_days(episodes).union(calendar.atypical_days(start, end)).difference(days)


# --- The sheets, in Spanish (they are read by people outside the team) ------------------------------------

VERDICT_TEXT = {
    "decrease": "**Se detecta una baja de la emisión.**",
    "increase": "**Se detecta un aumento de la emisión.**",
    "undetectable": "**No se detecta un cambio de la emisión.**",
}


def pct(x: float) -> str:
    return f"{x:+.0%}".replace("+-", "−").replace("-", "−")


def render_measure(result: dict[str, Any], title: str, period: tuple[str, str]) -> str:
    low, high = result["range"]
    lines = [
        f"# {title}",
        "",
        f"Días evaluados: {result['n_days']} días hábiles, del {result['days']['event'][0]} al "
        f"{result['days']['event'][-1]}. Referencia: {result['days']['n_normal']} días hábiles normales del "
        f"periodo {period[0]} a {period[1]} (sin contingencias, fin de año ni Semana Santa).",
        "",
        VERDICT_TEXT[result["verdict"]],
        "",
        "| | |",
        "|---|---|",
        f"| Cambio de la emisión de NOₓ, descontado el clima | {pct(result['change'])} |",
        f"| Rango compatible (contiene el cambio real ~90 % de las veces) | {pct(low)} a {pct(high)} |",
        f"| Cambio mínimo que este análisis puede ver con {len(result['days']['event'])} días | "
        f"bajas de {result['detectable_drop']:.0%} o más |",
    ]
    if result["claim"] is not None:
        fits = "cabe" if result["claim"]["fits"] else "no cabe"
        lines.append(
            f"| Cambio anunciado | {pct(result['claim']['change'])}: **{fits}** en el rango compatible |"
        )
    share = result["atypical_share"]
    if share >= MOSTLY_ATYPICAL:
        lines += [
            "",
            f"**Advertencia:** {share:.0%} de los días evaluados caen en un periodo atípico (fin de año o "
            "Semana Santa). En esos periodos el método ha confundido la acumulación de contaminación con "
            "emisión (en diciembre de 2023 midió +40 % cuando el tráfico era el de un día normal): no leas "
            "el resultado como un cambio de emisión sin otra evidencia.",
        ]
    elif share > 0:
        lines += [
            "",
            f"Nota: {share:.0%} de los días evaluados caen en un periodo atípico (fin de año o Semana "
            "Santa), donde el método es menos confiable. Son minoría, pero conviene repetir el análisis sin "
            "esos días.",
        ]
    if result["method"] == "extrapolated":
        lines += [
            "",
            "La medida dura tanto como la referencia o más: el rango y el mínimo detectable salen de la "
            "variación de un día a otro de la temporada, no de repetir el análisis con días al azar.",
        ]
    lines += [
        "",
        "## Cómo leerlo",
        "",
        "- El cambio compara los días evaluados con días hábiles normales de la misma temporada, después de "
        "descontar el efecto del clima (ventilación) con el estimador normalizado del sistema.",
        "- El rango compatible sale de repetir el análisis con días normales elegidos al azar, donde no hubo "
        "ningún cambio: es la incertidumbre honesta del resultado.",
        '- "No se detecta" no quiere decir que la medida no funcionó: puede haber un cambio menor al mínimo '
        "detectable. Más días bajan ese mínimo.",
        "- El método se validó con el confinamiento de 2020: midió una caída de ~50 % de la emisión vial, "
        "dentro del rango esperado (40 a 60 %), y no vio cambios en las mismas fechas de 2019.",
        "",
        "Fuente: estaciones de la red de monitoreo (SIMAT; desde 2025, vía OpenAQ). "
        "Estimador: normalizado por meteorología (E7).",
    ]
    return "\n".join(lines) + "\n"


def render_days(table: list[tuple[float, int]], cv: float, period: tuple[str, str]) -> str:
    lines = [
        "# ¿Cuántos días necesita una medida para poder evaluarla?",
        "",
        f"Con la variación de un día a otro de la emisión en {period[0]} a {period[1]} ({cv:.2f}), "
        "comparando contra un periodo de referencia de la misma duración, para detectar la baja el 80 % de "
        "las veces:",
        "",
        "| Baja de la emisión | Días hábiles necesarios |",
        "|---|---|",
        *[f"| {drop:.0%} | {k} (unas {int(np.ceil(k / 5))} semanas) |" for drop, k in table],
        "",
        "- Una medida que dure menos días que los de la tabla puede funcionar sin que el análisis lo vea.",
        "- La variación cambia con la temporada: en invierno, con estancamientos, se necesitan más días.",
        "- Las cifras son una extrapolación del comportamiento de días normales; se confirman con más años "
        "de datos.",
    ]
    return "\n".join(lines) + "\n"


def render_seasons(
    results: list[dict[str, Any]], combined: dict[str, Any], title: str, periods: list[tuple[str, str]]
) -> str:
    low, high = combined["range"]
    lines = [
        f"# {title}",
        "",
        f"{combined['n_days']} días hábiles en {combined['n_seasons']} temporadas; cada temporada se compara "
        "con sus propios días hábiles normales y los cambios se combinan.",
        "",
        VERDICT_TEXT[combined["verdict"]],
        "",
        "| | |",
        "|---|---|",
        f"| Cambio de la emisión de NOₓ, descontado el clima | {pct(combined['change'])} |",
        f"| Rango compatible (contiene el cambio real ~90 % de las veces) | {pct(low)} a {pct(high)} |",
        f"| Cambio mínimo que este análisis puede ver | bajas de {combined['detectable_drop']:.0%} o más |",
    ]
    if combined["claim"] is not None:
        fits = "cabe" if combined["claim"]["fits"] else "no cabe"
        lines.append(
            f"| Cambio anunciado | {pct(combined['claim']['change'])}: **{fits}** en el rango compatible |"
        )
    lines += ["", "| Temporada | Días | Cambio | Rango | Peso |", "|---|---|---|---|---|"]
    for (start, end), r, w in zip(periods, results, combined["weights"], strict=True):
        span = f"{pct(r['range'][0])} a {pct(r['range'][1])}"
        lines.append(f"| {start} a {end} | {r['n_days']} | {pct(r['change'])} | {span} | {w:.0%} |")
    if max(r["atypical_share"] for r in results) > 0:
        lines += [
            "",
            "Nota: parte de los días caen en periodos atípicos (fin de año o Semana Santa), donde el método "
            "es menos confiable.",
        ]
    lines += [
        "",
        "## Cómo leerlo",
        "",
        "- Sumar temporadas achica el rango y el cambio mínimo detectable: es la forma de evaluar medidas de "
        "efecto moderado.",
        "- Las temporadas desde 2025 usan datos de las estaciones sin validar (vía OpenAQ) y el viento de "
        "los aeropuertos; en noviembre–diciembre de 2024 esos datos dieron NOₓ 6 % más alto que los "
        "validados, lo que no afecta los cambios dentro de una temporada.",
        "",
        "Estimador: normalizado por meteorología (E7), validado con el confinamiento de 2020.",
    ]
    return "\n".join(lines) + "\n"
