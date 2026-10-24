"""P2: fuentes puntuales candidatas con intensidad a priori.

Combina centrales eléctricas (WRI Global Power Plant Database), aeropuertos (OSM) y
establecimientos manufactureros del DENUE. Cada subsector SCIAN recibe su % de NOₓ de la
Tabla 5 del inventario 2018 y lo reparte entre sus establecimientos por personal ocupado.
Luego agrega a celdas de 2 km y conserva las más intensas como candidatas.

Uso: .venv/bin/python scripts/point_candidates.py
Salida: data/interim/point_candidates.{gpkg,csv} y reports/point_candidates.md
"""
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/interim"
UTM = "EPSG:32614"
from config import DOMAIN
ZMVM_APPROX = box(-99.5, 19.0, -98.6, 19.95)  # excluye Toluca y Tula (fuera de la ZMVM)
NOX_TOTAL = 144_598  # t/año, inventario 2018
CELL = 2000
TOP_N = 12

# % del NOₓ total de la ZMVM por subsector (Tabla 5, inventario 2018)
SCIAN_SHARE = {
    "311": 0.24, "312": 0.04, "313": 0.16, "314": 0.16, "315": 0.12, "321": 0.01, "322": 0.67,
    "324": 0.02, "325": 0.42, "326": 0.37, "327": 1.50, "331": 0.17, "332": 0.25, "336": 0.23,
    "337": 0.01, "339": 0.05,
}
SCIAN_NAME = {
    "311": "alimentaria", "312": "bebidas", "313": "textil", "314": "textil", "315": "prendas",
    "321": "madera", "322": "papel", "324": "petróleo", "325": "química", "326": "plástico/hule",
    "327": "minerales no metálicos", "331": "metálicas básicas", "332": "productos metálicos",
    "336": "equipo de transporte", "337": "muebles", "339": "otras",
}
GEN_SHARE = 2.0  # generación eléctrica, % del NOₓ total
PER_OCU_MID = {
    "0 a 5 personas": 3, "6 a 10 personas": 8, "11 a 30 personas": 20, "31 a 50 personas": 40,
    "51 a 100 personas": 75, "101 a 250 personas": 175, "251 y más personas": 400,
}

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load_denue():
    cols = ["nom_estab", "raz_social", "codigo_act", "nombre_act", "per_ocu", "municipio", "latitud", "longitud"]
    frames = []
    for z in sorted((RAW / "denue").glob("denue_*_csv.zip")):
        with zipfile.ZipFile(z) as zf:
            name = next(n for n in zf.namelist() if n.startswith("conjunto_de_datos/") and n.endswith(".csv"))
            with zf.open(name) as f:
                df = pd.read_csv(f, encoding="latin1", usecols=cols, dtype={"codigo_act": str})
        frames.append(df[df.codigo_act.str[:2].isin(["31", "32", "33"])])
    df = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitud, df.latitud), crs=4326)


def main():
    say("# Fuentes puntuales candidatas\n")

    # --- industria (DENUE) ---
    d = load_denue()
    d = d[d.within(ZMVM_APPROX)].copy()
    d["scian3"] = d.codigo_act.str[:3]
    d = d[d.scian3.isin(SCIAN_SHARE)]
    # el inventario de fuentes puntuales cubre industria regulada; los micronegocios
    # (p. ej. tortillerías) están en fuentes de área
    d = d[d.per_ocu.isin(["51 a 100 personas", "101 a 250 personas", "251 y más personas"])]
    d["w"] = d.per_ocu.map(PER_OCU_MID).fillna(3)
    d["nox_t"] = d.scian3.map(SCIAN_SHARE) / 100 * NOX_TOTAL * d.w / d.groupby("scian3").w.transform("sum")
    say(f"- Establecimientos manufactureros en la ZMVM (aprox.): {len(d):,}; "
        f"NOₓ asignado: {d.nox_t.sum():,.0f} t/año ({d.nox_t.sum() / NOX_TOTAL:.1%})")
    d = d[d.within(DOMAIN)].to_crs(UTM)
    say(f"- Dentro del dominio: {len(d):,} establecimientos, {d.nox_t.sum():,.0f} t/año")

    x0, y0 = gpd.GeoSeries([DOMAIN], crs=4326).to_crs(UTM).total_bounds[:2]
    d["ix"] = ((d.geometry.x - x0) // CELL).astype(int)
    d["iy"] = ((d.geometry.y - y0) // CELL).astype(int)
    big = d[d.per_ocu.isin(["101 a 250 personas", "251 y más personas"])]
    cells = d.groupby(["ix", "iy"]).agg(
        nox_t=("nox_t", "sum"), n=("nox_t", "size"), municipio=("municipio", lambda s: s.mode().iat[0]),
        sub_top=("scian3", lambda s: d.loc[s.index].groupby("scian3").nox_t.sum().idxmax()),
    ).reset_index()
    cells["n_grandes"] = cells.apply(lambda r: ((big.ix == r.ix) & (big.iy == r.iy)).sum(), axis=1)
    cells = cells.sort_values("nox_t", ascending=False).head(TOP_N)
    # centro de masa (ponderado por NOₓ) de cada celda
    cm = d.assign(wx=d.geometry.x * d.nox_t, wy=d.geometry.y * d.nox_t).groupby(["ix", "iy"])[["wx", "wy", "nox_t"]].sum()
    cells = cells.join(cm[["wx", "wy"]], on=["ix", "iy"])
    cells["x"] = cells.wx / cells.join(cm.nox_t.rename("tot"), on=["ix", "iy"]).tot
    cells["y"] = cells.wy / cells.join(cm.nox_t.rename("tot"), on=["ix", "iy"]).tot
    ind = gpd.GeoDataFrame({
        "tipo": "industria",
        "nombre": [f"Industria {r.municipio} ({SCIAN_NAME[r.sub_top]})" for r in cells.itertuples()],
        "nox_prior_t_anio": cells.nox_t.round(0).values,
        "detalle": [f"{r.n} establecimientos, {r.n_grandes} con > 100 empleados" for r in cells.itertuples()],
    }, geometry=gpd.points_from_xy(cells.x, cells.y), crs=UTM)

    # --- centrales eléctricas ---
    g = pd.read_csv(RAW / "powerplants/global_power_plant_database.csv", low_memory=False)
    g = g[(g.country == "MEX")]
    g = gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g.longitude, g.latitude), crs=4326)
    g = g[g.within(ZMVM_APPROX) & (g.primary_fuel.isin(["Gas", "Oil", "Coal"]))]
    g["nox_t"] = GEN_SHARE / 100 * NOX_TOTAL * g.capacity_mw / g.capacity_mw.sum()
    g = g[g.within(DOMAIN)]
    # Las dos unidades de Valle de México comparten coordenadas: se agrupan
    g = g.dissolve(by=["latitude", "longitude"], aggfunc={"name": " + ".join, "capacity_mw": "sum", "nox_t": "sum"}).reset_index()
    pw = gpd.GeoDataFrame({
        "tipo": "central eléctrica", "nombre": g.name, "nox_prior_t_anio": g.nox_t.round(0),
        "detalle": [f"{c:,.0f} MW, gas (WRI GPPD v1.3)" for c in g.capacity_mw],
    }, geometry=g.geometry.values, crs=4326).to_crs(UTM)

    # --- aeropuertos ---
    a = json.loads((RAW / "osm/aerodromes_bbox.json").read_text())
    airports = {
        "MEX": ("AICM (MEX)", "Polígono OSM; el inventario la incluye en 'operación de aeronaves' (intensidad por definir)"),
        "NLU": ("AIFA (NLU)", "Polígono OSM; abrió en 2022, no está en el inventario 2018 (intensidad por definir)"),
    }
    rows = {}
    for e in a["elements"]:
        code = e["tags"].get("iata")
        if e["type"] == "way" and code in airports and code not in rows:
            rows[code] = Polygon([(p["lon"], p["lat"]) for p in e["geometry"]]).centroid
    ap = gpd.GeoDataFrame({
        "tipo": "aeropuerto", "nombre": [airports[c][0] for c in rows], "nox_prior_t_anio": np.nan,
        "detalle": [airports[c][1] for c in rows],
    }, geometry=list(rows.values()), crs=4326).to_crs(UTM)

    cand = pd.concat([pw, ap, ind], ignore_index=True)
    cand = gpd.GeoDataFrame(cand, crs=UTM)
    ll = cand.to_crs(4326)
    cand["lat"], cand["lon"] = ll.geometry.y.round(4), ll.geometry.x.round(4)
    cand["cuadrante"] = np.where(cand.lat >= 19.46, "N", "S") + np.where(cand.lon >= -99.13, "E", "O")
    cand.to_file(OUT / "point_candidates.gpkg")
    cand.drop(columns="geometry").to_csv(OUT / "point_candidates.csv", index=False)

    say(f"\n| # | Tipo | Nombre | NOₓ a priori (t/año) | Cuadrante | Lat, Lon | Detalle |")
    say("|---|---|---|---|---|---|---|")
    for i, r in cand.iterrows():
        nox = "—" if pd.isna(r.nox_prior_t_anio) else f"{r.nox_prior_t_anio:,.0f}"
        say(f"| {i + 1} | {r.tipo} | {r.nombre} | {nox} | {r.cuadrante} | {r.lat}, {r.lon} | {r.detalle} |")
    say("\nLas intensidades son a priori (para inicializar y regularizar la PINN), no verdad de campo.")
    (ROOT / "reports/point_candidates.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
