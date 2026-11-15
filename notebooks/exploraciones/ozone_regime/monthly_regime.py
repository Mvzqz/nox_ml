"""Month by month, 2024-2026: center HCHO/NO2 (TEMPO) against the center Sunday / weekday ozone (F2, repeat).

Question: does the center move from VOC-limited (Feb) toward transition (May) in the HCHO/NO2 ratio AND does
the Sunday ozone excess weaken in the same direction? Criterion fixed beforehand: confidence grows if, in at
least 2 of 3 years, the center ratio rises from February to May and the Sunday / weekday O3 ratio falls from
February to May. Weekend ratios reuse the pairing of `weekend_effect.py` (Sunday vs business days of the same
year, within +-21 days, matched by Tmax and afternoon wind), restricted to center stations (< 12 km from the
Zocalo) and cut by month of the Sunday; no minimum number of pairs per station (months have 3-5 Sundays).
Intervals: bootstrap over weeks (Sundays) for ozone, over days for the ratio.

Usage: uv run python notebooks/exploraciones/ozone_regime/monthly_regime.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).parent))
import hcho_no2_ratio as fnr
import weekend_effect as we

from nox_ml.data import simat

OUT = Path(__file__).parent / "results"
N_BOOT = 1000
RNG = np.random.default_rng(39)
YEARS = (2024, 2025, 2026)
GROUPS = {"feb": (2,), "mar": (3,), "apr": (4,), "may": (5,), "feb-mar": (2, 3), "abr-may": (4, 5)}
MONTH_NAME = {2: "feb", 3: "mar", 4: "apr", 5: "may"}


def center_fnr_by_month(px: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (year, month), g in px.groupby([px["day"].dt.year, px["day"].dt.month]):
        if month not in MONTH_NAME:
            continue
        days = g["day"].unique()
        by_day = {d: x for d, x in g.groupby("day")}

        def center(sub: pd.DataFrame) -> float:
            m = fnr.cell_ratio(sub)
            return fnr.center_fnr(m) if len(m) else np.nan

        boots = [center(pd.concat([by_day[d] for d in RNG.choice(days, len(days))])) for _ in range(200)]
        rows.append(
            {
                "year": year,
                "month": month,
                "days": len(days),
                "fnr_center": center(g),
                "fnr_lo": np.nanpercentile(boots, 5),
                "fnr_hi": np.nanpercentile(boots, 95),
            }
        )
    return pd.DataFrame(rows)


def ratio_ci(tr: np.ndarray, ctl: np.ndarray) -> tuple[float, np.ndarray]:
    """Median over center stations of sum(Sunday) / sum(matched mean); point value and week bootstrap."""

    def est(idx):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.nanmedian(tr[idx].sum(0) / ctl[idx].sum(0))

    n = tr.shape[0]
    return est(np.arange(n)), np.array([est(RNG.integers(0, n, n)) for _ in range(N_BOOT)])


def weekend_by_month() -> pd.DataFrame:
    hourly = pd.concat([we.simat_hourly(), we.openaq_hourly()], ignore_index=True)
    daily = we.station_daily(hourly)
    weather = we.domain_weather(daily, we.metar_daily())
    contingency, _ = we.contingency_days(daily)
    days = we.day_table(weather, contingency)
    cat = simat.load_catalog(we.RAW / "simat").set_index("station")
    dist = 111.32 * np.hypot(
        cat["lat"] - we.ZOCALO[0], (cat["lon"] - we.ZOCALO[1]) * np.cos(np.deg2rad(we.ZOCALO[0]))
    )
    wide = daily.pivot_table(index="day", columns="station", values="mda8_o3")
    wide = wide.loc[:, (dist.reindex(wide.columns) < we.CENTER_KM).to_numpy()]
    rows = []
    for year in YEARS:
        s = days[(days["season"] == "ozono") & (days.index.year == year)]
        pairs = we.match(days, s.index[s["kind"] == "sunday"], s.index[s["kind"] == "wd"])
        for label, months in GROUPS.items():
            sub = {t: m for t, m in pairs.items() if t.month in months}
            if len(sub) < 2:
                continue
            tr, ctl = we.pair_values(wide, sub)
            r, b = ratio_ci(tr, ctl)
            rows.append(
                {
                    "year": year,
                    "group": label,
                    "sundays": len(sub),
                    "o3_sun_ratio": r,
                    "lo": np.nanpercentile(b, 5),
                    "hi": np.nanpercentile(b, 95),
                    "boot": b,
                }
            )
    return pd.DataFrame(rows)


def criterion(f: pd.DataFrame, w: pd.DataFrame, boots: dict) -> pd.DataFrame:
    """February -> May per year, and Feb-Mar -> Apr-May as the less noisy version."""
    rows = []
    for year in YEARS:
        for a, b, ma, mb in (("feb", "may", (2,), (5,)), ("feb-mar", "abr-may", (2, 3), (4, 5))):
            if (year, a) not in boots or (year, b) not in boots:
                continue
            d = boots[(year, b)] - boots[(year, a)]
            wy = w[w["year"] == year].set_index("group")["o3_sun_ratio"]
            fy = f[f["year"] == year]
            fa = fy[fy["month"].isin(ma)]["fnr_center"].mean()
            fb = fy[fy["month"].isin(mb)]["fnr_center"].mean()
            rows.append(
                {
                    "year": year,
                    "contrast": f"{a}->{b}",
                    "fnr_from": fa,
                    "fnr_to": fb,
                    "o3_from": wy[a],
                    "o3_to": wy[b],
                    "o3_change": wy[b] - wy[a],
                    "o3_change_lo": np.nanpercentile(d, 5),
                    "o3_change_hi": np.nanpercentile(d, 95),
                    "fnr_rises": fb > fa,
                    "o3_weakens": wy[b] < wy[a],
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    px = fnr.load()
    px = px[px["day"].dt.year.isin(YEARS)]
    f = center_fnr_by_month(px)
    f.to_csv(OUT / "monthly_fnr_center.csv", index=False, float_format="%.4f")
    print(f.round(3).to_string(), flush=True)
    w = weekend_by_month()
    boots = {(r.year, r.group): r.boot for r in w.itertuples()}
    w.drop(columns="boot").to_csv(OUT / "monthly_weekend_center.csv", index=False, float_format="%.4f")
    print(w.drop(columns="boot").round(3).to_string(), flush=True)
    c = criterion(f, w, boots)
    c.to_csv(OUT / "monthly_criterion.csv", index=False, float_format="%.4f")
    print(c.round(3).to_string(), flush=True)
    mm = f.assign(group=f["month"].map(MONTH_NAME)).merge(w, on=["year", "group"])
    print(
        "Spearman FNR vs Sunday O3 (year-months):",
        len(mm),
        spearmanr(mm["fnr_center"], mm["o3_sun_ratio"], nan_policy="omit"),
    )


if __name__ == "__main__":
    main()
