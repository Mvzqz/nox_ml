"""Gemelo comparativo CDMX vs Los Ángeles con el mismo código y los mismos supuestos.

Reutiliza jacobian_hour (feasibility_linear.py) y perturb / run_scenario (improvement_tests.py):
pluma estacionaria, errores de observación ×2, fondos por hora marginalizados, 50 gemelos.
Para cada ciudad y nivel de error de dirección del viento (σ en grados) se calcula el error de
recuperación de la emisión vial por región, de las fuentes grandes y de 12 fuentes industriales.

LA (supuestos, documentados en reports/otras_ciudades.md):
- Red vial OSM con los mismos pesos por clase; total vial a priori calibrado para que la
  contribución vial media modelada en las estaciones sea 0.8 × (NOₓ medido de tarde − 5 ppb).
- Centrales: WRI GPPD (gas/petróleo/carbón, ≥ 100 MW) en el dominio, 2 % del total por capacidad.
- Aeropuertos comerciales LAX, BUR y LGB (OSM), 500 t/año cada uno (igual que en CDMX).
- 12 "zonas industriales": los 12 polígonos landuse=industrial más grandes de OSM, 150 t/año cada uno.

Uso: .venv/bin/python scripts/la_twin.py
"""
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Polygon

import improvement_tests as it
from feasibility_linear import ROAD_WEIGHT, jacobian_hour, load_inputs
from la_common import AFTERNOON, END, INT, LAT, LOCAL_OFFSET_H, LON, RAW, START, UTM

LEVELS = [30, 20, 10]
it.N_TWIN = 50
rng = np.random.default_rng(23)


def road_cells(path):
    osm = json.loads(path.read_text())
    rows = [(e["tags"]["highway"], LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
            for e in osm["elements"] if e["type"] == "way" and len(e.get("geometry", [])) > 1]
    roads = gpd.GeoDataFrame({"highway": [r[0] for r in rows]}, geometry=[r[1] for r in rows], crs=4326).to_crs(UTM)
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
    ix, iy = ((pts[:, 0] - x0) // 1000).astype(int), ((pts[:, 1] - y0) // 1000).astype(int)
    cells = pd.DataFrame({"ix": ix, "iy": iy, "w": wts}).groupby(["ix", "iy"]).w.sum().reset_index()
    cells["x"], cells["y"] = x0 + 500 + 1000 * cells.ix, y0 + 500 + 1000 * cells.iy
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    cells["region"] = (cells.ix * 3 // nx) + 3 * (cells.iy * 3 // ny)
    cells["w"] = cells.w / cells.w.sum()  # se escala después al total calibrado
    return cells


def la_candidates():
    from la_common import DOMAIN
    g = pd.read_csv(RAW.parents[0] / "powerplants/global_power_plant_database.csv", low_memory=False)
    g = gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g.longitude, g.latitude), crs=4326)
    g = g[(g.country == "USA") & g.within(DOMAIN) & g.primary_fuel.isin(["Gas", "Oil", "Coal"]) & (g.capacity_mw >= 100)]
    pw = gpd.GeoDataFrame({"tipo": "central eléctrica", "nombre": g.name.values, "cap": g.capacity_mw.values},
                          geometry=g.geometry.values, crs=4326)
    a = json.loads((RAW / "aerodromes_bbox.json").read_text())
    ap = {}
    for e in a["elements"]:
        code = e["tags"].get("iata")
        if e["type"] == "way" and code in ("LAX", "BUR", "LGB") and code not in ap:
            ap[code] = Polygon([(p["lon"], p["lat"]) for p in e["geometry"]]).centroid
    ap = gpd.GeoDataFrame({"tipo": "aeropuerto", "nombre": list(ap), "cap": np.nan}, geometry=list(ap.values()), crs=4326)
    ind = json.loads((RAW / "industrial_bbox.json").read_text())
    polys = [Polygon([(p["lon"], p["lat"]) for p in e["geometry"]]) for e in ind["elements"]
             if e["type"] == "way" and len(e.get("geometry", [])) > 3]
    ig = gpd.GeoDataFrame(geometry=polys, crs=4326).to_crs(UTM)
    ig = ig[ig.is_valid].assign(area=lambda d: d.area).sort_values("area", ascending=False).head(12)
    ig = gpd.GeoDataFrame({"tipo": "industria", "nombre": [f"Industrial OSM {i + 1}" for i in range(len(ig))], "cap": np.nan},
                          geometry=ig.centroid.values, crs=UTM).to_crs(4326)
    return pd.concat([pw, ap, ig], ignore_index=True).pipe(gpd.GeoDataFrame, crs=4326).to_crs(UTM)


def la_inputs(with_tempo=True):
    cells = road_cells(RAW / "roads_bbox.json")
    cand = la_candidates()
    b = pd.read_parquet(INT / "aqs_nonox.parquet")
    b = b[b["Parameter Code"] == 42603]
    pos = b.groupby("site")[["Latitude", "Longitude"]].first()
    st = gpd.GeoDataFrame(index=pos.index, geometry=gpd.points_from_xy(pos.Longitude, pos.Latitude), crs=4326).to_crs(UTM)
    b = b[b.local.dt.hour.isin(AFTERNOON)].rename(columns={"site": "id_station", "Sample Measurement": "NOX"})
    b["h"] = b.utc  # AQS: hora de inicio en GMT
    nox = b[["id_station", "h", "NOX"]].dropna()
    nox["est"] = False
    a = pd.read_parquet(INT / "aqs_no2.parquet")
    m = b.merge(a.rename(columns={"site": "id_station"})[["id_station", "utc", "Sample Measurement"]], on=["id_station", "utc"])
    ratio = m["Sample Measurement"].sum() / m.NOX.sum()
    w = pd.read_parquet(INT / "wind_stations.parquet")
    wind = w.groupby("h")[["u", "v"]].mean()
    e = json.loads((RAW / "era5_pbl_2023.json").read_text())["hourly"]
    pbl = pd.Series(e["boundary_layer_height"], index=pd.to_datetime(e["time"]))
    pbl = ((pbl + pbl.shift(-1)) / 2).clip(lower=200)
    px = pd.DataFrame(columns=["x", "y", "h"])
    if with_tempo:
        px = la_tempo_pixels()
    # Calibración del total vial: contribución vial media modelada en estaciones = 0.8 × (NOₓ − 5 ppb)
    cells_unit = cells.assign(w=cells.w * 1.0)  # 1 t/año en total
    hours = sorted(h for h in set(nox.h) & set(wind.index) & set(pbl.index) if np.isfinite(pbl.loc[h]))
    sample = hours[:: max(1, len(hours) // 60)]
    mod = []
    for h in sample:
        nh = nox[nox.h == h]
        K = jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand.iloc[:0], cells_unit, st, nh, px.iloc[:0], ratio)[0][1]
        mod.append(K.sum(1).mean())
    target = 0.8 * max(nox.NOX.mean() - 5, 1)
    total_road = target / np.mean(mod)
    cells["w"] = cells.w * total_road
    prior_rd = cells.groupby("region").w.sum().reindex(range(9)).fillna(0).values
    total = total_road / 0.86
    prior_pt = np.where(cand.tipo == "central eléctrica", 0.02 * total * cand.cap / cand.cap.sum(),
                        np.where(cand.tipo == "aeropuerto", 500.0, 150.0))
    sd_pt = np.where(cand.tipo == "aeropuerto", 2.0, 1.0) * prior_pt
    info = dict(total_road=total_road, ratio=ratio, n_st=len(st), nox_mean=nox.NOX.mean(),
                n_plants=int((cand.tipo == "central eléctrica").sum()), n_airports=int((cand.tipo == "aeropuerto").sum()))
    return cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, wind, pbl, px, info


def la_tempo_pixels():
    import netCDF4
    rows = []
    for f in sorted((RAW / "tempo").glob("TEMPO_NO2_L2_V04_*_zmvm.nc")):
        t = pd.Timestamp(f.name.split("_")[4][:15].replace("T", " "))
        with netCDF4.Dataset(f) as ds:
            df = pd.DataFrame({"lat": ds["geolocation/latitude"][:].filled(np.nan).ravel(),
                               "lon": ds["geolocation/longitude"][:].filled(np.nan).ravel(),
                               "qf": ds["product/main_data_quality_flag"][:].filled(255).ravel(),
                               "cf": ds["support_data/eff_cloud_fraction"][:].filled(np.nan).ravel(),
                               "vcd": ds["product/vertical_column_troposphere"][:].filled(np.nan).ravel()})
        df["utc"] = t
        rows.append(df)
    if not rows:
        return pd.DataFrame(columns=["x", "y", "h"])
    px = pd.concat(rows)
    px = px[px.lat.between(*LAT) & px.lon.between(*LON) & (px.qf == 0) & (px.cf < 0.2) & px.vcd.notna()]
    loc = px.utc + pd.Timedelta(hours=LOCAL_OFFSET_H)
    px = px[(loc >= START) & (loc < pd.Timestamp(END) + pd.Timedelta(days=1)) & loc.dt.hour.isin(AFTERNOON)]
    xy = gpd.GeoSeries.from_xy(px.lon, px.lat, crs=4326).to_crs(UTM)
    return px.assign(x=xy.x.values, y=xy.y.values, h=px.utc.dt.floor("h"))


def compute(cand, cells, st, nox, ratio, wind, pbl, px):
    hours = [h for h in sorted(set(nox.h) & set(wind.index)) if h in pbl.index and np.isfinite(pbl.loc[h])]
    out = []
    for h in hours:
        z = rng.standard_normal(2)
        nh, ph = nox[nox.h == h], px[px.h == h]
        rec = {"est": nh.est.values}
        for lvl in [0] + LEVELS:
            uv = wind.loc[h].values if lvl == 0 else it.perturb(wind.loc[h].values, z, lvl)
            rec[lvl] = {("NOx" if k == "st" else "TEMPO"): b for k, b in jacobian_hour(h, uv, pbl.loc[h], cand, cells, st, nh, ph, ratio)}
        out.append(rec)
    return out


def evaluate(name, recs, cand, prior_pt, sd_pt, prior_rd, lines):
    mean, Sa, n_src, types = it.state_layout(cand, prior_pt, sd_pt, prior_rd, ["NOx"])
    truth = mean[:, None] * rng.lognormal(0, 0.5, (n_src, it.N_TWIN))
    ind = [i for i, t in enumerate(types) if t == "industria"]
    air = [i for i, t in enumerate(types) if t == "aeropuerto"]
    plants = [i for i, t in enumerate(types) if t == "central eléctrica"]
    road = [i for i, t in enumerate(types) if t == "vial"]
    for tempo in (False, True):
        rr = recs if tempo else [{k: ({kk: vv for kk, vv in v.items() if kk != "TEMPO"} if isinstance(v, dict) else v)
                                    for k, v in r.items()} for r in recs]
        if tempo and not any("TEMPO" in r[0] for r in recs):
            continue
        for lvl in LEVELS:
            err, _ = it.run_scenario([(rr, cand, prior_pt, sd_pt, prior_rd)], dict(periods=[0], level=lvl, extras=False, tracers=False), truth)
            lines.append(f"| {name} | {'estaciones + TEMPO' if tempo else 'solo estaciones'} | ±{lvl}° | "
                         f"{np.median(err[road]):.0%} ({err[road].max():.0%}) | {np.median(err[air]):.0%} | {np.median(err[plants]):.0%} | "
                         f"{np.median(err[ind]):.0%} | {(err[ind] < 0.25).sum()} de {len(ind)} |")
            print(lines[-1], flush=True)


def main():
    lines = ["| Ciudad | Observaciones | Error de viento (σ) | Vial por región: mediana (máx) | Aeropuertos: mediana | Centrales: mediana | Industria: mediana | Industria < 25 % |",
             "|---|---|---|---|---|---|---|---|"]
    cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, wind, pbl, px, info = la_inputs()
    print("LA:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in info.items()},
          "píxeles TEMPO válidos:", len(px), "candidatas:", cand.tipo.value_counts().to_dict(), flush=True)
    recs = compute(cand, cells, st, nox, ratio, wind, pbl, px)
    evaluate("Los Ángeles", recs, cand, prior_pt, sd_pt, prior_rd, lines)

    c_cand, c_pp, c_sd, c_cells, c_prd, _, c_st, c_nox, c_ratio, c_wind, c_pbl, c_px = load_inputs(START, END)
    c_recs = compute(c_cand, c_cells, c_st, c_nox, c_ratio, c_wind, c_pbl, c_px)
    evaluate("CDMX", c_recs, c_cand, c_pp, c_sd, c_prd, lines)
    (INT / "la_twin_table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
