"""Prueba con datos reales usando la inversión lineal de feasibility_linear.py.

Estado: 16 fuentes puntuales | factor vial por región (3×3) × tipo de día (hábil, sábado,
domingo/festivo) | fondo por hora (estaciones y TEMPO). Los tres tipos de día tienen el mismo
a priori, así que cualquier baja en domingo viene de los datos.

Transporte: "domain" = pluma estacionaria con un vector de viento por hora para todo el dominio;
"field" = pluma con campo IDW de las estaciones en una malla de 1 km, promediado en fuente, punto
medio y receptor de cada par; "puff" = no estacionario (pluma de la última hora + puffs de las 6
horas previas, con perfil horario de tráfico y decaimiento químico; ver puff.py).

Salidas:
  1. Ajuste en muestra (estaciones y TEMPO).
  2. Emisión vial por tipo de día, con IC por bootstrap de días completos.
  3. Fuentes puntuales a posteriori.
  4. Validación dejando una estación fuera (LOO): modelo, IDW e híbrido (modelo + IDW de residuos).

Uso: .venv/bin/python scripts/real_check_linear.py 2023-11-01 2023-12-31 [--wind field] [--boot 200] [--sigma-theta 15]
σθ estándar = 30° (feasibility_linear.SIGMA_THETA); los reportes sin sufijo _sigma30 son de la configuración anterior (15°).
"""
import argparse
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from config import LAT, LON, UTM
import feasibility_linear as fl
import puff
from feasibility_linear import jacobian_hour, load_inputs
from puff import Trajectories, jacobian_hour_puff

ROOT = Path(__file__).resolve().parents[1]
SIG_ST, SIG_TP_BASE = 15.0, 5e15     # error de observación + representación con datos reales
# Peso de TEMPO: sus residuos tienen estructura espacial que no se promedia (reports/fondo_tempo.md), así que
# por defecto su σ por píxel se multiplica ×3. TEMPO_SIGMA_MULT=1 (o --tempo-sigma-mult 1) reproduce los
# reportes anteriores, incluidos fondo_tempo.py y centrales_pluma_fresca.py, que multiplican SIG_TP por su cuenta.
TEMPO_SIGMA_MULT = float(os.environ.get("TEMPO_SIGMA_MULT", "3"))
SIG_TP = SIG_TP_BASE * TEMPO_SIGMA_MULT
# Superobservaciones (opcional): promedio de píxeles por celda de SUPEROBS_KM km en cada escaneo, con
# σ² = SUPEROBS_SIG_CORR² + SIG_TP_BASE²/n (parte correlacionada de fondo_tempo.md + ruido por píxel).
SUPEROBS_KM = float(os.environ.get("SUPEROBS_KM", "0"))
SUPEROBS_SIG_CORR = 2.6e15
EST_FACTOR = 1.5                     # NOₓ estimado de NO₂ (estaciones sin NOₓ): error ×1.5
HOLIDAYS = {"2023-11-20", "2023-12-25", "2024-01-01", "2024-02-05", "2024-03-18", "2024-03-28", "2024-03-29", "2024-05-01"}
DAY_TYPES = ["hábil", "sábado", "domingo/festivo"]
REGIONS = fl.REGION_SCHEMES["3x3"]  # nombres actuales: fl.region_names() (depende de REGION_SCHEME)
rng = np.random.default_rng(7)


def local_day(h):
    return (h - pd.Timedelta(hours=6)).normalize()


def day_type(h):
    d = h - pd.Timedelta(hours=6)
    if d.strftime("%Y-%m-%d") in HOLIDAYS or d.dayofweek == 6:
        return 2
    return 1 if d.dayofweek == 5 else 0


def wind_field_factory(st, by_station):
    """Devuelve field(h) -> función por par (xs, ys, xr, yr) -> (U, V) con IDW en malla de 1 km."""
    x0, y0 = gpd.GeoSeries.from_xy([LON[0]], [LAT[0]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    x1, y1 = gpd.GeoSeries.from_xy([LON[1]], [LAT[1]], crs=4326).to_crs(UTM).iloc[0].coords[0]
    nx, ny = int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1
    gx, gy = np.meshgrid(x0 + 500 + 1000 * np.arange(nx), y0 + 500 + 1000 * np.arange(ny))
    groups = dict(tuple(by_station.groupby("h")))

    def field(h):
        g = groups[h]
        g = g[g.id_station.isin(st.index)]
        sx, sy = st.loc[g.id_station].geometry.x.values, st.loc[g.id_station].geometry.y.values
        d2 = np.maximum((gx[..., None] - sx) ** 2 + (gy[..., None] - sy) ** 2, 500.0 ** 2)
        w = 1 / d2
        U = (w * g.u.values).sum(-1) / w.sum(-1)
        V = (w * g.v.values).sum(-1) / w.sum(-1)

        def at(x, y):
            i = np.clip(((y - y0) // 1000).astype(int), 0, ny - 1)
            j = np.clip(((x - x0) // 1000).astype(int), 0, nx - 1)
            return U[i, j], V[i, j]

        def pair(xs, ys, xr, yr):
            XS, XR = np.broadcast_arrays(xs[None, :], xr[:, None])
            YS, YR = np.broadcast_arrays(ys[None, :], yr[:, None])
            u = np.zeros(XS.shape)
            v = np.zeros(XS.shape)
            for f in (0.0, 0.5, 1.0):  # fuente, punto medio, receptor
                a, b = at(XS + f * (XR - XS), YS + f * (YR - YS))
                u += a / 3
                v += b / 3
            return u, v

        return pair

    return field


def set_tempo_weight(mult=None, superobs_km=None):
    """Cambia el peso de TEMPO para las siguientes llamadas a build()."""
    global TEMPO_SIGMA_MULT, SIG_TP, SUPEROBS_KM
    if mult is not None:
        TEMPO_SIGMA_MULT = float(mult)
        SIG_TP = SIG_TP_BASE * TEMPO_SIGMA_MULT
    if superobs_km is not None:
        SUPEROBS_KM = float(superobs_km)


def tempo_tag():
    """Sufijo de reporte: vacío para el estándar (×3, píxel a píxel)."""
    return f"_so{SUPEROBS_KM:g}km" if SUPEROBS_KM > 0 else ("" if TEMPO_SIGMA_MULT == 3 else f"_tp{TEMPO_SIGMA_MULT:g}")


def build(start, end, wind_mode, no_industry=False, extras=False):
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = load_inputs(start, end, extras)
    est_ids = set(nox[nox.est].id_station)
    if no_industry:  # los clústeres industriales no son identificables (ver feasibility_linear)
        keep = (cand.tipo != "industria").values
        cand, prior_pt, sd_pt = cand[keep].reset_index(drop=True), prior_pt[keep], sd_pt[keep]
    n_pt = len(cand)
    nr = len(prior_rd)
    n_src = n_pt + 3 * nr
    hours = [h for h in sorted(set(nox.h) & set(wind.index)) if h in pbl.index]
    H = len(hours)
    n = n_src + 2 * H
    xa = np.r_[prior_pt, np.ones(3 * nr), np.full(H, 5.0), np.full(H, 5e15)]
    sa = np.r_[sd_pt, np.full(3 * nr, 0.5), np.full(H, 10.0), np.full(H, 5e15)]
    field = wind_field_factory(st, wind.attrs["by_station"]) if wind_mode == "field" else None
    traj = Trajectories(wind) if wind_mode == "puff" else None

    blocks = []   # (día, idx, KᵀK/σ², Kᵀy/σ²) para bootstrap
    st_rows = []  # (estación, hora, idx, fila K, y)
    tp_rows = []
    for k, h in enumerate(hours):
        dt = day_type(h)
        nox_h = nox[nox.h == h]
        px_h = px[px.h == h]
        if traj:
            jac = jacobian_hour_puff(h, traj, wind.loc[h].values, pbl.loc[h], cand, cells, st, nox_h, px_h, ratio)
        else:
            uv = field(h) if field else wind.loc[h].values
            jac = jacobian_hour(h, uv, pbl.loc[h], cand, cells, st, nox_h, px_h, ratio)
        for kind, K in jac:
            bg = n_src + (k if kind == "st" else H + k)
            idx = np.r_[np.arange(n_pt), n_pt + nr * dt + np.arange(nr), bg]
            Kf = np.c_[K, np.ones(len(K))]
            sig = SIG_ST if kind == "st" else SIG_TP
            y = nox_h.NOX.values if kind == "st" else px_h.vcd.values
            wr = np.where(nox_h.id_station.isin(est_ids), EST_FACTOR ** -2, 1.0) if kind == "st" else np.ones(len(y))
            if kind == "tp" and SUPEROBS_KM > 0:
                ix = (px_h.x.values // (1000 * SUPEROBS_KM)).astype(np.int64)
                iy = (px_h.y.values // (1000 * SUPEROBS_KM)).astype(np.int64)
                cell = np.unique(ix * 100_000 + iy, return_inverse=True)[1]
                cnt = np.bincount(cell)
                Kf = np.stack([np.bincount(cell, weights=Kf[:, j]) for j in range(Kf.shape[1])], 1) / cnt[:, None]
                y = np.bincount(cell, weights=y) / cnt
                sig = SIG_TP_BASE
                wr = SIG_TP_BASE ** 2 / (SUPEROBS_SIG_CORR ** 2 + SIG_TP_BASE ** 2 / cnt)
            blocks.append((local_day(h), idx, (Kf * wr[:, None]).T @ Kf / sig ** 2, Kf.T @ (wr * y) / sig ** 2))
            if kind == "st":
                st_rows += [(sid, h, idx, kr, yy) for sid, kr, yy in zip(nox_h.id_station.values, Kf, y)]
            else:
                tp_rows.append((idx, Kf, y))
    return dict(cand=cand, prior_pt=prior_pt, prior_rd=prior_rd, n_reg=nr, st=st, hours=hours, n=n, n_pt=n_pt, est_ids=est_ids,
                xa=xa, sa=sa, blocks=blocks, st_rows=st_rows, tp_rows=tp_rows)


def solve(m, weights=None, drop_station=None):
    N = np.diag(1 / m["sa"] ** 2)
    b = m["xa"] / m["sa"] ** 2
    for d, idx, A, g in m["blocks"]:
        w = 1.0 if weights is None else weights.get(d, 0)
        if w:
            N[np.ix_(idx, idx)] += w * A
            b[idx] += w * g
    if drop_station:
        for s, h, idx, kr, yy in m["st_rows"]:
            if s == drop_station:
                sig = SIG_ST * (EST_FACTOR if s in m["est_ids"] else 1.0)
                N[np.ix_(idx, idx)] -= np.outer(kr, kr) / sig ** 2
                b[idx] -= kr * yy / sig ** 2
    return N, b


def road_totals(m, x):
    n_pt, prior_rd = m["n_pt"], m["prior_rd"]
    nr = len(prior_rd)
    return np.array([prior_rd @ x[n_pt + nr * d: n_pt + nr * d + nr] for d in range(3)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--wind", choices=["domain", "field", "puff"], default="domain")
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--no-industry", action="store_true")
    ap.add_argument("--extras", action="store_true")
    ap.add_argument("--sigma-theta", type=float, default=np.rad2deg(fl.SIGMA_THETA),
                    help="incertidumbre de dirección del viento en grados (estándar 30; anterior 15)")
    ap.add_argument("--tempo-sigma-mult", type=float, default=TEMPO_SIGMA_MULT,
                    help="multiplicador de σ por píxel de TEMPO (estándar 3; anterior 1)")
    ap.add_argument("--superobs-km", type=float, default=SUPEROBS_KM,
                    help="promediar TEMPO en celdas de este tamaño por escaneo (0 = píxel a píxel)")
    a = ap.parse_args()
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(a.sigma_theta)
    set_tempo_weight(a.tempo_sigma_mult, a.superobs_km)
    m = build(a.start, a.end, a.wind, a.no_industry, a.extras)
    N, b = solve(m)
    S = np.linalg.inv(N)
    x = S @ b
    n_pt, st = m["n_pt"], m["st"]

    obs = np.array([r[4] for r in m["st_rows"]])
    pred = np.array([kr @ x[idx] for _, _, idx, kr, _ in m["st_rows"]])
    tp_obs = np.concatenate([y for *_, y in m["tp_rows"]])
    tp_pred = np.concatenate([Kf @ x[idx] for idx, Kf, _ in m["tp_rows"]])
    lines = [f"# Prueba con datos reales: inversión lineal, viento '{a.wind}' ({a.start} a {a.end})\n",
             f"- Horas: {len(m['hours'])}; observaciones de estación: {len(obs):,}; píxeles TEMPO: {len(tp_obs):,}; "
             f"σ obs: estaciones {SIG_ST} ppb, TEMPO {SIG_TP:.1e} (×{TEMPO_SIGMA_MULT:g})"
             + (f" — no aplica: superobservaciones de {SUPEROBS_KM:g} km con σ² = ({SUPEROBS_SIG_CORR:.1e})² + ({SIG_TP_BASE:.0e})²/n"
                if SUPEROBS_KM > 0 else "") + f"; σθ viento {a.sigma_theta:g}°",
             f"- Festivos tratados como domingo: {', '.join(sorted(d for d in HOLIDAYS if a.start <= d <= a.end))}\n",
             "## 1. Ajuste en muestra\n",
             f"- Estaciones NOₓ: r = {np.corrcoef(pred, obs)[0, 1]:.2f}, RMSE = {np.sqrt(np.mean((pred - obs) ** 2)):.1f} ppb "
             f"(media observada {obs.mean():.1f}, desv. est. {obs.std():.1f})",
             f"- TEMPO NO₂: r = {np.corrcoef(tp_pred, tp_obs)[0, 1]:.2f}\n"]

    # 2. vial por tipo de día + bootstrap por días
    tot = road_totals(m, x)
    days = sorted({d for d, *_ in m["blocks"]})
    boot = []
    for _ in range(a.boot):
        pick = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick]).groupby(level=0).sum().to_dict()
        Nb, bb = solve(m, weights=wts)
        boot.append(road_totals(m, np.linalg.solve(Nb, bb)))
    boot = np.array(boot)
    lines += ["## 2. Emisión vial por tipo de día\n",
              f"IC 90 % por bootstrap de {len(days)} días completos ({a.boot} réplicas).\n",
              "| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |", "|---|---|---|---|"]
    for d in range(3):
        nh = sum(day_type(h) == d for h in m["hours"])
        lo, hi = np.percentile(boot[:, d], [5, 95])
        lines.append(f"| {DAY_TYPES[d]} | {nh} | {tot[d]:,.0f} | {lo:,.0f}–{hi:,.0f} |")
    lines.append(f"| a priori (igual para todos) | | {m['prior_rd'].sum():,.0f} | |")
    for d in (1, 2):
        r = boot[:, d] / boot[:, 0]
        lo, hi = np.percentile(r, [5, 95])
        lines.append(f"\n- {DAY_TYPES[d]} / hábil = **{tot[d] / tot[0]:.2f}** (IC 90 % {lo:.2f}–{hi:.2f})")
    lines.append("\n| Región | " + " | ".join(DAY_TYPES) + " |")
    lines.append("|---|---|---|---|")
    nr = m["n_reg"]
    for i, rg in enumerate(fl.region_names()):
        lines.append(f"| {rg} | " + " | ".join(f"{x[n_pt + nr * d + i]:.2f}" for d in range(3)) + " |")
    lines.append("\n(factor α respecto al a priori de la región; a priori 1 ± 0.5)\n")

    # 3. puntuales
    lines += ["## 3. Fuentes puntuales\n", "| Fuente | A priori t/año | A posteriori t/año |", "|---|---|---|"]
    for i, nm in enumerate(m["cand"].nombre):
        lines.append(f"| {nm} | {m['prior_pt'][i]:,.0f} | {x[i]:,.0f} ± {np.sqrt(S[i, i]):,.0f} |")

    # 4. LOO: modelo, IDW e híbrido
    rows = pd.DataFrame([(s, h, o) for (s, h, *_, o) in m["st_rows"]], columns=["sid", "h", "obs"])
    xy = st.geometry
    lines += ["\n## 4. Estación retenida (LOO)\n",
              "Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.\n",
              "| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |",
              "|---|---|---|---|---|---|---|---|"]
    agg = []
    for sid in sorted(set(rows.sid.unique()) - m["est_ids"]):  # se evalúa solo donde se mide NOₓ
        Nl, bl = solve(m, drop_station=sid)
        xl = np.linalg.solve(Nl, bl)
        allpred = np.array([kr @ xl[idx] for _, _, idx, kr, _ in m["st_rows"]])
        rows["res"] = rows.obs - allpred
        mask = (rows.sid == sid).values
        pm, ob = allpred[mask], rows.obs.values[mask]
        pi, pr = [], []
        others = rows[~mask]
        dist = {s: max(xy[sid].distance(xy[s]) / 1000, 0.5) for s in others.sid.unique()}
        for h in rows.h.values[mask]:
            o = others[others.h == h]
            w = 1 / np.array([dist[s] for s in o.sid]) ** 2
            pi.append((w * o.obs.values).sum() / w.sum())
            pr.append((w * o.res.values).sum() / w.sum())
        pi, ph = np.array(pi), pm + np.array(pr)
        rmse = [np.sqrt(np.mean((p - ob) ** 2)) for p in (pm, pi, ph)]
        rr = [np.corrcoef(p, ob)[0, 1] for p in (pm, pi, ph)]
        bias = [np.mean(p - ob) for p in (pm, pi, ph)]
        agg.append((sid, len(ob), *rmse, *bias))
        lines.append(f"| {sid} | {len(ob)} | " + " | ".join(f"{v:.1f}" for v in rmse) + " | "
                     + " | ".join(f"{v:.2f}" for v in rr) + " |")
    ag = pd.DataFrame(agg, columns=["sid", "n", "model", "idw", "hybrid", "b_model", "b_idw", "b_hybrid"])
    wr = lambda c: np.sqrt((ag.n * ag[c] ** 2).sum() / ag.n.sum())
    lines.append(f"\n- RMSE ponderado: modelo {wr('model'):.1f}, IDW {wr('idw'):.1f}, híbrido {wr('hybrid'):.1f} ppb")
    for c in ("model", "idw", "hybrid"):
        ag[f"u_{c}"] = np.sqrt(np.maximum(ag[c] ** 2 - ag[f"b_{c}"] ** 2, 0))
    lines.append(f"- Parte constante (sesgo medio por estación, RMS): modelo {wr('b_model'):.1f}, IDW {wr('b_idw'):.1f}, "
                 f"híbrido {wr('b_hybrid'):.1f} ppb")
    lines.append(f"- Parte que varía hora a hora (RMSE sin el sesgo): modelo {wr('u_model'):.1f}, IDW {wr('u_idw'):.1f}, "
                 f"híbrido {wr('u_hybrid'):.1f} ppb")
    lines.append(f"- Modelo < IDW en {(ag.model < ag.idw).sum()} de {len(ag)} estaciones; "
                 f"híbrido < IDW en {(ag.hybrid < ag.idw).sum()} de {len(ag)}")

    tag = a.wind + ("_sin_industria" if a.no_industry else "") + ("_extras" if a.extras else "")
    if round(a.sigma_theta) != 15:  # los reportes sin sufijo son de la configuración anterior (15°)
        tag += f"_sigma{a.sigma_theta:g}"
    tag += tempo_tag()  # los reportes _sigma30 anteriores a peso_tempo.md usaban TEMPO ×1 (copias en *_tp1_*)
    out = ROOT / f"reports/real_check_linear_{tag}_{a.start}_{a.end}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
