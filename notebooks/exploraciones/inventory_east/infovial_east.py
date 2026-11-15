"""Tests 2 and 4: what the Infovial counts (Nov-Dec 2018, 26 primary corridors of CDMX) say about the east.

The inventory prior has no hourly or per-class detail by zone, so the east is proxied by the corridors that
lead east: Calzada Ignacio Zaragoza (to Ecatepec/Nezahualcoyotl side) and, as a wider proxy, the Eje 3
Oriente and Eje 2/1 Oriente. Classes C1-C6 are assumed ordered by size (C3-C6 heavy, as `sesgo_domingo.md`).
For each weighting of the heavy classes: share of the east corridors in the weekday flow of 12-17 h over
their share in the full day (the factor to apply to the inventory's 18.9 %), their heavy fraction and their
Sunday/weekday ratio against the rest.
"""

from pathlib import Path

import pandas as pd

FILES = [
    Path("data/raw/trafico/infovial_201811_clasificacion.csv"),
    Path("data/raw/trafico/infovial_201812_clasificacion.csv"),
]
EAST = {
    "strict": ["CALZADA IGNACIO ZARAGOZA"],
    "wide": [
        "CALZADA IGNACIO ZARAGOZA",
        "EJE TRONCAL METROPOLITANO-EJE 3 ORIENTE",
        "EJE 2 ORIENTE",
        "EJE 1 ORIENTE",
    ],
}
HEAVY = ["C3", "C4", "C5", "C6"]
HOLIDAYS = pd.to_datetime(["2018-11-19", "2018-12-12", "2018-12-24", "2018-12-25", "2018-12-31"])
INVENTORY_EAST = 0.1888  # share of the road prior (`shares.py`)
OUT = Path(__file__).parent / "out"


def load() -> pd.DataFrame:
    frame = pd.concat([pd.read_csv(f) for f in FILES])
    frame["fecha"] = pd.to_datetime(frame["fecha"])
    frame["hour"] = frame["hora"].str[:2].astype(int)
    frame["dow"] = frame["fecha"].dt.dayofweek
    # December 2018: the 18-31 Dec weeks are atypical (year end); keep Nov 1 - Dec 14
    frame = frame[(frame["fecha"] <= "2018-12-14") & ~frame["fecha"].isin(HOLIDAYS)]
    frame["heavy"] = frame["tipo_vehiculo"].isin(HEAVY)
    return frame.rename(columns={"id": "corridor"})


def weighted(frame: pd.DataFrame, heavy_weight: float) -> pd.Series:
    return frame["cantidad"] * frame["heavy"].map({True: heavy_weight, False: 1.0})


def main() -> None:
    frame = load()
    weekday = frame[frame["dow"] < 5]
    sunday = frame[frame["dow"] == 6]
    rows = []
    for name, corridors in EAST.items():
        for w in (1, 3, 10, 30):
            day = weighted(weekday, w).groupby(weekday["corridor"].isin(corridors)).sum()
            noon_mask = weekday["hour"].between(12, 17)
            noon = (
                weighted(weekday[noon_mask], w).groupby(weekday[noon_mask]["corridor"].isin(corridors)).sum()
            )
            share_day, share_noon = day[True] / day.sum(), noon[True] / noon.sum()
            sun = weighted(sunday, w).groupby(sunday["corridor"].isin(corridors)).sum()
            n_wd, n_sun = weekday["fecha"].nunique(), sunday["fecha"].nunique()
            ratio_east = (sun[True] / n_sun) / (day[True] / n_wd)
            ratio_rest = (sun[False] / n_sun) / (day[False] / n_wd)
            factor = share_noon / share_day
            east_noon = INVENTORY_EAST * factor / (INVENTORY_EAST * factor + 1 - INVENTORY_EAST)
            rows.append(
                {
                    "proxy": name,
                    "heavy_w": w,
                    "share_day": share_day,
                    "share_1217": share_noon,
                    "factor": factor,
                    "inventory_east_1217": east_noon,
                    "sunday_east": ratio_east,
                    "sunday_rest": ratio_rest,
                }
            )
    table = pd.DataFrame(rows)
    # heavy fraction of the counts and of the weighted emission (w=10) by corridor, on weekdays
    by_corridor = weekday.groupby("corridor").apply(
        lambda g: pd.Series(
            {
                "heavy_counts": g.loc[g["heavy"], "cantidad"].sum() / g["cantidad"].sum(),
                "heavy_emission_w10": weighted(g, 10)[g["heavy"]].sum() / weighted(g, 10).sum(),
            }
        ),
        include_groups=False,
    )
    sunday_by_corridor = (sunday.groupby("corridor")["cantidad"].sum() / sunday["fecha"].nunique()) / (
        weekday.groupby("corridor")["cantidad"].sum() / weekday["fecha"].nunique()
    )
    by_corridor["sunday_over_weekday"] = sunday_by_corridor
    OUT.mkdir(exist_ok=True)
    table.to_csv(OUT / "infovial_east.csv", index=False)
    by_corridor.to_csv(OUT / "infovial_corridors.csv")
    print(table.round(3).to_string())
    print(by_corridor.round(3).to_string())


if __name__ == "__main__":
    main()
