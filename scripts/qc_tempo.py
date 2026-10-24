"""P2: control de calidad de los recortes TEMPO NO₂ L2 según los criterios del plan.

Uso: .venv/bin/python scripts/qc_tempo.py 2023-11-01 2023-12-31
Salida: data/interim/tempo_pixels_{inicio}_{fin}.parquet y reports/qc_tempo_{inicio}_{fin}.md
"""
import sys
from pathlib import Path

import geopandas as gpd
import netCDF4
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/tempo"
OUT = ROOT / "data/interim"
from config import LAT, LON
CORE_LAT, CORE_LON = (19.33, 19.53), (-99.20, -99.03)  # centro urbano
MAX_CLOUD = 0.2
MATCH_KM = 3.0

start, end = sys.argv[1:3]
lines = [f"# QC TEMPO NO₂ L2 V04 ({start} a {end})\n"]


def say(s=""):
    print(s)
    lines.append(s)


def check(ok, msg):
    say(f"- {'✅' if ok else '❌'} {msg}")


rows = []
for f in sorted(RAW.glob("TEMPO_NO2_L2_V04_*_zmvm.nc")):
    t = pd.Timestamp(f.name.split("_")[4][:15].replace("T", " "), tz="UTC").tz_localize(None)
    if not (pd.Timestamp(start) <= t < pd.Timestamp(end) + pd.Timedelta(days=1)):
        continue
    with netCDF4.Dataset(f) as ds:
        units = ds["product/vertical_column_troposphere"].units
        g = {
            "vcd": ds["product/vertical_column_troposphere"][:].filled(np.nan).ravel(),
            "qf": ds["product/main_data_quality_flag"][:].filled(255).ravel(),
            "cf": ds["support_data/eff_cloud_fraction"][:].filled(np.nan).ravel(),
            "lat": ds["geolocation/latitude"][:].filled(np.nan).ravel(),
            "lon": ds["geolocation/longitude"][:].filled(np.nan).ravel(),
            "snow": ds["support_data/snow_ice_fraction"][:].filled(np.nan).ravel(),
        }
    df = pd.DataFrame(g)
    df["granule"], df["utc"], df["units"] = f.name, t, units
    rows.append(df)
px = pd.concat(rows, ignore_index=True)
px = px[px.lat.between(*LAT) & px.lon.between(*LON)]
px["valid"] = (px.qf == 0) & (px.cf < MAX_CLOUD) & px.vcd.notna()
px["local"] = px.utc - pd.Timedelta(hours=6)

say(f"- ℹ️ Granulos: {px.granule.nunique()}; días: {px.utc.dt.date.nunique()}; píxeles en dominio por granulo: mediana {px.groupby('granule').size().median():.0f}")
u = px.units.unique()
check(list(u) == ["molecules/cm^2"], f"Unidades: {list(u)}")
v = px[px.valid]
core = v[v.lat.between(*CORE_LAT) & v.lon.between(*CORE_LON)]
med = core.vcd.median()
check(1e15 <= med <= 1e16 * 3, f"Mediana VCD troposférica en el centro urbano: {med:.2e} (meta 10¹⁵–10¹⁶)")

frac = px.groupby("granule").valid.mean()
check((frac >= 0.5).mean() > 0.5, f"Granulos con ≥ 50 % del dominio válido: {(frac >= 0.5).mean():.0%} "
      f"({(frac >= 0.5).sum()} de {len(frac)})")
say(f"- ℹ️ Motivo de rechazo (píxeles): bandera ≠ 0 {(px.qf != 0).mean():.0%}, nubes ≥ {MAX_CLOUD} {(px.cf >= MAX_CLOUD).mean():.0%}")
by_day = px.groupby(px.local.dt.date).valid.mean()
say(f"- ℹ️ Días con ≥ 50 % de píxeles válidos en la tarde: {(by_day >= 0.5).sum()} de {len(by_day)}")

rest = v[~(v.lat.between(*CORE_LAT) & v.lon.between(*CORE_LON))]
ratio = core.vcd.mean() / rest.vcd.mean()
check(ratio > 1.2, f"Centro / alrededores: {ratio:.2f}× ({core.vcd.mean():.2e} vs {rest.vcd.mean():.2e})")

# Correlación con NO₂ de estaciones a la misma hora
st = gpd.read_file(ROOT / "data/interim/estaciones.gpkg").to_crs(4326)
st = st.set_index("cve_estac")[["geometry"]]
no2 = pd.read_parquet(ROOT / "data/interim/simat_nox.parquet", columns=["id_station", "utc", "NO2"])
no2 = no2[no2.id_station.isin(st.index) & no2.NO2.notna()]
v = v.copy()
v["hour"] = v.utc.dt.floor("h")
pairs = []
kx = 111.32 * np.cos(np.deg2rad(19.45))
for (gname, hr), gp in v.groupby(["granule", "hour"]):
    obs = no2[no2.utc == hr + pd.Timedelta(hours=1)]  # SIMAT etiqueta la hora al final del periodo
    for _, o in obs.iterrows():
        p = st.loc[o.id_station, "geometry"]
        d = np.hypot((gp.lon - p.x) * kx, (gp.lat - p.y) * 111.32)
        if d.min() <= MATCH_KM:
            pairs.append({"granule": gname, "station": o.id_station, "no2_ppb": o.NO2, "vcd": gp.vcd.values[d.argmin()]})
pairs = pd.DataFrame(pairs)
if len(pairs):
    r_all = pairs.no2_ppb.corr(pairs.vcd)
    r_gran = pairs.groupby("granule").apply(lambda g: g.no2_ppb.corr(g.vcd) if len(g) >= 5 else np.nan).dropna()
    st_mean = pairs.groupby("station")[["no2_ppb", "vcd"]].mean()
    r_st = st_mean.no2_ppb.corr(st_mean.vcd)
    check(r_all > 0, f"Correlación TEMPO vs NO₂ de estaciones (pares hora-estación, n={len(pairs)}): r = {r_all:.2f}")
    say(f"- ℹ️ Correlación espacial por granulo: mediana r = {r_gran.median():.2f} ({len(r_gran)} granulos con ≥ 5 estaciones)")
    say(f"- ℹ️ Correlación de promedios por estación ({len(st_mean)} estaciones): r = {r_st:.2f}")
else:
    say("- ❌ Sin pares estación–píxel")

OUT.mkdir(exist_ok=True)
tag = f"{start}_{end}"
px.drop(columns="units").to_parquet(OUT / f"tempo_pixels_{tag}.parquet")
(ROOT / f"reports/qc_tempo_{tag}.md").write_text("\n".join(lines) + "\n")
