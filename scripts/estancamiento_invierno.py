"""Estancamiento, validación en invierno: variantes físicas de la rapidez de transporte y de la capa límite, serie horaria
nov 2023 – may 2024 (misma serie que estancamiento_base.py). Se elige con una temporada y se evalúa en la otra.

Variantes: u<UMIN×10> piso; quad<σ×10> rapidez √(u²+σ²) (meandro/turbulencia); pow<U0×10> rapidez U0^0.5·u^0.5 (concentración ∝ u^−0.5);
sufijo _cap<m> tope de capa límite, _pe pbl_eff = √(1000·pbl), _pe7 pbl_eff = 1000^0.3·pbl^0.7.
Uso: .venv/bin/python scripts/estancamiento_invierno.py <variante>...      Salida: data/interim/estancamiento_horario_inv_<variante>.parquet
"""
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estancamiento_base as eb  # noqa: E402
import feasibility_linear as fl  # noqa: E402


def config(v):
    fl.U_MIN, fl.U_TURB, fl.U_POW = 1.0, 0.0, None
    cap = pe = None
    for tok in v.split("_"):
        if m := re.fullmatch(r"u(\d+)", tok):
            fl.U_MIN = int(m[1]) / 10
        elif m := re.fullmatch(r"quad(\d+)", tok):
            fl.U_TURB = int(m[1]) / 10
        elif m := re.fullmatch(r"pow(\d+)", tok):
            fl.U_POW = (int(m[1]) / 10, 0.5)
        elif m := re.fullmatch(r"cap(\d+)", tok):
            cap = float(m[1])
        elif tok == "pe":
            pe = 0.5
        elif tok == "pe7":
            pe = 0.7
        elif tok != "base":
            raise ValueError(tok)
    return cap, pe


def main():
    for v in sys.argv[1:]:
        cap, pe = config(v)
        eb.setup("base")
        if cap:
            eb.G["pbl"] = eb.G["pbl"].clip(upper=cap)
        if pe:
            eb.G["pbl"] = 1000.0 ** (1 - pe) * eb.G["pbl"] ** pe
        hours = sorted(h for h in set(eb.G["nox"].h) if h in eb.G["wind"].index and h in eb.G["pbl"].index)
        with Pool(7) as p:
            d = pd.DataFrame(p.map(eb.one, hours, chunksize=8))
        d.to_parquet(eb.INT / f"estancamiento_horario_inv_{v}.parquet")
        print(v, len(d), flush=True)


if __name__ == "__main__":
    main()
