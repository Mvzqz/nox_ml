"""Banco datos-vs-desempeño: estimador normalizado en Bogotá, nov–dic 2023, solo estaciones (reports/banco_datos.md).

Sin TEMPO ni red vial de Bogotá integradas, el "modelo con emisión fija" es la caja 1/(viento · capa límite)
(como bogota_dsc.py). Se calcula, con la misma definición que la_real.metrics y benchmark_common.normalized:
domingo/hábil, ancho del placebo (hábiles falsos como domingos) y CV de los hábiles; con las 15 estaciones y con
subconjuntos de 9 (5 al azar), para comparar con la CDMX en caja (benchmark_real.py, configuración "caja").
Tarde 12–17 h local (UTC−5). Festivos de Colombia en el periodo tratados como domingo.
Salida: data/interim/benchmark/bogota.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import bogota_dsc as bd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/interim/benchmark"
SOLO_VIENTO = False
FESTIVOS = {"2023-11-06", "2023-11-13", "2023-12-08", "2023-12-25"}


def day_type(d):
    if d.strftime("%Y-%m-%d") in FESTIVOS or d.dayofweek == 6:
        return 2
    return 1 if d.dayofweek == 5 else 0


def normalized(hourly, rng, n_placebo=2000):
    hourly = hourly.assign(day=hourly.index.normalize())
    dd = hourly.groupby("day").agg(obs=("obs", "sum"), fixed=("modelo", "sum"), n=("obs", "size"))
    dd = dd[dd.n >= 4]
    dd["dt"] = [day_type(d) for d in dd.index]

    def nr(q, a=0, b=2):
        g = q.groupby("dt")
        v = g.obs.sum() / g.fixed.sum()
        return v.get(b, np.nan) / v[a]

    def nr_crudo(q, a=0, b=2):
        g = q.groupby("dt")
        v = g.obs.sum() / g.n.sum()
        return v.get(b, np.nan) / v[a]
    out = {"norm_domingo": float(nr(dd)), "crudo_domingo": float(nr_crudo(dd))}
    out["norm_domingo_ic"] = np.nanpercentile([nr(dd.iloc[rng.integers(0, len(dd), len(dd))]) for _ in range(1000)], [5, 95]).tolist()
    wk = dd[dd.dt == 0]
    q = wk.obs / wk.fixed
    out["norm_cv_habiles"] = float(q.std() / q.mean())
    out["crudo_cv_habiles"] = float((wk.obs / wk.n).std() / (wk.obs / wk.n).mean())
    k = int((dd.dt == 2).sum())
    pl = []
    for _ in range(n_placebo):
        fake = np.zeros(len(wk), bool)
        fake[rng.choice(len(wk), k, replace=False)] = True
        a, b = wk[~fake], wk[fake]
        pl.append((b.obs.sum() / b.fixed.sum()) / (a.obs.sum() / a.fixed.sum()))
    out["placebo_mitad_ancho"] = float((np.percentile(pl, 95) - np.percentile(pl, 5)) / 2)
    out["n_domingos"], out["n_habiles"] = k, int(len(wk))
    return out


def city_hourly(st, stations, pbl):
    w = st[st.station.isin(stations)]
    nox = w.pivot_table(index=w.index, columns="station", values="nox")
    ws = w.pivot_table(index=w.index, columns="station", values="ws")
    lvl = nox.mean()
    city = (nox / lvl).mean(axis=1) * lvl.mean()
    df = pd.DataFrame({"obs": city, "frac": nox.notna().mean(axis=1), "ws": ws.mean(axis=1)})
    df = df[(df.frac >= 0.6) & df.index.hour.isin(range(12, 18))]
    df["pbl"] = pbl.reindex(df.index)
    df["modelo"] = 1.0 / (df.ws.clip(lower=bd.U_MIN) * df.pbl.clip(lower=bd.H_MIN))
    if SOLO_VIENTO:  # bogota.md: en Bogotá la capa límite de ERA5 empeora la normalización
        df["modelo"] = 1.0 / df.ws.clip(lower=bd.U_MIN)
    return df.dropna(subset=["obs", "ws", "pbl"])


def main():
    frames = [f for f in (bd.parse(p) for p in sorted((ROOT / "data/raw/bogota").glob("rmcab_*_2023-11_2023-12.json"))) if f is not None]
    st = pd.concat(frames)
    st = st[(st.index >= "2023-11-01") & (st.index < "2024-01-01")]
    cov = st[st.index.hour.isin(range(12, 18))].groupby("station").nox.apply(lambda s: s.notna().mean())
    good = sorted(cov[cov >= 0.86].index)
    pbl, _ = bd.load_pbl()
    rng = np.random.default_rng(5)
    global SOLO_VIENTO
    res = {"todas": normalized(city_hourly(st, good, pbl), rng) | {"n_estaciones": len(good)}}
    SOLO_VIENTO = True
    res["todas_solo_viento"] = normalized(city_hourly(st, good, pbl), rng) | {"n_estaciones": len(good)}
    SOLO_VIENTO = False
    srng = np.random.default_rng(99)
    for n in (9,):
        for s in range(5):
            keep = list(srng.choice(good, n, replace=False))
            res[f"est{n}_s{s}"] = normalized(city_hourly(st, keep, pbl), rng) | {"n_estaciones": n}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bogota.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
