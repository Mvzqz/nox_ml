"""Error real del viento: validación cruzada dejando fuera cada estación de viento.

Para cada estación REDMET (y los METAR de AICM y AIFA) en nov–dic 2023, 12–17 h, se predice su
viento con (a) el vector medio de las demás estaciones (como usa el modelo lineal) y (b) IDW de
las demás. Se reporta el error de dirección (horas con viento observado ≥ 1 m/s) y de velocidad.

Uso: .venv/bin/python scripts/wind_loo.py [inicio] [fin]
Salida: data/interim/wind_loo.csv e impresión de tablas en markdown.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from feasibility_linear import load_inputs

ROOT = Path(__file__).resolve().parents[1]
start, end = (sys.argv[1:3] if len(sys.argv) > 2 else ("2023-11-01", "2023-12-31"))


def ang_err(u1, v1, u2, v2):
    a1, a2 = np.degrees(np.arctan2(u1, v1)), np.degrees(np.arctan2(u2, v2))
    return np.abs((a1 - a2 + 180) % 360 - 180)


def main():
    _, _, _, _, _, _, st, nox, _, wind, _, _ = load_inputs(start, end, extras=True)
    w = wind.attrs["by_station"].copy()
    w = w[w.id_station.isin(st.index)]
    loc = w.h + pd.Timedelta(hours=-6)
    w = w[(loc >= start) & (loc < pd.Timestamp(end) + pd.Timedelta(days=1)) & loc.dt.hour.between(12, 17)]
    xy = {s: (st.loc[s].geometry.x, st.loc[s].geometry.y) for s in w.id_station.unique()}
    rows = []
    for h, g in w.groupby("h"):
        if len(g) < 4:
            continue
        for i, r in g.iterrows():
            o = g.drop(index=i)
            d = np.array([np.hypot(xy[s][0] - xy[r.id_station][0], xy[s][1] - xy[r.id_station][1]) for s in o.id_station])
            wt = 1 / np.maximum(d, 500) ** 2
            rows.append(dict(sid=r.id_station, h=h, u=r.u, v=r.v,
                             u_mean=o.u.mean(), v_mean=o.v.mean(),
                             u_idw=(wt * o.u).sum() / wt.sum(), v_idw=(wt * o.v).sum() / wt.sum()))
    df = pd.DataFrame(rows)
    df["sp"] = np.hypot(df.u, df.v)
    for m in ("mean", "idw"):
        df[f"dir_{m}"] = ang_err(df.u, df.v, df[f"u_{m}"], df[f"v_{m}"])
        df[f"sp_{m}"] = np.hypot(df[f"u_{m}"], df[f"v_{m}"]) - df.sp
    df.to_csv(ROOT / "data/interim/wind_loo.csv", index=False)
    ok = df[df.sp >= 1]
    print(f"Horas-estación: {len(df):,}; con viento ≥ 1 m/s: {len(ok):,} ({len(ok) / len(df):.0%}); estaciones: {df.sid.nunique()}\n")
    print("| Método | Error dirección mediana | p75 | Sesgo velocidad | Error abs. velocidad mediana |")
    print("|---|---|---|---|---|")
    for m, name in (("mean", "Vector medio del dominio"), ("idw", "IDW de las demás estaciones")):
        print(f"| {name} | {ok[f'dir_{m}'].median():.0f}° | {ok[f'dir_{m}'].quantile(.75):.0f}° | "
              f"{df[f'sp_{m}'].mean():+.2f} m/s | {df[f'sp_{m}'].abs().median():.2f} m/s |")
    print("\n| Estación | n | IDW mediana | IDW p75 | Vector medio mediana |")
    print("|---|---|---|---|---|")
    for s, g in ok.groupby("sid"):
        print(f"| {s} | {len(g)} | {g.dir_idw.median():.0f}° | {g.dir_idw.quantile(.75):.0f}° | {g.dir_mean.median():.0f}° |")
    # error equivalente a una normal: σ tal que mediana |N(0,σ)| = mediana medida → σ = mediana / 0.6745
    for m in ("mean", "idw"):
        print(f"\nσ equivalente ({m}): {ok[f'dir_{m}'].median() / 0.6745:.0f}°")


if __name__ == "__main__":
    main()
