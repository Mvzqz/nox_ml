"""Contingencias ambientales de 2024 con el estimador normalizado por meteorología.

Mismo estimador que pasó el placebo de 2019 (val2020_ratio.py): por hora de la tarde (12–17 h), NOₓ
observado (promedio de estaciones) ÷ NOₓ que predice el modelo con la emisión vial fija del a priori.
El cociente de ese índice entre días de contingencia y días de referencia comparables (mismo día de la
semana, ±4 semanas, sin contingencia) estima el cambio de emisión ya descontada la ventilación.

Calibración con placebos (días falsos de contingencia, sin medidas):
  - aleatorio: mismos días de la semana, sorteados entre los días sin contingencia de feb–jun;
  - estancado: igual, pero solo días con poca ventilación (modelo con emisión fija alto), como los reales;
  - ozono alto: los días sin contingencia con más O₃ máximo (la contingencia se activa por O₃).

Uso: .venv/bin/python scripts/contingencias_2024.py [--boot 1000] [--placebos 1000]
Salidas: data/interim/contingencias_2024_hourly.parquet, contingencias_2024.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from feasibility_linear import jacobian_hour, load_inputs

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
RAW = ROOT / "data/raw"
START, END = "2024-01-15", "2024-06-30"
HOLIDAYS = {"2024-02-05", "2024-03-18", "2024-03-28", "2024-03-29", "2024-05-01"}
WINDOW = 28  # días de búsqueda de referencias a cada lado
rng = np.random.default_rng(2024)


def build_hourly():
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, _, _, wind, pbl, _ = load_inputs("2024-02-15", "2024-05-31")
    nox = pd.read_parquet(INT / "simat_nox.parquet")
    nox = nox[nox.local.between(START, f"{END} 23:59") & nox.hour.between(12, 17) & nox.id_station.isin(st.index)]
    nox = nox[nox.NOX.notna()].copy()
    nox["h"] = nox.utc - pd.Timedelta(hours=1)
    n_pt = len(cand)
    px_empty = pd.DataFrame({"x": [], "y": []})
    rows = []
    for h, nh in nox.groupby("h"):
        if h not in wind.index or h not in pbl.index or np.isnan(pbl.loc[h]):
            continue
        K = jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, px_empty, 0.8)[0][1]
        rows.append({"h": h, "day": (h - pd.Timedelta(hours=6)).normalize(), "obs": nh.NOX.mean(),
                     "modelo": K[:, n_pt:n_pt + 9].sum(1).mean(), "n_est": len(nh),
                     "pbl": pbl.loc[h], "viento": float(np.hypot(*wind.loc[h].values))})
    df = pd.DataFrame(rows)
    df.to_parquet(INT / "contingencias_2024_hourly.parquet")
    return df


def ozone_daily():
    o = pd.read_csv(RAW / "simat/contaminantes_2024.csv.gz", skiprows=9, compression="zip")
    o = o[o.id_parameter == "O3"].dropna(subset=["value"])
    o["day"] = pd.to_datetime(o.date, format="ISO8601").dt.normalize()
    return o.groupby("day").value.max()  # máximo horario de cualquier estación, ppb


def daily(df):
    d = df.groupby("day").agg(obs=("obs", "sum"), modelo=("modelo", "sum"), horas=("h", "size"),
                              pbl=("pbl", "mean"), viento=("viento", "mean"))
    d = d[d.horas >= 4]
    d["ds"] = d.index.strftime("%Y-%m-%d")
    d["dow"] = d.index.dayofweek
    d["festivo"] = d.ds.isin(HOLIDAYS)
    return d


def refs_for(d, day, excluded):
    """Días de referencia: mismo día de la semana (festivo ↔ domingo), ±WINDOW días, fuera de `excluded`."""
    dow = 6 if day.strftime("%Y-%m-%d") in HOLIDAYS else day.dayofweek
    cand = d[(abs((d.index - day).days) <= WINDOW) & ~d.index.isin(excluded)]
    cand = cand[np.where(cand.festivo, 6, cand.dow) == dow]
    return list(cand.index)


def estimate(d, days, excluded):
    """Cocientes contingencia ÷ referencia: concentración, meteorología (modelo con emisión fija) y emisión."""
    refs = [r for day in days for r in refs_for(d, day, excluded)]
    if not refs:
        return None
    c, r = d.loc[days], d.loc[refs]
    conc = (c.obs.sum() / c.horas.sum()) / (r.obs.sum() / r.horas.sum())
    met = (c.modelo.sum() / c.horas.sum()) / (r.modelo.sum() / r.horas.sum())
    return {"concentracion": conc, "meteorologia": met, "emision": conc / met, "n_ref": len(set(refs))}


def boot(d, days, excluded, n):
    """Bootstrap estratificado: remuestrea días de contingencia y, para cada uno, sus referencias."""
    pairs = [(day, refs_for(d, day, excluded)) for day in days]
    pairs = [(a, b) for a, b in pairs if b]
    out = []
    for _ in range(n):
        pick = [pairs[i] for i in rng.integers(len(pairs), size=len(pairs))]
        cd = [a for a, _ in pick]
        rf = [x for _, b in pick for x in rng.choice(b, len(b))]
        c, r = d.loc[cd], d.loc[rf]
        out.append((c.obs.sum() / c.modelo.sum()) / (r.obs.sum() / r.modelo.sum()))
    return np.percentile(out, [5, 95])


def placebo(d, real_days, pool_mask, n):
    """Distribución del estimador con días falsos: mismo patrón de días de la semana, sacados de `pool_mask`."""
    real = set(real_days)
    dows = [6 if x.strftime("%Y-%m-%d") in HOLIDAYS else x.dayofweek for x in real_days]
    pool = d[pool_mask & ~d.index.isin(real)]
    by_dow = {k: list(pool[np.where(pool.festivo, 6, pool.dow) == k].index) for k in range(7)}
    res = []
    for _ in range(n):
        fake = []
        for k in dows:
            opts = [x for x in by_dow[k] if x not in fake]
            if opts:
                fake.append(opts[rng.integers(len(opts))])
        e = estimate(d, fake, real | set(fake))
        if e:
            res.append(e["emision"])
    res = np.array(res)
    return {"mediana": float(np.median(res)), "p5": float(np.percentile(res, 5)), "p95": float(np.percentile(res, 95)),
            "n": len(res), "muestras": res}


def episodes(days):
    ep, cur = [], [days[0]]
    for a in days[1:]:
        if (a - cur[-1]).days <= 1:
            cur.append(a)
        else:
            ep.append(cur)
            cur = [a]
    ep.append(cur)
    return ep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--placebos", type=int, default=1000)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--shift", type=int, default=0, help="desplaza las fechas (1 = las medidas aplican al día siguiente)")
    a = ap.parse_args()
    f = INT / "contingencias_2024_hourly.parquet"
    df = build_hourly() if (a.rebuild or not f.exists()) else pd.read_parquet(f)
    d = daily(df)
    d["o3max"] = ozone_daily().reindex(d.index)
    d["vent"] = d.modelo / d.horas  # alto = poca ventilación

    cont = pd.to_datetime(pd.read_csv(RAW / "contingencias/contingencias_ozono_2024.csv").fecha)
    cont = sorted(set(cont + pd.Timedelta(days=a.shift)))
    cont = [x for x in cont if x in d.index]
    excl = set(cont)
    # el día siguiente a una contingencia aún puede tener medidas: no se usa como referencia
    excl |= {x + pd.Timedelta(days=1) for x in cont}
    habiles = [x for x in cont if x.dayofweek < 5 and x.strftime("%Y-%m-%d") not in HOLIDAYS]
    findes = [x for x in cont if x not in habiles]

    out = {"dias_contingencia": len(cont), "dias_con_datos": int(len(d)), "grupos": {}, "episodios": [], "placebos": {}}
    for name, days in (("todos", cont), ("hábiles", habiles), ("fin de semana/festivo", findes)):
        e = estimate(d, days, excl)
        e["ic90"] = [float(v) for v in boot(d, days, excl, a.boot)]
        e["dias"] = len(days)
        e.update({k: float(d.loc[days][k].mean()) for k in ("pbl", "viento", "o3max")})
        out["grupos"][name] = e
    for ep in episodes(sorted(cont)):
        e = estimate(d, ep, excl)
        e["ic90"] = [float(v) for v in boot(d, ep, excl, a.boot)]
        e["fechas"] = f"{ep[0]:%d %b}" + ("" if len(ep) == 1 else f"–{ep[-1]:%d %b}")
        e["dias"] = len(ep)
        e["o3max"] = float(d.loc[ep].o3max.mean())
        out["episodios"].append(e)

    season = (d.index >= "2024-02-01") & (d.index <= "2024-06-15")
    non = ~d.index.isin(excl)
    vq = d.loc[cont].vent.quantile(0.25)
    oq = d[season & non].o3max.quantile(0.75)
    pools = {"aleatorio": season & non,
             "estancado": season & non & (d.vent >= vq).values,
             "ozono alto": season & non & (d.o3max >= oq).values}
    samples = {}
    for name, mask in pools.items():
        for grp, days in (("todos", cont), ("hábiles", habiles)):
            p = placebo(d, days, np.asarray(mask), a.placebos)
            samples[(name, grp)] = p.pop("muestras")
            p["dias_disponibles"] = int(np.asarray(mask).sum())
            out["placebos"][f"{name}|{grp}"] = p
    # estimación corregida por el placebo estancado: cociente real ÷ cociente placebo
    for grp in ("todos", "hábiles"):
        s = samples[("estancado", grp)]
        est = out["grupos"][grp]["emision"]
        out["grupos"][grp]["corregido_estancado"] = {"estimado": float(est / np.median(s)),
                                                     "rango_placebo": [float(est / np.percentile(s, 95)), float(est / np.percentile(s, 5))],
                                                     "fraccion_placebos_menores": float((s <= est).mean())}
    out["umbrales"] = {"ventilacion_q25_contingencia": float(vq), "o3max_q75_sin_contingencia": float(oq)}
    (INT / f"contingencias_2024{'' if a.shift == 0 else f'_shift{a.shift}'}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))

    print(f"Días de contingencia con datos: {len(cont)}; días con datos {len(d)}")
    for k, v in out["grupos"].items():
        print(f"{k:22s} n={v['dias']:2d} conc {v['concentracion']:.2f}  meteo {v['meteorologia']:.2f}  emisión {v['emision']:.2f} "
              f"(IC90 {v['ic90'][0]:.2f}–{v['ic90'][1]:.2f})  PBL {v['pbl']:.0f} viento {v['viento']:.1f} O3 {v['o3max']:.0f}")
        if "corregido_estancado" in v:
            c = v["corregido_estancado"]
            print(f"   corregido por placebo estancado {c['estimado']:.2f} ({c['rango_placebo'][0]:.2f}–{c['rango_placebo'][1]:.2f}); "
                  f"placebos ≤ real: {c['fraccion_placebos_menores']:.0%}")
    for e in out["episodios"]:
        print(f"  {e['fechas']:14s} n={e['dias']}  conc {e['concentracion']:.2f}  meteo {e['meteorologia']:.2f}  "
              f"emisión {e['emision']:.2f} ({e['ic90'][0]:.2f}–{e['ic90'][1]:.2f})  O3 {e['o3max']:.0f}")
    for k, v in out["placebos"].items():
        print(f"placebo {k:28s} mediana {v['mediana']:.2f}  90 % {v['p5']:.2f}–{v['p95']:.2f}  (pool {v['dias_disponibles']} días)")
    print(out["umbrales"])
    # meteorología media
    print(d[season & non][["pbl", "viento", "o3max", "vent"]].mean().round(2).to_dict())
    print(d.loc[cont][["pbl", "viento", "o3max", "vent"]].mean().round(2).to_dict())


if __name__ == "__main__":
    main()
