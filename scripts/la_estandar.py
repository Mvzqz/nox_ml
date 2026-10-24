"""LA con la configuración estándar de la CDMX (control positivo).

Igual que la CDMX (reports/config_final.md), adaptado a LA:
  - transporte: puffs (`la_puff.py`); viento del dominio (el mejor en LA) o, con --wind ml, el de la capa de mezcla
    de HRRR (`la_puff_ml.py`);
  - peso de TEMPO ×1/3 (σ = 3 × 5e15 molec/cm²), como `real_check_linear.TEMPO_SIGMA_MULT = 3`;
  - restricción de cociente por tipo de día (como Infovial en la CDMX, `pinn/invert.ratio_constraint`), con la
    referencia independiente de LA (no hay PeMS ni EMFAC por día de la semana; ver otras_ciudades.md):
      domingo 0.67 ± 0.07: Kim et al. 2016 (inventario CalNex: 410/620 t/d fin de semana/hábil = 0.66) y la caída
      dominical de 30–35 % del NO₂ (superficie y TROPOMI) en LA;
      sábado 0.80 ± 0.08: misma razón sábado/domingo que la caída nacional de NO₂ de TROPOMI (−16 % y −24 %,
      Goldberg et al. 2021) aplicada a la caída dominical de LA;
  - vida química constante de 4 h: la vida por mes y hora (`vida_quimica.py`) está calibrada con O₃, T y HR de SIMAT
    y aún no está validada; en LA solo hay un periodo (nov–dic), donde no cambia la temporada;
  - zonas: --zonas admin = 7 grupos de ciudades (`la_zonas.py`), o 3x3 = la malla original.

Además, con --gemelo, identificabilidad de las zonas: posterior (correlaciones entre zonas) y 30 gemelos con verdad
conocida (α hábil por zona ∈ [0.6, 1.4], sábado y domingo con los cocientes de arriba ± 0.1), con el mismo Jacobiano,
el fondo invertido como verdad del fondo y ruido con las σ de la inversión.

Uso: .venv/bin/python scripts/la_estandar.py --tag NOMBRE [--zonas admin|3x3] [--tempo-mult 3] [--restriccion]
                                            [--wind domain|ml] [--gemelo] [--boot 200]
Salida: data/interim/la/la_estandar_<tag>.json
"""
import argparse
import json

import numpy as np
import pandas as pd

import feasibility_linear as fl
import la_puff as lp
import la_real as lr
import la_zonas as lz
import puff
import real_check_linear as rcl
from feasibility_linear import MOLEC_CM2_PER_GM2, PPB_PER_GM3, T_PER_YR_TO_GS, U_MIN, plume
from la_common import END, INT, START

RATIO_PRIOR = {1: (0.80, 0.08), 2: (0.67, 0.07)}
NREG = 9


def jacobian_hour_zonas(h, tr, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    """`la_puff.jacobian_hour_la` con NREG regiones (en vez de 9 fijas)."""
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
    xs_c, ys_c = cells.x.values, cells.y.values
    prof_now = lp.la_profile(h, tr.flat)
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
    road_w = lambda t_rel: lp.la_profile(to_abs(t_rel), tr.flat)
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
            gp, cp = plume(xs_p, ys_p, xr_, yr_, up, vp, pbl_h, extra_sy=extra, x_max=np.maximum(np.hypot(up, vp), U_MIN) * 3600)
            gr, cr = plume(xs_c, ys_c, xr_, yr_, uc, vc, pbl_h, extra_sy=extra, x_max=np.maximum(np.hypot(uc, vc), U_MIN) * 3600)
            gp2, cp2 = lp.spatial_puffs(xs_p, ys_p, xr_, yr_, gw, t_target, pbl_h, lambda t: 1.0, extra)
            gr2, cr2 = lp.spatial_puffs(xs_c, ys_c, xr_, yr_, gw, t_target, pbl_h, road_w, extra)
        if kind == "st":
            f = T_PER_YR_TO_GS * PPB_PER_GM3
            kp, kr = (gp + gp2) * f, (gr * prof_now + gr2) * cells.w.values * f
        else:
            f = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * ratio
            kp, kr = (cp + cp2) * f, (cr * prof_now + cr2) * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(NREG)], 1)
        blocks.append((kind, np.hstack([kp, kr])))
    return blocks


def ratio_constraint(m, x_ref):
    """Igual que pinn/invert.ratio_constraint: α_dt,r − r_dt·α_hábil,r ≈ 0 con σ = σ_r·α_hábil,r."""
    n_pt, n, nr = m["n_pt"], m["n"], m["n_reg"]
    E = np.zeros((n, n))
    for dt, (r, sd) in RATIO_PRIOR.items():
        for i in range(nr):
            g = np.zeros(n)
            g[n_pt + nr * dt + i] = 1.0
            g[n_pt + i] = -r
            E += np.outer(g, g) / (sd * max(x_ref[n_pt + i], 0.1)) ** 2
    return E


_solve0 = rcl.solve


def solve_with_E(m, weights=None, drop_station=None):
    N, b = _solve0(m, weights=weights, drop_station=drop_station)
    return (N + m["E"], b) if m.get("E") is not None else (N, b)


def gemelo(m, n_rep=30, seed=5):
    """Identificabilidad de las zonas viales: correlaciones posteriores y gemelos con verdad conocida."""
    rng = np.random.default_rng(seed)
    n_pt, nr, n = m["n_pt"], m["n_reg"], m["n"]
    N, b = rcl.solve(m)
    S = np.linalg.inv(N)
    x_hat = S @ b
    ii = n_pt + np.arange(nr)
    sd = np.sqrt(np.diag(S)[ii])
    C = S[np.ix_(ii, ii)] / np.outer(sd, sd)
    off = C[~np.eye(nr, dtype=bool)]
    errs, rat = [], []
    for _ in range(n_rep):
        xt = x_hat.copy()
        a = rng.uniform(0.6, 1.4, nr)
        xt[ii] = a
        xt[n_pt + nr + np.arange(nr)] = a * (RATIO_PRIOR[1][0] + rng.uniform(-0.1, 0.1))
        xt[n_pt + 2 * nr + np.arange(nr)] = a * (RATIO_PRIOR[2][0] + rng.uniform(-0.1, 0.1))
        # observaciones sintéticas con el mismo Jacobiano y las σ de la inversión
        bsyn = (m["xa"] / m["sa"] ** 2).copy()
        for s, h, idx, kr, _ in m["st_rows"]:
            sig = rcl.SIG_ST * (rcl.EST_FACTOR if s in m["est_ids"] else 1.0)
            y = kr @ xt[idx] + rng.normal(0, sig)
            bsyn[idx] += kr * y / sig ** 2
        for idx, Kf, _ in m["tp_rows"]:
            y = Kf @ xt[idx] + rng.normal(0, rcl.SIG_TP_BASE, len(Kf))   # ruido por píxel; el ×3 es representación
            bsyn[idx] += Kf.T @ y / rcl.SIG_TP ** 2
        xs = np.linalg.solve(N, bsyn)
        errs.append(np.abs(xs[ii] / a - 1))
        tot_t = rcl.road_totals(m, xt)
        tot_s = rcl.road_totals(m, xs)
        rat.append([tot_s[2] / tot_s[0] - tot_t[2] / tot_t[0], tot_s.sum() / tot_t.sum() - 1])
    errs, rat = np.array(errs), np.array(rat)
    return {"corr_post_max_abs": float(np.abs(off).max()), "corr_post_mediana_abs": float(np.median(np.abs(off))),
            "sd_post_alfa_habil": sd.round(3).tolist(),
            "error_mediano_alfa_habil_por_zona": np.median(errs, 0).round(3).tolist(),
            "error_domingo_abs_mediano": float(np.median(np.abs(rat[:, 0]))),
            "error_total_vial_mediano": float(np.median(np.abs(rat[:, 1])))}


def main():
    global NREG
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--zonas", choices=["admin", "3x3"], default="admin")
    ap.add_argument("--tempo-mult", type=float, default=3.0)
    ap.add_argument("--restriccion", action="store_true")
    ap.add_argument("--wind", choices=["domain", "ml"], default="domain")
    ap.add_argument("--gemelo", action="store_true")
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    rcl.SIG_ST, rcl.SIG_TP_BASE = 15.0, 5e15
    rcl.SIG_TP = rcl.SIG_TP_BASE * a.tempo_mult
    rcl.SUPEROBS_KM = 0.0
    puff.LOSS_RATE = None
    puff.TAU_CHEM_H, puff.MAX_AGE_H = 4.0, 6

    cand, prior_pt, sd_pt, cells, prior_rd, st, nox, ratio, w, pbl_era5, px, info = lr.la_inputs()
    if a.zonas == "admin":
        cells = cells.copy()
        cells["region"] = lz.assign(cells, lz.zones())
        NREG = len(lz.ZONAS)
        prior_rd = cells.groupby("region").w.sum().reindex(range(NREG)).fillna(0).values
    else:
        NREG = 9
    _, hhours, hpbl, _ = lr.load_hrrr()
    wa = w[lr.to_local(w.h).hour.isin(range(12, 18))]
    nst = wa.groupby("h").sid.nunique()
    hours = sorted(set(nox.h) & set(nst[nst >= 8].index) & hhours & set(pbl_era5.dropna().index) & set(hpbl.index))
    if a.wind == "domain":
        tr = lp.Transport("domain", domain_traj=puff.Trajectories(w.groupby("h")[["u", "v"]].mean()))
    else:
        import la_puff_ml as lpm
        grids = lpm.ml_fields()
        hours = [h for h in hours if h in grids and h + pd.Timedelta(hours=1) in grids]
        tr = lp.Transport("field", gw=lp.make_gridwind(grids), pair_field=lpm.pair_from_grids(grids))
    nox, px = nox[nox.h.isin(hours)], px[px.h.isin(hours)]
    wind = wa[wa.h.isin(hours)].groupby("h")[["u", "v"]].mean()
    print(f"[{a.tag}] zonas {a.zonas} ({NREG}), TEMPO ×{a.tempo_mult:g}, restricción {a.restriccion}, viento {a.wind}; "
          f"horas {len(hours)}, obs NOₓ {len(nox):,}, píxeles TEMPO {len(px):,}", flush=True)
    rcl.local_day, rcl.day_type = lr.la_local_day, lr.la_day_type
    rcl.jacobian_hour_puff = jacobian_hour_zonas
    rcl.Trajectories = lambda *_a: tr
    rcl.load_inputs = lambda *_a, **_k: (cand, prior_pt, sd_pt, cells, prior_rd, 0.5 * prior_rd, st, nox, ratio, wind, pbl_era5, px)
    m = rcl.build(START, END, "puff", no_industry=False)
    rcl.solve = solve_with_E
    if a.restriccion:
        N, b = _solve0(m)
        m["E"] = ratio_constraint(m, np.linalg.solve(N, b))
    r = lr.metrics(m, a.boot)
    N, b = rcl.solve(m)
    S = np.linalg.inv(N)
    x = S @ b
    names = lz.ZONAS if a.zonas == "admin" else [str(i) for i in range(9)]
    r["zonas"] = {nm: {"prior_t_anio": float(prior_rd[i]), "alfa_habil": float(x[m["n_pt"] + i]),
                       "sd": float(np.sqrt(S[m["n_pt"] + i, m["n_pt"] + i])),
                       "domingo": float(x[m["n_pt"] + 2 * NREG + i] / x[m["n_pt"] + i])}
                  for i, nm in enumerate(names)}
    r["config"] = dict(zonas=a.zonas, n_zonas=NREG, tempo_mult=a.tempo_mult, restriccion=RATIO_PRIOR if a.restriccion else None,
                       viento=a.wind, vida_quimica_h=4.0)
    if a.gemelo:
        r["gemelo"] = gemelo(m)
    r["info"] = {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in info.items()}
    (INT / f"la_estandar_{a.tag}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
    print(a.tag, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                  if k not in ("puntuales", "loo_por_estacion", "info", "zonas")}, flush=True)


if __name__ == "__main__":
    main()
