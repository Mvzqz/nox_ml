"""¿Qué tan bien ve la red de estaciones cada celda del dominio?

Para cada celda de 1 km y cada hora 12–17 h: la celda se considera "observada" si alguna
estación NOₓ con dato válido está viento abajo, a ≤ MAXD km y dentro de un cono de ±HALF°.
Uso: .venv/bin/python scripts/observability.py 2023-11-01 2023-12-31
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from config import LAT, LON

ROOT = Path(__file__).resolve().parents[1]
MAXD, HALF = 10_000, 30
start, end = sys.argv[1:3]

st = gpd.read_file(ROOT / "data/interim/estaciones.gpkg").set_index("cve_estac")
nox = pd.read_parquet(ROOT / "data/interim/simat_nox.parquet")
nox = nox[nox.local.between(start, end) & nox.hour.between(12, 17) & nox.NOX.notna()]
nox = nox[nox.id_station.isin(st.index)]
w = pd.read_parquet(ROOT / "data/interim/simat_wind.parquet")
w = w[w.local.between(start, end) & w.local.dt.hour.between(12, 17)].dropna(subset=["WSP", "WDR"])
r = np.deg2rad(w.WDR)
w["u"], w["v"] = -w.WSP * np.sin(r), -w.WSP * np.cos(r)
wm = w.groupby("local")[["u", "v"]].mean()

b = st.total_bounds
x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(st.crs).iloc[0].coords[0]
x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(st.crs).iloc[0].coords[0]
gx, gy = np.meshgrid(np.arange(x0, x1, 1000) + 500, np.arange(y0, y1, 1000) + 500)
seen = np.zeros(gx.shape)
hours = 0
for t, g in nox.groupby("local"):
    if t not in wm.index:
        continue
    u, v = wm.loc[t]
    if np.hypot(u, v) < 0.5:
        continue
    hours += 1
    flow = np.arctan2(v, u)  # hacia dónde va el aire
    hit = np.zeros(gx.shape, bool)
    for s in st.loc[g.id_station.unique()].geometry:
        dx, dy = s.x - gx, s.y - gy  # vector celda -> estación
        d = np.hypot(dx, dy)
        ang = np.abs((np.arctan2(dy, dx) - flow + np.pi) % (2 * np.pi) - np.pi)
        hit |= (d <= MAXD) & (ang <= np.deg2rad(HALF))
    seen += hit
frac = seen / hours
n_st = nox.groupby("local").id_station.nunique()
print(f"Periodo {start}–{end}: {hours} horas con viento definido; estaciones válidas por hora: mediana {n_st.median():.0f}")
print(f"Celdas (de {frac.size}) vistas ≥ 20 % de las horas: {(frac >= .2).mean():.0%}; ≥ 5 %: {(frac >= .05).mean():.0%}; nunca: {(frac == 0).mean():.0%}")
# por zona: cuadrantes de 23 km
ny, nx = frac.shape
for name, sl in {"NO": (slice(ny // 2, ny), slice(0, nx // 2)), "NE": (slice(ny // 2, ny), slice(nx // 2, nx)),
                 "SO": (slice(0, ny // 2), slice(0, nx // 2)), "SE": (slice(0, ny // 2), slice(nx // 2, nx))}.items():
    print(f"  cuadrante {name}: mediana {np.median(frac[sl]):.0%} de horas observada")
# leave-out: impacto de perder estaciones (retención 20 %)
np.save(ROOT / "data/interim/observability.npy", frac)
