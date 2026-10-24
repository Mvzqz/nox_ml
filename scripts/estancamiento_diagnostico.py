"""Estancamiento, paso 1: diagnóstico del sesgo del estimador normalizado en días estancados sin contingencia.

Usa la serie horaria del modelo estándar (estancamiento_base.py) y, para cada día sin contingencia de feb–may 2024, el índice
rel = (observado ÷ modelo del día) ÷ (el mismo cociente en sus referencias: mismo día de la semana ±4 semanas).
rel = 1 es "sin cambio de emisión"; es el placebo de un solo día.

Uso: .venv/bin/python scripts/estancamiento_diagnostico.py
Salida: data/interim/estancamiento_diagnostico.json y tablas en pantalla.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contingencias_2024 as c24  # noqa: E402
import estancamiento_comun as ec  # noqa: E402

SEASON = ("2024-02-01", "2024-05-31")


def gm(x):
    return float(np.exp(np.nanmean(np.log(np.asarray(x, float)))))


def main():
    h = ec.load_hourly()
    d = ec.daily_from(h)
    cont, hab, excl = ec.contingency_days(d)
    pool = [x for x in d.index if SEASON[0] <= f"{x:%Y-%m-%d}" <= SEASON[1] and x not in excl]
    F = ec.features(d, h, pool, excl).astype(float)
    out = {"n_dias": len(F)}

    # 1. placebos con la definición del script de contingencias y con el cuartil estricto
    season = (d.index >= "2024-02-01") & (d.index <= "2024-06-15")
    non = ~d.index.isin(excl)
    vq = d.loc[cont].vent.quantile(0.25)
    out["pool_estancado_script"] = {"dias": int((season & non & (d.vent >= vq).values).sum()), "de": int((season & non).sum())}
    c24.rng = np.random.default_rng(11)
    for g, days in (("todos", cont), ("hábiles", hab)):
        p = c24.placebo(d, days, np.asarray(season & non & (d.vent >= vq).values), 500)
        out.setdefault("placebo_estancado_script", {})[g] = [p["mediana"], p["p5"], p["p95"]]
        p = c24.placebo(d, days, np.asarray(season & non), 500)
        out.setdefault("placebo_azar", {})[g] = [p["mediana"], p["p5"], p["p95"]]
        out.setdefault("real", {})[g] = c24.estimate(d, days, excl)

    # 2. por cuartil de ventilación independiente del modelo (viento × capa límite de la tarde)
    F["vv"] = (d.viento * d.pbl).reindex(F.index)
    F["q"] = pd.qcut(F.vv, 4, labels=False)                 # 0 = más estancado
    F["habil"] = F.index.dayofweek < 5
    tab = {}
    for k in range(4):
        g = F[F.q == k]
        tab[k] = {"n": int(len(g)), "viento": float(d.viento.reindex(g.index).mean()), "pbl": float(d.pbl.reindex(g.index).mean()),
                  "rel": gm(g.rel), "rel_habil": gm(g[g.habil].rel), "n_habil": int(g.habil.sum()),
                  "manana": gm(g.mI.dropna()), "prevI": gm(g.prevI.dropna()), "R": float(g.R.mean()),
                  "dth06": float(g.dth06.mean()), "dth18": float(g.dth18.mean()),
                  "frac_dth18_pos": float((g.dth18.dropna() > 0).mean())}
    out["cuartiles"] = tab

    # 3. regresiones de log(rel)
    reg = {}
    for etq, cols in (("met", ["lmet"]), ("viento_pbl", ["lwind", "lpbl"]), ("met+manana", ["lmet", "lmI"]),
                      ("met+previo", ["lmet", "lprevI"]), ("met+previo_modelo", ["lmet", "lprev_met"]), ("met+recirculacion", ["lmet", "R"]),
                      ("met+Δθ18", ["lmet", "dth18"]), ("met+Δθ06", ["lmet", "dth06"]),
                      ("met+Δθ18+previo+R", ["lmet", "dth18", "lprevI", "R"])):
        q = F.dropna(subset=cols + ["lrel"])
        b, t, r2 = ec.ols(q.lrel, q[cols])
        reg[etq] = {"n": int(len(q)), "r2": float(r2), "coef": {k: float(v) for k, v in b.items()}, "t": {k: float(v) for k, v in t.items()}}
    out["regresiones"] = reg

    # 4. días consecutivos estancados: rel según cuántos días previos seguidos estuvieron en el cuartil estancado
    vv_all = (d.viento * d.pbl)
    thr = F.vv.quantile(0.25)
    streak = {}
    for x in F.index:
        n, y = 0, x - pd.Timedelta(days=1)
        while y in vv_all.index and vv_all[y] <= thr and n < 5:
            n += 1
            y -= pd.Timedelta(days=1)
        streak[x] = n
    F["racha"] = pd.Series(streak)
    out["racha"] = {str(k): {"n": int(len(g)), "rel": gm(g.rel), "rel_estancados": gm(g[g.q == 0].rel) if (g.q == 0).any() else None,
                             "n_estancados": int((g.q == 0).sum())}
                    for k, g in F.assign(racha=F.racha.clip(upper=2)).groupby("racha")}

    # 5. capa límite contra radiosondeo: Δθ18 (estabilidad bajo 700 hPa, ~900 m) frente a la capa límite del modelo a las 18 h
    s = ec.sondeos()
    pbl18 = h[h.hl == 16].set_index("day").pbl                  # modelo, 16–17 h locales (última hora del estimador)
    j = pd.DataFrame({"dth18": s.dth18, "pbl16": pbl18}).dropna()
    j = j[(j.index >= SEASON[0]) & (j.index <= SEASON[1])]
    out["sondeo_vs_pbl"] = {"n": int(len(j)), "r": float(j.dth18.corr(np.log(j.pbl16))),
                            "frac_estable_bajo_700": float((j.dth18 > 0).mean()),
                            "pbl16_si_estable": float(j[j.dth18 > 0].pbl16.median()) if (j.dth18 > 0).any() else None,
                            "pbl16_si_mezclado": float(j[j.dth18 <= 0].pbl16.median()), "dth18_mediana": float(j.dth18.median())}
    out["dth06"] = {"mediana": float(s.dth06.median())}

    # 6. días de contingencia: ¿cuánto del exceso explica la regresión ajustada con días sin contingencia?
    Fc = ec.features(d, h, cont, excl).astype(float)
    pred = {}
    for etq, cols in (("met", ["lmet"]), ("met+Δθ18", ["lmet", "dth18"]), ("met+previo+R", ["lmet", "lprevI", "R"])):
        q = F.dropna(subset=cols + ["lrel"])
        b, _, _ = ec.ols(q.lrel, q[cols])
        qc = Fc.dropna(subset=cols)
        p = sum(b[c] * qc[c] for c in cols)
        pred[etq] = {"rel_predicho": float(np.exp(p.mean() + b["const"])), "rel_observado": gm(qc.rel), "n": int(len(qc)),
                     "exceso_no_explicado": float(gm(qc.rel) / np.exp(p.mean() + b["const"]))}
    out["contingencia_explicada"] = pred
    out["contingencia_medias"] = {k: float(Fc[k].mean()) for k in ("rel", "met", "prevI", "R", "dth18")}
    out["pool_medias"] = {k: float(F[k].mean()) for k in ("rel", "met", "prevI", "R", "dth18")}
    (ec.INT / "estancamiento_diagnostico.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))

    print("placebo estancado (script):", out["placebo_estancado_script"], out["pool_estancado_script"])
    print("placebo azar:", out["placebo_azar"])
    print("real:", {g: round(v["emision"], 2) for g, v in out["real"].items()})
    for k, v in tab.items():
        print("cuartil", k, {a: round(b, 2) for a, b in v.items()})
    for k, v in reg.items():
        print(k, round(v["r2"], 2), {a: round(b, 2) for a, b in v["coef"].items()}, {a: round(b, 1) for a, b in v["t"].items()}, v["n"])
    print("racha", out["racha"])
    print("sondeo", out["sondeo_vs_pbl"])
    print("contingencia explicada", pred)
    print(out["contingencia_medias"], out["pool_medias"])


if __name__ == "__main__":
    main()
