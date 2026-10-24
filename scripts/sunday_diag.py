"""Diagnóstico del sesgo dominical (nov–dic 2023): ¿por qué la inversión da domingo/hábil ≈ 0.4 si
Infovial indica ~0.8? Solo datos y modelo con emisión fija; no resuelve la inversión.

Revisa, por tipo de día y por fecha:
  - NOₓ observado de la tarde (12–17 h) y de la mañana (6–11 h);
  - contraste espacial (media de estaciones − percentil 10 de la hora), que es lo que ve la emisión vial;
  - ventilación: velocidad del viento del dominio y capa límite;
  - NOₓ que predice el modelo con la emisión vial fija (α = 1) y el cociente observado ÷ modelo;
  - Infovial ene-2017: cocientes por franja horaria y con distintos pesos de los pesados.

Uso: .venv/bin/python scripts/sunday_diag.py
Salida: data/interim/sunday_diag_days.csv y texto en pantalla.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import feasibility_linear as fl
from real_check_linear import day_type, local_day

ROOT = Path(__file__).resolve().parents[1]
START, END = "2023-11-01", "2023-12-31"
DT = ["hábil", "sábado", "domingo/festivo"]


def infovial():
    f = ROOT / "data/raw/trafico/infovial_201701_clasificacion.csv"
    d = pd.read_csv(f, usecols=["fecha", "hora", "tipo_vehiculo", "cantidad"])
    d["fecha"] = pd.to_datetime(d.fecha)
    d = d[~d.fecha.isin(pd.to_datetime(["2017-01-01", "2017-01-02"]))]
    d["hr"] = d.hora.str[:2].astype(int)
    dow = d.fecha.dt.dayofweek
    d["dt"] = np.select([dow == 6, dow == 5], [2, 1], 0)
    g = d.groupby(["dt", "fecha", "hr", "tipo_vehiculo"]).cantidad.sum().reset_index()
    g = g.groupby(["dt", "hr", "tipo_vehiculo"]).cantidad.mean().unstack()  # media por día de cada tipo
    out = {}
    for name, w in {"conteo": [1, 1, 1, 1, 1, 1], "pesos base 1,2,5,10,15,20": [1, 2, 5, 10, 15, 20],
                    "pesados ×3 (1,2,15,30,45,60)": [1, 2, 15, 30, 45, 60], "solo C3–C6": [0, 0, 1, 1, 1, 1]}.items():
        e = (g[[f"C{i}" for i in range(1, 7)]] * w).sum(1).unstack(0)
        for lab, hrs in {"mañana 6–11": range(6, 12), "tarde 12–17": range(12, 18), "día": range(24)}.items():
            s = e.loc[list(hrs)].sum()
            out[(name, lab)] = (s[1] / s[0], s[2] / s[0])
    return out


def main():
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = fl.load_inputs(START, END, extras=True)
    nox = nox[~nox.est]
    rows = []
    for h in sorted(set(nox.h) & set(wind.index) & set(pbl.index)):
        nh = nox[nox.h == h]
        (kind, K), *_ = fl.jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, px.iloc[:0], ratio)
        model = K[:, len(cand):].sum(1)                    # vial con α = 1, sin fondo ni puntuales
        y = nh.NOX.values
        rows.append(dict(h=h, day=local_day(h), dt=day_type(h), obs=y.mean(), p10=np.percentile(y, 10),
                         contrast=y.mean() - np.percentile(y, 10), model=model.mean(),
                         ws=np.hypot(*wind.loc[h].values), pbl=pbl.loc[h]))
    a = pd.DataFrame(rows)
    # NOₓ de la mañana por día (mismas estaciones)
    all_nox = pd.read_parquet(ROOT / "data/interim/simat_nox.parquet")
    am = all_nox[all_nox.local.between(START, f"{END} 23:59") & all_nox.hour.between(6, 11) & all_nox.id_station.isin(st.index)]
    am = am.assign(day=(am.utc - pd.Timedelta(hours=7)).dt.normalize()).groupby("day").NOX.mean()

    d = a.groupby("day").agg(dt=("dt", "first"), n=("h", "size"), obs=("obs", "mean"), p10=("p10", "mean"),
                             contrast=("contrast", "mean"), model=("model", "mean"), ws=("ws", "mean"), pbl=("pbl", "mean"))
    d["am"] = am.reindex(d.index).values
    d["ratio_om"] = d.obs / d.model
    d.to_csv(ROOT / "data/interim/sunday_diag_days.csv")

    print("== Medias por tipo de día (tarde 12–17 h, estaciones con NOₓ medido)")
    t = d.groupby("dt")[["obs", "p10", "contrast", "model", "ws", "pbl", "am"]].mean()
    t.index = [DT[i] for i in t.index]
    print(t.round(2).to_string())
    print("\n== Cociente respecto a hábil")
    print((t / t.iloc[0]).round(2).to_string())
    r = d.groupby("dt").apply(lambda g: g.obs.sum() / g.model.sum())
    print(f"\nObservado ÷ modelo con emisión fija (estimador normalizado, con fondo): "
          f"sábado {r[1] / r[0]:.2f}, domingo {r[2] / r[0]:.2f}")
    rc = d.groupby("dt").apply(lambda g: g.contrast.sum() / g.model.sum())
    print(f"Contraste ÷ modelo: sábado {rc[1] / rc[0]:.2f}, domingo {rc[2] / rc[0]:.2f}")
    print("\n== Domingos y festivos, día por día")
    print(d[d.dt == 2].round(2).to_string())
    print("\n== Hábiles: medianas")
    print(d[d.dt == 0][["obs", "contrast", "model", "ws", "pbl", "am", "ratio_om"]].describe().round(2).to_string())

    print("\n== Infovial ene-2017 (sábado/hábil, domingo/hábil)")
    for k, v in infovial().items():
        print(f"  {k[0]:32s} {k[1]:12s} {v[0]:.2f} {v[1]:.2f}")


if __name__ == "__main__":
    main()
