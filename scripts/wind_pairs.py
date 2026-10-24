"""Diferencia de dirección del viento entre pares de estaciones según su distancia (nov–dic 2023, 12–17 h).

Si a distancia ~0 la diferencia ya es grande, esa parte es ruido local (sitio, obstáculos), no
variación real del flujo. Uso: .venv/bin/python scripts/wind_pairs.py
"""
import numpy as np
import pandas as pd

from feasibility_linear import load_inputs
from wind_loo import ang_err

_, _, _, _, _, _, st, _, _, wind, _, _ = load_inputs("2023-11-01", "2023-12-31", extras=True)
w = wind.attrs["by_station"]
w = w[w.id_station.isin(st.index)]
loc = w.h - pd.Timedelta(hours=6)
w = w[(loc >= "2023-11-01") & (loc < "2024-01-01") & loc.dt.hour.between(12, 17)]
w = w[np.hypot(w.u, w.v) >= 1]
p = w.merge(w, on="h", suffixes=("_a", "_b"))
p = p[p.id_station_a < p.id_station_b]
pos = {s: (st.loc[s].geometry.x, st.loc[s].geometry.y) for s in w.id_station.unique()}
p["d_km"] = [np.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]) / 1000 for a, b in zip(p.id_station_a, p.id_station_b)]
p["dir"] = ang_err(p.u_a, p.v_a, p.u_b, p.v_b)
bins = [0, 5, 10, 15, 20, 30, 60]
p["bin"] = pd.cut(p.d_km, bins)
print("| Distancia entre estaciones | Pares-hora | Diferencia de dirección mediana | p75 |")
print("|---|---|---|---|")
for b, g in p.groupby("bin", observed=True):
    print(f"| {b.left:.0f}–{b.right:.0f} km | {len(g):,} | {g.dir.median():.0f}° | {g.dir.quantile(.75):.0f}° |")
