"""LA: calidad de TEMPO (fracción de píxeles válidos y concordancia con NO₂ de estaciones AQS).

Mismos criterios que qc_tempo.py (bandera = 0, nubes < 0.2, pareo ≤ 3 km a la misma hora).
Uso: .venv/bin/python scripts/la_tempo_qc.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from la_common import INT, UTM
from la_twin import la_tempo_pixels

px = la_tempo_pixels()
no2 = pd.read_parquet(INT / "aqs_no2.parquet")
pos = no2.groupby("site")[["Latitude", "Longitude"]].first()
st = gpd.GeoSeries.from_xy(pos.Longitude, pos.Latitude, crs=4326, index=pos.index).to_crs(UTM)
pairs = []
for (g, h), gp in px.groupby(["utc", "h"]):
    obs = no2[no2.utc == h]
    for _, o in obs.iterrows():
        p = st[o.site]
        d = np.hypot(gp.x - p.x, gp.y - p.y)
        if d.min() <= 3000:
            pairs.append({"gran": g, "site": o.site, "no2": o["Sample Measurement"], "vcd": gp.vcd.values[d.argmin()]})
pairs = pd.DataFrame(pairs)
rg = pairs.groupby("gran").apply(lambda q: q.no2.corr(q.vcd) if len(q) >= 5 else np.nan).dropna()
sm = pairs.groupby("site")[["no2", "vcd"]].mean()
print(f"Píxeles válidos (tarde): {len(px):,} en {px.utc.nunique()} granulos; días con datos: {px.h.dt.date.nunique()}")
print(f"TEMPO vs NO₂ AQS: pares {len(pairs):,}, r = {pairs.no2.corr(pairs.vcd):.2f}; por granulo mediana r = {rg.median():.2f} "
      f"({len(rg)} granulos con ≥ 5 estaciones); promedios por estación r = {sm.no2.corr(sm.vcd):.2f} ({len(sm)} estaciones)")
