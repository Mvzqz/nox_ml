"""Cobertura combinada: estaciones viento abajo (observability.py) + píxeles TEMPO válidos.

Una celda de 1 km está "vista por TEMPO" en una hora si el píxel válido más cercano está a
≤ PIX_KM (≈ medio píxel). Requiere haber corrido qc_tempo.py y observability.py para el periodo.
Uso: .venv/bin/python scripts/observability_tempo.py 2023-11-01 2023-12-31
"""
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from config import LAT, LON

ROOT = Path(__file__).resolve().parents[1]
PIX_KM = 3.0
start, end = sys.argv[1:3]

subprocess.run([sys.executable, str(ROOT / "scripts/observability.py"), start, end], check=True, capture_output=True)
f_st = np.load(ROOT / "data/interim/observability.npy")

px = pd.read_parquet(ROOT / f"data/interim/tempo_pixels_{start}_{end}.parquet")
px = px[px.valid]
cand = gpd.read_file(ROOT / "data/interim/point_candidates.gpkg")
utm = cand.crs
x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(utm).iloc[0].coords[0]
ny, nx = f_st.shape
gx, gy = np.meshgrid(x0 + 500 + 1000 * np.arange(nx), y0 + 500 + 1000 * np.arange(ny))
cells = np.c_[gx.ravel(), gy.ravel()]

pts = gpd.GeoSeries.from_xy(px.lon, px.lat, crs=4326).to_crs(utm)
px = px.assign(x=pts.x.values, y=pts.y.values, hour=px.utc.dt.floor("h"))
hours = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
hours = hours[(hours.hour >= 18)]  # 12–17 h local
seen = np.zeros(cells.shape[0])
for h, g in px.groupby("hour"):
    d, _ = cKDTree(g[["x", "y"]].values).query(cells)
    seen += d <= PIX_KM * 1000
f_tp = (seen / len(hours)).reshape(f_st.shape)


def at(arr, geom):
    return arr[int((geom.y - y0) // 1000), int((geom.x - x0) // 1000)]


lines = [f"# Cobertura estaciones + TEMPO ({start} a {end})\n",
         f"- Horas 12–17 h en el periodo: {len(hours)}; horas con algún píxel TEMPO válido: {px.hour.nunique()}",
         f"- Celdas vistas ≥ 20 % de las horas — estaciones: {(f_st >= .2).mean():.0%}; TEMPO: {(f_tp >= .2).mean():.0%}; "
         f"alguna de las dos: {(np.maximum(f_st, f_tp) >= .2).mean():.0%}",
         f"- Celdas nunca vistas — estaciones: {(f_st == 0).mean():.0%}; TEMPO: {(f_tp == 0).mean():.0%}\n",
         "| # | Candidata | Estaciones | TEMPO |", "|---|---|---|---|"]
for i, r in cand.iterrows():
    lines.append(f"| {i + 1} | {r.nombre} | {at(f_st, r.geometry):.0%} | {at(f_tp, r.geometry):.0%} |")
np.save(ROOT / "data/interim/observability_tempo.npy", f_tp)
(ROOT / f"reports/observability_{start}_{end}.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
