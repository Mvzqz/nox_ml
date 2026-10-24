"""Validación con un cambio conocido: confinamiento COVID-19 2020 (y 2019 como placebo).

Inversión lineal con transporte estacionario e industria agrupada (como real_check_linear
--no-industry), solo con estaciones (no había TEMPO). El factor vial α por región se estima por
grupo = periodo × tipo de día (hábil / fin de semana-festivo), todos con el mismo a priori, así
que cualquier diferencia entre periodos viene de los datos. IC 90 % por bootstrap de días.

Para repetir con las mejoras de la tarea B, pasar otra función de jacobiano a `run(..., jac_fn=...)`
con la misma firma que feasibility_linear.jacobian_hour.

Uso: .venv/bin/python scripts/val2020_linear.py [--boot 200]
Salida: data/interim/val2020_results.json y tabla en pantalla.
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from config import DOMAIN, UTM
from feasibility_linear import jacobian_hour, load_inputs

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
SIG_ST = 15.0
rng = np.random.default_rng(2020)

# Fases según Hernández-Paniagua et al. (2021): fase 2 desde 24–30 mar, fase 3 (total) desde 21 abr 2020
PERIODS = {
    2020: [("base", "2020-02-15", "2020-03-15"), ("fase2", "2020-03-30", "2020-04-20"), ("fase3", "2020-04-21", "2020-05-31")],
    2019: [("base", "2019-02-15", "2019-03-15"), ("fase2", "2019-03-30", "2019-04-20"), ("fase3", "2019-04-21", "2019-05-31")],
}
HOLIDAYS = {"2019-03-18", "2019-04-18", "2019-04-19", "2019-05-01", "2020-03-16", "2020-04-09", "2020-04-10", "2020-05-01"}
DAY = ["hábil", "fin de semana/festivo"]


def static_inputs():
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, *_ = load_inputs("2023-11-01", "2023-12-31")
    keep = (cand.tipo != "industria").values  # industria agrupada en el factor vial de su región
    cat = pd.read_csv(ROOT / "data/raw/simat/cat_estacion.csv", skiprows=1, encoding="latin1")
    st = gpd.GeoDataFrame(cat, geometry=gpd.points_from_xy(cat.longitud, cat.latitud), crs=4326)
    st = st[st.within(DOMAIN)].to_crs(UTM).set_index("cve_estac")[["geometry"]]
    return cand[keep].reset_index(drop=True), prior_pt[keep], sd_pt[keep], cells, prior_rd, st


def dynamic_inputs(st):
    nox = pd.read_parquet(INT / "simat_nox_2019_2020.parquet")
    nox = nox[nox.id_station.isin(st.index) & nox.hour.between(12, 17) & nox.NOX.notna()].copy()
    nox["h"] = nox.utc - pd.Timedelta(hours=1)
    w = pd.read_parquet(INT / "simat_wind_2019_2020.parquet")
    w = w[w.id_station.isin(st.index)].dropna(subset=["WSP", "WDR"])
    r = np.deg2rad(w.WDR)
    w["u"], w["v"] = -w.WSP * np.sin(r), -w.WSP * np.cos(r)
    wind = w.groupby(w.utc - pd.Timedelta(hours=1))[["u", "v"]].mean()
    e = json.loads((ROOT / "data/raw/era5_openmeteo/pbl_wind_center_2019-2020.json").read_text())["hourly"]
    pbl = pd.Series(e["boundary_layer_height"], index=pd.to_datetime(e["time"]))
    era_ws = pd.Series(e["wind_speed_10m"], index=pd.to_datetime(e["time"]))
    pbl = ((pbl + pbl.shift(-1)) / 2).clip(lower=200)
    return nox, wind, pbl, era_ws


def day_type(h):
    d = h - pd.Timedelta(hours=6)
    return 1 if (d.dayofweek >= 5 or d.strftime("%Y-%m-%d") in HOLIDAYS) else 0


def run(year, boot=200, jac_fn=jacobian_hour):
    cand, prior_pt, sd_pt, cells, prior_rd, st = static_inputs()
    nox, wind, pbl, era_ws = dynamic_inputs(st)
    periods = PERIODS[year]
    n_pt, G = len(cand), len(periods) * 2
    n_src = n_pt + 9 * G
    px_empty = pd.DataFrame({"x": [], "y": []})
    hours, groups = [], []
    for gi, (name, a, b) in enumerate(periods):
        hs = sorted(set(nox[nox.local.between(a, f"{b} 23:59")].h) & set(wind.index))
        for h in hs:
            hours.append(h)
            groups.append(gi * 2 + day_type(h))
    H = len(hours)
    n = n_src + H
    xa = np.r_[prior_pt, np.ones(9 * G), np.full(H, 5.0)]
    sa = np.r_[sd_pt, np.full(9 * G, 0.5), np.full(H, 10.0)]
    blocks = []
    obs_mean, pred_prior = {}, {}
    hourly = []
    for k, (h, g) in enumerate(zip(hours, groups)):
        nh = nox[nox.h == h]
        K = jac_fn(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, px_empty, 0.8)[0][1]
        idx = np.r_[np.arange(n_pt), n_pt + 9 * g + np.arange(9), n_src + k]
        Kf = np.c_[K, np.ones(len(K))]
        y = nh.NOX.values
        day = (h - pd.Timedelta(hours=6)).normalize()
        blocks.append((day, idx, Kf.T @ Kf / SIG_ST ** 2, Kf.T @ y / SIG_ST ** 2))
        obs_mean.setdefault(g, []).append(y.mean())
        # diagnóstico: NOₓ que el modelo predice con la emisión vial a priori (α = 1), sin fondo
        pred_prior.setdefault(g, []).append(K[:, n_pt:n_pt + 9].sum(1).mean())
        hourly.append({"h": h, "day": day, "g": g, "obs": y.mean(), "modelo": K[:, n_pt:n_pt + 9].sum(1).mean(), "k": k})

    def solve(weights=None):
        N = np.diag(1 / sa ** 2)
        bb = xa / sa ** 2
        for d, idx, A, gv in blocks:
            w = 1.0 if weights is None else weights.get(d, 0)
            if w:
                N[np.ix_(idx, idx)] += w * A
                bb[idx] += w * gv
        return np.linalg.solve(N, bb)

    def totals(x):
        return np.array([prior_rd @ x[n_pt + 9 * g: n_pt + 9 * g + 9] for g in range(G)])

    x = solve()
    tot = totals(x)
    hourly = pd.DataFrame(hourly)
    hourly["fondo"] = x[n_src + hourly.k.values]
    hourly.drop(columns="k").to_parquet(INT / f"val2020_hourly_{year}.parquet")
    days = sorted({d for d, *_ in blocks})
    bs = []
    for _ in range(boot):
        pick = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick]).groupby(level=0).sum().to_dict()
        bs.append(totals(solve(wts)))
    bs = np.array(bs)

    out = {"year": year, "hours": H, "obs": int(sum(len(nox[nox.h == h]) for h in hours)), "groups": {}}
    for g in range(G):
        name = periods[g // 2][0]
        out["groups"][f"{name}|{DAY[g % 2]}"] = {
            "horas": int(sum(1 for q in groups if q == g)), "vial": float(tot[g]),
            "nox_obs_ppb": float(np.mean(obs_mean.get(g, [np.nan]))),
            "nox_modelo_apriori_ppb": float(np.mean(pred_prior.get(g, [np.nan]))),
            "fondo_inferido_ppb": float(hourly[hourly.g == g].fondo.mean()),
        }
    out["ratios"] = {}
    for pi in (1, 2):
        for dt in (0, 1):
            g0, g1 = dt, pi * 2 + dt
            r = bs[:, g1] / bs[:, g0]
            out["ratios"][f"{periods[pi][0]}/base|{DAY[dt]}"] = {
                "inferido": float(tot[g1] / tot[g0]), "ic90": [float(np.percentile(r, 5)), float(np.percentile(r, 95))],
                "concentracion": float(np.mean(obs_mean[g1]) / np.mean(obs_mean[g0])),
                "modelo_apriori": float(np.mean(pred_prior[g1]) / np.mean(pred_prior[g0])),
                "muestras": [float(v) for v in r],
            }
    # meteorología por periodo (hábiles y fines de semana juntos)
    out["meteo"] = {}
    for name, a, b in periods:
        loc = pd.date_range(a, f"{b} 23:00", freq="h")
        utc = loc[(loc.hour >= 12) & (loc.hour <= 17)] + pd.Timedelta(hours=6)
        hh = [h for h in hours if a <= (h - pd.Timedelta(hours=6)).strftime("%Y-%m-%d") <= b]
        out["meteo"][name] = {"pbl_m": float(pbl.reindex(utc).mean()), "viento_era5_ms": float(era_ws.reindex(utc).mean()),
                              "viento_redmet_ms": float(np.hypot(*wind.loc[hh].mean().values)) if hh else None,
                              "rapidez_redmet_ms": float(np.mean(np.hypot(wind.loc[hh].u, wind.loc[hh].v))) if hh else None}
    out["prior_vial"] = float(prior_rd.sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    res = [run(y, a.boot) for y in (2020, 2019)]
    (INT / "val2020_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    # diferencia de diferencias: cociente 2020 ÷ cociente 2019 (muestras independientes por año)
    did = {}
    for k in res[0]["ratios"]:
        a, b = np.array(res[0]["ratios"][k]["muestras"]), np.array(res[1]["ratios"][k]["muestras"])
        smp = a / rng.permutation(b)
        did[k] = {"inferido": res[0]["ratios"][k]["inferido"] / res[1]["ratios"][k]["inferido"],
                  "ic90": [float(np.percentile(smp, 5)), float(np.percentile(smp, 95))],
                  "concentracion": res[0]["ratios"][k]["concentracion"] / res[1]["ratios"][k]["concentracion"]}
    (INT / "val2020_did.json").write_text(json.dumps(did, ensure_ascii=False, indent=1))
    print("\n== Diferencia de diferencias (2020 ÷ 2019)")
    for k, v in did.items():
        print(f"  {k:32s} inferido {v['inferido']:.2f} (IC90 {v['ic90'][0]:.2f}–{v['ic90'][1]:.2f})  concentración {v['concentracion']:.2f}")
    for r in res:
        print(f"\n== {r['year']}: {r['hours']} horas, {r['obs']} observaciones")
        for k, v in r["groups"].items():
            print(f"  {k:32s} horas {v['horas']:4d}  vial {v['vial']:9,.0f}  NOx obs {v['nox_obs_ppb']:.1f} ppb  modelo con a priori {v['nox_modelo_apriori_ppb']:.1f} ppb  fondo inferido {v['fondo_inferido_ppb']:.1f} ppb")
        for k, v in r["ratios"].items():
            print(f"  {k:32s} inferido {v['inferido']:.2f} (IC90 {v['ic90'][0]:.2f}–{v['ic90'][1]:.2f})  concentración {v['concentracion']:.2f}  modelo a priori {v['modelo_apriori']:.2f}")
        for k, v in r["meteo"].items():
            print(f"  meteo {k}: PBL {v['pbl_m']:.0f} m, viento ERA5 {v['viento_era5_ms']:.1f}, rapidez REDMET {v['rapidez_redmet_ms']:.1f} m/s")


if __name__ == "__main__":
    main()
