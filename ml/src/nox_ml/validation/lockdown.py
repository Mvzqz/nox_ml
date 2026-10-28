# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""A known change: the 2020 lockdown against the same dates of 2019, with any model of the registry.

The positive control the project lacks with 2023-2024 data. Phases after Hernández-Paniagua et al. (2021):
the base (15 Feb-15 Mar), phase 2 (partial measures, 30 Mar-20 Apr) and phase 3 (total lockdown, 21 Apr-31
May). For each year and phase, the model is fitted on the business days of the base and the phase, with the
phase relabeled as Sundays (`events._fit_ratio`), so its Sunday / weekday ratio is the emission of the phase
over the base. 2019 has no lockdown: its ratio is the seasonal change the model attributes to the emission (it
should be ~1), and 2020 over 2019 is the effect of the lockdown (difference in differences).

Only stations: TEMPO did not exist and MERRA-2 is not downloaded for 2019-2020 (`data.inputs.
LOCKDOWN_SOURCES`), so models that need either (the PINN with OH chemistry) do not apply. The research found
that the full inversion without TEMPO fails the 2019 placebo (`reports/validacion_2020.md`); the
meteorology-normalized estimator passed it.

Independent references of the size: the Google mobility of Mexico City on business days (people, not
vehicles; heavy diesel traffic fell less) and the meteorology-adjusted NO2 of the literature (about -20 % in
phase 2 and -43 % in phase 3). The expected drop of the road NOx emission in phase 3 is 40-60 %.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from nox_ml.data.inputs import LOCKDOWN_SOURCES, Inputs, load_inputs
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.inversion.normalized import WEEKDAY, day_type
from nox_ml.models import Model
from nox_ml.validation.events import _fit_ratio, _require_emissions, data_days, day_list
from nox_ml.validation.experiment import ExperimentConfig, code_version

YEARS = (2020, 2019)  # the lockdown and its placebo
WINDOW = ("02-15", "05-31")  # month-day of the data of each year
BASE = ("02-15", "03-15")
PHASES = {"phase2": ("03-30", "04-20"), "phase3": ("04-21", "05-31")}
SUFFIX = ".lockdown"
MOBILITY_FILE = Path("movilidad_2020") / "2020_MX_Region_Mobility_Report.csv"
MOBILITY_COLUMNS = {
    "workplaces": "workplaces_percent_change_from_baseline",
    "transit": "transit_stations_percent_change_from_baseline",
}


def business_days(inputs: Inputs, year: int, span: tuple[str, str]) -> pd.DatetimeIndex:
    days = data_days(inputs)
    days = days[(days >= f"{year}-{span[0]}") & (days <= f"{year}-{span[1]}")]
    return days[day_type(days, HOLIDAYS) == WEEKDAY]


def phase_ratio(
    inputs: Inputs, make_model: Callable[[], Model], year: int, phase: tuple[str, str]
) -> dict[str, Any]:
    """Emission of the business days of `phase` over those of the base, in `year`, and its interval."""
    base, event = business_days(inputs, year, BASE), business_days(inputs, year, phase)
    if base.empty or event.empty:
        raise ValueError(f"{year}: no business days with data in the base or the phase {phase}")
    ratio, bounds = _fit_ratio(inputs.on_days(base.union(event)), make_model, event)
    return {
        "ratio": ratio,
        "lo": None if bounds is None else bounds[0],
        "hi": None if bounds is None else bounds[1],
        "n_base": len(base),
        "n_phase": len(event),
    }


def difference_in_differences(lockdown: dict[str, Any], placebo: dict[str, Any]) -> dict[str, Any]:
    """2020 over 2019, with an interval at the same level that adds the half widths of the two log intervals
    in quadrature (independent years); no interval when either has none."""
    ratio = lockdown["ratio"] / placebo["ratio"]
    if lockdown["lo"] is None or placebo["lo"] is None:
        return {"ratio": ratio, "lo": None, "hi": None}
    spread = float(np.hypot(*(np.log(r["hi"] / r["lo"]) / 2 for r in (lockdown, placebo))))
    return {"ratio": ratio, "lo": ratio * float(np.exp(-spread)), "hi": ratio * float(np.exp(spread))}


def mobility(path: Path) -> dict[str, dict[str, float]]:
    """Mean change (fraction) of the Google mobility of Mexico City on the business days of each phase, from
    Google's own baseline (5 Jan-6 Feb 2020)."""
    table = pd.read_csv(path, parse_dates=["date"], low_memory=False)
    city = table[(table["sub_region_1"] == "Mexico City") & table["sub_region_2"].isna()].set_index("date")
    days = pd.DatetimeIndex(city.index)
    city = city[day_type(days, HOLIDAYS) == WEEKDAY]
    out = {}
    for phase, (start, end) in {"base": BASE, **PHASES}.items():
        rows = city.loc[f"{YEARS[0]}-{start}" : f"{YEARS[0]}-{end}"]
        out[phase] = {name: float(rows[column].mean() / 100) for name, column in MOBILITY_COLUMNS.items()}
    return out


def lockdown_effect(inputs_by_year: dict[int, Inputs], make_model: Callable[[], Model]) -> dict[str, Any]:
    """Phase over base for each year and phase, and 2020 over 2019."""
    _require_emissions(make_model)
    result: dict[str, Any] = {}
    for phase, span in PHASES.items():
        by_year = {year: phase_ratio(inputs_by_year[year], make_model, year, span) for year in YEARS}
        result[phase] = {
            **{str(year): value for year, value in by_year.items()},
            "did": difference_in_differences(by_year[YEARS[0]], by_year[YEARS[1]]),
        }
    return result


def run_lockdown(config: ExperimentConfig, runs_dir: Path = Path("runs")) -> Path:
    """`lockdown_effect` with the model of `config` (its period is not used), written to
    ``runs_dir/<name>.lockdown/``: ``lockdown.json``, ``config.yaml`` and ``code_version.json``. Only
    `nox-ml lockdown` calls this."""
    name = f"{config.name.removesuffix(SUFFIX)}{SUFFIX}"
    inputs_by_year = {
        year: load_inputs(
            config.data_dir,
            f"{year}-{WINDOW[0]}",
            f"{year}-{WINDOW[1]}",
            config.simat_hours,
            LOCKDOWN_SOURCES,
        )
        for year in YEARS
    }
    mobility_path = config.data_dir / "raw" / MOBILITY_FILE
    result = {
        "model": config.model.name,
        "level": config.placebo.level,
        "phases": {"base": BASE, **PHASES},
        "holidays": day_list(pd.DatetimeIndex([d for d in HOLIDAYS if d[:4] in {str(y) for y in YEARS}])),
        "effect": lockdown_effect(inputs_by_year, config.model.build),
        "mobility": mobility(mobility_path) if mobility_path.exists() else None,
    }
    out = runs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(
        yaml.safe_dump(config.model_copy(update={"name": name}).model_dump(mode="json"), sort_keys=False)
    )
    (out / "lockdown.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "code_version.json").write_text(json.dumps(code_version(), indent=2) + "\n")
    return out


def headline(result: dict[str, Any]) -> str:
    """Phase over base for 2020 and 2019 and their ratio, for the terminal."""

    def show(r: dict[str, Any]) -> str:
        bounds = "" if r["lo"] is None else f" ({r['lo']:.2f}-{r['hi']:.2f})"
        return f"{r['ratio']:.2f}{bounds}"

    lines = [f"{result['model']}: emission of the phase over the base (business days)"]
    for phase, r in result["effect"].items():
        lines.append(
            f"  {phase}: 2020 {show(r['2020'])}, 2019 {show(r['2019'])}, 2020 / 2019 {show(r['did'])}"
        )
    if result["mobility"]:
        for phase in PHASES:
            m = result["mobility"][phase]
            lines.append(
                f"  mobility {phase}: workplaces {m['workplaces']:+.0%}, transit {m['transit']:+.0%}"
            )
    return "\n".join(lines)
