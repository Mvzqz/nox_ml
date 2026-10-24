"""Genera reports/puntos_calientes.html a partir de hotspots_oversample.py.

Uso: .venv/bin/python scripts/hotspots_report.py
"""
import base64
import io
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import box

matplotlib.use("Agg")
from matplotlib import colormaps  # noqa: E402
from matplotlib.image import imsave  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
z = np.load(INT / "hotspots_grid.npz")
LON0, LAT0, LON1, LAT1 = [float(v) for v in z["bbox"]]
COSLAT = np.cos(np.deg2rad((LAT0 + LAT1) / 2))
W = 760
H = int(round(W * (LAT1 - LAT0) / ((LON1 - LON0) * COSLAT)))
px = lambda lon: (lon - LON0) / (LON1 - LON0) * W  # noqa: E731
py = lambda lat: (LAT1 - lat) / (LAT1 - LAT0) * H  # noqa: E731

SHORT = ["Nonoalco (central)", "Central Valle de México (Acolman)", "AIFA", "AICM", "Naucalpan (minerales)",
         "Tlalnepantla (minerales)", "Ecatepec (minerales)", "Iztacalco (minerales)", "Tlalnepantla norte (minerales)",
         "Azcapotzalco (minerales)", "Iztapalapa (minerales)", "Gustavo A. Madero (minerales)", "Ecatepec (química)",
         "Ecatepec norte (minerales)", "Tlalnepantla (equipo de transporte)", "Cuautitlán Izcalli (papel)"]


def png(arr, cmap, vmin, vmax):
    a = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
    rgba = colormaps[cmap](a)
    rgba[..., 3] = np.where(np.isfinite(arr), 0.92, 0)
    buf = io.BytesIO()
    imsave(buf, rgba[::-1], format="png")  # fila 0 = sur → arriba = norte
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def stops(cmap, n=9):
    return [matplotlib.colors.to_hex(colormaps[cmap](i / (n - 1))) for i in range(n)]


mean, resid, road, nobs = z["mean"], z["resid"], z["road"], z["nobs"]
ok = np.isfinite(resid)
lo_m, hi_m = np.nanpercentile(mean[ok], [2, 99.5])
layers = {
    "media": dict(img=png(mean / 1e15, "YlOrBr", lo_m / 1e15, hi_m / 1e15), cmap=stops("YlOrBr"),
                  lo=lo_m / 1e15, hi=hi_m / 1e15, unit="NO₂ troposférico (10¹⁵ moléculas/cm²)",
                  label="Promedio, todos los escaneos"),
    "residuo": dict(img=png(resid / 1e15, "PuOr_r", -5, 5), cmap=stops("PuOr_r"), lo=-5, hi=5,
                    unit="NO₂ por encima (naranja) o por debajo (morado) de lo que explica la red vial (10¹⁵)",
                    label="Residuo sobre la vialidad"),
    "p1": dict(img=png(z["mean_p1"] / 1e15, "YlOrBr", lo_m / 1e15, hi_m / 1e15), cmap=stops("YlOrBr"),
               lo=lo_m / 1e15, hi=hi_m / 1e15, unit="NO₂ troposférico (10¹⁵ moléculas/cm²)", label="Nov–dic 2023"),
    "p2": dict(img=png(z["mean_p2"] / 1e15, "YlOrBr", lo_m / 1e15, hi_m / 1e15), cmap=stops("YlOrBr"),
               lo=lo_m / 1e15, hi=hi_m / 1e15, unit="NO₂ troposférico (10¹⁵ moléculas/cm²)", label="Feb–may 2024"),
    "vial": dict(img=png(road, "Greys", 0, float(np.nanpercentile(road[ok], 99.5))), cmap=stops("Greys"),
                 lo=0, hi=float(np.nanpercentile(road[ok], 99.5)), unit="Vialidad ponderada por clase, suavizada a escala de píxel (km por celda)",
                 label="Densidad vial"),
}

# límites municipales simplificados, recortados al dominio
mun = gpd.read_file(INT / "municipios.gpkg").to_crs(4326)
mun["geometry"] = mun.geometry.intersection(box(LON0, LAT0, LON1, LAT1)).simplify(0.0015)
paths = []
for g in mun.geometry:
    for poly in getattr(g, "geoms", [g]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        xy = np.array(poly.exterior.coords)
        paths.append("M" + "L".join(f"{px(x):.1f} {py(y):.1f}" for x, y in xy) + "Z")
mun_path = "".join(paths)

c = pd.read_csv(INT / "hotspots_candidates.csv")
urb = ok & (road > np.nanpercentile(road[ok], 50))
c["pct"] = [round((resid[urb] < v).mean() * 100) for v in c.residuo_2km]
c["corto"] = SHORT


def lectura(r):
    if r.pct >= 85 and r.z_ud >= 1.5:
        return "señal probable"
    if r.pct >= 85 or r.z_ud >= 1.5:
        return "indicio"
    return "no destaca"


c["lectura"] = c.apply(lectura, axis=1)
cands = [dict(n=i + 1, name=r.corto, x=round(px(r.lon), 1), y=round(py(r.lat), 1), pct=int(r.pct), z=round(r.z_ud, 2),
              lect=r.lectura) for i, r in c.iterrows()]

pill = {"señal probable": "ok", "indicio": "fix", "no destaca": "na"}
rows = "\n".join(
    f"<tr><td class=\"num\">{i + 1}</td><td>{r.corto}</td><td class=\"num\">{r.vcd_2km / 1e15:.1f}</td>"
    f"<td class=\"num\">{r.cociente_vcd:.2f}</td><td class=\"num\">{r.cociente_vial:.2f}</td>"
    f"<td class=\"num\">{r.residuo_2km / 1e15:+.1f}</td><td class=\"num\">{int(r.pct)}</td>"
    f"<td class=\"num\">{r.z_ud:+.1f}</td><td><span class=\"pill {pill[r.lectura]}\">{r.lectura}</span></td></tr>"
    for i, r in c.iterrows())

r2_road, r2_both = 0.71, 0.78  # impresos por hotspots_oversample.py
corr_p = float(np.corrcoef(z["mean_p1"][ok], z["mean_p2"][ok])[0, 1])
n_med = int(np.nanmedian(nobs[ok]))

html = (ROOT / "scripts/hotspots_template.html").read_text()
html = (html.replace("__W__", str(W)).replace("__H__", str(H)).replace("__HB__", str(H + 64))
        .replace("__MUN__", mun_path).replace("__ROWS__", rows)
        .replace("__LAYERS__", json.dumps(layers, ensure_ascii=False))
        .replace("__CANDS__", json.dumps(cands, ensure_ascii=False))
        .replace("__CORRP__", f"{corr_p:.2f}").replace("__NMED__", f"{n_med:,}"))
(ROOT / "reports/puntos_calientes.html").write_text(html)
print("ok", W, H, len(html) // 1024, "KB")
