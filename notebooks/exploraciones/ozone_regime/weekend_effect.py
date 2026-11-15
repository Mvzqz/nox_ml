"""Weekend effect of ozone in the Mexico City basin: Sunday / weekday of MDA8 O3, afternoon Ox and NOx.

Step 1 of the ozone-regime exploration (`context/knowledge/regimen_ozono.md`). Each Sunday is compared with
the business days of the same season, within +-21 days, whose maximum temperature and afternoon wind are
alike (weather matching); the ratio is sum(Sunday) / sum(mean of its matched weekdays). Intervals: bootstrap
over weeks (each Sunday with its matched days is one week). Holidays, year-end, Easter weeks and contingency
days are left out; 2020 is analysed apart (lockdown).

Data: SIMAT 2019, 2020, 2023, 2024 (hourly tables, `nox_ml.data.simat`) and OpenAQ (SINAICA) 2025-2026,
with the METAR of MMMX for the weather of 2025-2026.

Usage: uv run python notebooks/exploraciones/ozone_regime/weekend_effect.py [out_dir]
"""

import gzip
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import simat
from nox_ml.data.calendar import atypical_days
from nox_ml.data.contingencies import measure_days, read_episodes
from nox_ml.data.openaq import simat_table
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.time import local_to_utc

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "results"
SIMAT_YEARS = [2019, 2020, 2023, 2024]
ZOCALO = (19.4326, -99.1332)
CENTER_KM = 12.0  # stations closer than this to the Zocalo are "center"
ACTIVATION_PPB = 154  # Phase I of the ozone contingency program (index 150 since 2019)
WINDOW_DAYS = 21
TMAX_TOL_C = 1.5
WIND_TOL = 0.25  # relative tolerance of the afternoon mean wind
MIN_MATCHES = 2
N_BOOT = 1000
OZONE_MONTHS = (2, 3, 4, 5, 6)
WINTER_MONTHS = (11, 12, 1)
AFTERNOON = range(12, 18)
MORNING = range(6, 10)
METRICS = ("mda8_o3", "ox_pm", "nox_24h", "nox_am")
RNG = np.random.default_rng(39)


# --- Hourly tables ------------------------------------------------------------------------------------------


def load_table(kind: str) -> pd.DataFrame:
    """SIMAT yearly tables; 2019-2020 are real gzip, 2023-2024 are ZIP named `.csv.gz`."""
    frames = []
    for y in SIMAT_YEARS:
        path = RAW / "simat" / f"{kind}_{y}.csv.gz"
        if zipfile.is_zipfile(path):
            frames.append(simat.parse_table(io.BytesIO(simat.read_zip_member(path))))
            continue
        # old format: one more header line, day-first dates and hours 01-24 (24:00 = midnight of next day)
        with gzip.open(path) as fh:
            df = pd.read_csv(fh, skiprows=10, dtype={"value": "float64"}, low_memory=False)
        stamp = df["date"].str.replace(" 24:00", " 00:00")
        local = pd.to_datetime(stamp, format="%d/%m/%Y %H:%M")
        df["local"] = local + pd.to_timedelta(df["date"].str.endswith(" 24:00").astype(int), unit="D")
        df["utc"] = local_to_utc(df["local"])
        frames.append(df.drop(columns="date"))
    return pd.concat(frames, ignore_index=True)


def simat_hourly() -> pd.DataFrame:
    """Station-hour table (local start of the hour) with O3, NO2, NOX (ppb), TMP (C) and WSP (m/s)."""
    pol = load_table("contaminantes")
    pol = pol[pol["id_parameter"].isin(("O3", "NO2", "NOX"))]
    pol.loc[pol["value"] < 0, "value"] = np.nan
    chem = simat.pivot_hourly(pol, ("O3", "NO2", "NOX"))
    met = load_table("meteorologia")
    tmp = simat.pivot_hourly(met, ("TMP",))
    wind = simat.clean_wind(met)[["id_station", "local", "WSP"]]
    hourly = chem.merge(tmp[["id_station", "local", "TMP"]], on=["id_station", "local"], how="outer")
    hourly = hourly.merge(wind, on=["id_station", "local"], how="outer")
    hourly["local"] = hourly["local"] - simat.HOUR_LABEL_SHIFT
    return hourly.drop(columns="utc", errors="ignore").assign(source="simat")


def openaq_hourly() -> pd.DataFrame:
    """OpenAQ station-hours from 2025 on (2024 is covered by SIMAT)."""
    raw = pd.concat([pd.read_parquet(p) for p in sorted((RAW / "openaq").glob("openaq_*.parquet"))])
    table = simat_table(raw)
    table["local"] = table["local"] - simat.HOUR_LABEL_SHIFT
    table = table[table["local"] >= "2025-01-01"]
    return table[["id_station", "local", "O3", "NO2", "NOX"]].assign(source="openaq")


def metar_daily() -> pd.DataFrame:
    """Daily Tmax (C) and afternoon mean wind (m/s) at MMMX, for 2025-2026."""
    m = pd.read_csv(RAW / "metar" / "MMMX_2024-2026.csv", na_values=["M"])
    t = pd.to_datetime(m["valid"]) - pd.Timedelta(hours=6)  # UTC -> local (no DST since 2022)
    m = m.assign(day=t.dt.normalize(), hour=t.dt.hour)
    m["tmp"] = (m["tmpf"] - 32) / 1.8
    m["wsp"] = m["sknt"] * 0.5144
    daily = m.groupby("day").agg(tmax=("tmp", "max"))
    daily["wind"] = m[m["hour"].isin(AFTERNOON)].groupby("day")["wsp"].mean()
    return daily


# --- Daily metrics ------------------------------------------------------------------------------------------


def station_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Per station-day: MDA8 O3 (8-h windows starting 07-16 h, >= 6 valid hours), afternoon Ox (O3 + NO2,
    12-17 h, >= 4 hours), NOx 24-h (>= 18 hours) and morning NOx (06-09 h, >= 3 hours)."""
    frames = []
    for st, g in hourly.groupby("id_station"):
        g = g.set_index("local").sort_index()
        g = g[~g.index.duplicated()].asfreq("h")
        o3 = g["O3"]
        roll = o3[::-1].rolling(8, min_periods=6).mean()[::-1]  # forward-looking window starting at the hour
        hour = g.index.hour
        day = g.index.normalize()
        d = pd.DataFrame(index=pd.Index(day.unique(), name="day"))
        d["mda8_o3"] = roll[(hour >= 7) & (hour <= 16)].groupby(day[(hour >= 7) & (hour <= 16)]).max()
        ox = (g["O3"] + g["NO2"])[np.isin(hour, AFTERNOON)]
        dd = day[np.isin(hour, AFTERNOON)]
        d["ox_pm"] = ox.groupby(dd).mean().where(ox.groupby(dd).count() >= 4)
        d["nox_24h"] = g["NOX"].groupby(day).mean().where(g["NOX"].groupby(day).count() >= 18)
        am = g["NOX"][np.isin(hour, MORNING)]
        da = day[np.isin(hour, MORNING)]
        d["nox_am"] = am.groupby(da).mean().where(am.groupby(da).count() >= 3)
        d["o3_max1h"] = o3.groupby(day).max()
        if "TMP" in g:
            d["tmax"] = g["TMP"].groupby(day).max()
            w = g["WSP"][np.isin(hour, AFTERNOON)]
            d["wind"] = w.groupby(dd).mean()
        frames.append(d.assign(station=st))
    return pd.concat(frames).reset_index()


def domain_weather(daily: pd.DataFrame, metar: pd.DataFrame) -> pd.DataFrame:
    """Median over SIMAT stations of Tmax and afternoon wind; METAR where SIMAT has none."""
    w = daily.groupby("day")[["tmax", "wind"]].median()
    return w.combine_first(metar).dropna()


def contingency_days(daily: pd.DataFrame) -> tuple[pd.DatetimeIndex, pd.Series]:
    """Days with contingency measures: the 2024 episodes and, for the other years, a proxy (the day after
    any station exceeded 154 ppb in one hour). Also the proxy activations per year."""
    peak = daily.groupby("day")["o3_max1h"].max()
    act = peak[peak > ACTIVATION_PPB].index
    proxy = pd.DatetimeIndex(act + pd.Timedelta(days=1))
    real = measure_days(read_episodes(RAW / "contingencias" / "contingencias_ozono_2024_episodios.csv"))
    days = proxy[proxy.year != 2024].union(real)
    per_year = pd.Series(act.year).value_counts().sort_index()
    return days, per_year


def day_table(weather: pd.DataFrame, contingency: pd.DatetimeIndex) -> pd.DataFrame:
    d = weather.copy()
    d["dow"] = d.index.day_of_week
    excluded = d.index.isin(pd.DatetimeIndex(HOLIDAYS)) | d.index.isin(atypical_days(d.index[0], d.index[-1]))
    excluded |= d.index.isin(contingency)
    d["kind"] = np.where(
        excluded, "skip", np.where(d["dow"] == 6, "sunday", np.where(d["dow"] < 5, "wd", "sat"))
    )
    month = d.index.month
    d["season"] = np.where(
        np.isin(month, OZONE_MONTHS), "ozono", np.where(np.isin(month, WINTER_MONTHS), "invierno", "")
    )
    # the ozone season split in two, to set against the monthly HCHO/NO2 (lower in Feb-Mar)
    d["subseason"] = np.where(
        np.isin(month, (2, 3)), "ozono_feb-mar", np.where(np.isin(month, (4, 5, 6)), "ozono_abr-jun", "")
    )
    d["lockdown"] = (d.index >= "2020-03-23") & (d.index <= "2020-06-30")
    return d


# --- Matching and ratios ------------------------------------------------------------------------------------


def match(days: pd.DataFrame, treated: pd.Index, pool: pd.Index, by_doy: bool = False) -> dict:
    """For every treated day, the pool days within WINDOW_DAYS with similar Tmax and afternoon wind."""
    out = {}
    pw = days.loc[pool]
    pkey = pw.index.day_of_year if by_doy else pw.index
    for t in treated:
        r = days.loc[t]
        dt = np.abs(pkey - (t.day_of_year if by_doy else t))
        dt = dt if by_doy else dt / pd.Timedelta(days=1)
        ok = (np.asarray(dt) <= WINDOW_DAYS) & (np.abs(pw["tmax"] - r["tmax"]) <= TMAX_TOL_C).to_numpy()
        ok &= (np.abs(pw["wind"] - r["wind"]) <= WIND_TOL * max(r["wind"], 0.5)).to_numpy()
        if ok.sum() >= MIN_MATCHES:
            out[t] = pw.index[ok]
    return out


def unmatched(days: pd.DataFrame, treated: pd.Index, pool: pd.Index) -> dict:
    """Same pairing without the weather condition (only the +-21-day window)."""
    out = {}
    for t in treated:
        near = pool[np.abs((pool - t) / pd.Timedelta(days=1)) <= WINDOW_DAYS]
        if len(near) >= MIN_MATCHES:
            out[t] = near
    return out


def pair_values(wide: pd.DataFrame, pairs: dict) -> tuple[np.ndarray, np.ndarray]:
    """(treated value, mean of its matches) per treated day x station."""
    tr = wide.reindex(list(pairs)).to_numpy()
    ctl = np.vstack([wide.reindex(m).mean().to_numpy() for m in pairs.values()])
    ok = ~np.isnan(tr) & ~np.isnan(ctl)
    return np.where(ok, tr, 0.0), np.where(ok, ctl, 0.0)


def ratios(
    tr: np.ndarray, ctl: np.ndarray, groups: dict[str, np.ndarray], stations: list[str]
) -> pd.DataFrame:
    """Per-station and per-zone (median of stations with >= 8 pairs) ratio with a week bootstrap."""
    n = tr.shape[0]
    cnt = (ctl > 0).sum(0)
    good = cnt >= 8

    def est(idx):
        with np.errstate(invalid="ignore", divide="ignore"):
            r = tr[idx].sum(0) / ctl[idx].sum(0)
        z = {k: np.nanmedian(r[g & good]) if (g & good).any() else np.nan for k, g in groups.items()}
        return r, z

    r0, z0 = est(np.arange(n))
    boots = [est(RNG.integers(0, n, n)) for _ in range(N_BOOT)]
    rb = np.array([b[0] for b in boots])
    rows = [
        {
            "unit": s,
            "ratio": r0[i],
            "lo": np.nanpercentile(rb[:, i], 5),
            "hi": np.nanpercentile(rb[:, i], 95),
            "n": cnt[i],
        }
        for i, s in enumerate(stations)
        if good[i]
    ]
    for k in groups:
        zb = np.array([b[1][k] for b in boots])
        rows.append(
            {"unit": k, "ratio": z0[k], "lo": np.nanpercentile(zb, 5), "hi": np.nanpercentile(zb, 95), "n": n}
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hourly = pd.concat([simat_hourly(), openaq_hourly()], ignore_index=True)
    daily = station_daily(hourly)
    weather = domain_weather(daily, metar_daily())
    contingency, activations = contingency_days(daily)
    days = day_table(weather, contingency)
    cat = simat.load_catalog(RAW / "simat").set_index("station")
    dist = 111.32 * np.hypot(cat["lat"] - ZOCALO[0], (cat["lon"] - ZOCALO[1]) * np.cos(np.deg2rad(ZOCALO[0])))
    activations.rename("activaciones_proxy").to_csv(OUT / "activations_per_year.csv")

    results = []
    for metric in METRICS:
        wide = daily.pivot_table(index="day", columns="station", values=metric)
        stations = list(wide.columns)
        d = dist.reindex(stations).to_numpy()
        groups = {"centro": d < CENTER_KM, "periferia": d >= CENTER_KM}
        cases = []
        for season in ("ozono", "invierno", "ozono_feb-mar", "ozono_abr-jun"):
            col = "subseason" if season.startswith("ozono_") else "season"
            sel = days[(days[col] == season) & ~days["lockdown"] & (days.index.year != 2020)]
            # pair within a season of one year (a winter spans Nov-Jan: keyed by the year of its November)
            key = np.where(sel.index.month == 1, sel.index.year - 1, sel.index.year)
            for kind, pairing in (("emparejado", match), ("sin_emparejar", None)):
                pairs = {}
                for k in np.unique(key):
                    s = sel[key == k]
                    sun, wd = s.index[s["kind"] == "sunday"], s.index[s["kind"] == "wd"]
                    pairs |= (pairing or (lambda dd, a, b: unmatched(dd, a, b)))(days, sun, wd)
                cases.append((f"domingo_{season}_{kind}", pairs))
        # lockdown: business days of Apr-May 2020 against those of Apr-May 2019, matched by weather and date
        lk = days[(days.index.month.isin((4, 5))) & (days["kind"] == "wd")]
        cases.append(
            (
                "confinamiento_abr-may_2020_vs_2019",
                match(days, lk.index[lk.index.year == 2020], lk.index[lk.index.year == 2019], by_doy=True),
            )
        )
        sun20 = days[(days.index.year == 2020) & days["lockdown"]]
        cases.append(
            (
                "domingo_confinamiento_2020",
                match(days, sun20.index[sun20["kind"] == "sunday"], sun20.index[sun20["kind"] == "wd"]),
            )
        )
        for name, pairs in cases:
            tr, ctl = pair_values(wide, pairs)
            r = ratios(tr, ctl, groups, stations).assign(metric=metric, case=name)
            results.append(r)
            print(
                metric,
                name,
                len(pairs),
                r[r["unit"].isin(groups)][["unit", "ratio", "lo", "hi"]].round(3).values.tolist(),
                flush=True,
            )
    res = pd.concat(results)
    res["dist_km"] = res["unit"].map(dist)
    res.to_csv(OUT / "weekend_ratios.csv", index=False, float_format="%.4f")
    days.to_csv(OUT / "days.csv", float_format="%.3f")


if __name__ == "__main__":
    main()
