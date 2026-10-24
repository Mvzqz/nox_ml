"""Estancamiento, paso 0: serie horaria del modelo estándar (puffs 24 h, vida química OH, admin_grupos, sin industria)
con emisión fija, 1 nov 2023 – 31 may 2024, horas locales 7–17 (etiqueta SIMAT), por hora: NOₓ observado medio
(estaciones con NOₓ medido), modelo total y desglosado (puntuales, vial, edad del puff).

Salida: data/interim/estancamiento_horario.parquet
Uso: .venv/bin/python scripts/estancamiento_base.py [variante] [--test]
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feasibility_linear as fl  # noqa: E402
import puff  # noqa: E402
import puffs_cdmx as pc  # noqa: E402
import vida_quimica as vq  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
START, END = "2023-11-01", "2024-05-31"


def _clim(pbl):
    """Climatología mes-hora (mediana) de la propia serie."""
    return pbl.groupby([pbl.index.month, pbl.index.hour]).transform("median")


def _encoger(pbl, k):
    """Encoge la capa límite hacia su climatología mes-hora: exp(k·log pbl + (1 − k)·log clim). k=1: sin cambio."""
    return np.exp(k * np.log(pbl) + (1 - k) * np.log(_clim(pbl)))


def _sonda(pbl, a):
    """Escala la capa límite del día con la estabilidad de las 18 h del radiosondeo (Δθ 700 hPa − superficie):
    más estable que la mediana → capa más baja. factor = exp(−a·(Δθ18 − mediana)), a en 1/K; sin sondeo, 1."""
    import estancamiento_comun as ec
    dth = ec.sondeos().dth18
    day = (pbl.index - pd.Timedelta(hours=6)).normalize()
    x = pd.Series(day.map(dth).values, index=pbl.index) - dth.median()
    return (pbl * np.exp(-a * x.fillna(0.0).clip(-3, 4))).clip(lower=200)


VARIANTES = {"base": lambda pbl: pbl,
             "pbl_tope1500": lambda pbl: pbl.clip(upper=1500),
             "pbl_tope1000": lambda pbl: pbl.clip(upper=1000),
             "pbl_encogida50": lambda pbl: _encoger(pbl, 0.5),
             "pbl_clim": lambda pbl: _encoger(pbl, 0.0),
             "pbl_sonda10": lambda pbl: _sonda(pbl, 0.10),
             "pbl_sonda20": lambda pbl: _sonda(pbl, 0.20),
             "pbl_sonda20_encogida50": lambda pbl: _sonda(_encoger(pbl, 0.5), 0.20),
             "edad48": lambda pbl: pbl,
             "umin15": lambda pbl: pbl,
             "umin20": lambda pbl: pbl,
             "umin25": lambda pbl: pbl,
             "umin30": lambda pbl: pbl,
             "umin20_sonda10": lambda pbl: _sonda(pbl, 0.10)}

G = {}


def setup(variante="base"):
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    vq.apply_variant(vq.STANDARD)
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, _, ratio, wind, pbl, px = fl.load_inputs("2024-02-15", "2024-05-31", True)
    keep = (cand.tipo != "industria").values
    cand, prior_pt = cand[keep].reset_index(drop=True), prior_pt[keep].copy()
    for nm, (p, s) in pc.NEW_PRIORS.items():
        prior_pt[next(i for i, c in enumerate(cand.nombre) if nm in c)] = p
    pbl = VARIANTES[variante](pbl)
    if variante.startswith("umin"):
        fl.U_MIN = puff.U_MIN = pc.U_MIN = int(variante[4:].split("_")[0]) / 10
    if variante == "edad48":
        puff.MAX_AGE_H = 48
    nox = pd.read_parquet(INT / "simat_nox.parquet")
    nox = nox[nox.local.between(START, f"{END} 23:59") & nox.hour.between(7, 17) & nox.id_station.isin(st.index) & nox.NOX.notna()].copy()
    nox["h"] = nox.utc - pd.Timedelta(hours=1)
    tr = pc.Transport("domain", vq.extended_profile(), traj=puff.Trajectories(wind))
    G.update(cand=cand, prior_pt=prior_pt, cells=cells, st=st, ratio=ratio, wind=wind, pbl=pbl, nox=nox, tr=tr, px=px.iloc[:0])


def one(h):
    g = G
    nh = g["nox"][g["nox"].h == h]
    (_, K), = pc.jacobian_puff_mx(h, g["tr"], g["wind"].loc[h].values, g["pbl"].loc[h], g["cand"], g["cells"], g["st"], nh, g["px"], g["ratio"])
    n_pt = len(g["cand"])
    pt = K[:, :n_pt] @ g["prior_pt"]
    rd = K[:, n_pt:].sum(1)
    return {"h": h, "obs": nh.NOX.mean(), "pt": pt.mean(), "rd": rd.mean(), "modelo": (pt + rd).mean(), "n_est": len(nh),
            "pbl": g["pbl"].loc[h], "u": g["wind"].loc[h, "u"], "v": g["wind"].loc[h, "v"]}


def main():
    variante = next((a for a in sys.argv[1:] if not a.startswith("--")), "base")
    setup(variante)
    hours = sorted(h for h in set(G["nox"].h) if h in G["wind"].index and h in G["pbl"].index)
    if "--test" in sys.argv:
        hours = hours[:8]
    t0 = time.time()
    with Pool(7) as p:
        rows = p.map(one, hours, chunksize=8)
    d = pd.DataFrame(rows)
    print(len(d), "horas en", round(time.time() - t0), "s")
    if "--test" not in sys.argv:
        d.to_parquet(INT / ("estancamiento_horario.parquet" if variante == "base" else f"estancamiento_horario_{variante}.parquet"))
    else:
        print(d)


if __name__ == "__main__":
    main()
