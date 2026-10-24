"""Datos reales: zonas viales administrativas frente a 3×3 + Ecatepec, ambas con puffs (reports/zonas_admin.md).

Corre puffs_cdmx.run con el esquema pedido (salida data/interim/puffs_cdmx/<periodo>_puff_<esquema>.json, el mismo
formato que config_final.py) y, con --report, arma las tablas: métricas de siempre, emisión vial por entidad
(CDMX / Estado de México) frente al inventario 2018 y α por zona.

Reparto por entidad: cada celda vial de 1 km lleva el α de su zona; se suma α · peso a priori por celda según la
entidad del punto (municipios de INEGI). Así se compara también el esquema 3×3, cuyas zonas cruzan el límite.

Uso: .venv/bin/python scripts/zonas_admin_real.py --period nov23 --schemes admin_grupos
     .venv/bin/python scripts/zonas_admin_real.py --report --schemes admin_grupos 3x3_ecatepec
"""
import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

import config_final as cf
import feasibility_linear as fl
import puffs_cdmx as pc
from config import UTM

ROOT = Path(__file__).resolve().parents[1]
INV = ROOT / "data/interim/inventario_2018_nox.csv"
LABEL = {"3x3_ecatepec": "3×3 + Ecatepec", "admin_grupos": "Grupos administrativos (13)",
         "admin_grupos_v2": "Grupos administrativos, v2"}


def cell_entity(scheme):
    """Celdas viales (peso a priori t/año, región) con su entidad."""
    fl.REGION_SCHEME = scheme
    cells = fl.load_inputs("2023-11-01", "2023-12-31", extras=False)[3]
    mun = gpd.read_file(fl.INT / "municipios.gpkg").to_crs(UTM)
    pts = gpd.GeoDataFrame(cells[["w", "region"]], geometry=gpd.GeoSeries.from_xy(cells.x, cells.y, crs=UTM))
    j = gpd.sjoin_nearest(pts, mun[["NOM_ENT", "geometry"]], how="left")
    j = j[~j.index.duplicated()]
    return pd.DataFrame({"w": j.w, "region": j.region, "entidad": j.NOM_ENT.map(
        {"Ciudad de México": "CDMX", "México": "EdoMex"}).fillna("otra")})


def by_entity(r, ce):
    a = np.array(r["alfa_habil"])
    e = (ce.w * a[ce.region.values]).groupby(ce.entidad).sum()
    p = ce.groupby("entidad").w.sum()
    return e, p


def report(schemes):
    inv = pd.read_csv(INV)
    inv_mov = inv[inv.tipo_fuente == "moviles"].set_index("entidad").nox_t_anio
    L = []
    ce = {s: cell_entity(s) for s in schemes}
    for period in pc.PERIODS:
        res = {s: json.loads((pc.OUT / f"{period}_puff_{s}.json").read_text()) for s in schemes
               if (pc.OUT / f"{period}_puff_{s}.json").exists()}
        if not res:
            continue
        L += [f"\n### {pc.PERIOD_LABEL[period]}\n",
              "| Zonas | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | "
              "SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |",
              "|---|---|---|---|---|---|---|---|"]
        for s, r in res.items():
            sub = cf.loo_subset(r, cf.DROP)
            sg, xl = cf.station(r, "SAG"), cf.station(r, "XAL")
            L.append(f"| {LABEL[s]} | {r['loo_model']:.1f} / {r['loo_idw']:.1f} / {r['loo_hybrid']:.1f} | {r['hibrido_gana']} | "
                     f"{sub['model']:.1f} / {sub['idw']:.1f} / {sub['hybrid']:.1f} | {sg['hybrid']:.1f} / {sg['idw']:.1f} | "
                     f"{xl['hybrid']:.1f} / {xl['idw']:.1f} | {r['fija_r_tempo_global']:.2f} / {r['muestra_r_tempo']:.2f} | "
                     f"{r['vial_habil'] / r['vial_apriori']:.0%} |")
        L += ["", "| Zonas | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles | "
              "Correlación mínima entre zonas |", "|---|---|---|---|---|---|---|"]
        for s, r in res.items():
            lo, hi = r["domingo_libre_ic"]
            nlo, nhi = r["norm_domingo_ic"]
            L.append(f"| {LABEL[s]} | {r['domingo_libre']:.2f} ({lo:.2f}–{hi:.2f}) | {r['domingo']:.2f} | "
                     f"{r['norm_domingo']:.2f} ({nlo:.2f}–{nhi:.2f}) | {r['placebo_mitad_ancho']:.2f} | "
                     f"{r['norm_cv_habiles']:.2f} | {r['corr_regiones_min']:.2f} |")
        L += ["", "Emisión vial de día hábil por entidad (t/año, dentro del dominio) frente al inventario 2018 de fuentes "
              "móviles (toda la entidad):\n", "| Zonas | CDMX | Edomex (parte en el dominio) | CDMX / Edomex | "
              "Inventario: CDMX / Edomex |", "|---|---|---|---|---|"]
        for s, r in res.items():
            e, p = by_entity(r, ce[s])
            L.append(f"| {LABEL[s]} | {e.get('CDMX', 0):,.0f} (a priori {p.get('CDMX', 0):,.0f}) | "
                     f"{e.get('EdoMex', 0):,.0f} (a priori {p.get('EdoMex', 0):,.0f}) | "
                     f"{e.get('CDMX', 0) / e.get('EdoMex', 1):.2f} | {inv_mov['CDMX']:,.0f} / {inv_mov['EdoMex']:,.0f} "
                     f"({inv_mov['CDMX'] / inv_mov['EdoMex']:.2f}) |")
        L += ["", "Factor vial α de día hábil por zona (± σ a posteriori):\n"]
        for s, r in res.items():
            L.append(f"- {LABEL[s]}: " + ", ".join(f"{n} {a:.2f} ± {sd:.2f}" for n, a, sd in
                                                 zip(r["regiones"], r["alfa_habil"], r["alfa_habil_sd"])))
        L += ["", "Pares de zonas más correlacionados a posteriori (α hábil):\n"]
        for s, r in res.items():
            C = np.array(r["corr_regiones"])
            iu = np.triu_indices(len(C), 1)
            o = np.argsort(C[iu])[:3]
            L.append(f"- {LABEL[s]}: " + ", ".join(f"{r['regiones'][iu[0][i]]}–{r['regiones'][iu[1][i]]} {C[iu][i]:.2f}" for i in o))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=list(pc.PERIODS), default="nov23")
    ap.add_argument("--schemes", nargs="+", default=["admin_grupos"])
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        print(report(a.schemes))
        return
    for s in a.schemes:
        fl.REGION_SCHEME = s
        pc.run(a.period, ["puff"], a.boot, tag=f"_{s}")


if __name__ == "__main__":
    main()
