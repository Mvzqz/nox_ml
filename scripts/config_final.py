"""Configuración final: puffs como transporte estándar y región vial propia para Ecatepec.

En reports/puffs_cdmx.md los puffs mejoraron TEMPO, el total vial y la estabilidad del estimador normalizado,
pero el híbrido empeoró en nov–dic por SAG y XAL (Ecatepec), que caían en la región "Centro". Aquí se prueban
dos esquemas de regiones (feasibility_linear.REGION_SCHEMES) con puffs y la configuración actual (σθ = 30°,
TEMPO ×1/3, restricción de cociente de Infovial, a priori de centrales de Climate TRACE), contra el 3×3:

  3x3               las 9 regiones originales
  3x3_ecatepec      el municipio de Ecatepec como región 10
  3x3_centro_norte  la región Centro partida en dos (la mitad norte, con Ecatepec sur y GAM norte, es la 10)

Uso: .venv/bin/python scripts/config_final.py --period nov23 --schemes 3x3 3x3_ecatepec 3x3_centro_norte
     .venv/bin/python scripts/config_final.py --report     (tablas para reports/config_final.md)
Salida: data/interim/puffs_cdmx/<periodo>_puff_<esquema>.json
"""
import argparse
import json

import numpy as np

import feasibility_linear as fl
import puffs_cdmx as pc

SCHEMES = ["3x3", "3x3_ecatepec", "3x3_centro_norte"]
LABEL = {"plume": "Pluma, 3×3 (estándar anterior)", "3x3": "Puffs, 3×3", "3x3_ecatepec": "Puffs, 3×3 + Ecatepec",
         "3x3_centro_norte": "Puffs, Centro partido en dos"}
DROP = {"SAG", "XAL"}


def loo_subset(r, drop):
    """LOO ponderado por número de horas sin las estaciones de `drop`."""
    a = [e for e in r["loo_por_estacion"] if e["sid"] not in drop]
    n = np.array([e["n"] for e in a])
    out = {c: float(np.sqrt((n * np.array([e[c] for e in a]) ** 2).sum() / n.sum())) for c in ("model", "idw", "hybrid")}
    out["gana"] = f"{sum(e['hybrid'] < e['idw'] for e in a)} de {len(a)}"
    return out


def station(r, sid):
    return next((e for e in r["loo_por_estacion"] if e["sid"] == sid), None)


def load(period):
    res = {}
    f = pc.OUT / f"{period}_plume.json"
    if f.exists():
        res["plume"] = json.loads(f.read_text())
    for s in SCHEMES:
        f = pc.OUT / f"{period}_puff_{s}.json"
        if f.exists():
            res[s] = json.loads(f.read_text())
    return res


def report():
    L = []
    for period in pc.PERIODS:
        res = load(period)
        if not res:
            continue
        L += [f"\n### {pc.PERIOD_LABEL[period]}\n",
              "| Configuración | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | "
              "SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |",
              "|---|---|---|---|---|---|---|---|"]
        for k, r in res.items():
            sub = loo_subset(r, DROP)
            sg, xl = station(r, "SAG"), station(r, "XAL")
            L.append(f"| {LABEL[k]} | {r['loo_model']:.1f} / {r['loo_idw']:.1f} / {r['loo_hybrid']:.1f} | {r['hibrido_gana']} | "
                     f"{sub['model']:.1f} / {sub['idw']:.1f} / {sub['hybrid']:.1f} | "
                     f"{sg['hybrid']:.1f} / {sg['idw']:.1f} | {xl['hybrid']:.1f} / {xl['idw']:.1f} | "
                     f"{r['fija_r_tempo_global']:.2f} / {r['muestra_r_tempo']:.2f} | {r['vial_habil'] / r['vial_apriori']:.0%} |")
        L += ["", "| Configuración | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles | "
              "Valle | Nonoalco | AICM | AIFA | Correlación mínima entre regiones |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in res.items():
            p = r["puntuales"]
            pt = lambda nm: next(f"{v[0]:,.0f} ± {v[1]:,.0f}" for n, v in p.items() if nm in n)
            lo, hi = r["domingo_libre_ic"]
            nlo, nhi = r["norm_domingo_ic"]
            cm = f"{r['corr_regiones_min']:.2f}" if "corr_regiones_min" in r else "–"
            L.append(f"| {LABEL[k]} | {r['domingo_libre']:.2f} ({lo:.2f}–{hi:.2f}) | {r['domingo']:.2f} | "
                     f"{r['norm_domingo']:.2f} ({nlo:.2f}–{nhi:.2f}) | {r['placebo_mitad_ancho']:.2f} | {r['norm_cv_habiles']:.2f} | "
                     f"{pt('Valle')} | {pt('Nonoalco')} | {pt('AICM')} | {pt('AIFA')} | {cm} |")
        L += ["", "Factor vial α de día hábil por región (± σ a posteriori):\n"]
        for k, r in res.items():
            if "alfa_habil" in r:
                L.append(f"- {LABEL[k]}: " + ", ".join(f"{n} {a:.2f} ± {s:.2f}" for n, a, s in
                                                     zip(r["regiones"], r["alfa_habil"], r["alfa_habil_sd"])))
        L += ["", "Pares de regiones más correlacionados a posteriori (α hábil):\n"]
        for k, r in res.items():
            if "corr_regiones" in r:
                C = np.array(r["corr_regiones"])
                iu = np.triu_indices(len(C), 1)
                o = np.argsort(C[iu])[:3]
                L.append(f"- {LABEL[k]}: " + ", ".join(f"{r['regiones'][iu[0][i]]}–{r['regiones'][iu[1][i]]} {C[iu][i]:.2f}" for i in o))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=list(pc.PERIODS), default="nov23")
    ap.add_argument("--schemes", nargs="+", default=SCHEMES, choices=SCHEMES)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        print(report())
        return
    for s in a.schemes:
        fl.REGION_SCHEME = s
        pc.run(a.period, ["puff"], a.boot, tag=f"_{s}")


if __name__ == "__main__":
    main()
