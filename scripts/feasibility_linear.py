"""Prueba rápida de factibilidad: inversión lineal bayesiana con un modelo de pluma gaussiana.

La concentración es lineal en las emisiones, así que para cada hora de la tarde se calcula la
contribución de cada fuente (1 t/año) en cada estación y píxel TEMPO, y se resuelve por mínimos
cuadrados regularizados. Si este modelo no separa dos fuentes, la PINN (misma física, mismos
datos) tampoco podrá.

Estado: 16 fuentes puntuales candidatas + factor vial por región (3×3) + fondo por hora
(uno para estaciones y otro para TEMPO).

Produce, para varios escenarios:
  1. Identificabilidad: incertidumbre a posteriori y pares de fuentes confundidas.
  2. Experimento gemelo: se plantan emisiones (a priori × lognormal σ = 0.5), se simulan
     observaciones con ruido y se mide el error de recuperación.

Uso: .venv/bin/python scripts/feasibility_linear.py 2023-11-01 2023-12-31
"""
import json
import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from config import LAT, LON, UTM

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
rng = np.random.default_rng(42)

# --- física y unidades ---
T_PER_YR_TO_GS = 1e6 / 3.156e7          # 1 t/año en g/s
PPB_PER_GM3 = 8.314 * 293 / (77_000 * 46) * 1e9  # NOₓ como NO₂, ~2,240 m s.n.m.
MOLEC_CM2_PER_GM2 = 6.022e23 / 46 / 1e4
# Incertidumbre de dirección del viento en la dispersión. Estándar desde oct 2026: 30°, que representa el error
# medido de dirección (28–32°, reports/viento.md) y mejoró gemelo y datos reales (reports/mejoras.md,
# reports/base_sigma30.md). La configuración anterior (15°) sigue disponible con SIGMA_THETA_DEG=15 o
# --sigma-theta 15 en real_check_linear.py.
SIGMA_THETA_LEGACY = np.deg2rad(15)
SIGMA_THETA = np.deg2rad(float(os.environ.get("SIGMA_THETA_DEG", 30)))
U_MIN = float(os.environ.get("U_MIN", 2.0))  # piso de la rapidez de transporte (m/s). Estándar desde oct 2026: 2.0 (reports/estancamiento.md); 1.0 = anterior (U_MIN=1.0 o --u-min 1.0)
PBL_MAX = float(os.environ["PBL_MAX"]) if os.environ.get("PBL_MAX") else None  # opción: tope de la capa límite (m); no es estándar
U_TURB = 0.0   # variante: rapidez efectiva √(u² + U_TURB²) (viento turbulento/meandro) en vez de piso
U_POW = None   # variante: (U0, β) → rapidez efectiva U0^(1−β)·máx(u, 0.5)^β (concentración ∝ u^−β)


def speed(mag):
    """Rapidez efectiva de transporte (m/s) a partir de la rapidez del viento vectorial medio del dominio."""
    if U_POW is not None:
        u0, beta = U_POW
        return u0 ** (1 - beta) * np.maximum(mag, 0.5) ** beta
    if U_TURB > 0:
        return np.sqrt(np.asarray(mag) ** 2 + U_TURB ** 2)
    return np.maximum(mag, U_MIN)


X_MAX = 40_000
ROAD_WEIGHT = {"motorway": 3, "trunk": 3, "primary": 2, "secondary": 1.5, "tertiary": 1}
MOBILE_ZMVM = 124_115                    # t/año, inventario 2018
ROAD_PRIOR_TOTAL = 0.8 * MOBILE_ZMVM     # supuesto: ~80 % del NOₓ vehicular de la ZMVM cae en el dominio
AIRPORT_PRIOR = 500                      # t/año, supuesto (no hay valor por aeropuerto en el inventario)
N_TWIN = 50

# --- regiones viales ---
# "3x3": las 9 regiones originales de ~18 km (0 = SO … 8 = NE). Las variantes agregan una región 9 para que
# Ecatepec no comparta factor con el Centro (con puffs, SAG y XAL quedaban mal: reports/puffs_cdmx.md):
#   "3x3_ecatepec":      las celdas dentro del municipio de Ecatepec (INEGI) forman la región 9.
#   "3x3_centro_norte":  la región Centro se parte en dos por la mitad norte-sur; la mitad norte es la región 9.
# El esquema se elige con REGION_SCHEME (variable de entorno o fl.REGION_SCHEME antes de load_inputs);
# "3x3_ecatepec" fue el estándar de reports/config_final.md; desde reports/vida_quimica.md el estándar es "admin_grupos".
REGION_SCHEMES = {
    "3x3": ["SO", "S", "SE", "O", "Centro", "E", "NO", "N", "NE"],
    "3x3_ecatepec": ["SO", "S", "SE", "O", "Centro", "E", "NO", "N", "NE", "Ecatepec"],
    "3x3_centro_norte": ["SO", "S", "SE", "O", "Centro-S", "E", "NO", "N", "NE", "Centro-N"],
}
REGION_SCHEME = os.environ.get("REGION_SCHEME", "admin_grupos")  # estándar desde reports/zonas_admin.md
# Esquemas "admin*": grupos de alcaldías y municipios (scripts/zonas_admin_design.py, reports/zonas_admin.md). Los
# polígonos están en data/interim/zonas_admin.gpkg, una capa por esquema; el orden de las filas es el de las regiones.
# Las celdas fuera de los polígonos (bordes del dominio) van al grupo más cercano.
ADMIN_GPKG = INT / "zonas_admin.gpkg"


def region_names():
    if REGION_SCHEME.startswith("admin"):
        return gpd.read_file(ADMIN_GPKG, layer=REGION_SCHEME).grupo.tolist()
    return REGION_SCHEMES[REGION_SCHEME]


def n_reg(cells=None):
    """Número de regiones viales: el de unas celdas ya construidas (attrs de load_inputs; 9 si no lo traen, p. ej.
    las de LA) o, sin celdas, el de REGION_SCHEME."""
    if cells is not None:
        return int(cells.attrs.get("n_reg", 9))
    return len(region_names())


def assign_regions(cells, nx, ny):
    """Región vial de cada celda de 1 km (columnas ix, iy, x, y) según REGION_SCHEME."""
    if REGION_SCHEME.startswith("admin"):
        z = gpd.read_file(ADMIN_GPKG, layer=REGION_SCHEME).to_crs(UTM).reset_index(drop=True)
        pts = gpd.GeoDataFrame(geometry=gpd.GeoSeries.from_xy(cells.x, cells.y, crs=UTM), index=cells.index)
        j = gpd.sjoin_nearest(pts, z[["geometry"]], how="left")
        return j[~j.index.duplicated()].index_right.reindex(cells.index).astype(int)
    reg = (cells.ix * 3 // nx) + 3 * (cells.iy * 3 // ny)
    if REGION_SCHEME == "3x3_ecatepec":
        mun = gpd.read_file(INT / "municipios.gpkg").to_crs(UTM)
        eca = mun[mun.NOMGEO.str.contains("Ecatepec")].geometry.union_all()
        inside = gpd.GeoSeries.from_xy(cells.x, cells.y, crs=UTM).within(eca).values
        reg = reg.where(~inside, 9)
    elif REGION_SCHEME == "3x3_centro_norte":
        mid = ny + ny // 2  # iy*3 en [ny, 2ny) es la fila central; la mitad norte empieza en 1.5 ny
        reg = reg.where(~((reg == 4) & (cells.iy * 3 >= mid)), 9)
    return reg.astype(int)


def plume(xs, ys, xr, yr, u, v, pbl, extra_sy=0.0, x_max=X_MAX):
    """Contribución de fuentes (xs, ys) en receptores (xr, yr) por 1 g/s.

    Devuelve (concentración a nivel de suelo en g/m³, columna en g/m²), con forma (receptores, fuentes).
    Pluma gaussiana de fuente a nivel de suelo, Briggs urbano clase B, mezcla limitada por la capa límite.
    """
    # u, v: escalares (un viento para todo el dominio) o matrices (receptores, fuentes) por par
    mag = np.hypot(u, v)
    sp = speed(mag)
    ex, ey = u / np.maximum(mag, 1e-6), v / np.maximum(mag, 1e-6)
    dx = xr[:, None] - xs[None, :]
    dy = yr[:, None] - ys[None, :]
    along = dx * ex + dy * ey
    cross = -dx * ey + dy * ex
    ok = (along > 0) & (along < x_max)
    a = np.maximum(along, 300.0)
    sy = np.sqrt((0.32 * a / np.sqrt(1 + 0.0004 * a)) ** 2 + (a * SIGMA_THETA) ** 2 + extra_sy ** 2)
    sz = 0.24 * a * np.sqrt(1 + 0.001 * a)
    zeff = np.minimum(np.sqrt(np.pi / 2) * sz, pbl)
    lat = np.exp(-cross ** 2 / (2 * sy ** 2)) / (np.sqrt(2 * np.pi) * sy * sp)
    col = np.where(ok, lat, 0.0)
    return col / zeff, col


def metar_wind(path, name):
    """Viento horario (u, v en m/s, h = inicio de hora UTC) y posición de una estación METAR de IEM."""
    m = pd.read_csv(path, parse_dates=["valid"]).dropna(subset=["sknt", "drct"])
    ws = m.sknt * 0.5144
    r = np.deg2rad(m.drct)
    m["u"], m["v"] = -ws * np.sin(r), -ws * np.cos(r)
    m["h"] = m.valid.dt.floor("h")
    w = m.groupby("h")[["u", "v"]].mean().reset_index()
    w["id_station"] = name
    lat = m.lat.iloc[0] if "lat" in m else 19.4363
    lon = m.lon.iloc[0] if "lon" in m else -99.0721
    return w, (lon, lat)


def load_inputs(start, end, extras=False):
    """extras=True agrega estaciones que solo miden NO₂ (NOₓ ≈ NO₂ / cociente, marcadas est=True)
    y el viento METAR de los aeropuertos AICM (MMMX) y AIFA (MMSM)."""
    cand = gpd.read_file(INT / "point_candidates.gpkg").to_crs(UTM)
    prior_pt = cand.nox_prior_t_anio.fillna(AIRPORT_PRIOR).values
    sd_pt = np.where(cand.tipo == "aeropuerto", 2.0, 1.0) * prior_pt

    # celdas viales de 1 km con peso por clase
    roads = gpd.read_file(INT / "roads.gpkg")
    roads["w"] = roads.highway.str.replace("_link", "").map(ROAD_WEIGHT).fillna(1)
    x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    pts, wts = [], []
    for g, w in zip(roads.geometry, roads.w):
        n = max(int(g.length // 100), 1)
        for d in np.linspace(0, g.length, n, endpoint=False) + g.length / n / 2:
            p = g.interpolate(d)
            pts.append((p.x, p.y))
            wts.append(w * g.length / n)
    pts, wts = np.array(pts), np.array(wts)
    inside = (pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1)
    pts, wts = pts[inside], wts[inside]
    ix = ((pts[:, 0] - x0) // 1000).astype(int)
    iy = ((pts[:, 1] - y0) // 1000).astype(int)
    cells = pd.DataFrame({"ix": ix, "iy": iy, "w": wts}).groupby(["ix", "iy"]).w.sum().reset_index()
    cells["x"] = x0 + 500 + 1000 * cells.ix
    cells["y"] = y0 + 500 + 1000 * cells.iy
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    cells["region"] = assign_regions(cells, nx, ny)  # 0 = SO … 8 = NE (+ 9 según REGION_SCHEME)
    cells["w"] = cells.w / cells.w.sum() * ROAD_PRIOR_TOTAL  # t/año por celda a priori
    prior_rd = cells.groupby("region").w.sum().reindex(range(n_reg())).values
    cells.attrs["n_reg"] = n_reg()
    sd_rd = 0.5 * prior_rd

    st = gpd.read_file(INT / "estaciones.gpkg").to_crs(UTM).set_index("cve_estac")
    nox = pd.read_parquet(INT / "simat_nox.parquet")
    nox = nox[nox.local.between(start, f"{end} 23:59") & nox.hour.between(12, 17) & nox.id_station.isin(st.index)]
    full = nox.NOX.notna() & nox.NO2.notna()
    ratio = nox[full].NO2.sum() / nox[full].NOX.sum()
    nox["est"] = False
    if extras:
        only_no2 = nox.NOX.isna() & nox.NO2.notna()
        nox.loc[only_no2, "NOX"] = nox.loc[only_no2, "NO2"] / ratio
        nox.loc[only_no2, "est"] = True
    nox = nox[nox.NOX.notna()].copy()
    nox["h"] = nox.utc - pd.Timedelta(hours=1)  # SIMAT etiqueta al final de la hora

    w = pd.read_parquet(INT / "simat_wind.parquet")
    w = w[w.id_station.isin(st.index)].dropna(subset=["WSP", "WDR"])
    r = np.deg2rad(w.WDR)
    w["u"], w["v"] = -w.WSP * np.sin(r), -w.WSP * np.cos(r)
    w["h"] = w.utc - pd.Timedelta(hours=1)
    w = w[["h", "id_station", "u", "v"]]
    if extras:
        for f, name in (("MMMX_2023-2024.csv", "MMMX"), ("MMSM_2023-2024.csv", "MMSM")):
            mw, (lon, lat) = metar_wind(ROOT / "data/raw/metar" / f, name)
            w = pd.concat([w, mw], ignore_index=True)
            pt = gpd.GeoSeries.from_xy([lon], [lat], crs=4326).to_crs(UTM).iloc[0]
            st.loc[name, "geometry"] = pt
    wind = w.groupby("h")[["u", "v"]].mean()
    wind.attrs["by_station"] = w

    e = json.loads((ROOT / "data/raw/era5_openmeteo/pbl_wind_center_2023-2024_full.json").read_text())["hourly"]
    pbl = pd.Series(e["boundary_layer_height"], index=pd.to_datetime(e["time"]))
    # Open-Meteo no tiene capa límite ERA5 de ene–jun 2024. Para nov 2023–jun 2024 se usa la serie ERA5 +
    # MERRA-2 corregido de scripts/pbl_fill.py (reports/capa_limite.md); fuera de ese rango, si queda algún
    # hueco, se rellena con la climatología mes-hora.
    filled = pd.read_parquet(INT / "pbl_2023_2024.parquet").pbl_m
    pbl = filled.combine_first(pbl)
    clim = pbl.groupby([pbl.index.month, pbl.index.hour]).median()
    gap = pbl.isna()
    pbl[gap] = [clim.get((t.month, t.hour), np.nan) for t in pbl.index[gap]]
    pbl = ((pbl + pbl.shift(-1)) / 2).clip(lower=200)  # promedio de la hora
    if PBL_MAX:
        pbl = pbl.clip(upper=PBL_MAX)

    px = pd.read_parquet(INT / f"tempo_pixels_{start}_{end}.parquet")
    px = px[px.valid].copy()
    xy = gpd.GeoSeries.from_xy(px.lon, px.lat, crs=4326).to_crs(UTM)
    px["x"], px["y"], px["h"] = xy.x.values, xy.y.values, px.utc.dt.floor("h")
    return cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px


def jacobian_hour(h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    """Filas de la hora h: [16 puntos | n_reg() regiones viales] para estaciones y píxeles TEMPO.

    uv: (u, v) del dominio, o una función field(xs, ys, xr, yr) -> (U, V) por par fuente–receptor.
    """
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values

    def wind(xs, ys, xr, yr):
        return uv(xs, ys, xr, yr) if callable(uv) else uv

    blocks = []
    if len(nox_h):
        sxy = st.loc[nox_h.id_station.values].geometry
        xr, yr = sxy.x.values, sxy.y.values
        cp, _ = plume(xs_p, ys_p, xr, yr, *wind(xs_p, ys_p, xr, yr), pbl_h)
        cr, _ = plume(cells.x.values, cells.y.values, xr, yr, *wind(cells.x.values, cells.y.values, xr, yr), pbl_h)
        kp = cp * T_PER_YR_TO_GS * PPB_PER_GM3
        kr = (cr * cells.w.values * T_PER_YR_TO_GS * PPB_PER_GM3)  # por celda, ya multiplicado por a priori
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(n_reg(cells))], 1)
        blocks.append(("st", np.hstack([kp, kr])))
    if len(px_h):
        xr, yr = px_h.x.values, px_h.y.values
        _, cp = plume(xs_p, ys_p, xr, yr, *wind(xs_p, ys_p, xr, yr), pbl_h, extra_sy=1300)  # ~ píxel de 2×4.5 km
        _, cr = plume(cells.x.values, cells.y.values, xr, yr, *wind(cells.x.values, cells.y.values, xr, yr), pbl_h,
                      extra_sy=1300)
        f = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * ratio
        kp = cp * f
        kr = cr * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(n_reg(cells))], 1)
        blocks.append(("tp", np.hstack([kp, kr])))
    return blocks


def run(start, end):
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = load_inputs(start, end)
    n_src = len(cand) + n_reg()
    # Estado de fuentes en unidades relativas al a priori para las regiones viales (factor α, a priori 1)
    xa_src = np.r_[prior_pt, np.ones(n_reg())]
    sa_src = np.r_[sd_pt, sd_rd / prior_rd]
    hours = sorted(set(nox.h) & set(wind.index))
    hours = [h for h in hours if h in pbl.index]
    H = len(hours)
    n = n_src + 2 * H
    xa = np.r_[xa_src, np.full(H, 5.0), np.full(H, 5e15)]
    sa = np.r_[sa_src, np.full(H, 5.0), np.full(H, 3e15)]

    scen = {
        "Solo estaciones": dict(tempo=False, f_err=1.0, wind_err=False),
        "Estaciones + TEMPO": dict(tempo=True, f_err=1.0, wind_err=False),
        "Estaciones + TEMPO, pesimista": dict(tempo=True, f_err=2.0, wind_err=True),
    }
    SIG = {"st": 8.0, "tp": 3e15}
    # verdad del gemelo
    x_true = np.repeat(xa[:, None], N_TWIN, 1).astype(float)
    x_true[:n_src] *= rng.lognormal(0, 0.5, (n_src, N_TWIN))
    x_true[n_src:] += sa[n_src:, None] * rng.standard_normal((2 * H, N_TWIN))

    results = {}
    for name, cfg in scen.items():
        N = np.diag(1 / sa ** 2)
        b = np.repeat((xa / sa ** 2)[:, None], N_TWIN, 1)
        n_obs = 0
        for k, h in enumerate(hours):
            uv = wind.loc[h].values
            nox_h = nox[nox.h == h]
            px_h = px[px.h == h] if cfg["tempo"] else px.iloc[:0]
            blocks = jacobian_hour(h, uv, pbl.loc[h], cand, cells, st, nox_h, px_h, ratio)
            if cfg["wind_err"]:  # verdad generada con viento perturbado: el modelo no conoce el error
                ang = rng.normal(0, np.deg2rad(20))
                fac = rng.lognormal(0, 0.25)
                ca, sa_ = np.cos(ang), np.sin(ang)
                uv_t = fac * np.array([ca * uv[0] - sa_ * uv[1], sa_ * uv[0] + ca * uv[1]])
                blocks_t = jacobian_hour(h, uv_t, pbl.loc[h], cand, cells, st, nox_h, px_h, ratio)
            else:
                blocks_t = blocks
            for (kind, K), (_, Kt) in zip(blocks, blocks_t):
                m = K.shape[0]
                bg = n_src + (k if kind == "st" else H + k)
                Kf = np.zeros((m, n_src + 1))
                Kf[:, :n_src], Kf[:, n_src] = K, 1.0
                Ktf = np.zeros_like(Kf)
                Ktf[:, :n_src], Ktf[:, n_src] = Kt, 1.0
                idx = np.r_[np.arange(n_src), bg]
                sig = SIG[kind] * cfg["f_err"]
                y = Ktf @ x_true[idx] + sig * rng.standard_normal((m, N_TWIN))
                N[np.ix_(idx, idx)] += Kf.T @ Kf / sig ** 2
                b[idx] += Kf.T @ y / sig ** 2
                n_obs += m
        S = np.linalg.inv(N)
        x_hat = S @ b
        sd_post = np.sqrt(np.diag(S))[:n_src]
        corr = S[:n_src, :n_src] / np.outer(sd_post, sd_post)
        A = np.eye(n) - S @ np.diag(1 / sa ** 2)
        err = np.abs(x_hat[:n_src] - x_true[:n_src]) / x_true[:n_src]
        results[name] = dict(sd_post=sd_post, corr=corr, dofs=np.trace(A[:n_src, :n_src]),
                             err=np.median(err, 1), n_obs=n_obs)
        print(f"{name}: {n_obs:,} observaciones, DOFS fuentes = {results[name]['dofs']:.1f} de {n_src}", flush=True)

    names = list(cand.nombre) + [f"Vial región {r}" for r in region_names()]
    prior_abs = np.r_[prior_pt, prior_rd]
    lines = [f"# Factibilidad: inversión lineal ({start} a {end})\n",
             f"- Horas usadas: {H}; cociente NO₂/NOₓ de la tarde: {ratio:.2f}; "
             f"σ obs nominal: estaciones {SIG['st']} ppb, TEMPO {SIG['tp']:.0e} molec/cm²",
             "- Reducción = 1 − σ posterior / σ a priori (0 % = los datos no informan; 100 % = determinada). "
             "Error gemelo = mediana del error relativo de 50 gemelos.",
             "- Pesimista: errores ×2 y verdad generada con viento perturbado (±20° y ±25 % de velocidad por hora).\n"]
    lines.append("| Fuente | A priori t/año | " + " | ".join(f"{s}: reducción / error gemelo" for s in scen) + " |")
    lines.append("|---|---|" + "---|" * len(scen))
    for i, nm in enumerate(names):
        cellsv = []
        for s in scen:
            red = 1 - results[s]["sd_post"][i] / sa_src[i]
            cellsv.append(f"{red:.0%} / {results[s]['err'][i]:.0%}")
        lines.append(f"| {nm} | {prior_abs[i]:,.0f} | " + " | ".join(cellsv) + " |")
    lines.append("\n| Escenario | Observaciones | DOFS de fuentes (de %d) |" % n_src)
    lines.append("|---|---|---|")
    for s in scen:
        lines.append(f"| {s} | {results[s]['n_obs']:,} | {results[s]['dofs']:.1f} |")
    c = results["Estaciones + TEMPO"]["corr"]
    iu = np.triu_indices(n_src, 1)
    order = np.argsort(c[iu])[:8]
    lines.append("\n## Pares más confundidos (Estaciones + TEMPO; correlación a posteriori negativa = el modelo no sabe a cuál asignar)\n")
    lines.append("| Fuente A | Fuente B | r |")
    lines.append("|---|---|---|")
    for o in order:
        i, j = iu[0][o], iu[1][o]
        lines.append(f"| {names[i]} | {names[j]} | {c[i, j]:.2f} |")
    out = ROOT / f"reports/feasibility_linear_{start}_{end}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    run(*sys.argv[1:3])
