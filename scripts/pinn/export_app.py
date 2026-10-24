"""Prepara los archivos que lee la app (app/app.py): capas del mapa y resultados precalculados.

Lee data/processed/pinn/resultados_*.json y normalizado_*.parquet (de invert.py), el estimador
normalizado de los domingos (data/interim/sunday_fix.json), las contingencias de 2024
(data/interim/contingencias_2024*, de scripts/contingencias_2024.py) y la validación 2020, y escribe en
data/processed/app/. La app no corre modelos.

Uso: .venv/bin/python scripts/pinn/export_app.py
"""
import json
import re
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import LAT, LON, UTM  # noqa: E402
import feasibility_linear as fl  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INT = ROOT / "data/interim"
PINN = ROOT / "data/processed/pinn"
APP = ROOT / "data/processed/app"


def regions(scheme=None):
    """Polígonos de las regiones viales: celdas de 1 km asignadas con feasibility_linear.assign_regions (la misma
    regla que load_inputs) y disueltas por región. scheme: esquema de regiones (por defecto el estándar)."""
    if scheme:
        fl.REGION_SCHEME = scheme
    x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    if fl.REGION_SCHEME.startswith("admin"):
        # Grupos de alcaldías y municipios: se dibujan con sus límites reales, recortados al dominio (el modelo usa
        # las celdas de 1 km; las de los bordes van al grupo más cercano).
        z = gpd.read_file(fl.ADMIN_GPKG, layer=fl.REGION_SCHEME).to_crs(UTM).reset_index(drop=True)
        z["geometry"] = z.geometry.intersection(box(x0, y0, x1, y1))
        z["region"], z["nombre"] = z.index, z.grupo
        cols = ["region", "nombre", "geometry"] + [c for c in ("entidad", "municipios") if c in z]
        return z[cols].to_crs(4326)
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    ix, iy = np.meshgrid(np.arange(nx), np.arange(ny))
    cells = pd.DataFrame({"ix": ix.ravel(), "iy": iy.ravel()})
    cells["x"], cells["y"] = x0 + 500 + 1000 * cells.ix, y0 + 500 + 1000 * cells.iy
    cells["region"] = fl.assign_regions(cells, nx, ny)
    g = gpd.GeoDataFrame(cells, geometry=[box(x - 500, y - 500, x + 500, y + 500) for x, y in zip(cells.x, cells.y)], crs=UTM)
    g = g.dissolve("region").reset_index()[["region", "geometry"]]
    g["geometry"] = g.geometry.clip(box(x0, y0, x1, y1))
    g["nombre"] = [fl.region_names()[r] for r in g.region]
    if "Ecatepec" in fl.region_names():
        # Para el mapa, Ecatepec se dibuja con su límite municipal (el modelo usa las celdas de 1 km cuyo centro
        # cae dentro); los bloques del 3×3 se recortan con ese límite para que no queden huecos ni traslapes.
        mun = gpd.read_file(INT / "municipios.gpkg").to_crs(UTM)
        eca = mun[mun.NOMGEO.str.contains("Ecatepec")].geometry.union_all().intersection(box(x0, y0, x1, y1))
        k = fl.region_names().index("Ecatepec")
        base = g.set_index("region").geometry.copy()
        blocks = (cells.ix * 3 // nx) + 3 * (cells.iy * 3 // ny)
        cb = gpd.GeoSeries([box(x - 500, y - 500, x + 500, y + 500) for x, y in zip(cells.x, cells.y)], crs=UTM)
        for r in base.index:
            base[r] = eca if r == k else cb[(blocks == r).values].union_all().intersection(box(x0, y0, x1, y1)).difference(eca)
        g["geometry"] = g.region.map(base).values
    return g.to_crs(4326)


def contingencias():
    """Serie diaria (observado, modelo con emisión fija, índice) con los días de contingencia marcados."""
    import contingencias_2024 as c24
    d = c24.daily(pd.read_parquet(INT / "contingencias_2024_hourly.parquet"))
    cont = pd.to_datetime(pd.read_csv(ROOT / "data/raw/contingencias/contingencias_ozono_2024.csv").fecha)
    out = pd.DataFrame({"dia": d.index, "obs_ppb": d.obs / d.horas, "modelo_ppb": d.modelo / d.horas,
                        "contingencia": d.index.isin(cont)})
    out["indice"] = out.obs_ppb / out.modelo_ppb
    out.to_parquet(APP / "contingencias_2024_diario.parquet")
    return json.load(open(INT / "contingencias_2024.json")), json.load(open(INT / "contingencias_2024_shift1.json"))


def main():
    APP.mkdir(parents=True, exist_ok=True)
    scheme = None
    st = gpd.read_file(INT / "estaciones.gpkg").to_crs(4326)
    st[["cve_estac", "geometry"] + [c for c in ("nom_estac",) if c in st]].to_file(APP / "estaciones.geojson", driver="GeoJSON")
    rd = gpd.read_file(INT / "roads.gpkg")
    rd = rd[rd.highway.isin(["motorway", "trunk", "primary"])].to_crs(UTM)
    rd["geometry"] = rd.simplify(80)
    rd[["highway", "geometry"]].to_crs(4326).to_file(APP / "carreteras.geojson", driver="GeoJSON")
    cand = gpd.read_file(INT / "point_candidates.gpkg").to_crs(4326)
    cand[["nombre", "tipo", "geometry"]].to_file(APP / "candidatos.geojson", driver="GeoJSON")

    periods = {}
    for f in sorted(PINN.glob("resultados_*.json")):
        if not re.fullmatch(r"resultados_\d{4}-\d\d-\d\d_\d{4}-\d\d-\d\d\.json", f.name):
            continue  # variantes con sufijo (_tp1, _so8km): solo para comparar, la app usa el estándar
        r = json.load(open(f))
        key = f"{r['periodo'][0]}_{r['periodo'][1]}"
        periods[key] = r
        scheme = r.get("esquema_regiones", "3x3")
        for kind in ("lineal", "pinn"):
            src = PINN / f"normalizado_{kind}_{key}.parquet"
            if src.exists():
                shutil.copy(src, APP / src.name)
    val = json.load(open(INT / "val2020_ratio.json")) if (INT / "val2020_ratio.json").exists() else {}
    kv = PINN / "kernel_validation.json"
    sf = INT / "sunday_fix.json"
    cont, cont1 = contingencias() if (INT / "contingencias_2024.json").exists() else ({}, {})
    regions(scheme).to_file(APP / "regiones.geojson", driver="GeoJSON")  # mismo esquema que los resultados
    meta = {"regiones": fl.region_names(), "tipos_dia": ["hábil", "sábado", "domingo/festivo"],
            "validacion_2020": val, "nucleo": json.load(open(kv)) if kv.exists() else {},
            "domingo_normalizado": json.load(open(sf))["normalizado"] if sf.exists() else {},
            "infovial_dia_completo": {"sabado": [0.84, 0.89], "domingo": [0.65, 0.73]},
            "contingencias_2024": cont, "contingencias_2024_dia_siguiente": cont1}
    json.dump({"periodos": periods, "meta": meta}, open(APP / "resultados.json", "w"), ensure_ascii=False, default=float)
    print("listo:", sorted(p.name for p in APP.iterdir()))


if __name__ == "__main__":
    main()
