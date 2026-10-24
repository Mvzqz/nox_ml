"""Prueba con datos reales de las mejoras de bajo esfuerzo (nov–dic 2023), sin modificar los scripts base.

Variantes, sobre la base "industria agrupada + estaciones extra" (real_check_linear --no-industry --extras):
  - perfil Infovial: cociente sábado/hábil y domingo/hábil medido como a priori (restricción por región)
    y, con transporte no estacionario, perfil horario medido por tipo de día;
  - σθ = 30°: error de dirección del viento representado en la dispersión (equivale a promediar
    el jacobiano sobre direcciones perturbadas);
  - viento ponderado: CHO, FAC, ACO y CUA con peso 0.25 en el viento del dominio;
  - Acolman elevada: altura efectiva 200 m (factor exp(−H²/2σz²) en estaciones; TEMPO no cambia).

Uso: .venv/bin/python scripts/improve_real.py
Salida: reports/improve_real_2023-11-01_2023-12-31.md (tabla)
"""
from pathlib import Path

import numpy as np
import pandas as pd

import feasibility_linear as fl
import puff
import real_check_linear as rcl

ROOT = Path(__file__).resolve().parents[1]
START, END = "2023-11-01", "2023-12-31"
N_BOOT = 100
BAD_WIND = {"CHO", "FAC", "ACO", "CUA"}
BAD_WEIGHT = 0.25
STACK_H = 200.0
# Infovial ene-2017, tarde 12–17 h, conteos ponderados por emisión de NOₓ por clase (C1..C6 = 1, 2, 5, 10, 15, 20)
RATIO_PRIOR = {1: 0.95, 2: 0.80}   # sábado, domingo/festivo respecto al hábil
RATIO_SD = 0.15
# Perfil horario (hora local → factor) ponderado por emisión, relativo a la media diaria de días hábiles.
# Los perfiles de fin de semana se reescalan para tener la misma media de 12–17 h que el hábil:
# el nivel lo da α de cada tipo de día y aquí solo cuenta la forma.
PROF_RAW = {
    0: {6: .86, 7: 1.30, 8: 1.47, 9: 1.42, 10: 1.38, 11: 1.35, 12: 1.35, 13: 1.39, 14: 1.44, 15: 1.46, 16: 1.44, 17: 1.46},
    1: {6: .49, 7: .82, 8: 1.15, 9: 1.25, 10: 1.28, 11: 1.30, 12: 1.35, 13: 1.39, 14: 1.44, 15: 1.42, 16: 1.32, 17: 1.22},
    2: {6: .33, 7: .53, 8: .72, 9: .87, 10: .97, 11: 1.03, 12: 1.09, 13: 1.16, 14: 1.21, 15: 1.20, 16: 1.10, 17: 1.09},
}
_ref = np.mean([PROF_RAW[0][h] for h in range(12, 18)])
PROFILE_BY_DT = {dt: {h: v * _ref / np.mean([p[k] for k in range(12, 18)]) for h, v in p.items()} for dt, p in PROF_RAW.items()}

ORIG = dict(load=rcl.load_inputs, jac=rcl.jacobian_hour, jac_puff=rcl.jacobian_hour_puff,
            sig=fl.SIGMA_THETA_LEGACY, profile=dict(puff.PROFILE))


def configure(sigma30=False, weighted=False, stack=False, infovial_profile=False):
    fl.SIGMA_THETA = np.deg2rad(30) if sigma30 else ORIG["sig"]
    puff.SIGMA_THETA = fl.SIGMA_THETA

    def load(start, end, extras=False):
        out = list(ORIG["load"](start, end, extras))
        if weighted:
            w = out[9].attrs["by_station"].copy()
            w["wt"] = np.where(w.id_station.isin(BAD_WIND), BAD_WEIGHT, 1.0)
            g = w.assign(wu=w.u * w.wt, wv=w.v * w.wt).groupby("h")[["wu", "wv", "wt"]].sum()
            wind = pd.DataFrame({"u": g.wu / g.wt, "v": g.wv / g.wt})
            wind.attrs["by_station"] = w.drop(columns="wt")
            out[9] = wind
        return tuple(out)

    def jac(h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio):
        blocks = ORIG["jac"](h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio)
        if not stack or callable(uv):
            return blocks
        j = int(np.flatnonzero(cand.nombre.str.contains("Valle de México").values)[0])
        src = cand.geometry.iloc[j]
        out = []
        for kind, K in blocks:
            if kind == "st":
                K = K.copy()
                rx = st.loc[nox_h.id_station.values].geometry
                u, v = uv
                mag = max(np.hypot(u, v), 1e-6)
                along = np.maximum(((rx.x.values - src.x) * u + (rx.y.values - src.y) * v) / mag, 300.0)
                sz = 0.24 * along * np.sqrt(1 + 0.001 * along)
                K[:, j] *= np.exp(-STACK_H ** 2 / (2 * sz ** 2))
            out.append((kind, K))
        return out

    def jac_puff(h, traj, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio, **kw):
        puff.PROFILE = PROFILE_BY_DT[rcl.day_type(h)] if infovial_profile else ORIG["profile"]
        return ORIG["jac_puff"](h, traj, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio, **kw)

    rcl.load_inputs, rcl.jacobian_hour, rcl.jacobian_hour_puff = load, jac, jac_puff


def ratio_constraint(m, x_ref):
    """Restricción α_dt,r − r_dt · α_hábil,r ≈ 0 con σ = 0.15 · α_hábil,r (a priori correlacionado)."""
    n_pt, n = m["n_pt"], m["n"]
    E = np.zeros((n, n))
    for dt, r in RATIO_PRIOR.items():
        for i in range(9):
            g = np.zeros(n)
            g[n_pt + 9 * dt + i] = 1.0
            g[n_pt + i] = -r
            sig = RATIO_SD * max(x_ref[n_pt + i], 0.1)
            E += np.outer(g, g) / sig ** 2
    return E


def evaluate(m, E=None):
    def solve(**kw):
        N, b = rcl.solve(m, **kw)
        return (N + E if E is not None else N), b

    N, b = solve()
    x = np.linalg.solve(N, b)
    n_pt, st = m["n_pt"], m["st"]
    names = list(m["cand"].nombre)
    pick = lambda key: x[next(i for i, nm in enumerate(names) if key in nm)]
    tot = rcl.road_totals(m, x)
    tp_obs = np.concatenate([y for *_, y in m["tp_rows"]])
    tp_pred = np.concatenate([Kf @ x[idx] for idx, Kf, _ in m["tp_rows"]])
    days = sorted({d for d, *_ in m["blocks"]})
    rng = np.random.default_rng(3)
    boot = []
    for _ in range(N_BOOT):
        pick_d = rng.choice(len(days), len(days))
        wts = pd.Series(1, index=[days[i] for i in pick_d]).groupby(level=0).sum().to_dict()
        Nb, bb = solve(weights=wts)
        tb = rcl.road_totals(m, np.linalg.solve(Nb, bb))
        boot.append(tb[2] / tb[0])
    lo, hi = np.percentile(boot, [5, 95])

    rows = pd.DataFrame([(s, h, o) for (s, h, *_, o) in m["st_rows"]], columns=["sid", "h", "obs"])
    xy = st.geometry
    agg = []
    for sid in sorted(set(rows.sid) - m["est_ids"]):
        Nl, bl = solve(drop_station=sid)
        xl = np.linalg.solve(Nl, bl)
        allpred = np.array([kr @ xl[idx] for _, _, idx, kr, _ in m["st_rows"]])
        res = rows.obs.values - allpred
        mask = (rows.sid == sid).values
        ob, pm = rows.obs.values[mask], allpred[mask]
        others = rows[~mask]
        dist = {s: max(xy[sid].distance(xy[s]) / 1000, 0.5) for s in others.sid.unique()}
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
        agg.append(out)
    a = pd.DataFrame(agg, columns=["n", "m", "bm", "i", "bi", "hy", "bh"])
    wr = lambda c: np.sqrt((a.n * a[c] ** 2).sum() / a.n.sum())
    a["um"] = np.sqrt(np.maximum(a.m ** 2 - a.bm ** 2, 0))
    a["uh"] = np.sqrt(np.maximum(a.hy ** 2 - a.bh ** 2, 0))
    return dict(rm=wr("m"), ri=wr("i"), rh=wr("hy"), um=wr("um"), uh=wr("uh"), win=int((a.hy < a.i).sum()), n_st=len(a),
                sun=tot[2] / tot[0], lo=lo, hi=hi, inv=tot[0] / m["prior_rd"].sum(),
                tempo=np.corrcoef(tp_pred, tp_obs)[0, 1],
                aco=pick("Valle de México"), aicm=pick("AICM"), aifa=pick("AIFA"))


VARIANTS = [
    ("S0", "Base estacionaria (industria agrupada + estaciones extra)", "domain", {}, False),
    ("S1", "S0 + cociente semanal de Infovial como a priori", "domain", {}, True),
    ("S2", "S0 + error de viento σθ = 30°", "domain", dict(sigma30=True), False),
    ("S3", "S0 + viento ponderado (CHO, FAC, ACO, CUA × 0.25)", "domain", dict(weighted=True), False),
    ("S4", "S0 + Acolman elevada (200 m)", "domain", dict(stack=True), False),
    ("S5", "S2 + S3 + S4 (física, sin a priori semanal)", "domain", dict(sigma30=True, weighted=True, stack=True), False),
    ("S6", "S5 + a priori semanal (todo)", "domain", dict(sigma30=True, weighted=True, stack=True), True),
    ("P0", "Base no estacionaria (puffs)", "puff", {}, False),
    ("P1", "P0 + perfil horario de Infovial por tipo de día", "puff", dict(infovial_profile=True), False),
    ("P2", "P1 + σθ 30° + viento ponderado (física, sin a priori semanal)", "puff",
     dict(infovial_profile=True, sigma30=True, weighted=True), False),
    ("P3", "P2 + a priori semanal (todo)", "puff", dict(infovial_profile=True, sigma30=True, weighted=True), True),
]


def main():
    lines = ["| Variante | RMSE LOO modelo / IDW / híbrido (ppb) | Hora a hora modelo / híbrido | Híbrido < IDW | "
             "Domingo/hábil (IC 90 %) | Vial / inventario | TEMPO r | Acolman / AICM / AIFA (t/año) |",
             "|---|---|---|---|---|---|---|---|"]
    cache = {}
    for code, label, mode, cfg, prior in VARIANTS:
        configure(**cfg)
        key = (mode, tuple(sorted(cfg.items())))
        if key not in cache:
            cache[key] = rcl.build(START, END, mode, no_industry=True, extras=True)
        m = cache[key]
        E = None
        if prior:
            N0, b0 = rcl.solve(m)
            E = ratio_constraint(m, np.linalg.solve(N0, b0))
        r = evaluate(m, E)
        line = (f"| {code}. {label} | {r['rm']:.1f} / {r['ri']:.1f} / {r['rh']:.1f} | {r['um']:.1f} / {r['uh']:.1f} | "
                f"{r['win']} de {r['n_st']} | {r['sun']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) | {r['inv']:.0%} | {r['tempo']:.2f} | "
                f"{r['aco']:,.0f} / {r['aicm']:,.0f} / {r['aifa']:,.0f} |")
        lines.append(line)
        print(line, flush=True)
    configure()
    out = ROOT / f"reports/improve_real_{START}_{END}.md"
    out.write_text("# Mejoras de bajo esfuerzo con datos reales\n\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
