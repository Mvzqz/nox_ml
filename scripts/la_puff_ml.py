"""LA: puffs con el viento HRRR de la capa de mezcla (`la_hrrr_ml.py`) en lugar del de 10 m.

Misma configuración y mismas métricas que `la_puff.py` (σθ = 30°, σ estaciones 15 ppb, σ TEMPO 5e15, vial 3×3 ×
tipo de día, perfil horario supuesto), para comparar directamente con `la_real_la_puff_{domain,idw,hrrr}.json`:

  puff_hrrr_ml      = trayectorias y pluma de la hora actual con el viento medio 10 m → capa límite de HRRR;
  puff_hrrr_ml_dir  = dirección de la capa de mezcla con la rapidez del viento a 10 m (separa el efecto de la
                      dirección del de la rapidez, que en la capa de mezcla es ~50 % mayor).

Uso: .venv/bin/python scripts/la_puff_ml.py [--boot 200] [--modes puff_hrrr_ml puff_hrrr_ml_dir]
Salida: data/interim/la/la_real_la_<modo>.json
"""
import argparse
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

import feasibility_linear as fl
import la_puff as lp
import la_real as lr
import puff
import real_check_linear as rcl
from la_common import END, INT, RAW, START

ML_NC = RAW / f"hrrr_field/hrrr_ml_{START}_{END}.nc"


def ml_fields(dir_only=False):
    """Campos de 1 km por hora de validez: (U, V) de la capa de mezcla (o su dirección con la rapidez de 10 m)."""
    ds = xr.open_dataset(ML_NC)
    x0, y0, nx, ny, gx, gy = lr.grid_geometry()
    pts = gpd.GeoSeries.from_xy(gx.ravel(), gy.ravel(), crs=lr.UTM).to_crs(4326)
    flat = np.c_[ds.latitude.values.ravel(), ds.longitude.values.ravel() * np.cos(np.deg2rad(34))]
    q = np.c_[pts.y.values, pts.x.values * np.cos(np.deg2rad(34))]
    nn = np.argmin(((q[:, None, :] - flat[None, :, :]) ** 2).sum(-1), axis=1)
    out = {}
    for i, t in enumerate(pd.DatetimeIndex(ds.time.values)):
        u, v = ds.u_ml.values[i].ravel()[nn], ds.v_ml.values[i].ravel()[nn]
        if dir_only:
            s10 = np.hypot(ds.u10.values[i].ravel()[nn], ds.v10.values[i].ravel()[nn])
            s = np.maximum(np.hypot(u, v), 1e-6)
            u, v = u / s * s10, v / s * s10
        out[t] = (u.reshape(ny, nx), v.reshape(ny, nx))
    return out


def pair_from_grids(grids):
    """Viento por par fuente–receptor para la hora AQS [h, h+1): promedio de los análisis h y h+1 (como load_hrrr)."""
    x0, y0, nx, ny, _, _ = lr.grid_geometry()

    def field(h):
        (u0, v0), (u1, v1) = grids[h], grids[h + pd.Timedelta(hours=1)]
        return lr.pair_function((u0 + u1) / 2, (v0 + v1) / 2, x0, y0, nx, ny)
    return field


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["puff_hrrr_ml", "puff_hrrr_ml_dir"])
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.SIG_ST, rcl.SIG_TP = 15.0, 5e15
    rcl.SUPEROBS_KM = 0.0

    cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, w, pbl_era5, px, info = lr.la_inputs()
    _, hhours, hpbl, _ = lr.load_hrrr()
    wa = w[lr.to_local(w.h).hour.isin(range(12, 18))]
    nst = wa.groupby("h").sid.nunique()
    hours = sorted(set(nox.h) & set(nst[nst >= 8].index) & hhours & set(pbl_era5.dropna().index) & set(hpbl.index))
    nox, px = nox[nox.h.isin(hours)], px[px.h.isin(hours)]
    wind = wa[wa.h.isin(hours)].groupby("h")[["u", "v"]].mean()
    print(f"LA puffs capa de mezcla: horas {len(hours)}, obs NOₓ {len(nox):,}, píxeles TEMPO {len(px):,}", flush=True)
    rcl.local_day, rcl.day_type = lr.la_local_day, lr.la_day_type
    rcl.jacobian_hour_puff = lp.jacobian_hour_la
    for mode in a.modes:
        grids = ml_fields(dir_only=mode.endswith("_dir"))
        miss = [h for h in hours if h not in grids or h + pd.Timedelta(hours=1) not in grids]
        if miss:
            print(f"{mode}: {len(miss)} horas sin análisis de capa de mezcla; se excluyen", flush=True)
        hrs = [h for h in hours if h not in miss]
        tr = lp.Transport("field", gw=lp.make_gridwind(grids), pair_field=pair_from_grids(grids))
        rcl.Trajectories = lambda *_a, _tr=tr: _tr
        nx_, px_ = nox[nox.h.isin(hrs)], px[px.h.isin(hrs)]
        rcl.load_inputs = lambda *_a, **_k: (cand, prior_pt, sd_pt, cells, prior_rd, 0.5 * prior_rd, st, nx_, ratio,
                                              wind.loc[hrs], pbl_era5, px_)
        m = rcl.build(START, END, "puff", no_industry=False)
        r = lr.metrics(m, a.boot)
        r["info"] = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}
        (INT / f"la_real_la_{mode}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        print(mode, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                     if k not in ("puntuales", "loo_por_estacion", "info")}, flush=True)


if __name__ == "__main__":
    main()
