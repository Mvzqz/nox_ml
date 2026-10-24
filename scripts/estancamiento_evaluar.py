"""Estancamiento, paso 2: evalúa las correcciones contra los criterios (placebo estancado, aleatorio, domingo, validación 2020).

Variantes de modelo (estancamiento_base.py): se leen de data/interim/estancamiento_horario[_variante].parquet.
Variantes empíricas (sobre el modelo base): el denominador del día se multiplica por (vent/vent_ref)^(γ−1)·exp(κ·(Δθ18 − mediana)),
con γ y κ ajustados con días SIN contingencia (feb–may 2024) de la regresión
    log(rel) = a + (γ−1)·log(met) + κ·Δθ18,
donde rel = índice del día ÷ índice de sus referencias (mismo día de la semana ±4 semanas), met = ventilación modelada relativa
y Δθ18 = estabilidad 700 hPa − superficie del radiosondeo de las 18 h locales.

Uso: .venv/bin/python scripts/estancamiento_evaluar.py
Salida: data/interim/estancamiento_evaluacion.json y tablas en pantalla.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contingencias_2024 as c24  # noqa: E402
import estancamiento_comun as ec  # noqa: E402
import real_check_linear as rcl  # noqa: E402
import val2020_ratio as v20  # noqa: E402

INT = ec.INT
SEASON = ("2024-02-01", "2024-05-31")
MODELOS = ["base", "pbl_tope1500", "pbl_tope1000", "pbl_encogida50", "pbl_clim", "pbl_sonda10", "pbl_sonda20",
           "pbl_sonda20_encogida50", "edad48", "umin15", "umin20", "umin25", "umin30", "umin20_sonda10"]
NPLAC = 300


def gm(x):
    x = np.asarray(x, float)
    return float(np.exp(np.nanmean(np.log(x))))


def load(variant):
    f = "estancamiento_horario.parquet" if variant == "base" else f"estancamiento_horario_{variant}.parquet"
    if not (INT / f).exists():
        return None
    h = ec.load_hourly(f)
    return h, ec.daily_from(h)


def pool_days(d, excl):
    return [x for x in d.index if SEASON[0] <= f"{x:%Y-%m-%d}" <= SEASON[1] and x not in excl]


def sunday(d, a, b):
    """Estimador normalizado del domingo (domingo+festivo ÷ hábil), como la_real.metrics."""
    x = d[(d.index >= a) & (d.index <= b)].copy()
    x["dt"] = [rcl.day_type(t + pd.Timedelta(hours=6)) for t in x.index]
    g = x.groupby("dt")
    v = g.obs.sum() / g.modelo.sum()
    wk = x[x.dt == 0]
    cv = float((wk.obs / wk.modelo).std() / (wk.obs / wk.modelo).mean())
    return float(v[2] / v[0]), float(v[1] / v[0]), cv


def pendiente(d, days, excl):
    """Pendiente de log(rel) sobre log(ventilación modelada relativa) en `days` y su t."""
    rel = ec.rel_single(d, days, excl)
    met = pd.Series({x: np.log((d.loc[x].modelo / d.loc[x].horas) / (d.loc[r].modelo.sum() / d.loc[r].horas.sum()))
                     for x in rel.index for r in [c24.refs_for(d, x, excl)]})
    b, t, _ = ec.ols(np.log(rel), pd.DataFrame({"lmet": met}))
    return float(b["lmet"]), float(t["lmet"]), int(len(rel))


def metrics(name, d, base_d, cont, hab, excl, lmet_ref=None):
    out = {"nombre": name}
    pool = pool_days(d, excl)
    rel = ec.rel_single(d, pool, excl)
    # ventilación independiente del modelo: viento × capa límite base (mismos días en todas las variantes)
    vv = (base_d.viento * base_d.pbl).reindex(rel.index)
    q = pd.qcut(vv, 4, labels=False)
    out["rel_q"] = [gm(rel[q == k]) for k in range(4)]            # 0 = más estancado
    out["rel_estancado_habil"] = gm(rel[(q == 0) & (rel.index.dayofweek < 5)])
    out["n_estancado"] = int((q == 0).sum())
    rng = np.random.default_rng(5)
    bs = [gm(rel[q == 0].values[rng.integers(0, int((q == 0).sum()), int((q == 0).sum()))]) for _ in range(1000)]
    out["rel_estancado_ic90"] = [float(np.percentile(bs, 5)), float(np.percentile(bs, 95))]
    out["sd_log_rel"] = float(np.log(rel).std())
    # pendiente de log rel sobre log(ventilación modelada relativa)
    met = {}
    for day in rel.index:
        r = c24.refs_for(d, day, excl)
        met[day] = np.log((d.loc[day].modelo / d.loc[day].horas) / (d.loc[r].modelo.sum() / d.loc[r].horas.sum())) if lmet_ref is None else lmet_ref[day]
    met = pd.Series(met)
    b, t, r2 = ec.ols(np.log(rel), pd.DataFrame({"lmet": met}))
    out["pendiente"], out["pendiente_t"], out["r2_met"] = b["lmet"], t["lmet"], r2
    pre = [x for x in d.index if x not in excl and "2023-11-08" <= f"{x:%Y-%m-%d}" <= "2024-01-31"
           and not ("2023-12-20" <= f"{x:%Y-%m-%d}" <= "2024-01-07")]
    out["pendiente_previo"] = pendiente(d, pre, excl) if lmet_ref is None else None
    # estimador real y placebos (definición del script de contingencias)
    for g, days in (("todos", cont), ("hábiles", hab)):
        out.setdefault("real", {})[g] = c24.estimate(d, days, excl)["emision"]
    season = (d.index >= "2024-02-01") & (d.index <= "2024-06-15")
    non = ~d.index.isin(excl)
    vq = d.loc[cont].vent.quantile(0.25)
    oq = d[season & non].o3max.quantile(0.75)
    pools = {"azar": season & non, "estancado": season & non & (d.vent >= vq).values, "ozono alto": season & non & (d.o3max >= oq).values}
    out["placebo"] = {}
    for k, m in pools.items():
        for g, days in (("todos", cont), ("hábiles", hab)):
            c24.rng = np.random.default_rng(11)
            p = c24.placebo(d, days, np.asarray(m), NPLAC)
            out["placebo"][f"{k}|{g}"] = [p["mediana"], p["p5"], p["p95"]]
    out["domingo_nov23"], out["sabado_nov23"], out["cv_nov23"] = sunday(d, "2023-11-01", "2023-12-31")
    out["domingo_prim24"], out["sabado_prim24"], out["cv_prim24"] = sunday(d, "2024-02-15", "2024-05-31")
    return out


def fit(base_d, base_h, excl, days):
    """γ y κ de log rel = a + (γ−1) log met + κ Δθ18 con los días `days` (sin contingencia)."""
    F = ec.features(base_d, base_h, days, excl).astype(float)
    return F


def coef(F, with_dth):
    cols = ["lmet"] + (["dth18"] if with_dth else [])
    q = F.dropna(subset=cols + ["lrel"])
    q = q.assign(dth18=q.dth18 - DTH_MED) if with_dth else q
    b, t, r2 = ec.ols(q.lrel, q[cols])
    return b, t


DTH_MED = float(ec.sondeos().dth18.median())


def adjust(d, gamma, kappa, vent_ref, desde_sondeo=None):
    """Denominador corregido: modelo · (vent/ref)^(γ−1) · exp(κ·(Δθ18 − mediana))."""
    x = d.copy()
    f = (x.vent / vent_ref) ** (gamma - 1)
    if kappa:
        s = ec.sondeos().dth18.reindex(x.index)
        f = f * np.exp(kappa * (s - DTH_MED).fillna(0.0))
    x["modelo"] = x.modelo * f
    return x


def cv_empirico(F, with_dth, nfold=8):
    """Validación cruzada por bloques de días consecutivos: sd del log(rel) y media del cuartil estancado, antes y después."""
    F = F.sort_index().dropna(subset=["lrel", "lmet"] + (["dth18"] if with_dth else []))
    blocks = np.array_split(np.arange(len(F)), nfold)
    res = pd.Series(index=F.index, dtype=float)
    for bl in blocks:
        tr = F.drop(F.index[bl])
        b, _ = coef(tr, with_dth)
        te = F.iloc[bl]
        pred = b["lmet"] * te.lmet + (b.get("dth18", 0) * (te.dth18 - DTH_MED) if with_dth else 0) + b["const"]
        res.iloc[bl] = te.lrel - pred + b["const"]       # se conserva la constante: solo se quita lo explicado por met y Δθ18
    return F.lrel, res


def run_val2020(gamma, kappa):
    """Los 8 estimadores de val2020_ratio (año × fase × tipo de día) con el denominador corregido día a día."""
    out = {}
    for y in (2020, 2019):
        df = pd.read_parquet(INT / f"val2020_hourly_{y}.parquet")
        vent = df.groupby("day").modelo.transform("mean")
        ref = np.exp(np.log(df.groupby("day").modelo.mean()).mean())
        f = (vent / ref) ** (gamma - 1)
        if kappa:
            s = ec.sondeos("2018-12-01", "2021-01-01").dth18
            med = s.median()
            f = f * np.exp(kappa * (df.day.map(s) - med).fillna(0.0))
        df["modelo"] = df.modelo * f
        for p in (1, 2):
            for dt in (0, 1):
                out[f"{y}|{v20.NAMES[p]}|{v20.DAY[dt]}"] = float(v20.ratio(df, dt, 2 * p + dt))
    return out


def main():
    base = load("base")
    bh, bd = base
    cont, hab, excl = ec.contingency_days(bd)
    pool = pool_days(bd, excl)
    res = {"modelos": {}, "empiricas": {}}
    # --- variantes de modelo
    for v in MODELOS:
        r = load(v)
        if r is None:
            print("falta", v)
            continue
        res["modelos"][v] = metrics(v, r[1], bd, cont, hab, excl)
        print(v, "listo", flush=True)
    # --- correcciones empíricas
    F = fit(bd, bh, excl, pool)
    vent_ref = float(np.exp(np.log(bd.loc[pool].vent).mean()))
    nonc = [x for x in bd.index if x not in excl and "2023-11-08" <= f"{x:%Y-%m-%d}" <= "2024-05-31"
            and not ("2023-12-20" <= f"{x:%Y-%m-%d}" <= "2024-01-07")]
    F_all = fit(bd, bh, excl, nonc)
    F_pre = F_all[F_all.index < "2024-02-01"]          # solo datos anteriores al periodo de prueba
    defs = (("emp_gamma", False, F), ("emp_gamma_sonda", True, F), ("emp_gamma_previo", False, F_pre),
            ("emp_gamma_todo", False, F_all))
    for name, with_dth, Ffit in defs:
        b, t = coef(Ffit, with_dth)
        gamma, kappa = 1 + b["lmet"], b.get("dth18", 0.0)
        # el denominador solo recibe lo explicado por met y Δθ18 (la constante se ignora: se cancela en el cociente)
        d = adjust(bd, gamma, kappa, vent_ref)
        lmet_base = {x: np.log((bd.loc[x].modelo / bd.loc[x].horas) / (bd.loc[c24.refs_for(bd, x, excl)].modelo.sum() / bd.loc[c24.refs_for(bd, x, excl)].horas.sum())) for x in ec.rel_single(bd, pool, excl).index}
        m = metrics(name, d, bd, cont, hab, excl, lmet_ref=lmet_base)
        m.update(gamma=float(gamma), kappa=float(kappa), t=t)
        m['n_ajuste'] = int(Ffit.dropna(subset=['lrel', 'lmet']).shape[0])
        a, bcv = cv_empirico(F, with_dth)
        m["cv"] = {"sd_antes": float(a.std()), "sd_despues": float(bcv.std())}
        # fuera de muestra temporal: ajustar con feb–mar, probar en abr–may (y al revés)
        for etq, (tr_rng, te_rng) in {"feb-mar→abr-may": (("2024-02-01", "2024-03-31"), ("2024-04-01", "2024-05-31")),
                                      "abr-may→feb-mar": (("2024-04-01", "2024-05-31"), ("2024-02-01", "2024-03-31"))}.items():
            tr = F[(F.index >= tr_rng[0]) & (F.index <= tr_rng[1])]
            te = F[(F.index >= te_rng[0]) & (F.index <= te_rng[1])].dropna(subset=["lrel", "lmet"] + (["dth18"] if with_dth else []))
            bb, _ = coef(tr, with_dth)
            pred = bb["lmet"] * te.lmet + (bb["dth18"] * (te.dth18 - DTH_MED) if with_dth else 0)
            m.setdefault("temporal", {})[etq] = {"sd_antes": float(te.lrel.std()), "sd_despues": float((te.lrel - pred).std()), "gamma": float(1 + bb["lmet"])}
        m["val2020"] = run_val2020(gamma, kappa)
        res["empiricas"][name] = m
        print(name, "gamma", round(gamma, 2), "kappa", round(kappa, 3), flush=True)
    res["val2020_base"] = run_val2020(1.0, 0.0)
    res["val2020_original"] = {f"{y}|{k}": v["estimado"] for y in ("2020", "2019") for k, v in json.loads((INT / "val2020_ratio.json").read_text())[y].items()}
    (INT / "estancamiento_evaluacion.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print_tables(res)


def print_tables(res):
    allm = {**res["modelos"], **res["empiricas"]}
    print("\nnombre | rel por cuartil (estancado→ventilado) | estancado hábil (IC) | pendiente(t) | real todos/hábiles | placebo estancado | azar | domingo nov/prim | CV nov/prim")
    for k, m in allm.items():
        print(f"{k:24s} {[round(x, 2) for x in m['rel_q']]} {m['rel_estancado_habil']:.2f} ({m['rel_estancado_ic90'][0]:.2f}-{m['rel_estancado_ic90'][1]:.2f}) "
              f"pend {m['pendiente']:.2f} (t {m['pendiente_t']:.1f}; previo {m['pendiente_previo'][0] if m['pendiente_previo'] else float('nan'):.2f}) real {m['real']['todos']:.2f}/{m['real']['hábiles']:.2f} "
              f"est {m['placebo']['estancado|todos'][0]:.2f} [{m['placebo']['estancado|todos'][1]:.2f}-{m['placebo']['estancado|todos'][2]:.2f}] "
              f"azar {m['placebo']['azar|todos'][0]:.2f} [{m['placebo']['azar|todos'][1]:.2f}-{m['placebo']['azar|todos'][2]:.2f}] "
              f"dom {m['domingo_nov23']:.2f}/{m['domingo_prim24']:.2f} cv {m['cv_nov23']:.2f}/{m['cv_prim24']:.2f} sd {m['sd_log_rel']:.3f}")
    for k, m in res["empiricas"].items():
        print(k, {a: round(b, 3) for a, b in m.items() if a in ("gamma", "kappa")}, m["cv"], m["temporal"])
        print("  val2020", {a: round(b, 2) for a, b in m["val2020"].items()})
    print("val2020 base ", {a: round(b, 2) for a, b in res["val2020_base"].items()})
    print("val2020 orig ", {a: round(b, 2) for a, b in res["val2020_original"].items()})


if __name__ == "__main__":
    main()
