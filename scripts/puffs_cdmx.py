"""CDMX: pluma estacionaria frente a puffs (transporte dependiente del tiempo) con la configuración actual.

Motivación: en LA lo que mejoró la inversión fueron los puffs, no un viento mejor (otras_ciudades.md, «Puffs + HRRR»).
En la CDMX los puffs se habían probado con σθ = 15°, TEMPO ×1 y sin restricción (RESUMEN.md) y empeoraban las
estaciones (LOO 14.1 → 15.1) aunque mejoraban TEMPO (0.74 → 0.83). Aquí se repite con la configuración actual:
σθ = 30°, σ de TEMPO ×3, restricción de cociente de Infovial (sábado 0.87, domingo 0.69, σ 0.02), a priori de
centrales de Climate TRACE (Valle 1,600 ± 650, Nonoalco 100 ± 100), capa límite ERA5 + MERRA-2, sin clústeres
industriales y con estaciones extra (como scripts/pinn/invert.py).

Modos:
  plume              pluma estacionaria con el vector medio del dominio (estándar actual)
  puff               puffs (puff.py) con el vector medio del dominio, perfil horario supuesto puff.PROFILE, vida 4 h
  puff_idw           puffs que viajan por el campo IDW de las estaciones (malla 1 km, como la_puff.py)
  puff_infovial      puff con el perfil horario de Infovial (emisión ponderada por clase, por tipo de día)
  puff_plano         puff sin perfil horario (emisión vial constante)
  puff_tau2 / puff_tau8   puff con vida química de 2 h / 8 h

Métricas: las de la_real.metrics (LOO modelo/IDW/híbrido con descomposición sesgo/hora a hora, r con emisión fija,
estimador normalizado con placebo, CV de hábiles, puntuales) con la restricción, más el domingo libre (sin
restricción) con bootstrap y un diagnóstico por hora local.

Uso: .venv/bin/python scripts/puffs_cdmx.py --period nov23 --modes plume puff puff_idw [--boot 200]
     .venv/bin/python scripts/puffs_cdmx.py --report
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import feasibility_linear as fl
import puff
import real_check_linear as rcl
import la_real as lr
from config import LAT, LON, UTM
from feasibility_linear import MOLEC_CM2_PER_GM2, PPB_PER_GM3, T_PER_YR_TO_GS, U_MIN, plume
from la_puff import GridWind, spatial_puffs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/puffs_cdmx"
PERIODS = {"nov23": ("2023-11-01", "2023-12-31"), "prim24": ("2024-02-15", "2024-05-31")}
PERIOD_LABEL = {"nov23": "nov–dic 2023", "prim24": "feb–may 2024"}
RATIO_PRIOR = {1: (0.87, 0.02), 2: (0.69, 0.02)}            # igual que scripts/pinn/invert.py
NEW_PRIORS = {"Valle de México": (1600.0, 650.0), "Nonoalco": (100.0, 100.0)}  # centrales_generacion.md
EMIS_W = [1, 2, 5, 10, 15, 20]                                # pesos de emisión por clase C1…C6 (mejoras.md)
rng = np.random.default_rng(5)


# ---------------------------------------------------------------- perfiles horarios de emisión vial
def infovial_profile():
    """Perfil horario por tipo de día (hábil, sábado, domingo), emisión ponderada por clase, media diaria = 1."""
    f = OUT / "perfil_infovial.json"
    if f.exists():
        return {int(k): {int(h): v for h, v in d.items()} for k, d in json.loads(f.read_text()).items()}
    d = pd.read_csv(ROOT / "data/raw/trafico/infovial_201701_clasificacion.csv",
                    usecols=["fecha", "hora", "tipo_vehiculo", "cantidad"])
    d["fecha"] = pd.to_datetime(d.fecha)
    d = d[~d.fecha.isin(pd.to_datetime(["2017-01-01", "2017-01-02"]))]
    d["hr"] = d.hora.str[:2].astype(int)
    dow = d.fecha.dt.dayofweek
    d["dt"] = np.select([dow == 6, dow == 5], [2, 1], 0)
    g = d.groupby(["dt", "fecha", "hr", "tipo_vehiculo"]).cantidad.sum().reset_index()
    g = g.groupby(["dt", "hr", "tipo_vehiculo"]).cantidad.mean().unstack()
    e = (g[[f"C{i}" for i in range(1, 7)]] * EMIS_W).sum(1).unstack(0)   # filas hora, columnas tipo de día
    prof = {int(dt): {int(h): float(e.loc[h, dt] / e[dt].mean()) for h in e.index} for dt in e.columns}
    OUT.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(prof, indent=1))
    return prof


def profile_fn(kind):
    """Devuelve f(h_utc) -> factor de emisión vial (h = inicio de hora UTC)."""
    if kind == "plano":
        return lambda h: 1.0
    if kind == "infovial":
        prof = infovial_profile()
        return lambda h: prof[rcl.day_type(h)][(h + pd.Timedelta(hours=-6)).hour]
    return lambda h: puff.PROFILE.get((h + pd.Timedelta(hours=-6)).hour, 1.0)


# ---------------------------------------------------------------- campo IDW en malla para las trayectorias
def grid_geom():
    import geopandas as gpd
    x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    gx, gy = np.meshgrid(x0 + 500 + 1000 * np.arange(nx), y0 + 500 + 1000 * np.arange(ny))
    return x0, y0, nx, ny, gx, gy


class GridWindMX(GridWind):
    def __init__(self, grids, t0, geom):
        self.grids, self.t0 = grids, t0
        self.x0, self.y0, self.nx, self.ny = geom
        self.keys = np.array(sorted(grids))


def idw_gridwind(by_station, st, hours):
    x0, y0, nx, ny, gx, gy = grid_geom()
    need = sorted({h + pd.Timedelta(hours=k) for h in hours for k in range(-8, 2)})
    by = by_station[by_station.h.isin(need) & by_station.id_station.isin(st.index)]
    t0 = need[0]
    grids = {}
    for h, g in by.groupby("h"):
        if len(g) < 5:
            continue
        sx, sy = st.loc[g.id_station].geometry.x.values, st.loc[g.id_station].geometry.y.values
        w = 1 / np.maximum((gx[..., None] - sx) ** 2 + (gy[..., None] - sy) ** 2, 500.0 ** 2)
        grids[int(round((h - t0) / pd.Timedelta(hours=1)))] = ((w * g.u.values).sum(-1) / w.sum(-1),
                                                                (w * g.v.values).sum(-1) / w.sum(-1))
    return GridWindMX(grids, t0, (x0, y0, nx, ny))


# ---------------------------------------------------------------- Jacobiano con puffs
class Transport:
    def __init__(self, kind, prof, traj=None, gw=None, pair_field=None):
        self.kind, self.prof, self.traj, self.gw, self.pair_field = kind, prof, traj, gw, pair_field


def jacobian_puff_mx(h, tr, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
    xs_c, ys_c = cells.x.values, cells.y.values
    clock = tr.traj if tr.kind == "domain" else tr.gw
    t_target = clock.t(h) + 0.5
    prof_now = tr.prof(h)
    road_w = lambda t_rel: tr.prof(clock.t0 + pd.Timedelta(hours=float(np.floor(t_rel))))
    if tr.kind != "domain":
        pair = tr.pair_field(h)
    u, v = wind_h
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
            reach = float(fl.speed(np.hypot(u, v))) * 3600
            gp, cp = plume(xs_p, ys_p, xr_, yr_, u, v, pbl_h, extra_sy=extra, x_max=reach)
            gr, cr = plume(xs_c, ys_c, xr_, yr_, u, v, pbl_h, extra_sy=extra, x_max=reach)
            gp2, cp2 = puff._puffs(xs_p, ys_p, xr_, yr_, tr.traj, t_target, pbl_h, lambda t: 1.0, extra)
            gr2, cr2 = puff._puffs(xs_c, ys_c, xr_, yr_, tr.traj, t_target, pbl_h, road_w, extra)
        else:
            up, vp = pair(xs_p, ys_p, xr_, yr_)
            uc, vc = pair(xs_c, ys_c, xr_, yr_)
            gp, cp = plume(xs_p, ys_p, xr_, yr_, up, vp, pbl_h, extra_sy=extra, x_max=fl.speed(np.hypot(up, vp)) * 3600)
            gr, cr = plume(xs_c, ys_c, xr_, yr_, uc, vc, pbl_h, extra_sy=extra, x_max=fl.speed(np.hypot(uc, vc)) * 3600)
            gp2, cp2 = spatial_puffs(xs_p, ys_p, xr_, yr_, tr.gw, t_target, pbl_h, lambda t: 1.0, extra)
            gr2, cr2 = spatial_puffs(xs_c, ys_c, xr_, yr_, tr.gw, t_target, pbl_h, road_w, extra)
        if kind == "st":
            f = T_PER_YR_TO_GS * PPB_PER_GM3
            kp, kr = (gp + gp2) * f, (gr * prof_now + gr2) * cells.w.values * f
        else:
            f = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * ratio
            kp, kr = (cp + cp2) * f, (cr * prof_now + cr2) * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(fl.n_reg(cells))], 1)
        blocks.append((kind, np.hstack([kp, kr])))
    return blocks


# ---------------------------------------------------------------- restricción de cociente (como invert.py)
def ratio_constraint(m, x_ref):
    n_pt, n, nr = m["n_pt"], m["n"], m["n_reg"]
    E = np.zeros((n, n))
    for dt, (r, sd) in RATIO_PRIOR.items():
        for i in range(nr):
            g = np.zeros(n)
            g[n_pt + nr * dt + i] = 1.0
            g[n_pt + i] = -r
            E += np.outer(g, g) / (sd * max(x_ref[n_pt + i], 0.1)) ** 2
    return E


_orig_solve = rcl.solve


def solve_e(m, weights=None, drop_station=None):
    N, b = _orig_solve(m, weights=weights, drop_station=drop_station)
    if m.get("E") is not None:
        N = N + m["E"]
    return N, b


rcl.solve = solve_e


def free_sunday(m, boot):
    N, b = rcl.solve(m)
    x = np.linalg.solve(N, b)
    tot = rcl.road_totals(m, x)
    days = sorted({d for d, *_ in m["blocks"]})
    bs = []
    for _ in range(boot):
        pick = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick]).groupby(level=0).sum().to_dict()
        Nb, bb = rcl.solve(m, weights=wts)
        t = rcl.road_totals(m, np.linalg.solve(Nb, bb))
        bs.append(t[2] / t[0])
    return x, {"domingo_libre": float(tot[2] / tot[0]), "domingo_libre_ic": np.percentile(bs, [5, 95]).tolist(),
               "sabado_libre": float(tot[1] / tot[0]), "vial_habil_libre": float(tot[0])}


def hour_diag(m, x):
    """Por hora local: media observada, modelo con emisión fija, modelo invertido, y r día a día."""
    n_pt, nr = m["n_pt"], m["n_reg"]
    rows = []
    for s, h, idx, kr, yy in m["st_rows"]:
        if s in m["est_ids"]:
            continue
        rows.append((h, (h - pd.Timedelta(hours=6)).hour, yy, float(kr[:n_pt] @ m["prior_pt"] + kr[n_pt:n_pt + nr].sum()),
                     float(kr @ x[idx]), float(kr[n_pt:n_pt + nr] @ x[idx][n_pt:n_pt + nr])))
    d = pd.DataFrame(rows, columns=["h", "hl", "obs", "fija", "inv", "vial_inv"])
    out = {}
    for hl, g in d.groupby("hl"):
        hm = g.groupby("h")[["obs", "fija"]].mean()
        out[int(hl)] = {"obs": float(g.obs.mean()), "fija": float(g.fija.mean()), "inv": float(g.inv.mean()),
                        "vial_inv": float(g.vial_inv.mean()), "rmse_inv": float(np.sqrt(((g.inv - g.obs) ** 2).mean())),
                        "r_fija_dias": float(hm.obs.corr(hm.fija))}
    return out


# ---------------------------------------------------------------- corrida
def run(period, modes, boot, tag=""):
    """tag: sufijo del archivo de salida (p. ej. el esquema de regiones, config_final.py)."""
    start, end = PERIODS[period]
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.set_tempo_weight(3, 0)
    t0 = time.time()
    inp = list(fl.load_inputs(start, end, extras=True))
    cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
    for nm, (p, s) in NEW_PRIORS.items():
        i = next(i for i, c in enumerate(cand.nombre) if nm in c)
        prior_pt[i], sd_pt[i] = p, s
    inp[1], inp[2] = prior_pt, sd_pt
    st, wind, pbl, nox = inp[6], inp[9], inp[10], inp[7]
    rcl.load_inputs = lambda *_a, **_k: tuple(inp)
    print(f"[{period}] datos cargados en {time.time() - t0:.0f} s; {nox.h.nunique()} horas", flush=True)
    hours = sorted(set(nox.h) & set(wind.index) & set(pbl.index))
    OUT.mkdir(parents=True, exist_ok=True)
    gw = None
    for mode in modes:
        t1 = time.time()
        puff.TAU_CHEM_H = {"puff_tau2": 2.0, "puff_tau8": 8.0}.get(mode, 4.0)
        prof = profile_fn({"puff_infovial": "infovial", "puff_plano": "plano"}.get(mode, "supuesto"))
        if mode == "plume":
            m = rcl.build(start, end, "domain", no_industry=True, extras=True)
        else:
            if mode == "puff_idw":
                gw = gw or idw_gridwind(wind.attrs["by_station"], st, hours)
                tr = Transport("field", prof, gw=gw, pair_field=rcl.wind_field_factory(st, wind.attrs["by_station"]))
            else:
                tr = Transport("domain", prof, traj=puff.Trajectories(wind))
            rcl.Trajectories = lambda *_a, _tr=tr: _tr
            rcl.jacobian_hour_puff = jacobian_puff_mx
            m = rcl.build(start, end, "puff", no_industry=True, extras=True)
        tb = time.time() - t1
        m.pop("E", None)
        x0, free = free_sunday(m, boot)
        m["E"] = ratio_constraint(m, x0)
        r = lr.metrics(m, boot)
        N, b = rcl.solve(m)
        x = np.linalg.solve(N, b)
        r.update(free)
        r["por_hora"] = hour_diag(m, x)
        # identificabilidad de las regiones viales: correlación a posteriori entre los α hábiles
        nr, n_pt = m["n_reg"], m["n_pt"]
        S = np.linalg.inv(N)[n_pt:n_pt + nr, n_pt:n_pt + nr]
        sd = np.sqrt(np.diag(S))
        C = S / np.outer(sd, sd)
        r["regiones"] = fl.region_names()
        r["alfa_habil"], r["alfa_habil_sd"] = x[n_pt:n_pt + nr].tolist(), sd.tolist()
        r["corr_regiones"] = C.tolist()
        r["corr_regiones_min"] = float(C[np.triu_indices(nr, 1)].min())
        r["segundos_jacobiano"], r["segundos_total"] = tb, time.time() - t1
        (OUT / f"{period}_{mode}{tag}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        print(f"[{period}] {mode}{tag} ({time.time() - t1:.0f} s):",
              {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
               if k not in ("puntuales", "loo_por_estacion", "por_hora", "corr_regiones", "alfa_habil", "alfa_habil_sd", "regiones")}, flush=True)


# ---------------------------------------------------------------- reporte (tablas)
MODE_LABEL = {"plume": "Pluma estacionaria (estándar)", "puff": "Puffs, viento del dominio", "puff_idw": "Puffs, viento IDW",
              "puff_infovial": "Puffs + perfil Infovial", "puff_plano": "Puffs sin perfil horario",
              "puff_tau2": "Puffs, vida química 2 h", "puff_tau8": "Puffs, vida química 8 h"}


def tables():
    lines = []
    f2 = lambda v: f"{v:.2f}"
    for period in PERIODS:
        res = {md: json.loads((OUT / f"{period}_{md}.json").read_text()) for md in MODE_LABEL if (OUT / f"{period}_{md}.json").exists()}
        if not res:
            continue
        lines += [f"\n### {PERIOD_LABEL[period]}\n",
                  "| Transporte | LOO modelo / IDW / híbrido (ppb) | Sesgo / hora a hora del modelo | Híbrido < IDW | "
                  "r fija estaciones (hora / espacial) | r fija TEMPO (global / por escaneo) | r TEMPO invertido | Vial hábil / inventario |",
                  "|---|---|---|---|---|---|---|---|"]
        for md, r in res.items():
            lines.append(f"| {MODE_LABEL[md]} | {r['loo_model']:.1f} / {r['loo_idw']:.1f} / {r['loo_hybrid']:.1f} | "
                         f"{r['loo_sesgo_model']:.1f} / {r['loo_hora_model']:.1f} | {r['hibrido_gana']} | "
                         f"{f2(r['fija_r_est_hora'])} / {f2(r['fija_r_est_espacial'])} | "
                         f"{f2(r['fija_r_tempo_global'])} / {f2(r['fija_r_tempo_por_hora_mediana'])} | {f2(r['muestra_r_tempo'])} | "
                         f"{r['vial_habil'] / r['vial_apriori']:.0%} |")
        lines += ["", "| Transporte | Domingo/hábil libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | "
                  "CV hábiles normalizado / crudo | Valle | Nonoalco | AICM | AIFA |", "|---|---|---|---|---|---|---|---|---|---|"]
        for md, r in res.items():
            p = r["puntuales"]
            pt = lambda k: next(f"{v[0]:,.0f} ± {v[1]:,.0f}" for nm, v in p.items() if k in nm)
            lo, hi = r["domingo_libre_ic"]
            nlo, nhi = r["norm_domingo_ic"]
            lines.append(f"| {MODE_LABEL[md]} | {r['domingo_libre']:.2f} ({lo:.2f}–{hi:.2f}) | {r['domingo']:.2f} | "
                         f"{r['norm_domingo']:.2f} ({nlo:.2f}–{nhi:.2f}) | {r['placebo_mitad_ancho']:.2f} | "
                         f"{r['norm_cv_habiles']:.2f} / {r['crudo_cv_habiles']:.2f} | {pt('Valle')} | {pt('Nonoalco')} | "
                         f"{pt('AICM')} | {pt('AIFA')} |")
        lines += ["", "Por hora local (ppb; media en estaciones con NOₓ medido): observado, modelo con emisión fija (a priori), "
                  "modelo invertido, y r día a día del modelo fijo.\n",
                  "| Transporte | " + " | ".join(f"{h}–{h + 1} h" for h in range(11, 17)) + " |", "|---|" + "---|" * 6]
        for md, r in res.items():
            ph = r["por_hora"]
            cells = []
            for h in range(11, 17):  # hora local de inicio (SIMAT la etiqueta al final: 12–17 h)
                q = ph.get(str(h))
                cells.append("–" if q is None else f"{q['obs']:.0f} / {q['fija']:.0f} / {q['inv']:.0f} / r {q['r_fija_dias']:.2f}")
            lines.append(f"| {MODE_LABEL[md]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=list(PERIODS), default="nov23")
    ap.add_argument("--modes", nargs="+", default=["plume", "puff", "puff_idw"])
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        print(tables())
        return
    run(a.period, a.modes, a.boot)


if __name__ == "__main__":
    main()
