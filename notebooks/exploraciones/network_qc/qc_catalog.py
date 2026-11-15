# ruff: noqa: E501, B007  (exploration script: long lines and unused loop keys are fine here)
"""F7 exploration: quality control of the public air-quality networks (SIMAT and OpenAQ/SINAICA).

Runs simple detectors the repository QC does not cover and writes, next to this file:
  - catalog.csv           one row per anomaly (type, source, station, month, hours, value, known_to_project)
  - summary_by_month.csv  anomalies per month, source and type (all and "relevant")
  - duplicates.csv        SIMAT vs OpenAQ comparison of the stations present in both, Nov-Dec 2024

Usage (from the repository root, with data/raw linked):
    uv run python notebooks/exploraciones/network_qc/qc_catalog.py [--cache DIR]

All hours are keyed by `h`, the start of the hour in UTC (SIMAT stamps the end of the hour, local time).
Nothing here touches nox_ml/ or the frozen configs; the existing SIMAT loaders are reused read-only.
"""

import argparse
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import simat
from nox_ml.data.openaq import PARAMETERS as OAQ_PARAMETERS
from nox_ml.data.openaq import PPM_TO_PPB
from nox_ml.time import local_to_utc

HERE = Path(__file__).parent
RAW = Path("data/raw")
SIMAT_YEARS = (2019, 2020, 2023, 2024)
COLS = ("NO", "NO2", "NOX", "O3")
HOUR = pd.Timedelta(hours=1)
OPENAQ_SHIFT_FIXED = pd.Timestamp("2024-11-17")  # documented: OpenAQ is one hour off before this date

# Detector settings (chosen up front, not tuned on the data)
STUCK_MIN_RUN = 8  # identical consecutive readings
STUCK_MIN_VALUE = {
    "NO": 5.0,
    "NO2": 5.0,
    "NOX": 5.0,
    "O3": 5.0,
    "WSP": 0.5,
}  # below this a flat line is plausible
MIN_FLAG_HOURS = 12  # per station-month, for the hourly consistency rules
GAP_MIN_HOURS = 72
JUMP_WINDOW_DAYS = 14
JUMP_FACTOR = 2.0  # station vs the rest of the network, 14-day medians before/after
SCALE_FACTOR = 4.0
NETWORK_STEP_FACTOR = 1.8
MIN_DAY_HOURS = 18
LAG_RANGE = (-2, -1, 0, 1, 2)
LAG_GAIN = 0.05  # correlation gain of the best lag over lag 0
MIN_LAG_HOURS = 300
OUTAGE_SHARE = 0.2  # network outage: fewer than 20 % of the usual stations report
OUTAGE_MIN_HOURS = 6
NETWORK_STUCK_STATIONS = 5
RELEVANT_HOURS = {"stuck": 12, "gap": 168, "NO2_gt_NOX": 24, "NOx_sum_mismatch": 24, "negative": 24}


# --- Loading -----------------------------------------------------------------------------------------------


def _read_member(path: Path) -> bytes:
    """SIMAT files are ZIP (2023-24) or real gzip (2019-20) behind the same `.csv.gz` name."""
    import gzip

    head = path.read_bytes()[:2]
    if head == b"PK":
        return simat.read_zip_member(path)
    with gzip.open(path) as f:
        return f.read()


def load_simat_long(kind: str, year: int) -> pd.DataFrame:
    """Raw long table of one SIMAT year with `h` (UTC hour start). Handles both the 2019-20 and 2023-24 layout."""
    text = _read_member(RAW / "simat" / f"{kind}_{year}.csv.gz").decode("latin1")
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.lstrip('"').startswith("date"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype={"value": "float64"})
    day, clock = df["date"].str.slice(0, 10), df["date"].str.slice(11)  # "24:00" means 00:00 of the next day
    fmt = "%d/%m/%Y" if "/" in day.iloc[0] else "%Y-%m-%d"
    df["local"] = pd.to_datetime(day.str.strip(), format=fmt) + pd.to_timedelta(
        clock.str.slice(0, 2).replace("", "00").astype(int), unit="h"
    )
    df["h"] = local_to_utc(df["local"]) - HOUR
    return df


def simat_wide() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hourly NO, NO2, NOX, O3, WSP per station (raw: no masking, no mph fix) and the unit-id table."""
    frames, units = [], []
    for y in SIMAT_YEARS:
        pol = load_simat_long("contaminantes", y)
        met = load_simat_long("meteorologia", y)
        long = pd.concat([pol[pol["id_parameter"].isin(COLS)], met[met["id_parameter"] == "WSP"]])
        long["month"] = long["local"].dt.to_period("M")
        units.append(
            long.groupby(["id_station", "id_parameter", "month"])["unit"].agg(lambda s: s.mode().iat[0])
        )
        wide = long.pivot_table(
            index=["id_station", "h"], columns="id_parameter", values="value", aggfunc="mean"
        )
        frames.append(wide.reset_index())
    w = pd.concat(frames, ignore_index=True).rename(columns={"id_station": "station"})
    w = w.reindex(columns=["station", "h", *COLS, "WSP"])
    unit_ids = pd.concat(units).rename("unit").reset_index()
    return w, unit_ids


def openaq_wide() -> tuple[pd.DataFrame, list[tuple[pd.Timestamp, pd.Timestamp]]]:
    """Raw OpenAQ table in ppb (negatives kept), and the covered windows (end clipped to the last hour seen)."""
    frames, windows = [], []
    for path in sorted((RAW / "openaq").glob("openaq_*.parquet")):
        d = pd.read_parquet(path)
        start = pd.Timestamp(re.findall(r"\d{4}-\d{2}-\d{2}", path.name)[0])
        windows.append(
            (start, min(pd.Timestamp(re.findall(r"\d{4}-\d{2}-\d{2}", path.name)[1]), d["h"].max() + HOUR))
        )
        frames.append(d)
    raw = pd.concat(frames, ignore_index=True)
    raw["column"] = raw["parameter"].map(OAQ_PARAMETERS)
    raw = raw.dropna(subset=["column"])
    w = raw.pivot_table(index=["station", "h"], columns="column", values="value", aggfunc="mean") * PPM_TO_PPB
    w = w.reindex(columns=list(COLS)).reset_index()
    return w, windows


# --- Detectors ---------------------------------------------------------------------------------------------


def event(source, typ, param, station, start, end, hours, value, note=""):
    return {
        "source": source, "type": typ, "param": param, "station": station, "start": start, "end": end,
        "hours": hours, "value": value, "note": note,
    }  # fmt: skip


def stuck_events(w: pd.DataFrame, source: str) -> list[dict]:
    """Runs of >= STUCK_MIN_RUN identical consecutive readings (missing ones skipped) above a floor value."""
    out = []
    for p in [c for c in (*COLS, "WSP") if c in w]:
        s = w[["station", "h", p]].dropna().sort_values(["station", "h"])
        new = (s["station"] != s["station"].shift()) | (s[p] != s[p].shift())
        s["run"] = new.cumsum()
        g = s.groupby("run").agg(
            station=("station", "first"),
            start=("h", "min"),
            end=("h", "max"),
            n=("h", "size"),
            v=(p, "first"),
        )
        g = g[(g["n"] >= STUCK_MIN_RUN) & (g["v"] > STUCK_MIN_VALUE[p])]
        out += [
            event(source, "stuck", p, r.station, r.start, r.end, int(r.n), float(r.v)) for r in g.itertuples()
        ]
    return out


def monthly_flag_events(w: pd.DataFrame, source: str) -> list[dict]:
    """Hourly consistency rules, aggregated per station-month: negatives, NO2 > NOX, NO + NO2 far from NOX."""
    rules = {
        "NO2_gt_NOX": w["NO2"] > w["NOX"] * 1.1 + 3,
        "NOx_sum_mismatch": ((w["NO"] + w["NO2"] - w["NOX"]).abs() > 0.25 * w["NOX"].clip(lower=0) + 5),
    }
    for c in COLS:
        rules[f"negative_{c}"] = w[c] < (-1 if c == "O3" else 0)  # tiny negative noise in O3 is tolerated
    out = []
    month = w["h"].dt.to_period("M")
    for name, flag in rules.items():
        typ, param = ("negative", name[9:]) if name.startswith("negative_") else (name, "NOX")
        f = w[flag.fillna(False)]
        for (st, m), g in f.groupby(["station", month[f.index]]):
            if len(g) >= (1 if typ == "negative" else MIN_FLAG_HOURS):
                out.append(
                    event(
                        source,
                        typ,
                        param,
                        st,
                        g["h"].min(),
                        g["h"].max(),
                        len(g),
                        float(g[param if typ == "negative" else "NO2"].median()),
                    )
                )
    return out


def gap_events(w: pd.DataFrame, source: str, windows) -> list[dict]:
    """Missing stretches of NOX >= GAP_MIN_HOURS inside the windows, for stations that report NOX at all."""
    out = []
    for start, end in windows:
        grid = pd.date_range(start, end - HOUR, freq="h")
        ww = w[w["h"].between(start, end - HOUR) & w["NOX"].notna()]
        for st, g in ww.groupby("station"):
            present = pd.Series(False, index=grid)
            present[g["h"].values] = True
            run = (present != present.shift()).cumsum()
            for _, seg in present.groupby(run):
                if not seg.iloc[0] and len(seg) >= GAP_MIN_HOURS:
                    out.append(event(source, "gap", "NOX", st, seg.index[0], seg.index[-1], len(seg), 0.0))
    return out


def daily_frame(w: pd.DataFrame, p: str) -> pd.DataFrame:
    """Days x stations mean of parameter `p`, only days with MIN_DAY_HOURS valid hours; UTC days, fine for shifts."""
    x = w[["station", "h", p]].dropna()
    x = x.assign(day=x["h"].dt.floor("D"))
    g = x.groupby(["day", "station"])[p].agg(["mean", "size"])
    g = g[g["size"] >= MIN_DAY_HOURS]["mean"].unstack()
    return g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))


def _shift_series(r: pd.DataFrame) -> pd.DataFrame:
    roll = r.rolling(JUMP_WINDOW_DAYS, min_periods=JUMP_WINDOW_DAYS // 2).median()
    return roll.shift(-(JUMP_WINDOW_DAYS - 1)) - roll.shift(1)


def _cluster(series: pd.Series, thr: float):
    """Days where |series| > thr, merged when closer than the window; yields (day, value) of each cluster peak."""
    hit = series[series.abs() > thr].dropna()
    if hit.empty:
        return
    gid = (hit.index.to_series().diff() > pd.Timedelta(days=JUMP_WINDOW_DAYS)).cumsum()
    for _, g in hit.groupby(gid.values):
        yield g.abs().idxmax(), g.loc[g.abs().idxmax()]


def jump_events(w: pd.DataFrame, source: str) -> list[dict]:
    """Persistent level shifts of a station against the rest of the network, and steps of the network itself."""
    out = []
    for p in ("NOX", "O3", "WSP"):
        if p not in w or w[p].notna().sum() == 0:
            continue
        d = daily_frame(w, p)
        cnt = d.notna().sum(axis=1)
        n_other = d.notna().rsub(cnt, axis=0)
        tot = d.sum(axis=1)  # NaN-skipping row sums
        loo = d.fillna(0).rsub(tot, axis=0).div(n_other).where(n_other >= 5)
        r = np.log((d + 1) / (loo + 1))
        shift = _shift_series(r)
        for st in shift:
            for day, val in _cluster(shift[st], np.log(JUMP_FACTOR)):
                f = float(np.exp(val))
                typ = "scale_jump" if max(f, 1 / f) >= SCALE_FACTOR else "level_shift"
                out.append(
                    event(
                        source,
                        typ,
                        p,
                        st,
                        day,
                        day + pd.Timedelta(days=JUMP_WINDOW_DAYS),
                        JUMP_WINDOW_DAYS * 24,
                        f,
                    )
                )
        net = np.log(d.median(axis=1) + 1)
        roll = net.rolling(JUMP_WINDOW_DAYS, min_periods=JUMP_WINDOW_DAYS // 2).median()
        step = roll.shift(-(JUMP_WINDOW_DAYS - 1)) - roll.shift(1)
        for day, val in _cluster(step, np.log(NETWORK_STEP_FACTOR)):
            out.append(
                event(
                    source,
                    "network_step",
                    p,
                    "ALL",
                    day,
                    day + pd.Timedelta(days=JUMP_WINDOW_DAYS),
                    JUMP_WINDOW_DAYS * 24,
                    float(np.exp(val)),
                )
            )
    return out


def lag_events(w: pd.DataFrame, source: str) -> list[dict]:
    """Per station-month, the lag (-2..2 h) of best correlation with the leave-one-out mean of the other stations."""
    out = []
    for p in (
        "O3",
    ):  # NO2 was tried and dropped: its lag flags repeat at the same suburban stations (geography)
        if w[p].notna().sum() == 0:
            continue
        piv = w.pivot_table(index="h", columns="station", values=p)
        piv = piv.reindex(pd.date_range(piv.index.min(), piv.index.max(), freq="h"))
        total, cnt = piv.sum(axis=1), piv.notna().sum(axis=1)
        for st in piv:
            ref = ((total - piv[st].fillna(0)) / (cnt - piv[st].notna())).where((cnt - piv[st].notna()) >= 5)
            x = piv[st]
            for m, xm in x.groupby(x.index.to_period("M")):
                best = {}
                for k in LAG_RANGE:
                    both = pd.concat([xm, ref.shift(-k).reindex(xm.index)], axis=1).dropna()
                    if len(both) >= MIN_LAG_HOURS:
                        best[k] = both.iloc[:, 0].corr(both.iloc[:, 1])
                if 0 in best and len(best) == len(LAG_RANGE):
                    k = max(best, key=best.get)
                    if k != 0 and best[k] - best[0] >= LAG_GAIN:
                        out.append(
                            event(
                                source,
                                "time_shift",
                                p,
                                st,
                                xm.index[0],
                                xm.index[-1],
                                len(xm.dropna()),
                                float(k),
                                f"corr0={best[0]:.2f} corr_best={best[k]:.2f}",
                            )
                        )
    return out


def unit_events(unit_ids: pd.DataFrame, units: pd.Series) -> list[dict]:
    """Station-months whose unit id differs from the usual one of that parameter (e.g. ppm instead of ppb)."""
    u = unit_ids.assign(sym=unit_ids["unit"].map(units))
    usual = u.groupby("id_parameter")["sym"].agg(lambda s: s.mode().iat[0])
    bad = u[u["sym"] != u["id_parameter"].map(usual)]
    return [
        event(
            "SIMAT",
            "unit_label",
            r.id_parameter,
            r.id_station,
            r.month.start_time,
            r.month.end_time,
            0,
            np.nan,
            f"{r.sym} instead of {usual[r.id_parameter]}",
        )
        for r in bad.itertuples()
    ]


# --- SIMAT vs OpenAQ ---------------------------------------------------------------------------------------


def best_lag_corr(a: pd.Series, b: pd.Series, min_hours: int = 100) -> tuple[int, float, float]:
    """Lag k of b (b shifted by k h) with the best correlation to a; returns (k, corr_best, corr_0)."""
    res = {}
    for k in LAG_RANGE:
        both = pd.concat([a, b.shift(-k).reindex(a.index)], axis=1).dropna()
        res[k] = both.iloc[:, 0].corr(both.iloc[:, 1]) if len(both) >= min_hours else np.nan
    k = max((k for k in res if not np.isnan(res[k])), key=res.get, default=0)
    return k, res.get(k, np.nan), res.get(0, np.nan)


def compare_duplicates(s: pd.DataFrame, o: pd.DataFrame) -> pd.DataFrame:
    """Same station, same hour in SIMAT and OpenAQ (Nov-Dec 2024), before and after the documented shift fix."""
    lo, hi = pd.Timestamp("2024-11-01"), pd.Timestamp("2025-01-01")
    s, o = s[s["h"].between(lo, hi - HOUR)], o[o["h"].between(lo, hi - HOUR)]
    rows = []
    for st in sorted(set(s["station"]) & set(o["station"])):
        for p in COLS:
            for period, (a, b) in {
                "before_17nov": (lo, OPENAQ_SHIFT_FIXED),
                "after_17nov": (OPENAQ_SHIFT_FIXED, hi),
            }.items():
                x = s[(s["station"] == st) & s["h"].between(a, b - HOUR)].set_index("h")[p]
                y = o[(o["station"] == st) & o["h"].between(a, b - HOUR)].set_index("h")[p]
                if x.notna().sum() < 100 or y.notna().sum() < 100:
                    rows.append(
                        {
                            "station": st,
                            "param": p,
                            "period": period,
                            "n_simat": int(x.notna().sum()),
                            "n_openaq": int(y.notna().sum()),
                        }
                    )
                    continue
                k, cb, c0 = best_lag_corr(x, y)
                j = pd.concat([x, y], axis=1, keys=["s", "o"]).dropna()
                rows.append({
                    "station": st, "param": p, "period": period, "n_simat": int(x.notna().sum()), "n_openaq": int(y.notna().sum()),
                    "n_both": len(j), "only_simat": int((x.notna() & ~y.reindex(x.index).notna()).sum()),
                    "only_openaq": int((y.notna() & ~x.reindex(y.index).notna()).sum()),
                    "share_equal": float(((j["s"] - j["o"]).abs() <= 1.0).mean()), "median_diff": float((j["o"] - j["s"]).median()),
                    "median_ratio": float(j["o"].median() / j["s"].median()) if j["s"].median() > 0 else np.nan,
                    "best_lag": k, "corr_best": cb, "corr_lag0": c0,
                })  # fmt: skip
    return pd.DataFrame(rows)


# --- Driver ------------------------------------------------------------------------------------------------


def month_of(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["start"]).dt.to_period("M").astype(str)


def network_outage_events(w: pd.DataFrame, source: str, windows) -> list[dict]:
    """Stretches where almost no station reports NOX although the network usually does (usual = 90th percentile
    of the hourly station count over a 30-day window)."""
    out = []
    for start, end in windows:
        ww = w[w["h"].between(start, end - HOUR) & w["NOX"].notna()]
        n = (
            ww.groupby("h")["station"]
            .nunique()
            .reindex(pd.date_range(start, end - HOUR, freq="h"), fill_value=0)
        )
        usual = n.rolling(24 * 30, min_periods=24, center=True).quantile(0.9)
        low = n < OUTAGE_SHARE * usual
        run = (low != low.shift()).cumsum()
        for _, seg in low.groupby(run):
            if (
                seg.iloc[0] and len(seg) >= OUTAGE_MIN_HOURS and seg.index[0] != start
            ):  # not the start of a file
                out.append(
                    event(
                        source,
                        "network_outage",
                        "NOX",
                        "ALL",
                        seg.index[0],
                        seg.index[-1],
                        len(seg),
                        float(usual[seg.index].median()),
                    )
                )
    return out


def network_stuck_events(ev: list[dict]) -> list[dict]:
    """Individual stuck runs that start at the same hour in >= 5 stations: the feed froze, not the sensors."""
    st = pd.DataFrame([e for e in ev if e["type"] == "stuck" and e["param"] != "WSP"])
    if st.empty:
        return []
    out = []
    for (src, start), g in st.groupby(["source", st["start"].dt.floor("2h")]):
        if g["station"].nunique() >= NETWORK_STUCK_STATIONS:
            out.append(
                event(
                    src,
                    "network_stuck",
                    "ALL",
                    "ALL",
                    g["start"].min(),
                    g["end"].max(),
                    int(g["hours"].max()),
                    float(g["station"].nunique()),
                    "value = stations frozen",
                )
            )
    return out


def daily_overlap(s: pd.DataFrame, o: pd.DataFrame) -> pd.DataFrame:
    """Per day (Nov-Dec 2024): stations and hours with NOX in each source, and the network O3 lag (OpenAQ vs SIMAT)."""
    lo, hi = pd.Timestamp("2024-11-01"), pd.Timestamp("2025-01-01")
    common = set(s["station"]) & set(o["station"])
    s, o = s[s["h"].between(lo, hi - HOUR) & s["station"].isin(common)], o[o["h"].between(lo, hi - HOUR)]
    day = lambda d: d["h"].dt.floor("D")  # noqa: E731
    out = pd.DataFrame({
        "simat_hours": s[s["NOX"].notna()].groupby(day(s[s["NOX"].notna()])).size(),
        "openaq_hours": o[o["NOX"].notna()].groupby(day(o[o["NOX"].notna()])).size(),
    }).fillna(0)  # fmt: skip
    a = s.groupby("h")["O3"].mean()
    b = o.groupby("h")["O3"].mean()
    lags = {}
    for d in out.index:
        w = pd.date_range(d - pd.Timedelta(days=1), d + pd.Timedelta(days=2), freq="h")
        lags[d] = (
            best_lag_corr(a.reindex(w), b.reindex(w), 48)[0]
            if a.reindex(w).notna().sum() > 48 and b.reindex(w).notna().sum() > 48
            else np.nan
        )
    out["openaq_missing_share"] = 1 - out["openaq_hours"] / out["simat_hours"]
    out["o3_lag_openaq_vs_simat"] = pd.Series(lags)
    return out


def completeness_by_month(w: pd.DataFrame, source: str, windows) -> pd.DataFrame:
    """Share of station-hours with NOX per month, for the stations that report at all in that month."""
    rows = []
    for start, end in windows:
        grid = pd.date_range(start, end - HOUR, freq="h")
        ww = w[w["h"].between(start, end - HOUR) & w["NOX"].notna()]
        for m, g in ww.groupby(ww["h"].dt.to_period("M")):
            hours = (grid.to_period("M") == m).sum()
            rows.append(
                {
                    "source": source,
                    "month": str(m),
                    "stations": g["station"].nunique(),
                    "completeness": len(g) / (g["station"].nunique() * hours),
                }
            )
    return pd.DataFrame(rows)


def known_to_project(c: pd.DataFrame) -> pd.Series:
    """Findings the project already documents: mph wind 2024, SIMAT 2023-24 stuck NOX, OpenAQ 1 h shift."""
    y = pd.to_datetime(c["start"]).dt.year
    wind = (c["param"] == "WSP") & (c["type"] == "network_step") & (c["source"] == "SIMAT") & (y == 2024)
    stuck = (c["type"] == "stuck") & (c["param"] == "NOX") & (c["source"] == "SIMAT") & y.isin([2023, 2024])
    shift = (
        (c["source"] == "OpenAQ")
        & (c["type"] == "time_shift")
        & (pd.to_datetime(c["start"]) < OPENAQ_SHIFT_FIXED)
    )
    return wind | stuck | shift


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=None, help="Directory to cache the loaded hourly tables.")
    args = ap.parse_args()
    cache = args.cache
    if cache and (cache / "simat_wide.parquet").exists():
        s, unit_ids = (
            pd.read_parquet(cache / "simat_wide.parquet"),
            pd.read_parquet(cache / "simat_units.parquet"),
        )
        unit_ids["month"] = pd.PeriodIndex(unit_ids["month"], freq="M")
    else:
        s, unit_ids = simat_wide()
        if cache:
            cache.mkdir(parents=True, exist_ok=True)
            s.to_parquet(cache / "simat_wide.parquet")
            unit_ids.assign(month=unit_ids["month"].astype(str)).to_parquet(cache / "simat_units.parquet")
    o, o_windows = openaq_wide()
    units = simat.load_units(RAW / "simat")

    ev = []
    for y in SIMAT_YEARS:  # per year so gaps and 'stations present' are per year; jumps need adjacency, so run jumps/lags on all years
        wy = s[s["h"].dt.year == y]
        ev += stuck_events(wy, "SIMAT") + monthly_flag_events(wy, "SIMAT")
        ev += gap_events(wy, "SIMAT", [(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01"))])
    ev += jump_events(s, "SIMAT") + lag_events(s, "SIMAT") + unit_events(unit_ids, units)
    ev += stuck_events(o, "OpenAQ") + monthly_flag_events(o, "OpenAQ") + gap_events(o, "OpenAQ", o_windows)
    ev += jump_events(o, "OpenAQ") + lag_events(o, "OpenAQ")

    ev += network_outage_events(
        s, "SIMAT", [(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")) for y in SIMAT_YEARS]
    )
    ev += network_outage_events(o, "OpenAQ", o_windows)
    ev += network_stuck_events(ev)

    cat = pd.DataFrame(ev)
    cat["month"] = month_of(cat)
    cat["known_to_project"] = known_to_project(cat)
    thr = cat["type"].map(RELEVANT_HOURS)
    cat["relevant"] = np.where(thr.notna(), cat["hours"] >= thr, True)
    # A station gap that mostly lies inside a network outage is the outage, not the station.
    out = cat[cat["type"] == "network_outage"]
    for i, g in cat[cat["type"] == "gap"].iterrows():
        o_ = out[(out["source"] == g["source"]) & (out["start"] <= g["end"]) & (out["end"] >= g["start"])]
        if (
            len(o_)
            and (np.minimum(o_["end"], g["end"]) - np.maximum(o_["start"], g["start"])).sum() / HOUR
            >= 0.5 * g["hours"]
        ):
            cat.loc[i, ["relevant", "note"]] = [False, "inside network outage"]
    # Level shifts and network steps are candidates: seasonal change or weather can produce them.
    candidate = (
        cat["type"].isin(["level_shift", "scale_jump", "network_step", "stuck"]) & ~cat["known_to_project"]
    )
    cat["status"] = np.where(cat["known_to_project"], "known", np.where(candidate, "candidate", "new"))
    cat.sort_values(["source", "start", "type", "station"]).to_csv(HERE / "catalog.csv", index=False)

    ref = cat[(cat["month"] >= "2024-01") & (cat["status"] == "new") & cat["relevant"]]
    summ = ref.groupby(["month", "source", "type"]).size().unstack(fill_value=0)
    summ["total_new_relevant"] = summ.sum(axis=1)
    summ.to_csv(HERE / "summary_by_month.csv")
    daily_overlap(s, o).to_csv(HERE / "duplicates_daily.csv")
    year_windows = [(pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")) for y in SIMAT_YEARS]
    pd.concat(
        [completeness_by_month(s, "SIMAT", year_windows), completeness_by_month(o, "OpenAQ", o_windows)]
    ).to_csv(HERE / "completeness_by_month.csv", index=False)
    compare_duplicates(s, o).to_csv(HERE / "duplicates.csv", index=False)
    print(f"{len(cat)} events; {int(cat['relevant'].sum())} relevant; {len(ref)} new, relevant and from 2024")
    print(summ.to_string())


if __name__ == "__main__":
    main()
