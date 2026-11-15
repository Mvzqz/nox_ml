"""Rates by group of episode types from ``resultados.csv`` (written by `validate.py`).

Usage: uv run python notebooks/exploraciones/episodes/summary.py
"""

from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
GROUPS = {
    "clima": ["estancada", "ventilada"],
    "emision_baja": ["festivo", "semana_santa", "confinamiento"],
    "acumulacion": ["fin_de_anio", "fondo_alto"],
}
SCORES = ["weather_ok", "fp", "weather_ok_p", "fp_p"]


def main() -> None:
    r = pd.read_csv(HERE / "resultados.csv")
    known = [t for types in GROUPS.values() for t in types]
    rows = {g: r[r.type.isin(t)] for g, t in GROUPS.items()}
    rows["todos_con_causa"] = r[r.type.isin(known)]
    rows["sin_cambio_de_emision"] = r[r.type.isin(GROUPS["clima"] + GROUPS["acumulacion"])]
    table = pd.DataFrame({g: s[SCORES].astype(float).mean() for g, s in rows.items()}).T
    table.insert(0, "n", [len(s) for s in rows.values()])
    print(table.round(2))
    weather = rows["clima"]
    # lenient: a weather week whose concentration was usual and came out "normal" is not an error
    print(
        "weather weeks, normal accepted:",
        (weather.weather_ok | (weather.verdict == "normal")).mean().round(2),
    )
    print("  prudent:", (weather.weather_ok_p | (weather.prudent == "normal")).mean().round(2))
    print(
        "weather ratio unusual in the weather weeks:",
        ((weather.weather < weather.weather_lo) | (weather.weather > weather.weather_hi)).mean().round(2),
    )
    print(
        "concentration unusual in the weather weeks:",
        (
            (weather.concentration < weather.concentration_lo)
            | (weather.concentration > weather.concentration_hi)
        )
        .mean()
        .round(2),
    )
    low = rows["emision_baja"]
    found = (low.verdict.isin(["emission", "both"]) & (low.emission < 1)).sum()
    print(
        f"emission drops claimed: {found} of {len(low)}; "
        f"prudent 'no lo explica': {(low.prudent == 'no_explica').sum()}"
    )
    print(pd.crosstab(r.type, r.verdict))
    print(pd.crosstab(r.type, r.prudent))


if __name__ == "__main__":
    main()
