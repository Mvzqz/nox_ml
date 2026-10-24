"""LA con datos reales: ¿mejor viento + transporte no estacionario (puffs) mejora la inversión?

`la_real.py` mostró que con pluma estacionaria un viento mejor (HRRR, IDW) no mejora ninguna métrica. Aquí se
repite con el transporte dependiente del tiempo de `puff.py` (pluma de la hora actual + sub-puffs de las 6 horas
previas, perfil horario de tráfico, decaimiento químico), con tres vientos:

  puff_domain = puffs con el vector medio de las estaciones (como `real_check_linear.py --wind puff` en la CDMX);
  puff_idw    = puffs que viajan por el campo IDW de las estaciones (malla 1 km, todas las horas);
  puff_hrrr   = puffs que viajan por el campo HRRR 3 km (análisis 05–18 h local; `la_hrrr_field.py` +
                `la_hrrr_morning.py`), pluma de la hora actual con el viento HRRR por par fuente–receptor;
  puff_hrrr_flat = igual, pero emisión vial sin perfil horario (sensibilidad al perfil supuesto).

En los modos espaciales cada sub-puff sigue su propia trayectoria (integración cada ≤ 15 min con el campo
interpolado linealmente en el tiempo), y su dispersión crece con la distancia recorrida, como en `puff.py`.

Perfil horario de tráfico: `puff.PROFILE` (supuesto urbano típico, pico 7–9 h y 16–18 h). No hay PeMS (sin cuenta),
así que no se usa un perfil medido de LA.

Configuración fija (otro agente cambia defaults en paralelo): σθ = 30°, σ estaciones 15 ppb, σ TEMPO 5e15
molec/cm² (el peso de TEMPO de `la_real.py`), fondo por hora para estaciones y TEMPO. Mismas 363 horas y mismas
métricas que `la_real.py` (función `metrics`).

Uso: .venv/bin/python scripts/la_puff.py [--boot 200] [--modes puff_domain puff_idw puff_hrrr puff_hrrr_flat]
Salida: data/interim/la/la_real_la_<modo>.json
"""
import argparse
import json

import numpy as np
import pandas as pd
import xarray as xr

import feasibility_linear as fl
import la_real as lr
import puff
import real_check_linear as rcl
from feasibility_linear import MOLEC_CM2_PER_GM2, PPB_PER_GM3, T_PER_YR_TO_GS, U_MIN, plume
from la_common import END, INT, RAW, START

STEP_H = 0.25


class GridWind:
    """Viento en la malla de 1 km de `la_real.grid_geometry`, interpolado linealmente en el tiempo (horas flotantes)."""

    def __init__(self, grids, t0):
        self.grids = grids  # dict hora entera (desde t0) -> (U, V)
        self.t0 = t0
        self.x0, self.y0, self.nx, self.ny, _, _ = lr.grid_geometry()
        self.keys = np.array(sorted(grids))

    def t(self, h):
        return (h - self.t0) / pd.Timedelta(hours=1)

    def _grid(self, k):
        if k in self.grids:
            return self.grids[k]
        j = self.keys[np.argmin(np.abs(self.keys - k))]  # hueco: análisis más cercano
        return self.grids[j]

    def at(self, t, x, y):
        k = int(np.floor(t))
        f = t - k
        (U0, V0), (U1, V1) = self._grid(k), self._grid(k + 1)
        i = np.clip(((y - self.y0) // 1000).astype(int), 0, self.ny - 1)
        j = np.clip(((x - self.x0) // 1000).astype(int), 0, self.nx - 1)
        return (1 - f) * U0[i, j] + f * U1[i, j], (1 - f) * V0[i, j] + f * V1[i, j]

    def displacement(self, xs, ys, t_from, t_to):
        """Desplazamiento (dx, dy) y distancia recorrida L de cada fuente entre t_from y t_to (Euler a ≤ 15 min)."""
        n = max(1, int(np.ceil((t_to - t_from) / STEP_H - 1e-9)))
        dt = (t_to - t_from) / n
        x, y = xs.astype(float).copy(), ys.astype(float).copy()
        L = np.zeros(len(xs))
        for s in range(n):
            u, v = self.at(t_from + (s + 0.5) * dt, x, y)
            x += u * dt * 3600
            y += v * dt * 3600
            L += np.maximum(np.hypot(u, v), U_MIN) * dt * 3600
        return x - xs, y - ys, L


def hrrr_grids():
    """Análisis HRRR (tarde + mañana) llevados a la malla de 1 km por vecino más cercano."""
    dss = [xr.open_dataset(RAW / f"hrrr_field/hrrr_field_{START}_{END}.nc"),
           xr.open_dataset(RAW / f"hrrr_field/hrrr_field_manana_{START}_{END}.nc")]
    x0, y0, nx, ny, gx, gy = lr.grid_geometry()
    import geopandas as gpd
    pts = gpd.GeoSeries.from_xy(gx.ravel(), gy.ravel(), crs=lr.UTM).to_crs(4326)
    lat, lon = dss[0].latitude.values, dss[0].longitude.values
    flat = np.c_[lat.ravel(), lon.ravel() * np.cos(np.deg2rad(34))]
    q = np.c_[pts.y.values, pts.x.values * np.cos(np.deg2rad(34))]
    nn = np.argmin(((q[:, None, :] - flat[None, :, :]) ** 2).sum(-1), axis=1)
    out = {}
    for ds in dss:
        for i, t in enumerate(pd.DatetimeIndex(ds.time.values)):
            out[t] = (ds.u10.values[i].ravel()[nn].reshape(ny, nx), ds.v10.values[i].ravel()[nn].reshape(ny, nx))
    return out


def idw_grids(w):
    x0, y0, nx, ny, gx, gy = lr.grid_geometry()
    out = {}
    for h, g in w.groupby("h"):
        if len(g) < 5:
            continue
        d2 = np.maximum((gx[..., None] - g.x.values) ** 2 + (gy[..., None] - g.y.values) ** 2, 500.0 ** 2)
        wt = 1 / d2
        out[h] = ((wt * g.u.values).sum(-1) / wt.sum(-1), (wt * g.v.values).sum(-1) / wt.sum(-1))
    return out


def make_gridwind(grids_by_time):
    t0 = min(grids_by_time)
    return GridWind({int(round((t - t0) / pd.Timedelta(hours=1))): g for t, g in grids_by_time.items()}, t0)


def spatial_puffs(xs, ys, xr_, yr_, gw, t_target, pbl_h, weights_fn, extra_sy):
    """Como `puff._puffs`, pero cada fuente se desplaza con su propia trayectoria por el campo."""
    g = np.zeros((len(xr_), len(xs)))
    c = np.zeros((len(xr_), len(xs)))
    dt = 3600 / puff.SUB_PER_H
    ages = 1 + (np.arange(puff.MAX_AGE_H * puff.SUB_PER_H) + 0.5) / puff.SUB_PER_H
    for a in ages:
        t_rel = t_target - a
        dx, dy, L = gw.displacement(xs, ys, t_rel, t_target)
        w = weights_fn(t_rel)
        sy2 = (0.32 * L / np.sqrt(1 + 0.0004 * L)) ** 2 + (fl.SIGMA_THETA * L) ** 2 + puff.SIGMA0 ** 2 + extra_sy ** 2
        sz = 0.24 * L * np.sqrt(1 + 0.001 * L)
        zeff = np.minimum(np.sqrt(np.pi / 2) * sz, pbl_h)
        r2 = (xr_[:, None] - (xs + dx)[None, :]) ** 2 + (yr_[:, None] - (ys + dy)[None, :]) ** 2
        col = w * dt * np.exp(-r2 / (2 * sy2[None, :])) / (2 * np.pi * sy2[None, :]) * np.exp(-a / puff.TAU_CHEM_H)
        c += col
        g += col / zeff[None, :]
    return g, c


class Transport:
    """Objeto 'traj' que `real_check_linear.build` pasa a `jacobian_hour_puff` (parcheado abajo)."""

    def __init__(self, kind, domain_traj=None, gw=None, pair_field=None, flat=False):
        self.kind, self.domain_traj, self.gw, self.pair_field, self.flat = kind, domain_traj, gw, pair_field, flat


def la_profile(t_abs, flat):
    if flat:
        return 1.0
    return puff.PROFILE.get(lr.to_local(t_abs.floor("h")).hour, 1.0)


def jacobian_hour_la(h, tr, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
    xs_c, ys_c = cells.x.values, cells.y.values
    prof_now = la_profile(h, tr.flat)
    if tr.kind == "domain":
        traj = tr.domain_traj
        u, v = wind_h
        t_target = traj.t(h) + 0.5
        to_abs = lambda t_rel: traj.t0 + pd.Timedelta(hours=float(t_rel))
    else:
        gw = tr.gw
        t_target = gw.t(h) + 0.5
        to_abs = lambda t_rel: gw.t0 + pd.Timedelta(hours=float(t_rel))
        pair = tr.pair_field(h)
    road_w = lambda t_rel: la_profile(to_abs(t_rel), tr.flat)

    blocks = []
    for kind, rows in (("st", nox_h), ("tp", px_h)):
        if not len(rows):
            continue
        if kind == "st":
            sxy = st.loc[rows.id_station.values].geometry
            xr_, yr_, extra = sxy.x.values, sxy.y.values, 0.0
        else:
            xr_, yr_, extra = rows.x.values, rows.y.values, 1300.0
        if tr.kind == "domain":
            reach = max(np.hypot(u, v), U_MIN) * 3600
            gp, cp = plume(xs_p, ys_p, xr_, yr_, u, v, pbl_h, extra_sy=extra, x_max=reach)
            gr, cr = plume(xs_c, ys_c, xr_, yr_, u, v, pbl_h, extra_sy=extra, x_max=reach)
            gp2, cp2 = puff._puffs(xs_p, ys_p, xr_, yr_, traj, t_target, pbl_h, lambda t: 1.0, extra)
            gr2, cr2 = puff._puffs(xs_c, ys_c, xr_, yr_, traj, t_target, pbl_h, road_w, extra)
        else:
            up, vp = pair(xs_p, ys_p, xr_, yr_)
            uc, vc = pair(xs_c, ys_c, xr_, yr_)
            gp, cp = plume(xs_p, ys_p, xr_, yr_, up, vp, pbl_h, extra_sy=extra,
                           x_max=np.maximum(np.hypot(up, vp), U_MIN) * 3600)
            gr, cr = plume(xs_c, ys_c, xr_, yr_, uc, vc, pbl_h, extra_sy=extra,
                           x_max=np.maximum(np.hypot(uc, vc), U_MIN) * 3600)
            gp2, cp2 = spatial_puffs(xs_p, ys_p, xr_, yr_, gw, t_target, pbl_h, lambda t: 1.0, extra)
            gr2, cr2 = spatial_puffs(xs_c, ys_c, xr_, yr_, gw, t_target, pbl_h, road_w, extra)
        if kind == "st":
            f = T_PER_YR_TO_GS * PPB_PER_GM3
            kp = (gp + gp2) * f
            kr = (gr * prof_now + gr2) * cells.w.values * f
        else:
            f = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * ratio
            kp = (cp + cp2) * f
            kr = (cr * prof_now + cr2) * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(9)], 1)
        blocks.append((kind, np.hstack([kp, kr])))
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["puff_domain", "puff_idw", "puff_hrrr", "puff_hrrr_flat"])
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--limit-hours", type=int, default=0, help="solo para pruebas: usar las primeras N horas")
    ap.add_argument("--no-loo", action="store_true")
    a = ap.parse_args()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.SIG_ST, rcl.SIG_TP = 15.0, 5e15

    cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, w, pbl_era5, px, info = lr.la_inputs()
    hfield, hhours, hpbl, _ = lr.load_hrrr()
    wa = w[lr.to_local(w.h).hour.isin(range(12, 18))]
    nst = wa.groupby("h").sid.nunique()
    hours = sorted(set(nox.h) & set(nst[nst >= 8].index) & hhours & set(pbl_era5.dropna().index) & set(hpbl.index))
    if a.limit_hours:
        hours = hours[:a.limit_hours]
    nox, px = nox[nox.h.isin(hours)], px[px.h.isin(hours)]
    wind = wa[wa.h.isin(hours)].groupby("h")[["u", "v"]].mean()
    print(f"LA puffs: horas {len(hours)}, obs NOₓ {len(nox):,}, píxeles TEMPO {len(px):,}, celdas viales {len(cells):,}", flush=True)

    wind_all = w.groupby("h")[["u", "v"]].mean()          # todas las horas, para las trayectorias
    idw_pair = lr.idw_factory(wa[wa.h.isin(hours)])
    gw_idw = make_gridwind(idw_grids(w))
    hgrids = hrrr_grids() if any(md.startswith("puff_hrrr") for md in a.modes) else {pd.Timestamp(START): None}
    gw_hrrr = make_gridwind(hgrids) if any(md.startswith("puff_hrrr") for md in a.modes) else None
    miss = [h for h in hours for k in range(-7, 1) if (h + pd.Timedelta(hours=k)) not in hgrids]
    print(f"HRRR: {len(hgrids)} análisis; horas de trayectoria sin análisis (se usa el más cercano): {len(set(miss))}", flush=True)

    rcl.local_day, rcl.day_type = lr.la_local_day, lr.la_day_type
    rcl.jacobian_hour_puff = jacobian_hour_la
    for mode in a.modes:
        if mode == "puff_domain":
            tr = Transport("domain", domain_traj=puff.Trajectories(wind_all))
        elif mode == "puff_idw":
            tr = Transport("field", gw=gw_idw, pair_field=idw_pair)
        else:
            tr = Transport("field", gw=gw_hrrr, pair_field=hfield, flat=mode.endswith("flat"))
        rcl.Trajectories = lambda *_a, _tr=tr: _tr
        rcl.load_inputs = lambda *_a, **_k: (cand, prior_pt, sd_pt, cells, prior_rd, 0.5 * prior_rd, st, nox, ratio, wind, pbl_era5, px)
        m = rcl.build(START, END, "puff", no_industry=False)
        r = lr.metrics(m, a.boot, loo=not a.no_loo)
        if a.limit_hours:
            print(mode, "prueba", {k: v for k, v in r.items() if isinstance(v, float)}, flush=True)
            continue
        r["info"] = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}
        (INT / f"la_real_la_{mode}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        print(mode, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                     if k not in ("puntuales", "loo_por_estacion", "info")}, flush=True)


if __name__ == "__main__":
    main()
