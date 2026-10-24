"""LA: viento horario por estación (ASOS + sitios AQS) y error real por validación cruzada.

Mismo método que wind_loo.py (CDMX): cada estación se predice con (a) el vector medio de las demás
y (b) IDW de las demás; error de dirección en horas con viento observado ≥ 1 m/s, 12–17 h locales.
Opcional (c): HRRR, si existe data/interim/la/hrrr_at_stations.parquet (ver la_hrrr.py).

Uso: .venv/bin/python scripts/la_wind.py
Salida: data/interim/la/wind_stations.parquet, data/interim/la/wind_loo.csv; tablas en markdown.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from la_common import AFTERNOON, END, INT, LOCAL_OFFSET_H, RAW, START, UTM

EXCLUDE = {"MWS"}  # Mount Wilson: cima a ~1,700 m, no representa el flujo de la cuenca


def ang_err(u1, v1, u2, v2):
    a1, a2 = np.degrees(np.arctan2(u1, v1)), np.degrees(np.arctan2(u2, v2))
    return np.abs((a1 - a2 + 180) % 360 - 180)


def uv(ws, wd):
    r = np.deg2rad(wd)
    return -ws * np.sin(r), -ws * np.cos(r)


def station_winds():
    a = pd.read_csv(RAW / "asos_2023-11-12.csv", parse_dates=["valid"]).dropna(subset=["sknt", "drct"])
    a = a[~a.station.isin(EXCLUDE)]
    a["u"], a["v"] = uv(a.sknt * 0.5144, a.drct)
    a["h"] = a.valid.dt.floor("h")
    asos = a.groupby(["station", "h"]).agg(u=("u", "mean"), v=("v", "mean"), lat=("lat", "first"), lon=("lon", "first")).reset_index()
    asos = asos.rename(columns={"station": "sid"})
    q = pd.read_parquet(INT / "aqs_wind.parquet")
    ws = q[q["Parameter Code"] == 61103].set_index(["site", "utc"])["Sample Measurement"]
    wd = q[q["Parameter Code"] == 61104].set_index(["site", "utc"])["Sample Measurement"]
    j = pd.concat({"ws": ws, "wd": wd}, axis=1).dropna().reset_index()
    j["u"], j["v"] = uv(j.ws * 0.5144, j.wd)
    pos = q.groupby("site")[["Latitude", "Longitude"]].first()
    j["lat"], j["lon"] = pos.loc[j.site, "Latitude"].values, pos.loc[j.site, "Longitude"].values
    aqs = j.rename(columns={"site": "sid", "utc": "h"})[["sid", "h", "u", "v", "lat", "lon"]]
    w = pd.concat([asos, aqs], ignore_index=True)
    loc = w.h + pd.Timedelta(hours=LOCAL_OFFSET_H)
    w = w[(loc >= START) & (loc < pd.Timestamp(END) + pd.Timedelta(days=1))]
    g = gpd.GeoSeries.from_xy(w.lon, w.lat, crs=4326).to_crs(UTM)
    w["x"], w["y"] = g.x.values, g.y.values
    w.to_parquet(INT / "wind_stations.parquet")
    return w


def main():
    w = station_winds()
    loc = w.h + pd.Timedelta(hours=LOCAL_OFFSET_H)
    w = w[loc.dt.hour.isin(AFTERNOON)]
    hrrr = None
    try:
        hrrr = pd.read_parquet(INT / "hrrr_at_stations.parquet").set_index(["sid", "h"])
    except FileNotFoundError:
        pass
    rows = []
    for h, g in w.groupby("h"):
        if len(g) < 4:
            continue
        for i, r in g.iterrows():
            o = g.drop(index=i)
            d = np.hypot(o.x - r.x, o.y - r.y)
            wt = 1 / np.maximum(d, 500) ** 2
            row = dict(sid=r.sid, h=h, u=r.u, v=r.v, u_mean=o.u.mean(), v_mean=o.v.mean(),
                       u_idw=(wt * o.u).sum() / wt.sum(), v_idw=(wt * o.v).sum() / wt.sum())
            if hrrr is not None and (r.sid, h) in hrrr.index:
                row["u_hrrr"], row["v_hrrr"] = hrrr.loc[(r.sid, h), ["u", "v"]]
            rows.append(row)
    df = pd.DataFrame(rows)
    df["sp"] = np.hypot(df.u, df.v)
    methods = [("mean", "Vector medio de las demás"), ("idw", "IDW de las demás estaciones")]
    if "u_hrrr" in df:
        methods.append(("hrrr", "HRRR (3 km) interpolado"))
    for m, _ in methods:
        df[f"dir_{m}"] = ang_err(df.u, df.v, df[f"u_{m}"], df[f"v_{m}"])
    df.to_csv(INT / "wind_loo.csv", index=False)
    ok = df[df.sp >= 1]
    print(f"Estaciones: {df.sid.nunique()}; horas-estación: {len(df):,}; con viento ≥ 1 m/s: {len(ok):,} ({len(ok) / len(df):.0%})\n")
    print("| Método | n | Error dirección mediana | p75 | σ equivalente |")
    print("|---|---|---|---|---|")
    for m, name in methods:
        e = ok[f"dir_{m}"].dropna()
        print(f"| {name} | {len(e):,} | {e.median():.0f}° | {e.quantile(.75):.0f}° | {e.median() / 0.6745:.0f}° |")
    if "dir_hrrr" in ok:
        both = ok.dropna(subset=["dir_hrrr"])
        print(f"\nMismas horas que HRRR (n={len(both):,}): IDW {both.dir_idw.median():.0f}°, vector medio {both.dir_mean.median():.0f}°, HRRR {both.dir_hrrr.median():.0f}°")
    print("\n| Estación | n | IDW mediana | Vector medio mediana |" + (" HRRR mediana |" if "dir_hrrr" in ok else ""))
    print("|---|---|---|---|" + ("---|" if "dir_hrrr" in ok else ""))
    for s, g in ok.groupby("sid"):
        extra = f" {g.dir_hrrr.median():.0f}° |" if "dir_hrrr" in g and g.dir_hrrr.notna().any() else (" — |" if "dir_hrrr" in ok else "")
        print(f"| {s} | {len(g)} | {g.dir_idw.median():.0f}° | {g.dir_mean.median():.0f}° |" + extra)


if __name__ == "__main__":
    main()
