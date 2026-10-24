"""Evalúa las variantes de estancamiento_invierno.py por temporada: pendiente, cuartiles estancado/ventilado, domingo.
Uso: .venv/bin/python scripts/estancamiento_invierno_eval.py <variante>...   (base y u20 incluidos)"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estancamiento_comun as ec  # noqa: E402
import estancamiento_evaluar as ev  # noqa: E402

SEAS = {"inv": ("2023-11-08", "2024-01-31"), "prim": ("2024-02-01", "2024-05-31")}


def load(v):
    return ec.daily_from(ec.load_hourly(f"estancamiento_horario_inv_{v}.parquet"))


def evaluate(v, bd, excl):
    d = load(v)
    out = {}
    for s, (a, b) in SEAS.items():
        days = [x for x in d.index if a <= f"{x:%Y-%m-%d}" <= b and x not in excl and not ("2023-12-20" <= f"{x:%Y-%m-%d}" <= "2024-01-07")]
        rel = ec.rel_single(d, days, excl)
        vv = (bd.viento * bd.pbl).reindex(rel.index)
        q = pd.qcut(vv, 4, labels=False)
        sl, t, n = ev.pendiente(d, days, excl)
        out[s] = {"n": n, "pend": sl, "t": t, "q": [ev.gm(rel[q == k]) for k in range(4)], "sd": float(np.log(rel).std()),
                  "gm": ev.gm(rel)}
    out["dom_nov"], out["sab_nov"], out["cv_nov"] = ev.sunday(d, "2023-11-01", "2023-12-31")
    out["dom_prim"], out["sab_prim"], out["cv_prim"] = ev.sunday(d, "2024-02-15", "2024-05-31")
    return out


def main():
    bd = load("base")
    _, _, excl = ec.contingency_days(bd)
    res = {}
    print("variante | invierno: pend(t) q1 q4 sd | primavera: pend(t) q1 q4 sd | domingo nov / prim")
    for v in sys.argv[1:]:
        r = res[v] = evaluate(v, bd, excl)
        f = lambda s: f"{r[s]['pend']:+.2f}({r[s]['t']:.1f}) {r[s]['q'][0]:.2f} {r[s]['q'][3]:.2f} {r[s]['sd']:.3f}"
        print(f"{v:18s} | {f('inv')} | {f('prim')} | {r['dom_nov']:.2f} / {r['dom_prim']:.2f}")
    Path(ec.INT / "estancamiento_invierno_eval.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
