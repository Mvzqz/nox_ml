"""LA con datos reales: ¿un mejor viento mejora la inversión? Mismo método que la CDMX (real_check_linear.py).

Inversión lineal (σθ = 30°, fondo por hora para estaciones y TEMPO, vial 3×3 × tipo de día, aeropuertos
LAX/BUR/LGB y centrales de gas ≥ 100 MW; sin "industria" OSM, igual que la opción B de la CDMX), con
tres vientos sobre las mismas horas:
  domain = vector medio de las 20 estaciones de viento (ASOS + AQS) para todo el dominio;
  idw    = campo IDW de esas estaciones en malla de 1 km (promedio en fuente, punto medio y receptor);
  hrrr   = campo HRRR 3 km (promedio de los análisis h y h+1) llevado a la misma malla de 1 km;
  hrrr_pbl = HRRR con su propia capa límite (media del dominio) en lugar de la de ERA5 en un punto.

Métricas (las de la CDMX): ajuste en muestra; domingo/hábil y sábado/hábil con bootstrap de días;
LOO modelo/IDW/híbrido y descomposición sesgo/hora a hora; habilidad del modelo con emisión fija
(sin invertir) frente a estaciones y TEMPO; estimador normalizado por meteorología (observado ÷ modelo con
emisión fija) con su placebo de días falsos.

Hora local civil: America/Los_Angeles (PDT = UTC−7 hasta el 5 nov 2023, después PST = UTC−8). Tarde 12–17 h.
Uso: .venv/bin/python scripts/la_real.py [--boot 200] [--modes domain idw hrrr hrrr_pbl]
     .venv/bin/python scripts/la_real.py --city cdmx --modes domain field   (mismas métricas en la CDMX)
Salida: data/interim/la/la_real_<ciudad>_<modo>.json
"""
import argparse
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

import feasibility_linear as fl
import puff
import real_check_linear as rcl
from la_common import END, INT, LAT, LON, RAW, START, UTM

TZ = "America/Los_Angeles"
LA_HOLIDAYS = {"2023-11-23", "2023-12-25"}  # Acción de Gracias y Navidad (tratados como domingo)
rng = np.random.default_rng(11)


def to_local(t):
    t = pd.DatetimeIndex(t) if not isinstance(t, pd.Timestamp) else t
    return t.tz_localize("UTC").tz_convert(TZ).tz_localize(None)


def la_local_day(h):
    return to_local(h).normalize()


def la_day_type(h):
    d = to_local(h)
    if d.strftime("%Y-%m-%d") in LA_HOLIDAYS or d.dayofweek == 6:
        return 2
    return 1 if d.dayofweek == 5 else 0


# ---------- viento en malla de 1 km ----------
def grid_geometry():
    x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    gx, gy = np.meshgrid(x0 + 500 + 1000 * np.arange(nx), y0 + 500 + 1000 * np.arange(ny))
    return x0, y0, nx, ny, gx, gy


def pair_function(U, V, x0, y0, nx, ny):
    """Viento por par fuente–receptor: promedio del campo en fuente, punto medio y receptor (como real_check_linear)."""
    def at(x, y):
        i = np.clip(((y - y0) // 1000).astype(int), 0, ny - 1)
        j = np.clip(((x - x0) // 1000).astype(int), 0, nx - 1)
        return U[i, j], V[i, j]

    def pair(xs, ys, xr, yr):
        XS, XR = np.broadcast_arrays(xs[None, :], xr[:, None])
        YS, YR = np.broadcast_arrays(ys[None, :], yr[:, None])
        u, v = np.zeros(XS.shape), np.zeros(XS.shape)
        for f in (0.0, 0.5, 1.0):
            a, b = at(XS + f * (XR - XS), YS + f * (YR - YS))
            u += a / 3
            v += b / 3
        return u, v

    return pair


def idw_factory(w):
    x0, y0, nx, ny, gx, gy = grid_geometry()
    groups = dict(tuple(w.groupby("h")))

    def field(h):
        g = groups[h]
        d2 = np.maximum((gx[..., None] - g.x.values) ** 2 + (gy[..., None] - g.y.values) ** 2, 500.0 ** 2)
        wt = 1 / d2
        return pair_function((wt * g.u.values).sum(-1) / wt.sum(-1), (wt * g.v.values).sum(-1) / wt.sum(-1), x0, y0, nx, ny)

    return field


def load_hrrr():
    ds = xr.open_dataset(RAW / f"hrrr_field/hrrr_field_{START}_{END}.nc")
    x0, y0, nx, ny, gx, gy = grid_geometry()
    pts = gpd.GeoSeries.from_xy(gx.ravel(), gy.ravel(), crs=UTM).to_crs(4326)
    lat, lon = ds.latitude.values, ds.longitude.values
    flat = np.c_[lat.ravel(), lon.ravel() * np.cos(np.deg2rad(34))]
    q = np.c_[pts.y.values, pts.x.values * np.cos(np.deg2rad(34))]
    nn = np.argmin(((q[:, None, :] - flat[None, :, :]) ** 2).sum(-1), axis=1)  # vecino más cercano 3 km → 1 km
    times = pd.DatetimeIndex(ds.time.values)
    u = ds.u10.values.reshape(len(times), -1)[:, nn].reshape(len(times), ny, nx)
    v = ds.v10.values.reshape(len(times), -1)[:, nn].reshape(len(times), ny, nx)
    pbl = pd.Series(ds.hpbl.values.reshape(len(times), -1)[:, nn].mean(1), index=times)
    pos = {t: i for i, t in enumerate(times)}

    def field(h):
        i, j = pos[h], pos[h + pd.Timedelta(hours=1)]
        return pair_function((u[i] + u[j]) / 2, (v[i] + v[j]) / 2, x0, y0, nx, ny)

    ok = [t for t in times if t + pd.Timedelta(hours=1) in pos]
    pbl_h = pd.Series({t: (pbl[t] + pbl[t + pd.Timedelta(hours=1)]) / 2 for t in ok}).clip(lower=200)
    # para validar el campo contra las estaciones: viento HRRR en cada estación de viento (hora h)
    return field, set(ok), pbl_h, (u, v, pos, x0, y0, nx, ny)


# ---------- entradas de LA en el formato de feasibility_linear.load_inputs ----------
def la_inputs():
    import la_twin as lt
    cand, prior_pt, sd_pt, cells, prior_rd, st, _, ratio, _, pbl, _, info = lt.la_inputs(with_tempo=False)
    keep = (cand.tipo != "industria").values
    cand, prior_pt, sd_pt = cand[keep].reset_index(drop=True), prior_pt[keep], sd_pt[keep]
    cand["nombre"] = cand.nombre.astype(str)
    b = pd.read_parquet(INT / "aqs_nonox.parquet")
    b = b[b["Parameter Code"] == 42603].rename(columns={"site": "id_station", "Sample Measurement": "NOX"})
    b["h"] = b.utc
    loc = to_local(b.h)
    b = b[(loc >= START) & (loc < pd.Timestamp(END) + pd.Timedelta(days=1)) & loc.hour.isin(range(12, 18))]
    nox = b[["id_station", "h", "NOX"]].dropna().assign(est=False)
    w = pd.read_parquet(INT / "wind_stations.parquet")
    lt.AFTERNOON = range(11, 18)          # superconjunto PST; se filtra abajo con hora civil
    px = lt.la_tempo_pixels()
    loc = to_local(px.utc)
    px = px[loc.hour.isin(range(12, 18))].copy()
    return cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, w, pbl, px, info


# ---------- métricas ----------
def metrics(m, boot, loo=True):
    N, b = rcl.solve(m)
    S = np.linalg.inv(N)
    x = S @ b
    n_pt = m["n_pt"]
    out = {"horas": len(m["hours"])}
    obs = np.array([r[4] for r in m["st_rows"]])
    pred = np.array([kr @ x[idx] for _, _, idx, kr, _ in m["st_rows"]])
    out["muestra_r_est"], out["muestra_rmse_est"] = np.corrcoef(pred, obs)[0, 1], np.sqrt(np.mean((pred - obs) ** 2))
    if m["tp_rows"]:
        tp_obs = np.concatenate([y for *_, y in m["tp_rows"]])
        tp_pred = np.concatenate([Kf @ x[idx] for idx, Kf, _ in m["tp_rows"]])
        out["muestra_r_tempo"] = np.corrcoef(tp_pred, tp_obs)[0, 1]
        out["n_tempo"] = len(tp_obs)

    # domingo/hábil y sábado/hábil (inversión completa) con bootstrap de días
    tot = rcl.road_totals(m, x)
    days = sorted({d for d, *_ in m["blocks"]})
    bs = []
    for _ in range(boot):
        pick = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick]).groupby(level=0).sum().to_dict()
        Nb, bb = rcl.solve(m, weights=wts)
        bs.append(rcl.road_totals(m, np.linalg.solve(Nb, bb)))
    bs = np.array(bs)
    out["vial_habil"] = tot[0]
    out["vial_apriori"] = float(m["prior_rd"].sum())
    for d, k in ((1, "sabado"), (2, "domingo")):
        out[k] = tot[d] / tot[0]
        out[k + "_ic"] = np.percentile(bs[:, d] / bs[:, 0], [5, 95]).tolist()
    out["puntuales"] = {nm: [float(x[i]), float(np.sqrt(S[i, i])), float(m["prior_pt"][i])] for i, nm in enumerate(m["cand"].nombre)}

    # habilidad del modelo con emisión fija (a priori), sin invertir
    rows = pd.DataFrame([(s, h, o) for s, h, _, _, o in m["st_rows"]], columns=["sid", "h", "obs"])
    # el Jacobiano guarda la fila completa [puntos | 9 viales del tipo de día | fondo]; idx ya mapea el tipo de día
    rows["fixed"] = [float(kr[:n_pt] @ m["prior_pt"] + kr[n_pt:n_pt + m.get("n_reg", 9)].sum()) for *_, kr, _ in m["st_rows"]]
    out["fija_r_est_hora"] = rows.obs.corr(rows.fixed)
    hr = rows.groupby("h")[["obs", "fixed"]].mean()
    out["fija_r_est_media_horaria"] = hr.obs.corr(hr.fixed)
    # anomalía dentro de cada hora (patrón espacial entre estaciones)
    an = rows.assign(o=rows.obs - rows.groupby("h").obs.transform("mean"), f=rows.fixed - rows.groupby("h").fixed.transform("mean"))
    out["fija_r_est_espacial"] = an.o.corr(an.f)
    if m["tp_rows"]:
        rs, allo, allf = [], [], []
        for idx, Kf, y in m["tp_rows"]:
            f = Kf[:, :n_pt] @ m["prior_pt"] + Kf[:, n_pt:n_pt + m.get("n_reg", 9)].sum(1)
            allo.append(y)
            allf.append(f)
            if len(y) >= 30 and f.std() > 0:
                rs.append(np.corrcoef(f, y)[0, 1])
        out["fija_r_tempo_global"] = np.corrcoef(np.concatenate(allf), np.concatenate(allo))[0, 1]
        out["fija_r_tempo_por_hora_mediana"] = float(np.median(rs))

    # estimador normalizado: Σ observado ÷ Σ modelo con emisión fija, por tipo de día
    hr = hr.assign(day=[rcl.local_day(h) for h in hr.index], dt=[rcl.day_type(h) for h in hr.index])
    dd = hr.groupby("day").agg(obs=("obs", "sum"), fixed=("fixed", "sum"), dt=("dt", "first"), n=("obs", "size"))
    dd = dd[dd.n >= 4]

    def nr(d, a=0, bset=2):
        g = d.groupby("dt")
        v = g.obs.sum() / g.fixed.sum()
        return v.get(bset, np.nan) / v[a]
    out["norm_domingo"] = nr(dd)
    out["norm_sabado"] = nr(dd, 0, 1)
    bsn = np.array([[nr(q), nr(q, 0, 1)] for q in (dd.iloc[rng.integers(0, len(dd), len(dd))] for _ in range(1000))])
    out["norm_domingo_ic"] = np.nanpercentile(bsn[:, 0], [5, 95]).tolist()
    out["norm_sabado_ic"] = np.nanpercentile(bsn[:, 1], [5, 95]).tolist()
    wk = dd[dd.dt == 0]
    out["norm_cv_habiles"] = float((wk.obs / wk.fixed).std() / (wk.obs / wk.fixed).mean())
    out["crudo_cv_habiles"] = float((wk.obs / wk.n).std() / (wk.obs / wk.n).mean())
    # placebo: días hábiles falsos como "domingo" (mismo número que domingos reales), contra los demás hábiles
    k = int((dd.dt == 2).sum())
    pl = []
    for _ in range(2000):
        fake = rng.choice(len(wk), k, replace=False)
        msk = np.zeros(len(wk), bool)
        msk[fake] = True
        a, b2 = wk[~msk], wk[msk]
        pl.append((b2.obs.sum() / b2.fixed.sum()) / (a.obs.sum() / a.fixed.sum()))
    pl = np.array(pl)
    out["placebo_p5_p95"] = np.percentile(pl, [5, 95]).tolist()
    out["placebo_mitad_ancho"] = float((np.percentile(pl, 95) - np.percentile(pl, 5)) / 2)
    out["n_domingos"] = k
    out["n_habiles"] = int(len(wk))

    if loo:
        st = m["st"]
        rows = pd.DataFrame([(s, h, o) for (s, h, *_, o) in m["st_rows"]], columns=["sid", "h", "obs"])
        agg = []
        for sid in sorted(set(rows.sid.unique()) - m["est_ids"]):
            Nl, bl = rcl.solve(m, drop_station=sid)
            xl = np.linalg.solve(Nl, bl)
            allpred = np.array([kr @ xl[idx] for _, _, idx, kr, _ in m["st_rows"]])
            rows["res"] = rows.obs - allpred
            mask = (rows.sid == sid).values
            pm, ob = allpred[mask], rows.obs.values[mask]
            others = rows[~mask]
            dist = {s: max(st.geometry[sid].distance(st.geometry[s]) / 1000, 0.5) for s in others.sid.unique()}
            pi, prr = [], []
            for h in rows.h.values[mask]:
                o = others[others.h == h]
                wv = 1 / np.array([dist[s] for s in o.sid]) ** 2
                pi.append((wv * o.obs.values).sum() / wv.sum())
                prr.append((wv * o.res.values).sum() / wv.sum())
            pi, ph = np.array(pi), pm + np.array(prr)
            agg.append((sid, len(ob), *[np.sqrt(np.mean((p - ob) ** 2)) for p in (pm, pi, ph)],
                        *[np.mean(p - ob) for p in (pm, pi, ph)], *[np.corrcoef(p, ob)[0, 1] for p in (pm, pi, ph)]))
        ag = pd.DataFrame(agg, columns=["sid", "n", "model", "idw", "hybrid", "b_model", "b_idw", "b_hybrid", "r_model", "r_idw", "r_hybrid"])
        wr = lambda c: float(np.sqrt((ag.n * ag[c] ** 2).sum() / ag.n.sum()))
        for c in ("model", "idw", "hybrid"):
            ag[f"u_{c}"] = np.sqrt(np.maximum(ag[c] ** 2 - ag[f"b_{c}"] ** 2, 0))
            out[f"loo_{c}"] = wr(c)
            out[f"loo_sesgo_{c}"] = wr(f"b_{c}")
            out[f"loo_hora_{c}"] = wr(f"u_{c}")
            out[f"loo_r_{c}"] = float(np.average(ag[f"r_{c}"], weights=ag.n))
        out["hibrido_gana"] = f"{int((ag.hybrid < ag.idw).sum())} de {len(ag)}"
        out["modelo_gana"] = f"{int((ag.model < ag.idw).sum())} de {len(ag)}"
        out["loo_por_estacion"] = ag.round(2).to_dict("records")
    return out


def run_la(modes, boot):
    cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, w, pbl_era5, px, info = la_inputs()
    hfield, hhours, hpbl, _ = load_hrrr()
    wloc = to_local(w.h)
    wa = w[wloc.hour.isin(range(12, 18))]
    nst = wa.groupby("h").sid.nunique()
    hours = sorted(set(nox.h) & set(nst[nst >= 8].index) & hhours & set(pbl_era5.dropna().index) & set(hpbl.index))
    nox, px = nox[nox.h.isin(hours)], px[px.h.isin(hours)]
    wind = wa[wa.h.isin(hours)].groupby("h")[["u", "v"]].mean()
    wind.attrs["by_station"] = None  # el campo lo arma wind_field_factory (reemplazado abajo)
    print(f"LA: horas comunes {len(hours)}, obs NOₓ {len(nox):,}, píxeles TEMPO {len(px):,}, cociente NO₂/NOₓ {ratio:.2f}, "
          f"vial a priori {prior_rd.sum():,.0f} t/año; fuentes {cand.tipo.value_counts().to_dict()}", flush=True)
    idw = idw_factory(wa[wa.h.isin(hours)])
    rcl.local_day, rcl.day_type = la_local_day, la_day_type
    res = {}
    for mode in modes:
        pbl = hpbl if mode == "hrrr_pbl" else pbl_era5
        rcl.load_inputs = lambda *a, **k: (cand, prior_pt, sd_pt, cells, prior_rd, 0.5 * prior_rd, st, nox, ratio, wind, pbl, px)
        rcl.wind_field_factory = lambda *a, **k: (hfield if mode.startswith("hrrr") else idw)
        m = rcl.build(START, END, "domain" if mode == "domain" else "field", no_industry=False)
        r = metrics(m, boot)
        r["info"] = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}
        res[mode] = r
        (INT / f"la_real_la_{mode}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        print(mode, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                     if k not in ("puntuales", "loo_por_estacion")}, flush=True)
    return res


def run_cdmx(modes, boot):
    for mode in modes:
        m = rcl.build("2023-11-01", "2023-12-31", mode, no_industry=True, extras=False)
        r = metrics(m, boot)
        (INT / f"la_real_cdmx_{mode}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        print("CDMX", mode, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                             if k not in ("puntuales", "loo_por_estacion")}, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", choices=["la", "cdmx"], default="la")
    ap.add_argument("--modes", nargs="+", default=["domain", "idw", "hrrr", "hrrr_pbl"])
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    if a.city == "la":
        run_la(a.modes, a.boot)
    else:
        run_cdmx(a.modes, a.boot)


if __name__ == "__main__":
    main()
