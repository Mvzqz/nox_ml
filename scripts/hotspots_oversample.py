"""Mapa de puntos calientes: sobremuestreo de TEMPO NO₂ y contraste por fuente candidata.

1. Sobremuestreo: cada píxel válido (bandera = 0, nubes < 0.2) se reparte en su polígono
   (latitude_bounds / longitude_bounds, esquinas consecutivas) con 8×8 sub-puntos bilineales de igual
   peso; cada sub-punto suma al promedio de la celda de 0.005° (~0.5 km) donde cae. Equivale a un
   promedio ponderado por área de traslape. n_obs = píxeles distintos que tocan la celda.
2. Proxy vial: longitud de vía ponderada por clase (mismos pesos que feasibility_linear.py) en la misma
   malla, suavizada con una gaussiana de σ = 1.5 km (escala de un píxel TEMPO) para comparar con justicia.
   Ajuste lineal VCD ~ a + b·vial (+ gradiente lineal en lat/lon como alternativa) → mapa de residuo.
3. Contraste por candidata: media a ≤ 2 km frente al anillo de 4–8 km, para VCD, vialidad y residuo.
4. Prueba viento arriba / viento abajo por escaneo (viento medio REDMET de la hora, ≥ 1.5 m/s):
   VCD media de los píxeles a 2–8 km en el semicono viento abajo (±45°) menos viento arriba (±45°),
   comparada con la misma cantidad en 60 puntos de control dentro de la ciudad.

Uso: .venv/bin/python scripts/hotspots_oversample.py
Salida: data/interim/hotspots_grid.npz, data/interim/hotspots_candidates.csv
"""
import glob
from pathlib import Path

import geopandas as gpd
import netCDF4
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter

from config import BBOX, UTM

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
RES = 0.005
NSUB = 8
ROAD_WEIGHT = {"motorway": 3, "trunk": 3, "primary": 2, "secondary": 1.5, "tertiary": 1}
LON0, LAT0, LON1, LAT1 = BBOX
NX = int(round((LON1 - LON0) / RES))
NY = int(round((LAT1 - LAT0) / RES))
KX = 111.32 * np.cos(np.deg2rad(19.5))  # km por grado de longitud
PERIODS = {"nov–dic 2023": ("2023-11-01", "2024-01-01"), "feb–may 2024": ("2024-02-15", "2024-06-01")}


def oversample():
    acc = {p: [np.zeros(NX * NY), np.zeros(NX * NY), np.zeros(NX * NY)] for p in list(PERIODS) + ["todo"]}
    u = (np.arange(NSUB) + 0.5) / NSUB
    S, T = np.meshgrid(u, u)
    S, T = S.ravel(), T.ravel()
    w = np.stack([(1 - S) * (1 - T), S * (1 - T), S * T, (1 - S) * T], 1)  # (64, 4)
    n_files = 0
    for f in sorted(glob.glob(str(ROOT / "data/raw/tempo/TEMPO_NO2_L2_V04_*_zmvm.nc"))):
        t = pd.Timestamp(Path(f).name.split("_")[4][:15].replace("T", " "))
        per = [p for p, (a, b) in PERIODS.items() if pd.Timestamp(a) <= t < pd.Timestamp(b)]
        if not per:
            continue
        with netCDF4.Dataset(f) as ds:
            vcd = ds["product/vertical_column_troposphere"][:].filled(np.nan).ravel()
            qf = ds["product/main_data_quality_flag"][:].filled(255).ravel()
            cf = ds["support_data/eff_cloud_fraction"][:].filled(np.nan).ravel()
            lab = ds["geolocation/latitude_bounds"][:].filled(np.nan).reshape(-1, 4)
            lob = ds["geolocation/longitude_bounds"][:].filled(np.nan).reshape(-1, 4)
        ok = (qf == 0) & (cf < 0.2) & np.isfinite(vcd) & np.isfinite(lab).all(1) & np.isfinite(lob).all(1)
        if not ok.any():
            continue
        n_files += 1
        vcd, lab, lob = vcd[ok], lab[ok], lob[ok]
        plat = lab @ w.T  # (npix, 64)
        plon = lob @ w.T
        ix = np.floor((plon - LON0) / RES).astype(int)
        iy = np.floor((plat - LAT0) / RES).astype(int)
        inside = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
        cell = np.where(inside, iy * NX + ix, -1)
        vals = np.repeat(vcd[:, None], NSUB * NSUB, 1)
        sel = cell >= 0
        c, v = cell[sel], vals[sel]
        pix = np.repeat(np.arange(len(vcd))[:, None], NSUB * NSUB, 1)[sel]
        uniq = np.unique(pix.astype(np.int64) * (NX * NY) + c) % (NX * NY)
        for p in per + ["todo"]:
            acc[p][0] += np.bincount(c, weights=v, minlength=NX * NY)
            acc[p][1] += np.bincount(c, minlength=NX * NY)
            acc[p][2] += np.bincount(uniq, minlength=NX * NY)
    out = {}
    for p, (sv, sw, n) in acc.items():
        with np.errstate(invalid="ignore", divide="ignore"):
            out[p] = (np.where(sw > 0, sv / sw, np.nan).reshape(NY, NX), n.reshape(NY, NX))
    return out, n_files


def road_grid():
    r = gpd.read_file(INT / "roads.gpkg").to_crs(4326)
    r["w"] = r.highway.str.replace("_link", "").map(ROAD_WEIGHT).fillna(1)
    ru = r.to_crs(UTM)
    g = np.zeros(NX * NY)
    for geom, geom_utm, wt in zip(r.geometry, ru.geometry, r.w):
        n = max(int(geom_utm.length // 100), 1)
        d = np.linspace(0, 1, n, endpoint=False) + 0.5 / n
        pts = [geom.interpolate(x, normalized=True) for x in d]
        lon = np.array([p.x for p in pts])
        lat = np.array([p.y for p in pts])
        ix = np.floor((lon - LON0) / RES).astype(int)
        iy = np.floor((lat - LAT0) / RES).astype(int)
        ok = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
        np.add.at(g, iy[ok] * NX + ix[ok], wt * geom_utm.length / n / 1000)  # km ponderados
    g = g.reshape(NY, NX)
    sig_y = 1.5 / (RES * 111.32)
    sig_x = 1.5 / (RES * KX)
    return g, gaussian_filter(g, (sig_y, sig_x), mode="constant")


def disk_ring(lon, lat):
    lons = LON0 + (np.arange(NX) + 0.5) * RES
    lats = LAT0 + (np.arange(NY) + 0.5) * RES
    LO, LA = np.meshgrid(lons, lats)
    d = np.hypot((LO - lon) * KX, (LA - lat) * 111.32)
    return d <= 2, (d >= 4) & (d <= 8)


def updown(cands, n_ctrl=60):
    """Diferencia viento abajo − viento arriba por escaneo, para candidatas y puntos de control."""
    px = pd.concat([pd.read_parquet(INT / f"tempo_pixels_{a}_{b}.parquet")
                    for a, b in (("2023-11-01", "2023-12-31"), ("2024-02-15", "2024-05-31"))])
    px = px[px.valid]
    w = pd.read_parquet(INT / "simat_wind.parquet").dropna(subset=["WSP", "WDR"])
    st = gpd.read_file(INT / "estaciones.gpkg").cve_estac
    w = w[w.id_station.isin(st)]
    r = np.deg2rad(w.WDR)
    w["u"], w["v"] = -w.WSP * np.sin(r), -w.WSP * np.cos(r)
    wind = w.groupby(w.utc - pd.Timedelta(hours=1))[["u", "v"]].mean()
    px["h"] = px.utc.dt.floor("h")
    px = px.join(wind, on="h", how="inner")
    px = px[np.hypot(px.u, px.v) >= 1.5]
    rng = np.random.default_rng(3)
    # control: puntos aleatorios en la ciudad (zona con VCD media alta, sin candidatas a < 3 km)
    ctrl = []
    while len(ctrl) < n_ctrl:
        lo, la = rng.uniform(-99.25, -99.0), rng.uniform(19.3, 19.6)
        if all(np.hypot((lo - c.lon) * KX, (la - c.lat) * 111.32) > 3 for c in cands.itertuples()):
            ctrl.append((lo, la))

    def stat(lon, lat):
        dx = (px.lon.values - lon) * KX
        dy = (px.lat.values - lat) * 111.32
        d = np.hypot(dx, dy)
        sp = np.hypot(px.u.values, px.v.values)
        cosang = (dx * px.u.values + dy * px.v.values) / (np.maximum(d, 1e-6) * sp)
        ring = (d >= 2) & (d <= 8)
        down = ring & (cosang >= np.cos(np.deg2rad(45)))
        up = ring & (cosang <= -np.cos(np.deg2rad(45)))
        g = pd.DataFrame({"gr": px.granule.values, "down": np.where(down, px.vcd.values, np.nan),
                          "up": np.where(up, px.vcd.values, np.nan)})
        m = g.groupby("gr").agg(down=("down", "mean"), up=("up", "mean")).dropna()
        return (m.down - m.up).mean(), len(m)

    c_vals = np.array([stat(lo, la)[0] for lo, la in ctrl])
    res = []
    for c in cands.itertuples():
        dv, n = stat(c.lon, c.lat)
        res.append((dv, n, (dv - c_vals.mean()) / c_vals.std()))
    return res, c_vals


def main():
    maps, n_files = oversample()
    raw, road = road_grid()
    mean, nobs = maps["todo"]
    ok = np.isfinite(mean) & (nobs >= 50)
    X1 = np.c_[np.ones(ok.sum()), road[ok]]
    b1, *_ = np.linalg.lstsq(X1, mean[ok], rcond=None)
    r2_road = 1 - ((mean[ok] - X1 @ b1) ** 2).sum() / ((mean[ok] - mean[ok].mean()) ** 2).sum()
    lons = LON0 + (np.arange(NX) + 0.5) * RES
    lats = LAT0 + (np.arange(NY) + 0.5) * RES
    LO, LA = np.meshgrid(lons, lats)
    X2 = np.c_[X1, LO[ok] - LO[ok].mean(), LA[ok] - LA[ok].mean()]
    b2, *_ = np.linalg.lstsq(X2, mean[ok], rcond=None)
    r2_both = 1 - ((mean[ok] - X2 @ b2) ** 2).sum() / ((mean[ok] - mean[ok].mean()) ** 2).sum()
    resid = np.full_like(mean, np.nan)
    resid[ok] = mean[ok] - X2 @ b2

    cand = gpd.read_file(INT / "point_candidates.gpkg").to_crs(4326)
    cand["lon"], cand["lat"] = cand.geometry.x, cand.geometry.y
    rows = []
    for c in cand.itertuples():
        dsk, rng_ = disk_ring(c.lon, c.lat)
        dsk, rng_ = dsk & ok, rng_ & ok
        rows.append({
            "nombre": c.nombre, "tipo": c.tipo, "lon": c.lon, "lat": c.lat,
            "vcd_2km": np.nanmean(mean[dsk]), "vcd_anillo": np.nanmean(mean[rng_]),
            "vial_2km": np.nanmean(road[dsk]), "vial_anillo": np.nanmean(road[rng_]),
            "residuo_2km": np.nanmean(resid[dsk]), "nobs_2km": np.nanmedian(nobs[dsk]),
        })
    df = pd.DataFrame(rows)
    df["cociente_vcd"] = df.vcd_2km / df.vcd_anillo
    df["cociente_vial"] = df.vial_2km / df.vial_anillo
    ud, c_vals = updown(cand)
    df["abajo_menos_arriba"] = [u[0] for u in ud]
    df["escaneos_ud"] = [u[1] for u in ud]
    df["z_ud"] = [u[2] for u in ud]
    df.to_csv(INT / "hotspots_candidates.csv", index=False)
    np.savez_compressed(INT / "hotspots_grid.npz",
                        mean=mean, nobs=nobs, resid=resid, road=road, road_raw=raw,
                        mean_p1=maps["nov–dic 2023"][0], mean_p2=maps["feb–may 2024"][0],
                        nobs_p1=maps["nov–dic 2023"][1], nobs_p2=maps["feb–may 2024"][1],
                        bbox=np.array(BBOX), res=RES)
    print(f"archivos con píxeles válidos: {n_files}; celdas: {NX}×{NY}; n_obs mediana {np.nanmedian(nobs[ok]):.0f}")
    print(f"R² VCD ~ vialidad: {r2_road:.2f}; con gradiente lat/lon: {r2_both:.2f}; coef {b2}")
    print(f"control abajo−arriba: media {c_vals.mean():.2e}, sd {c_vals.std():.2e}")
    pd.set_option("display.width", 220)
    print(df[["nombre", "vcd_2km", "cociente_vcd", "cociente_vial", "residuo_2km", "abajo_menos_arriba", "z_ud", "escaneos_ud"]]
          .round(3).to_string())


if __name__ == "__main__":
    main()
