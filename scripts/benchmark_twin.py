"""Banco datos-vs-desempeño, parte 1: gemelos con datos degradados (reports/banco_datos.md).

Base (CDMX, nov–dic 2023): puffs con el viento del dominio, vida química constante de 4 h y puffs de 6 h, σθ = 30°,
TEMPO ×1/3, zonas admin_grupos (13), restricción de cociente de Infovial, a priori de centrales de Climate TRACE,
sin clústeres industriales, estaciones extra (como zonas_admin_twin.py). La vida química no cambia la
identificabilidad del gemelo (la verdad y la inversión usan la misma), así que se usa la vida fija, más barata.

Dos verdades:
  ideal      α por zona ~ LN(0, 0.3), sábado/domingo = α·0.87/0.69·LN(0, 0.03), fondo uniforme por hora
             (la de zonas_admin_twin.py; solo el viento tiene error)
  realista   α por MUNICIPIO ~ LN(0, 0.3) (error de distribución espacial dentro de cada zona), sábado/domingo con
             cociente global 0.87/0.69·LN(0, 0.08) y por municipio ·LN(0, 0.05) (la referencia de tráfico no es
             exacta), y un gradiente de fondo por hora (plano con pendiente N(0, 2 ppb) y N(0, 10¹⁵) por 20 km)
             que la inversión, con fondo uniforme, no representa.
Ambas: observaciones con el viento rotado (AR(1) por hora, ρ = 0.8) con σ = 0, 15, 30 o 45°, ruido de 15 ppb
(×1.5 en NO₂ estimado) y 5·10¹⁵ en TEMPO; inversión siempre con el viento sin rotar.

Degradaciones (con σ = 30°, el error medido en la CDMX): sin TEMPO; sin restricción de tráfico; 15 y 9 estaciones de
NOₓ (sin las extras de NO₂; 5 subconjuntos al azar), con y sin TEMPO.
Métricas (mediana de N_DRAWS verdades): error por zona |Ê/E − 1| del día hábil, error del total, error del cociente
domingo/hábil, error del cociente CDMX/Edomex; σ a posteriori relativa (σ/0.5) y |corr| máxima entre zonas.

Uso: .venv/bin/python scripts/benchmark_twin.py      Salida: data/interim/benchmark/twin.json
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.linalg import cho_factor, cho_solve

import benchmark_common as bc
import feasibility_linear as fl
import puff
import puffs_cdmx as pc
import zonas_admin_twin as zat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/benchmark"
CACHE = OUT / "cache"
N_DRAWS = 40
SIGMAS = [0, 15, 30, 45]
N_SUB_SEEDS = 5
CDMX_ZONES = 5  # las 5 primeras zonas de admin_grupos son de la CDMX


def build_cached(tag, period, scheme, z=None, sig=0):
    """Construye (o lee de caché) las filas dispersas de un Jacobiano con el viento rotado σ·z."""
    f = CACHE / f"{tag}.npz"
    meta_f = CACHE / f"{tag}.json"
    start, end, inp = zat.setup(period, scheme)
    puff.MAX_AGE_H, puff.LOSS_RATE, puff.TAU_CHEM_H = 6, None, 4.0
    puff._loss_cache.clear()
    if f.exists():
        d = np.load(f, allow_pickle=True)
        meta = json.loads(meta_f.read_text())
        R = dict(Gs=sp.csr_matrix((d["gs_data"], d["gs_ind"], d["gs_ptr"]), shape=tuple(d["gs_shape"])),
                 Gt=sp.csr_matrix((d["gt_data"], d["gt_ind"], d["gt_ptr"]), shape=tuple(d["gt_shape"])),
                 sid=d["sid"], h=np.array(list(pd.to_datetime(d["h"]))), ys=d["ys"], yt=d["yt"], est=d["est"])
        m = {k: (np.array(v) if isinstance(v, list) else v) for k, v in meta.items()}
        m["hours"] = [pd.Timestamp(t) for t in meta["hours"]]
        m["est_ids"] = set(meta["est_ids"])
        return m, R, inp
    wind = inp[9] if not sig else bc.rotate_wind(inp[9], z, sig)
    t0 = time.time()
    m = zat.build(start, end, inp, wind)
    R = bc.sparse_rows(m)
    print(f"  [{tag}] Jacobiano en {time.time() - t0:.0f} s", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f, gs_data=R["Gs"].data, gs_ind=R["Gs"].indices, gs_ptr=R["Gs"].indptr, gs_shape=R["Gs"].shape,
                        gt_data=R["Gt"].data, gt_ind=R["Gt"].indices, gt_ptr=R["Gt"].indptr, gt_shape=R["Gt"].shape,
                        sid=R["sid"], h=np.array([str(t) for t in R["h"]]), ys=R["ys"], yt=R["yt"], est=R["est"])
    meta = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in m.items()
            if k in ("n", "n_pt", "n_reg", "xa", "sa", "prior_pt", "prior_rd")}
    meta["hours"] = [str(t) for t in m["hours"]]
    meta["est_ids"] = sorted(m["est_ids"])
    meta_f.write_text(json.dumps(meta))
    return dict(m, est_ids=m["est_ids"]), R, inp


def tempo_xy(inp, hours):
    px = inp[11]
    xy = [px[px.h == h][["x", "y"]].values for h in hours]
    return np.vstack([a for a in xy if len(a)])


def main():
    t00 = time.time()
    period = "nov23"
    rng = np.random.default_rng(2026)
    z = None
    # viento: misma secuencia estandarizada para todos los σ (cambia solo la magnitud del error)
    _, _, inp0 = zat.setup(period, "admin_grupos")
    z = pd.Series(bc.ar1(len(inp0[9]), 0.8, rng), index=inp0[9].index)

    m, R, inp = build_cached("nom_admin_grupos", period, "admin_grupos")
    nr, n_pt, H = m["n_reg"], m["n_pt"], len(m["hours"])
    hours = m["hours"]
    st = inp[6]
    sx = st.geometry.x.reindex(R["sid"]).values
    sy = st.geometry.y.reindex(R["sid"]).values
    xc, yc = np.nanmean(sx), np.nanmean(sy)
    pxy = tempo_xy(inp, hours)
    assert len(pxy) == R["Gt"].shape[0], (len(pxy), R["Gt"].shape)
    h_index = {h: k for k, h in enumerate(hours)}
    st_hk = np.array([h_index[pd.Timestamp(h)] for h in R["h"]])
    px_hk = np.concatenate([np.full(int((inp[11].h == h).sum()), k) for k, h in enumerate(hours) if (inp[11].h == h).any()])
    c_s = inp[3]
    w_cell = c_s.w.values
    Wz = pd.Series(w_cell).groupby(c_s.region.values).sum().reindex(range(nr)).values

    # estaciones: NOₓ medido (sin las extras de NO₂) para los subconjuntos
    nox_ids = sorted(set(R["sid"][~R["est"]]))
    print("a priori por zona / Σw de celdas:", np.round(m["prior_rd"] / Wz, 3), flush=True)
    print(f"estaciones NOₓ: {len(nox_ids)}; extras NO₂: {len(set(R['sid'][R['est']]))}; zonas {nr}; horas {H}", flush=True)

    # configuraciones de la inversión
    E = pc.ratio_constraint(m, m["xa"])
    cfgs = {"base": dict(keep=None, tempo=True, E=E), "sin_tempo": dict(keep=None, tempo=False, E=E),
            "sin_restriccion": dict(keep=None, tempo=True, E=None),
            "sin_tempo_sin_restriccion": dict(keep=None, tempo=False, E=None)}
    srng = np.random.default_rng(99)
    subsets = {}
    for n_st in (15, 9):
        for s in range(N_SUB_SEEDS):
            keep = set(srng.choice(nox_ids, n_st, replace=False))
            subsets[f"est{n_st}_s{s}"] = sorted(keep)
            cfgs[f"est{n_st}_s{s}"] = dict(keep=keep, tempo=True, E=E)
            cfgs[f"est{n_st}_sin_tempo_s{s}"] = dict(keep=keep, tempo=False, E=E)
    fac = {}
    for k, c in cfgs.items():
        N = bc.normal_matrix(m, R, c["keep"], c["tempo"], c["E"])
        C, sd = bc.posterior_corr(N, m)
        iu = np.triu_indices(nr, 1)
        fac[k] = (cho_factor(N), float(np.max(np.abs(C[iu]))), float(np.median(sd / 0.5)))
    print(f"matrices normales listas ({time.time() - t00:.0f} s)", flush=True)

    # entidad de cada zona (las 5 primeras son de la CDMX)
    ent = np.array([0] * CDMX_ZONES + [1] * (nr - CDMX_ZONES))

    def metrics_draw(xh, true_zone, true_sun_ratio):
        Z = np.array([xh[n_pt + nr * d: n_pt + nr * (d + 1)] * Wz for d in range(3)])
        ez = Z[0] / true_zone - 1
        et = Z[0].sum() / true_zone.sum() - 1
        es = (Z[2].sum() / Z[0].sum()) / true_sun_ratio - 1
        r_hat = Z[0][ent == 0].sum() / Z[0][ent == 1].sum()
        r_true = true_zone[ent == 0].sum() / true_zone[ent == 1].sum()
        return ez, et, es, r_hat / r_true - 1

    results = {}
    for truth in ("ideal", "realista"):
        for sig in SIGMAS:
            if truth == "ideal":
                if sig == 0:
                    mt, Rt, inpt = m, R, inp
                else:
                    mt, Rt, inpt = build_cached(f"ideal_s{sig}", period, "admin_grupos", z, sig)
            else:
                mt, Rt, inpt = build_cached(f"real_mun_s{sig}", period, "admin_mun", z, sig)
            assert Rt["Gs"].shape[0] == R["Gs"].shape[0] and Rt["Gt"].shape[0] == R["Gt"].shape[0]
            assert (Rt["sid"] == R["sid"]).all()
            ntr, nptt = mt["n_reg"], mt["n_pt"]
            if truth == "realista":
                c_m = inpt[3]
                assert np.allclose(c_m.w.values, w_cell)
            run_cfgs = list(cfgs) if sig == 30 else ["base", "sin_tempo"]
            acc = {k: {"ez": [], "et": [], "es": [], "ee": []} for k in run_cfgs}
            drng = np.random.default_rng(17)
            for _ in range(N_DRAWS):
                if truth == "ideal":
                    a = np.exp(drng.normal(0, 0.3, ntr))
                    a_sat = a * 0.87 * np.exp(drng.normal(0, 0.03, ntr))
                    a_sun = a * 0.69 * np.exp(drng.normal(0, 0.03, ntr))
                    true_zone = a * Wz
                    true_sun = (a_sun * Wz).sum() / (a * Wz).sum()
                else:
                    a = np.exp(drng.normal(0, 0.3, ntr))
                    a_sat = a * 0.87 * np.exp(drng.normal(0, 0.08)) * np.exp(drng.normal(0, 0.05, ntr))
                    a_sun = a * 0.69 * np.exp(drng.normal(0, 0.08)) * np.exp(drng.normal(0, 0.05, ntr))
                    ac, acs = a[c_m.region.values], a_sun[c_m.region.values]
                    true_zone = pd.Series(w_cell * ac).groupby(c_s.region.values).sum().reindex(range(nr)).values
                    true_sun = (w_cell * acs).sum() / (w_cell * ac).sum()
                x = np.r_[mt["prior_pt"] * np.exp(drng.normal(0, 0.3, nptt)), a, a_sat, a_sun,
                          np.maximum(drng.normal(5, 3, H), 0), drng.normal(5e15, 1e15, H)]
                sig_st = np.where(Rt["est"], 15.0 * 1.5, 15.0)
                ys = Rt["Gs"] @ x + drng.normal(0, 1, len(sig_st)) * sig_st
                yt = Rt["Gt"] @ x + drng.normal(0, 5e15, Rt["Gt"].shape[0])
                if truth == "realista":
                    g = drng.normal(0, 1, (H, 2))
                    ys = ys + 2.0 * (g[st_hk, 0] * (sx - xc) + g[st_hk, 1] * (sy - yc)) / 2e4
                    gt = drng.normal(0, 1, (H, 2))
                    yt = yt + 1e15 * (gt[px_hk, 0] * (pxy[:, 0] - xc) + gt[px_hk, 1] * (pxy[:, 1] - yc)) / 2e4
                for k in run_cfgs:
                    c = cfgs[k]
                    xh = cho_solve(fac[k][0], bc.rhs(m, R, ys, yt, c["keep"], c["tempo"]))
                    ez, et, es, ee = metrics_draw(xh, true_zone, true_sun)
                    acc[k]["ez"].append(ez)
                    acc[k]["et"].append(et)
                    acc[k]["es"].append(es)
                    acc[k]["ee"].append(ee)
            for k in run_cfgs:
                q = acc[k]
                results[f"{truth}|{sig}|{k}"] = {
                    "verdad": truth, "sigma_viento": sig, "config": k,
                    "error_zona": float(np.median(np.abs(q["ez"]))),
                    "error_zona_p90": float(np.percentile(np.abs(q["ez"]), 90)),
                    "error_total": float(np.median(np.abs(q["et"]))),
                    "error_domingo": float(np.median(np.abs(q["es"]))),
                    "error_cdmx_edomex": float(np.median(np.abs(q["ee"]))),
                    "corr_max": fac[k][1], "sd_rel_mediana": fac[k][2]}
            print(f"[{truth} σ={sig}°] " + "; ".join(f"{k}: zona {results[f'{truth}|{sig}|{k}']['error_zona']:.0%}"
                                                      for k in run_cfgs if not k.endswith(('_s1', '_s2', '_s3', '_s4'))),
                  f"({time.time() - t00:.0f} s)", flush=True)
    cfg_used = {"REGION_SCHEME": "admin_grupos", "transporte": "puffs, viento del dominio, 6 h", "vida_quimica": "constante 4 h",
                "sigma_theta_deg": 30, "tempo_sigma_mult": 3, "restriccion": "Infovial 0.87/0.69 ± 0.02 (salvo sin_restriccion)",
                "periodo": "2023-11-01 a 2023-12-31", "n_draws": N_DRAWS, "estaciones_nox": nox_ids, "subconjuntos": subsets}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "twin.json").write_text(json.dumps({"configuracion": cfg_used, "resultados": results}, ensure_ascii=False, indent=1))
    print(f"listo en {time.time() - t00:.0f} s", flush=True)


if __name__ == "__main__":
    main()
