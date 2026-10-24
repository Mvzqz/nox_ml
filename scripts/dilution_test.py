"""¿Explica la ventilación por hora el error hora a hora? Factor de dilución por hora en la inversión lineal.

Modelo de estaciones: y = fondo_h + s_h · (K_fuentes · x). TEMPO no lleva s_h (la columna no depende
de la altura de mezcla). Es bilineal: se resuelve alternando
  A) con s fijo, inversión lineal de emisiones y fondos (como real_check_linear.py);
  B) con x fijo, ajuste de (s_h, fondo_h) por hora con las estaciones de esa hora.
En LOO la estación retenida sale de ambos pasos: su s_h viene solo de las demás estaciones en esa
hora, la misma información que usa IDW.

Uso: .venv/bin/python scripts/dilution_test.py 2023-11-01 2023-12-31 [--transport domain|puff]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from real_check_linear import DAY_TYPES, SIG_ST, SIG_TP, build, day_type, road_totals

ROOT = Path(__file__).resolve().parents[1]
S_PRIOR_SD = 0.5
N_ITER = 6


def prepare(m):
    """Agrupa filas de estaciones por hora y precalcula la parte TEMPO (no depende de s)."""
    n = m["n"]
    N_tp = np.zeros((n, n))
    b_tp = np.zeros(n)
    for idx, Kf, y in m["tp_rows"]:
        N_tp[np.ix_(idx, idx)] += Kf.T @ Kf / SIG_TP ** 2
        b_tp[idx] += Kf.T @ y / SIG_TP ** 2
    rows = pd.DataFrame([(s, h, o) for (s, h, *_, o) in m["st_rows"]], columns=["sid", "h", "obs"])
    K = np.array([kr for *_, kr, _ in m["st_rows"]])          # [fuentes..., 1]
    IDX = np.array([idx for _, _, idx, _, _ in m["st_rows"]])  # mismas posiciones por fila
    hours = sorted(rows.h.unique())
    hpos = {h: i for i, h in enumerate(hours)}
    rows["hi"] = rows.h.map(hpos)
    return N_tp, b_tp, rows, K, IDX, hours


def step_a(m, N_tp, b_tp, K, IDX, y, s_row, keep):
    N = np.diag(1 / m["sa"] ** 2) + N_tp
    b = m["xa"] / m["sa"] ** 2 + b_tp
    Ks = K[keep].copy()
    Ks[:, :-1] *= s_row[keep, None]
    for idx_key in np.unique(IDX[keep], axis=0):
        sel = (IDX[keep] == idx_key).all(1)
        Kh, yh = Ks[sel], y[keep][sel]
        N[np.ix_(idx_key, idx_key)] += Kh.T @ Kh / SIG_ST ** 2
        b[idx_key] += Kh.T @ yh / SIG_ST ** 2
    return np.linalg.solve(N, b)


def step_b(m, x, K, IDX, y, rows, keep, n_hours):
    """(s_h, fondo_h) por hora con prior s ~ N(1, 0.5²), fondo ~ N(5, 10²)."""
    src = np.array([K[i, :-1] @ x[IDX[i, :-1]] for i in range(len(K))])
    s = np.ones(n_hours)
    for hi, g in rows[keep].groupby("hi"):
        ii = g.index.values
        A = np.c_[src[ii], np.ones(len(ii))]
        P = np.diag([1 / S_PRIOR_SD ** 2, 1 / 10.0 ** 2])
        rhs = A.T @ y[ii] / SIG_ST ** 2 + P @ np.array([1.0, 5.0])
        sol = np.linalg.solve(A.T @ A / SIG_ST ** 2 + P, rhs)
        s[hi] = np.clip(sol[0], 0.2, 5.0)
    return s, src


def fit(m, prep, drop=None):
    N_tp, b_tp, rows, K, IDX, hours = prep
    y = rows.obs.values
    keep = (rows.sid != drop).values if drop else np.ones(len(rows), bool)
    s = np.ones(len(hours))
    for _ in range(N_ITER):
        x = step_a(m, N_tp, b_tp, K, IDX, y, s[rows.hi.values], keep)
        s, _ = step_b(m, x, K, IDX, y, rows, keep, len(hours))
    x = step_a(m, N_tp, b_tp, K, IDX, y, s[rows.hi.values], keep)
    src = np.array([K[i, :-1] @ x[IDX[i, :-1]] for i in range(len(K))])
    bg = np.array([x[IDX[i, -1]] for i in range(len(K))])
    pred = bg + s[rows.hi.values] * src
    return x, s, pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--transport", choices=["domain", "puff"], default="domain")
    a = ap.parse_args()
    m = build(a.start, a.end, a.transport)
    prep = fit_prep = prepare(m)
    rows = prep[2]
    st = m["st"]
    x, s, pred_in = fit(m, prep)

    tot = road_totals(m, x)
    lines = [f"# Factor de dilución por hora (transporte '{a.transport}', {a.start} a {a.end})\n",
             f"- s_h por hora con a priori 1 ± {S_PRIOR_SD}, acotado a [0.2, 5]; {N_ITER} iteraciones alternadas.",
             f"- Ajuste en muestra, estaciones: r = {np.corrcoef(pred_in, rows.obs)[0, 1]:.2f}",
             f"- s_h: mediana {np.median(s):.2f}, percentiles 10–90 {np.percentile(s, 10):.2f}–{np.percentile(s, 90):.2f}",
             f"- Domingo-festivo / hábil = {tot[2] / tot[0]:.2f}; sábado / hábil = {tot[1] / tot[0]:.2f}; "
             f"total vial hábil = {tot[0]:,.0f} t/año ({tot[0] / m['prior_rd'].sum():.0%} del a priori)"]

    # ¿sigue s_h a la física? correlación con capa límite ERA5 y velocidad del viento
    e = json.loads((ROOT / "data/raw/era5_openmeteo/pbl_wind_center_2023-2024_full.json").read_text())["hourly"]
    pbl = pd.Series(e["boundary_layer_height"], index=pd.to_datetime(e["time"]))
    ws = pd.Series(e["wind_speed_10m"], index=pd.to_datetime(e["time"]))
    hours = prep[5]
    sh = pd.Series(s, index=hours)
    lines.append(f"- Correlación de log s_h con capa límite ERA5: {np.corrcoef(np.log(sh), pbl.reindex(hours))[0, 1]:.2f}; "
                 f"con velocidad del viento ERA5: {np.corrcoef(np.log(sh), ws.reindex(hours))[0, 1]:.2f} "
                 "(se esperan negativas: más mezcla o más viento = menos concentración)\n")

    # LOO
    xy = st.geometry
    agg = []
    for sid in sorted(rows.sid.unique()):
        _, _, pl = fit(m, prep, drop=sid)
        mask = (rows.sid == sid).values
        ob, pm = rows.obs.values[mask], pl[mask]
        res = rows.obs.values - pl
        others = rows[~mask]
        dist = {o: max(xy[sid].distance(xy[o]) / 1000, 0.5) for o in others.sid.unique()}
        pi, pr = [], []
        for h in rows.h.values[mask]:
            o = others[others.h == h]
            w = 1 / np.array([dist[q] for q in o.sid]) ** 2
            pi.append((w * o.obs.values).sum() / w.sum())
            pr.append((w * res[o.index.values]).sum() / w.sum())
        pi, ph = np.array(pi), pm + np.array(pr)
        out = [len(ob)]
        for p in (pm, pi, ph):
            out += [np.sqrt(np.mean((p - ob) ** 2)), np.mean(p - ob)]
        agg.append((sid, *out))
        print(f"{sid}: modelo {out[1]:.1f} IDW {out[3]:.1f} híbrido {out[5]:.1f}", flush=True)
    ag = pd.DataFrame(agg, columns=["sid", "n", "model", "b_model", "idw", "b_idw", "hybrid", "b_hybrid"])
    wr = lambda c: np.sqrt((ag.n * ag[c] ** 2).sum() / ag.n.sum())
    for c in ("model", "idw", "hybrid"):
        ag[f"u_{c}"] = np.sqrt(np.maximum(ag[c] ** 2 - ag[f"b_{c}"] ** 2, 0))
    lines += ["## Estación retenida (LOO)\n",
              "| | Modelo con s_h | IDW | Híbrido |", "|---|---|---|---|",
              f"| RMSE total (ppb) | {wr('model'):.1f} | {wr('idw'):.1f} | {wr('hybrid'):.1f} |",
              f"| Sesgo por estación (RMS) | {wr('b_model'):.1f} | {wr('b_idw'):.1f} | {wr('b_hybrid'):.1f} |",
              f"| Error hora a hora | {wr('u_model'):.1f} | {wr('u_idw'):.1f} | {wr('u_hybrid'):.1f} |",
              f"| Estaciones donde gana a IDW | {(ag.model < ag.idw).sum()} de {len(ag)} | — | "
              f"{(ag.hybrid < ag.idw).sum()} de {len(ag)} |",
              "\n| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido |", "|---|---|---|---|---|"]
    for r in ag.itertuples():
        lines.append(f"| {r.sid} | {r.n} | {r.model:.1f} | {r.idw:.1f} | {r.hybrid:.1f} |")
    outp = ROOT / f"reports/dilution_test_{a.transport}_{a.start}_{a.end}.md"
    outp.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
