"""CO como trazador en las contingencias de 2024: mismo estimador que contingencias_2024.py, aplicado a CO,
NOx y al cociente CO/NOx, en dos ventanas: mañana (7–11 h) y tarde (12–17 h).

Por hora: concentración observada (promedio de estaciones con dato) ÷ índice del modelo con emisión vial fija
(mismo Jacobiano que NOx; el CO es inerte a esta escala, así que la dispersión es la misma). Las estaciones
se promedian por contaminante, cada uno con sus propias estaciones.
Uso: .venv/bin/python scripts/contingencias_co.py [--boot 1000] [--placebos 500] [--rebuild]
Salidas: data/interim/contingencias_co_hourly.parquet, contingencias_co.json
"""
import argparse
import json

import numpy as np
import pandas as pd

import contingencias_2024 as c24
from contingencias_2024 import HOLIDAYS, INT, RAW, START, END, estimate, refs_for, episodes, ozone_daily
from feasibility_linear import jacobian_hour, load_inputs

WINDOWS = {"tarde 12–17 h": (12, 17), "mañana 7–11 h": (7, 11)}
rng = np.random.default_rng(2025)


def build_hourly():
    cand, _, _, cells, _, _, st, _, _, wind, pbl, _ = load_inputs("2024-02-15", "2024-05-31")
    nox = pd.read_parquet(INT / "simat_nox.parquet")[["id_station", "utc", "hour", "local", "NOX"]].rename(columns={"NOX": "v"})
    nox["gas"] = "NOX"
    co = pd.read_parquet(INT / "simat_tracers.parquet")
    co = co[co.id_parameter == "CO"].copy()
    co["hour"] = co.local.dt.hour
    co = co[["id_station", "utc", "hour", "local", "value"]].rename(columns={"value": "v"})
    co["gas"] = "CO"
    al = pd.concat([nox, co])
    al = al[al.local.between(START, f"{END} 23:59") & al.hour.between(7, 17) & al.id_station.isin(st.index) & al.v.notna()].copy()
    al["h"] = al.utc - pd.Timedelta(hours=1)
    n_pt = len(cand)
    px = pd.DataFrame({"x": [], "y": []})
    rows = []
    for h, nh in al.groupby("h"):
        if h not in wind.index or h not in pbl.index or np.isnan(pbl.loc[h]):
            continue
        u = nh.drop_duplicates("id_station").reset_index(drop=True)
        K = jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, u[["id_station"]], px, 0.8)[0][1]
        m_st = pd.Series(K[:, n_pt:n_pt + 9].sum(1), index=u.id_station)
        for gas, g in nh.groupby("gas"):
            rows.append({"h": h, "gas": gas, "hour": int(g.hour.iloc[0]), "day": (h - pd.Timedelta(hours=6)).normalize(),
                         "obs": g.v.mean(), "modelo": m_st.loc[g.id_station].mean(), "n_est": len(g),
                         "pbl": pbl.loc[h], "viento": float(np.hypot(*wind.loc[h].values))})
    df = pd.DataFrame(rows)
    df.to_parquet(INT / "contingencias_co_hourly.parquet")
    return df


def daily(df, lo, hi, gas):
    x = df[(df.gas == gas) & df.hour.between(lo, hi)]
    d = x.groupby("day").agg(obs=("obs", "sum"), modelo=("modelo", "sum"), horas=("h", "size"),
                             pbl=("pbl", "mean"), viento=("viento", "mean"))
    d = d[d.horas >= (4 if hi - lo > 4 else 3)]
    d["ds"] = d.index.strftime("%Y-%m-%d")
    d["dow"] = d.index.dayofweek
    d["festivo"] = d.ds.isin(HOLIDAYS)
    return d


def pair_stats(dn, dc, days, refs_by_day, pick=None):
    """Cocientes de emisión (NOx, CO, CO/NOx) para días `days` con referencias dadas."""
    out = {}
    for name, d in (("NOX", dn), ("CO", dc)):
        refs = [r for x in days for r in refs_by_day[x]]
        c, r = d.loc[days], d.loc[refs]
        out[name] = (c.obs.sum() / c.modelo.sum()) / (r.obs.sum() / r.modelo.sum())
        out[name + "_conc"] = (c.obs.sum() / c.horas.sum()) / (r.obs.sum() / r.horas.sum())
        out[name + "_met"] = (c.modelo.sum() / c.horas.sum()) / (r.modelo.sum() / r.horas.sum())
    out["ratio"] = out["CO"] / out["NOX"]
    return out


def joint_boot(dn, dc, days, excl, n):
    refs = {x: refs_for(dn, x, excl) for x in days}
    days = [x for x in days if refs[x]]
    res = []
    for _ in range(n):
        pick = [days[i] for i in rng.integers(len(days), size=len(days))]
        rb = {}
        stats = {}
        for name, d in (("NOX", dn), ("CO", dc)):
            cd = d.loc[pick]
            rf = [y for x in pick for y in rng.choice(refs[x], len(refs[x]))]
            r = d.loc[rf]
            stats[name] = (cd.obs.sum() / cd.modelo.sum()) / (r.obs.sum() / r.modelo.sum())
        res.append((stats["NOX"], stats["CO"], stats["CO"] / stats["NOX"]))
    a = np.percentile(np.array(res), [5, 95], axis=0)
    return {"NOX": a[:, 0].tolist(), "CO": a[:, 1].tolist(), "ratio": a[:, 2].tolist()}


def joint_placebo(dn, dc, real_days, pool_mask, n):
    real = set(real_days)
    dows = [6 if x.strftime("%Y-%m-%d") in HOLIDAYS else x.dayofweek for x in real_days]
    pool = dn[pool_mask & ~dn.index.isin(real)]
    by = {k: list(pool[np.where(pool.festivo, 6, pool.dow) == k].index) for k in range(7)}
    res = []
    for _ in range(n):
        fake = []
        for k in dows:
            opts = [x for x in by[k] if x not in fake]
            if opts:
                fake.append(opts[rng.integers(len(opts))])
        ex = real | set(fake)
        refs = {x: refs_for(dn, x, ex) for x in fake}
        fk = [x for x in fake if refs[x]]
        if fk:
            s = pair_stats(dn, dc, fk, refs)
            res.append((s["NOX"], s["CO"], s["ratio"]))
    r = np.array(res)
    return {g: {"mediana": float(np.median(r[:, i])), "p5": float(np.percentile(r[:, i], 5)), "p95": float(np.percentile(r[:, i], 95))}
            for i, g in enumerate(("NOX", "CO", "ratio"))} | {"n": len(r)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--placebos", type=int, default=500)
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    f = INT / "contingencias_co_hourly.parquet"
    df = build_hourly() if (a.rebuild or not f.exists()) else pd.read_parquet(f)
    o3 = ozone_daily()
    cont = sorted(pd.to_datetime(pd.read_csv(RAW / "contingencias/contingencias_ozono_2024.csv").fecha))
    out = {}
    for wname, (lo, hi) in WINDOWS.items():
        dn, dc = daily(df, lo, hi, "NOX"), daily(df, lo, hi, "CO")
        idx = dn.index.intersection(dc.index)
        dn, dc = dn.loc[idx].copy(), dc.loc[idx].copy()
        dn["o3max"] = o3.reindex(idx)
        dn["vent"] = dn.modelo / dn.horas
        cd = [x for x in cont if x in idx]
        excl = set(cd) | {x + pd.Timedelta(days=1) for x in cd}
        habiles = [x for x in cd if x.dayofweek < 5 and x.strftime("%Y-%m-%d") not in HOLIDAYS]
        w = {"grupos": {}, "episodios": [], "placebos": {}}
        for gname, days in (("todos", cd), ("hábiles", habiles)):
            refs = {x: refs_for(dn, x, excl) for x in days}
            s = pair_stats(dn, dc, [x for x in days if refs[x]], refs)
            s["ic90"] = joint_boot(dn, dc, days, excl, a.boot)
            s["dias"] = len(days)
            s["pbl"] = float(dn.loc[days].pbl.mean()); s["viento"] = float(dn.loc[days].viento.mean())
            w["grupos"][gname] = s
        season = (idx >= "2024-02-01") & (idx <= "2024-06-15")
        non = ~idx.isin(excl)
        vq = dn.loc[cd].vent.quantile(0.25)
        pools = {"aleatorio": season & non, "estancado": season & non & (dn.vent >= vq).values}
        for pn, mask in pools.items():
            for gname, days in (("todos", cd), ("hábiles", habiles)):
                w["placebos"][f"{pn}|{gname}"] = joint_placebo(dn, dc, days, np.asarray(mask), a.placebos)
        out[wname] = w
        print(f"== {wname}: {len(cd)} días de contingencia con datos de ambos")
        for g, s in w["grupos"].items():
            print(f" {g:8s} n={s['dias']} NOx conc {s['NOX_conc']:.2f} met {s['NOX_met']:.2f} emis {s['NOX']:.2f} ({s['ic90']['NOX'][0]:.2f}–{s['ic90']['NOX'][1]:.2f}) | "
                  f"CO conc {s['CO_conc']:.2f} met {s['CO_met']:.2f} emis {s['CO']:.2f} ({s['ic90']['CO'][0]:.2f}–{s['ic90']['CO'][1]:.2f}) | "
                  f"CO/NOx {s['ratio']:.2f} ({s['ic90']['ratio'][0]:.2f}–{s['ic90']['ratio'][1]:.2f})")
        for k, p in w["placebos"].items():
            print(f"  placebo {k:20s} " + " | ".join(f"{g} {p[g]['mediana']:.2f} [{p[g]['p5']:.2f}–{p[g]['p95']:.2f}]" for g in ("NOX", "CO", "ratio")) + f" n={p['n']}")
    (INT / "contingencias_co.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
