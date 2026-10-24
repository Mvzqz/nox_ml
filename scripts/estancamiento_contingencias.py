"""Estancamiento, paso 3: contingencias 2024 con el modelo base y con la corrección elegida (piso de viento U_MIN = 2 m/s).

Repite los grupos y episodios de contingencias_2024.py con las series horarias de estancamiento_base.py (puffs 24 h, vida química
OH, admin_grupos), con y sin corrección, y con las fechas desplazadas +1 día. No toca los archivos de contingencias_2024.

Uso: .venv/bin/python scripts/estancamiento_contingencias.py
Salida: data/interim/estancamiento_contingencias.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contingencias_2024 as c24  # noqa: E402
import estancamiento_comun as ec  # noqa: E402

VARIANTES = {"base": "estancamiento_horario.parquet", "umin20": "estancamiento_horario_umin20.parquet"}


def main():
    res = {}
    for v, f in VARIANTES.items():
        h = ec.load_hourly(f)
        d = ec.daily_from(h)
        for shift in (0, 1):
            cont, hab, excl = ec.contingency_days(d, shift)
            fin = [x for x in cont if x not in hab]
            c24.rng = np.random.default_rng(3)
            r = {"grupos": {}, "placebos": {}}
            for g, days in (("todos", cont), ("hábiles", hab), ("fin de semana/festivo", fin)):
                e = c24.estimate(d, days, excl)
                e["ic90"] = [float(x) for x in c24.boot(d, days, excl, 500)]
                e["dias"] = len(days)
                r["grupos"][g] = {k: float(val) if not isinstance(val, (list, int)) else val for k, val in e.items()}
            season = (d.index >= "2024-02-01") & (d.index <= "2024-06-15")
            non = ~d.index.isin(excl)
            vq = d.loc[cont].vent.quantile(0.25)
            oq = d[season & non].o3max.quantile(0.75)
            pools = {"azar": season & non, "estancado": season & non & (d.vent >= vq).values, "ozono alto": season & non & (d.o3max >= oq).values}
            for k, m in pools.items():
                for g, days in (("todos", cont), ("hábiles", hab)):
                    p = c24.placebo(d, days, np.asarray(m), 500)
                    r["placebos"][f"{k}|{g}"] = [p["mediana"], p["p5"], p["p95"]]
                    if k == "estancado":
                        r["grupos"][g]["sobre_placebo_estancado"] = r["grupos"][g]["emision"] / p["mediana"]
            if shift == 0:
                r["episodios"] = []
                for ep in c24.episodes(sorted(cont)):
                    e = c24.estimate(d, ep, excl)
                    lo, hi = c24.boot(d, ep, excl, 300)
                    r["episodios"].append({"fechas": f"{ep[0]:%d %b}" + ("" if len(ep) == 1 else f"–{ep[-1]:%d %b}"), "dias": len(ep),
                                           "meteo": float(e["meteorologia"]), "emision": float(e["emision"]), "ic90": [float(lo), float(hi)]})
            res[f"{v}|shift{shift}"] = r
            print(v, "shift", shift, {g: (round(x["emision"], 2), [round(y, 2) for y in x["ic90"]], round(x.get("sobre_placebo_estancado", np.nan), 2)) for g, x in r["grupos"].items()},
                  {k: [round(y, 2) for y in x] for k, x in r["placebos"].items()}, flush=True)
    (ec.INT / "estancamiento_contingencias.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
