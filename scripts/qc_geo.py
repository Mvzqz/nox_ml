"""P1/P2: control de calidad de catálogo de estaciones, límites INEGI y red vial OSM.

Uso: .venv/bin/python scripts/qc_geo.py
Salida: data/interim/{roads,municipios,estaciones}.gpkg y reports/qc_geo.md
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/interim"
REP = ROOT / "reports"
UTM = "EPSG:32614"
from config import DOMAIN

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def check(ok, msg):
    say(f"- {'✅' if ok else '❌'} {msg}")


def main():
    say("# QC geoespacial\n")

    # ---------------- INEGI ----------------
    say("## Límites municipales (INEGI 2022)\n")
    cdmx = gpd.read_file(RAW / "inegi/cdmx_2022.json")
    edomex = gpd.read_file(RAW / "inegi/edomex_2022.json")
    check(len(cdmx) == 16, f"Alcaldías CDMX: {len(cdmx)}")
    check(cdmx.crs is not None and cdmx.crs.to_epsg() == 4326, f"CRS: {cdmx.crs}")
    mun = pd.concat([cdmx, edomex], ignore_index=True)
    mun = mun[mun.intersects(DOMAIN)]
    say(f"- ℹ️ Columnas: {list(mun.columns)}")
    say(f"- ℹ️ Municipios/alcaldías que tocan el dominio: {len(mun)}")
    mun.to_crs(UTM).to_file(OUT / "municipios.gpkg")

    # ---------------- Estaciones ----------------
    say("\n## Catálogo de estaciones\n")
    cat = pd.read_csv(RAW / "simat/cat_estacion.csv", skiprows=1, encoding="latin1")
    st = gpd.GeoDataFrame(cat, geometry=gpd.points_from_xy(cat.longitud, cat.latitud), crs=4326)
    st = st[st.within(DOMAIN)]
    used = pd.read_parquet(OUT / "simat_nox.parquet", columns=["id_station"]).id_station.unique()
    wind = pd.read_parquet(OUT / "simat_wind.parquet", columns=["id_station"]).id_station.unique()
    st["nox"] = st.cve_estac.isin(used)
    st["wind"] = st.cve_estac.isin(wind)
    st = st[st.nox | st.wind]
    say(f"- ℹ️ Estaciones con NOₓ en el dominio: {st.nox.sum()}; con viento: {st.wind.sum()}")
    alt_bad = st[~st.alt.between(2200, 3000)]
    check(alt_bad.empty, f"Altitud 2,200–3,000 m (fuera: {dict(zip(alt_bad.cve_estac, alt_bad.alt)) or 'ninguna'})")
    name_col = next(c for c in mun.columns if c.lower() in ("nomgeo", "nom_mun", "name", "nombre"))
    j = gpd.sjoin(st, mun[[name_col, "geometry"]], how="left", predicate="within")
    say(f"\n| Estación | Nombre | Cae en | NOₓ | Viento |")
    say("|---|---|---|---|---|")
    for _, r in j.sort_values("cve_estac").iterrows():
        say(f"| {r.cve_estac} | {r.nom_estac} | {r[name_col]} | {'✔' if r.nox else ''} | {'✔' if r.wind else ''} |")
    say("\n- ⚠️ Revisar a ojo: el nombre de la estación suele ser la colonia, no el municipio.")
    j.to_crs(UTM).to_file(OUT / "estaciones.gpkg")

    # separación media entre estaciones NOx (resolución efectiva de la red)
    s = st[st.nox].to_crs(UTM)
    nn = s.geometry.apply(lambda g: s.geometry[s.geometry != g].distance(g).min())
    say(f"- ℹ️ Distancia al vecino NOₓ más cercano: mediana {nn.median() / 1000:.1f} km, máx {nn.max() / 1000:.1f} km")

    # ---------------- OSM ----------------
    say("\n## Red vial (OSM vía Overpass)\n")
    osm = json.loads((RAW / "osm/roads_bbox.json").read_text())
    rows = [
        {"osm_id": e["id"], "highway": e["tags"]["highway"], "name": e["tags"].get("name", ""),
         "geometry": LineString([(p["lon"], p["lat"]) for p in e["geometry"]])}
        for e in osm["elements"] if e["type"] == "way" and len(e.get("geometry", [])) > 1
    ]
    roads = gpd.GeoDataFrame(rows, crs=4326).to_crs(UTM)
    roads["km"] = roads.length / 1000
    km = roads.groupby(roads.highway.str.replace("_link", "")).km.sum().round(0)
    say(f"- ℹ️ Snapshot OSM: {osm['osm3s']['timestamp_osm_base']}; vías: {len(roads):,}")
    for cls in ["motorway", "trunk", "primary", "secondary", "tertiary"]:
        check(km.get(cls, 0) > 0, f"Clase {cls}: {km.get(cls, 0):,.0f} km")
    for name in ["Periférico", "Circuito Interior", "Viaducto", "Insurgentes"]:
        n = roads[roads.name.str.contains(name, case=False)]
        check(n.km.sum() > 5, f"'{name}': {n.km.sum():.0f} km en {len(n)} tramos")
    dom_utm = gpd.GeoSeries([DOMAIN], crs=4326).to_crs(UTM).iloc[0]
    edge = roads[roads.crosses(dom_utm.exterior)]
    check(len(edge) > 0, f"Vías que cruzan el borde del dominio (sin recorte): {len(edge)}")
    roads.to_file(OUT / "roads.gpkg")

    (REP / "qc_geo.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
