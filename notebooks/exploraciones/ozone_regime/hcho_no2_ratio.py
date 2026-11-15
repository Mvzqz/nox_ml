"""HCHO/NO2 column ratio (FNR) from TEMPO over the Mexico City basin, 12-16 h local, Feb-May 2024 and 2025.

Step 2 of the ozone-regime exploration (`context/knowledge/regimen_ozono.md`). HCHO (V04, total column) and
NO2 (V04, tropospheric column) come from the same scan, so their pixels pair one to one. Valid pixel: quality
flag 0 in both products, effective cloud fraction < 0.2, solar zenith < 70 deg. Pixels are binned to a
0.05 deg grid; the ratio of each cell is mean(HCHO) / mean(NO2) over the period (ratio of means: the single
pixel HCHO is too noisy for a ratio of single values). Noise: split-half maps (odd vs even ISO weeks) and a
day bootstrap. The map is read at the SIMAT stations and set against the Sunday / weekday ozone of step 1.

Usage: uv run python notebooks/exploraciones/ozone_regime/hcho_no2_ratio.py
"""

from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from nox_ml.data import simat

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).parent / "results"
BBOX = (-99.4, 19.1, -98.8, 19.8)
CELL = 0.05
MAX_CF = 0.2
MAX_SZA = 70.0
MIN_PIXELS = 30  # per cell and period
THRESHOLDS = {"Duncan2010": (1.0, 2.0), "Jin2017": (3.2, 4.1)}
SEASONS = {"2024": ("2024-02-01", "2024-05-31"), "2025": ("2025-02-01", "2025-05-31")}
N_BOOT = 300
RNG = np.random.default_rng(39)


def read_pair(hcho_path: Path) -> pd.DataFrame | None:
    """Paired pixels of one scan; None when the NO2 granule of the scan is missing or the cut differs."""
    no2_path = RAW / "tempo" / hcho_path.name.replace("HCHO", "NO2")
    if not no2_path.exists():
        return None
    with netCDF4.Dataset(hcho_path) as h, netCDF4.Dataset(no2_path) as n:
        hv = h["product/vertical_column"][:].filled(np.nan)
        nv = n["product/vertical_column_troposphere"][:].filled(np.nan)
        if hv.shape != nv.shape:
            return None
        df = pd.DataFrame(
            {
                "hcho": hv.ravel(),
                "no2": nv.ravel(),
                "hqf": h["product/main_data_quality_flag"][:].filled(255).ravel(),
                "nqf": n["product/main_data_quality_flag"][:].filled(255).ravel(),
                "cf": n["support_data/eff_cloud_fraction"][:].filled(np.nan).ravel(),
                "sza": h["geolocation/solar_zenith_angle"][:].filled(np.nan).ravel(),
                "lat": h["geolocation/latitude"][:].filled(np.nan).ravel(),
                "lon": h["geolocation/longitude"][:].filled(np.nan).ravel(),
            }
        )
    df["utc"] = pd.to_datetime(hcho_path.name.split("_")[4], format="%Y%m%dT%H%M%SZ")
    return df


def load() -> pd.DataFrame:
    frames = [
        p
        for f in sorted((RAW / "tempo_hcho").glob("TEMPO_HCHO_L2_V04_*_zmvm.nc"))
        if (p := read_pair(f)) is not None
    ]
    px = pd.concat(frames, ignore_index=True)
    px = px[px["lon"].between(BBOX[0], BBOX[2]) & px["lat"].between(BBOX[1], BBOX[3])]
    ok = (px["hqf"] == 0) & (px["nqf"] == 0) & (px["cf"] < MAX_CF) & (px["sza"] < MAX_SZA)
    px = px[ok & px["hcho"].notna() & px["no2"].notna()].copy()
    px["local"] = px["utc"] - pd.Timedelta(hours=6)
    px["day"] = px["local"].dt.normalize()
    px["week"] = px["local"].dt.isocalendar().week.astype(int)
    px["ix"] = ((px["lon"] - BBOX[0]) // CELL).astype(int)
    px["iy"] = ((px["lat"] - BBOX[1]) // CELL).astype(int)
    return px


def cell_ratio(px: pd.DataFrame) -> pd.DataFrame:
    g = px.groupby(["ix", "iy"])
    out = g[["hcho", "no2"]].mean().assign(n=g.size())
    out = out[out["n"] >= MIN_PIXELS]
    out["fnr"] = out["hcho"] / out["no2"]
    return out


def center_fnr(m: pd.DataFrame) -> float:
    """Ratio of the mean columns of the cells within 0.1 deg of the Zocalo."""
    lon = BBOX[0] + (m.index.get_level_values("ix") + 0.5) * CELL
    lat = BBOX[1] + (m.index.get_level_values("iy") + 0.5) * CELL
    c = m[(np.abs(lon + 99.133) < 0.1) & (np.abs(lat - 19.433) < 0.1)]
    return float(c["hcho"].mean() / c["no2"].mean())


def regime(fnr: pd.Series, lo: float, hi: float) -> pd.Series:
    return pd.Series(np.where(fnr < lo, "COV", np.where(fnr > hi, "NOx", "transicion")), index=fnr.index)


def day_bootstrap_se(px: pd.DataFrame) -> pd.Series:
    """Standard error of each cell's FNR, resampling whole days."""
    days = px["day"].unique()
    by_day = {d: g for d, g in px.groupby("day")}
    reps = []
    for _ in range(N_BOOT):
        pick = RNG.choice(days, len(days))
        reps.append(cell_ratio(pd.concat([by_day[d] for d in pick]))["fnr"])
    return pd.concat(reps, axis=1).std(axis=1)


def main() -> None:
    px = load()
    cat = simat.load_catalog(RAW / "simat").set_index("station")
    weekend = pd.read_csv(OUT / "weekend_ratios.csv")
    w = weekend[(weekend["case"] == "domingo_ozono_emparejado") & weekend["dist_km"].notna()]
    o3 = w[w["metric"] == "mda8_o3"].set_index("unit")
    rows, maps, month_rows = [], [], []
    for label, (start, end) in SEASONS.items():
        s = px[(px["day"] >= start) & (px["day"] <= end)]
        if s.empty:
            continue
        m = cell_ratio(s)
        m["se"] = day_bootstrap_se(s)
        odd, even = cell_ratio(s[s["week"] % 2 == 1])["fnr"], cell_ratio(s[s["week"] % 2 == 0])["fnr"]
        both = pd.concat([odd, even], axis=1, keys=["odd", "even"]).dropna()
        split_r = spearmanr(both["odd"], both["even"]).statistic
        months = []
        for mo, sm in s.groupby(s["day"].dt.month):
            mc = cell_ratio(sm)
            months.append(mc["fnr"].rename(mo))
            month_rows.append(
                {
                    "season": label,
                    "month": mo,
                    "days": sm["day"].nunique(),
                    "fnr_median": mc["fnr"].median(),
                    "fnr_center": center_fnr(mc),
                    **{
                        f"frac_Duncan2010_{r}": (regime(mc["fnr"], 1.0, 2.0) == r).mean()
                        for r in ("COV", "NOx")
                    },
                }
            )
        monthly = pd.concat(months, axis=1)
        month_r = monthly.corr(method="spearman").where(~np.eye(monthly.shape[1], dtype=bool)).stack().mean()
        for name, (lo, hi) in THRESHOLDS.items():
            m[f"reg_{name}"] = regime(m["fnr"], lo, hi)
        m["season"] = label
        maps.append(m.reset_index())
        # stations: the cell that holds each station
        st = cat.loc[cat.index.intersection(o3.index)]
        key = list(
            zip(
                ((st["lon"] - BBOX[0]) // CELL).astype(int),
                ((st["lat"] - BBOX[1]) // CELL).astype(int),
                strict=True,
            )
        )
        st = st.assign(fnr=[m["fnr"].get(k, np.nan) for k in key], o3_sun=o3.loc[st.index, "ratio"])
        st = st.assign(
            no2=[m["no2"].get(k, np.nan) for k in key], hcho=[m["hcho"].get(k, np.nan) for k in key]
        )
        st = st.assign(nox_sun=w[w["metric"] == "nox_24h"].set_index("unit")["ratio"].reindex(st.index))
        st = st.assign(
            o3_lo=o3.loc[st.index, "lo"], o3_hi=o3.loc[st.index, "hi"], km=o3.loc[st.index, "dist_km"]
        )
        st["o3_sign"] = np.where(st["o3_lo"] > 1, "sube", np.where(st["o3_hi"] < 1, "baja", "igual"))
        st["regime"] = regime(st["fnr"], *THRESHOLDS["Duncan2010"]).where(st["fnr"].notna())
        rho = spearmanr(st["fnr"], st["o3_sun"], nan_policy="omit").statistic
        rho_km = spearmanr(st["km"], st["o3_sun"], nan_policy="omit").statistic
        # does FNR say more than the distance to the center? partial Spearman on ranks
        rk = st[["fnr", "o3_sun", "km"]].dropna().rank()
        res = {c: rk[c] - np.polyval(np.polyfit(rk["km"], rk[c], 1), rk["km"]) for c in ("fnr", "o3_sun")}
        rho_partial = float(np.corrcoef(res["fnr"], res["o3_sun"])[0, 1])
        # local threshold: the FNR at which the Sunday / weekday ozone of the stations crosses 1
        ok = st[["fnr", "o3_sun"]].dropna()
        slope, icpt = np.polyfit(ok["fnr"], ok["o3_sun"], 1)
        crossing = (1 - icpt) / slope
        print(pd.crosstab(st["regime"], st["o3_sign"]), flush=True)
        st.assign(season=label)[
            ["season", "lat", "lon", "km", "fnr", "regime", "o3_sun", "o3_lo", "o3_hi", "o3_sign", "nox_sun"]
        ].to_csv(OUT / f"stations_fnr_{label}.csv", float_format="%.4f")
        frac = {
            f"frac_{name}_{r}": (m[f"reg_{name}"] == r).mean()
            for name in THRESHOLDS
            for r in ("COV", "transicion", "NOx")
        }
        rows.append(
            {
                "season": label,
                "pixels": len(s),
                "days": s["day"].nunique(),
                "cells": len(m),
                "fnr_median": m["fnr"].median(),
                "fnr_p10": m["fnr"].quantile(0.1),
                "fnr_p90": m["fnr"].quantile(0.9),
                "fnr_center": center_fnr(m),
                "frac_below_crossing": (m["fnr"] < crossing).mean(),
                "se_median": m["se"].median(),
                "split_half_spearman": split_r,
                "monthly_spearman_mean": month_r,
                "stations_rho_fnr_vs_o3_sunday": rho,
                "stations_rho_km_vs_o3_sunday": rho_km,
                # the spatial ranking comes mostly from NO2: compare with each column alone
                "stations_rho_minus_no2_vs_o3_sunday": spearmanr(-st["no2"], st["o3_sun"]).statistic,
                "stations_rho_hcho_vs_o3_sunday": spearmanr(st["hcho"], st["o3_sun"]).statistic,
                "stations_slope_o3_per_fnr": slope,
                "stations_fnr_where_o3_sunday_is_1": crossing,
                "fnr_o3_up_stations_median": st.loc[st["o3_sign"] == "sube", "fnr"].median(),
                "fnr_other_stations_median": st.loc[st["o3_sign"] != "sube", "fnr"].median(),
                "stations_rho_partial_km": rho_partial,
                "stations_n": int(st["fnr"].notna().sum()),
                "cov_stations_o3_up": int(((st["regime"] == "COV") & (st["o3_sign"] == "sube")).sum()),
                "cov_stations": int((st["regime"] == "COV").sum()),
                "noncov_stations_o3_up": int(((st["regime"] != "COV") & (st["o3_sign"] == "sube")).sum()),
                "noncov_stations": int(((st["regime"] != "COV") & st["regime"].notna()).sum()),
                **frac,
            }
        )
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "fnr_summary.csv", index=False, float_format="%.4f")
    pd.DataFrame(month_rows).to_csv(OUT / "fnr_monthly.csv", index=False, float_format="%.4f")
    print(pd.DataFrame(month_rows).round(3).to_string(), flush=True)
    pd.concat(maps).to_csv(OUT / "fnr_map.csv", index=False, float_format="%.4g")


if __name__ == "__main__":
    main()
