"""Banco datos-vs-desempeño, parte 0: ficha de datos por ciudad (reports/banco_datos.md).

Calcula lo que se puede medir con los datos descargados (estaciones de NOₓ: número, densidad, distancia al vecino
más cercano, área de su envolvente; error de dirección del viento con validación cruzada; píxeles de TEMPO por
escaneo) y agrega lo ya medido en reports/ (fuentes, años y resoluciones).
Salida: data/interim/fichas_datos.json
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INT, RAW = ROOT / "data/interim", ROOT / "data/raw"


def station_stats(lon, lat, epsg, area_dom):
    g = gpd.GeoSeries.from_xy(lon, lat, crs=4326).to_crs(epsg)
    xy = np.c_[g.x, g.y]
    d = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    np.fill_diagonal(d, np.inf)
    hull = g.union_all().convex_hull.area / 1e6
    return {"n": int(len(g)), "dominio_km2": area_dom, "densidad_por_1000km2": round(1000 * len(g) / area_dom, 1),
            "vecino_mas_cercano_km": round(float(np.median(d.min(1))) / 1000, 1), "envolvente_km2": round(hull),
            "km2_por_estacion_envolvente": round(hull / len(g))}


def ang_err(a, b):
    return np.abs((np.asarray(a) - np.asarray(b) + 180) % 360 - 180)


def wind_loo_file(f, cols):
    w = pd.read_csv(f)
    w = w[w.sp >= 1.0] if "sp" in w else w
    obs = np.rad2deg(np.arctan2(w.u, w.v))   # dirección hacia donde va (misma convención para todos)
    out = {}
    for c in cols:
        uu, vv = w[f"u_{c}"], w[f"v_{c}"]
        out[c] = round(float(np.nanmedian(ang_err(obs, np.rad2deg(np.arctan2(uu, vv))))), 1)
    out["horas_estacion"] = int(len(w))
    return out


def bogota():
    cat = {s["stationId"]: s for s in json.load(open(RAW / "bogota/rmcab_estaciones.json"))}
    rows, comp = [], {}
    for f in sorted((RAW / "bogota").glob("rmcab_*_2023-11_2023-12.json")):
        j = json.load(open(f))
        inv = {v: k for k, v in j["canales"].items()}
        d = pd.DataFrame(j["datos"])
        d["t"] = pd.to_datetime(d.datetime.str.replace(" 24:00", " 00:00"), format="%d-%m-%Y %H:%M", errors="coerce")
        d.loc[d.datetime.str.contains(" 24:00", na=False), "t"] += pd.Timedelta(days=1)
        d = d[d.t.notna()]
        nox = pd.to_numeric(d.get(inv.get("NOX")), errors="coerce") if "NOX" in inv else pd.Series(np.nan, index=d.index)
        comp[j["id"]] = float(nox.notna().mean())
        if "Vel Viento" in inv and "Dir Viento" in inv:
            ws = pd.to_numeric(d[inv["Vel Viento"]], errors="coerce")
            wd = pd.to_numeric(d[inv["Dir Viento"]], errors="coerce")
            rows.append(pd.DataFrame({"sid": j["id"], "t": d.t, "ws": ws, "wd": wd}))
    good = [s for s, c in comp.items() if c >= 0.86]
    lon = [cat[s]["location"]["longitude"] for s in good]
    lat = [cat[s]["location"]["latitude"] for s in good]
    # dominio de análisis: la zona urbana (~380 km² según bogota.md); se reporta también la envolvente
    stats = station_stats(lon, lat, 32618, 380)
    stats["n_con_nox"] = len(comp)
    # viento: validación cruzada en la tarde (12–17 h local), viento ≥ 1 m/s, como wind_loo.py
    w = pd.concat(rows).dropna()
    w = w[(w.t.dt.hour >= 12) & (w.t.dt.hour <= 17) & (w.ws > 0)]
    th = np.deg2rad(w.wd)
    w["u"], w["v"] = -w.ws * np.sin(th), -w.ws * np.cos(th)   # viento hacia donde va
    xy = gpd.GeoSeries.from_xy([cat[s]["location"]["longitude"] for s in w.sid.unique()],
                               [cat[s]["location"]["latitude"] for s in w.sid.unique()], crs=4326).to_crs(32618)
    pos = dict(zip(w.sid.unique(), zip(xy.x, xy.y)))
    errs_m, errs_i = [], []
    for t, g in w.groupby("t"):
        if len(g) < 5:
            continue
        for _, r in g[g.ws >= 1].iterrows():
            o = g[g.sid != r.sid]
            um, vm = o.u.mean(), o.v.mean()
            dd = np.array([np.hypot(pos[s][0] - pos[r.sid][0], pos[s][1] - pos[r.sid][1]) for s in o.sid])
            wt = 1 / np.maximum(dd, 500) ** 2
            ui, vi = (wt * o.u).sum() / wt.sum(), (wt * o.v).sum() / wt.sum()
            obs = np.rad2deg(np.arctan2(r.u, r.v))
            errs_m.append(ang_err(obs, np.rad2deg(np.arctan2(um, vm))))
            errs_i.append(ang_err(obs, np.rad2deg(np.arctan2(ui, vi))))
    wind = {"mean": round(float(np.median(errs_m)), 1), "idw": round(float(np.median(errs_i)), 1),
            "horas_estacion": len(errs_m), "estaciones_viento": int(w.sid.nunique())}
    return stats, wind


def main():
    st = gpd.read_file(INT / "estaciones.gpkg")
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from config import LAT, LON
    st = st[st.nox.astype(bool) & st.longitud.between(*LON) & st.latitud.between(*LAT)]
    # estaciones de NOₓ que entran en la inversión de nov–dic 2023 (caché del gemelo, si existe)
    cache = INT / "benchmark/cache/nom_admin_grupos.npz"
    if cache.exists():
        d = np.load(cache, allow_pickle=True)
        used = set(d["sid"][~d["est"]])
        st = st[st.cve_estac.isin(used) | st.id_station.isin(used)] if "id_station" in st else st[st.cve_estac.isin(used)]
    cdmx_st = station_stats(st.longitud.astype(float), st.latitud.astype(float), 32614, 3260)
    aq = pd.read_parquet(INT / "la/aqs_nonox.parquet")
    sites = aq.groupby(["County Code", "Site Num"])[["Latitude", "Longitude"]].first()
    la_st = station_stats(sites.Longitude, sites.Latitude, 32611, 3080)
    bog_st, bog_wind = bogota()
    cdmx_wind = wind_loo_file(INT / "wind_loo.csv", ["mean", "idw"])
    la_wind = wind_loo_file(INT / "la/wind_loo.csv", ["mean", "idw", "hrrr"])
    fichas = {
        "CDMX": {
            "periodo": "nov–dic 2023 (tardes 12–17 h)",
            "estaciones_nox": cdmx_st | {"fuente": "SIMAT (RAMA); más estaciones solo de NO₂ como extras"},
            "satelite": {"tipo": "TEMPO horario", "pixeles_por_escaneo_mediana": round(78227 / 366),
                         "escaneos": 366, "nota": "píxeles usados en la inversión / horas (la_real_cdmx_domain.json)"},
            "viento": {"fuente": "REDMET + METAR; modelo usa el vector medio del dominio", "error_direccion_loo_grados": cdmx_wind,
                       "era5_grados": 55, "modelo_de_alta_resolucion": "no (WRF de SEDEMA no disponible)"},
            "trafico": {"fuente": "Infovial", "año": 2017, "resolucion": "26 vialidades primarias, horario por clase de vehículo"},
            "capa_limite": "ERA5 (Open-Meteo) + MERRA-2 corregido",
            "inventario": "SEDEMA 2018 por entidad (sin NOₓ municipal); EDGAR v8.1 0.1°",
        },
        "Los Ángeles": {
            "periodo": "nov–dic 2023 (tardes 12–17 h, hora civil)",
            "estaciones_nox": la_st | {"fuente": "EPA AQS"},
            "satelite": {"tipo": "TEMPO horario", "pixeles_por_escaneo_mediana": round(50875 / 363),
                         "escaneos": 363, "nota": "píxeles totales / horas (otras_ciudades.md)"},
            "viento": {"fuente": "ASOS + AQS; HRRR 3 km", "error_direccion_loo_grados": la_wind},
            "trafico": {"fuente": "ninguna integrada (PeMS pendiente de cuenta; EMFAC en proceso)", "año": None, "resolucion": None},
            "capa_limite": "HRRR / ERA5",
            "inventario": "EDGAR v8.1 0.1° (CARB pendiente)",
        },
        "Bogotá": {
            "periodo": "nov–dic 2023 (muestra); Día sin carro 2015–2024",
            "estaciones_nox": bog_st | {"fuente": "RMCAB (SDA)", "nota": "dominio = zona urbana ~380 km² (bogota.md)"},
            "satelite": {"tipo": "ninguno horario (TROPOMI 1 pasada diaria, nublado; no integrado)", "pixeles_por_escaneo_mediana": 0},
            "viento": {"fuente": "RMCAB + METAR SKBO", "error_direccion_loo_grados": bog_wind},
            "trafico": {"fuente": "Secretaría de Movilidad", "año": "2019–2020", "resolucion": "conteos por punto (sin verificar)"},
            "capa_limite": "ERA5 (Open-Meteo)",
            "inventario": "SDA 2023 (resolución sin verificar); EDGAR v8.1 0.1°",
        },
    }
    (INT / "fichas_datos.json").write_text(json.dumps(fichas, ensure_ascii=False, indent=1))
    print(json.dumps(fichas, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
