"""Pruebas de corrección del sesgo dominical (nov–dic 2023), sin modificar los scripts compartidos.

Base: industria agrupada + estaciones extra + σθ = 30° (S2 de improve_real.py), viento del dominio.
Variantes:
  B0  base;
  B1  sin festivos atípicos (20-nov, 24-dic, 25-dic, 31-dic fuera de la inversión);
  B2  fondo separado por tipo de día: un fondo libre por tipo de día + desviación horaria acotada (σ 3 ppb);
  B3  B2 con el fondo por tipo de día atado a la emisión: fondo_dt = f0 · α_dt (arrastre de emisiones previas);
  B4  a priori fuerte de Infovial (domingo 0.80 ± 0.05): ¿lo rechazan los datos? (compara LOO);
  P1  puffs + perfil horario de Infovial por tipo de día + σθ 30°;
  P2  P1 con decaimiento químico más lento (vida media 12 h en vez de 4 h): más arrastre de la mañana.
Además: estimador normalizado por meteorología domingo ÷ hábil (con y sin fondo), con IC por bootstrap de días.

Uso: .venv/bin/python scripts/sunday_fix.py
Salida: data/interim/sunday_fix.json y tabla en pantalla.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import improve_real as ir
import puff
import real_check_linear as rcl

ROOT = Path(__file__).resolve().parents[1]
START, END = ir.START, ir.END
ODD_DAYS = pd.to_datetime(["2023-11-20", "2023-12-24", "2023-12-25", "2023-12-31"])
SIG_BG_HOUR = 3.0


def drop_days(m, days):
    m = dict(m)
    m["blocks"] = [b for b in m["blocks"] if b[0] not in set(days)]
    keep_h = {h for h in m["hours"] if rcl.local_day(h) not in set(days)}
    m["st_rows"] = [r for r in m["st_rows"] if r[1] in keep_h]
    return m


def split_background(m, tied=False):
    """Agrega 3 fondos por tipo de día (estaciones) y acota el fondo horario a σ 3 ppb alrededor de 0.
    tied=True: en vez de 3 fondos libres, un solo f0 y el fondo del tipo de día es f0·α_dt,región media;
    se linealiza como columnas extra: fondo = Σ_r w_r·α_dt,r·f0 ≈ f0_ref·Σ_r w_r·α_dt,r con f0_ref fijo
    (estimado de B2 en hábil), es decir, una columna constante en los α del tipo de día."""
    m = dict(m)
    n0, H, n_pt = m["n"], len(m["hours"]), m["n_pt"]
    n_src = n_pt + 27
    hour_dt = {k: rcl.day_type(h) for k, h in enumerate(m["hours"])}
    xa, sa = m["xa"].copy(), m["sa"].copy()
    xa[n_src:n_src + H], sa[n_src:n_src + H] = 0.0, SIG_BG_HOUR
    if not tied:
        m["xa"], m["sa"], m["n"] = np.r_[xa, np.full(3, 10.0)], np.r_[sa, np.full(3, 20.0)], n0 + 3
    else:
        m["xa"], m["sa"] = xa, sa
    blocks, st_rows = [], []
    w_reg = m["prior_rd"] / m["prior_rd"].sum()
    f0 = m.get("f0_ref", 10.0)

    def extend(idx, A, g, k):
        dt = hour_dt[k]
        if not tied:
            return np.r_[idx, n0 + dt], np.block([[A, A[:, -1:]], [A[-1:, :], A[-1:, -1:]]]), np.r_[g, g[-1]]
        # columna vial del tipo de día += f0·w_r (la parte "fondo" que escala con la emisión)
        T = np.eye(len(idx))
        cols = [i for i, j in enumerate(idx) if n_pt + 9 * dt <= j < n_pt + 9 * dt + 9]
        for c in cols:
            T[-1, c] = f0 * w_reg[idx[c] - n_pt - 9 * dt]   # K' = K·T: K'[:, c] = K[:, c] + 1·f0·w
        return idx, T.T @ A @ T, T.T @ g

    for d, idx, A, g in m["blocks"]:
        k = int(idx[-1] - n_src)
        if k >= H:                       # TEMPO: sin cambios
            blocks.append((d, idx, A, g))
            continue
        blocks.append((d, *extend(idx, A, g, k)))
    for s, h, idx, kr, yy in m["st_rows"]:
        k = int(idx[-1] - n_src)
        dt = hour_dt[k]
        if not tied:
            st_rows.append((s, h, np.r_[idx, n0 + dt], np.r_[kr, 1.0], yy))
        else:
            kr = kr.copy()
            for c, j in enumerate(idx):
                if n_pt + 9 * dt <= j < n_pt + 9 * dt + 9:
                    kr[c] += f0 * w_reg[j - n_pt - 9 * dt]
            st_rows.append((s, h, idx, kr, yy))
    m["blocks"], m["st_rows"] = blocks, st_rows
    return m


def strong_prior(m, sd):
    N0, b0 = rcl.solve(m)
    x0 = np.linalg.solve(N0, b0)
    old = ir.RATIO_SD
    ir.RATIO_SD = sd
    E = ir.ratio_constraint(m, x0)
    ir.RATIO_SD = old
    return E


def backgrounds(m, E=None):
    N, b = rcl.solve(m)
    if E is not None:
        N = N + E
    x = np.linalg.solve(N, b)
    n_src, H = m["n_pt"] + 27, len(m["hours"])
    bg = pd.Series(x[n_src:n_src + H], index=[rcl.day_type(h) for h in m["hours"]])
    if m["n"] > n_src + 2 * H:          # fondos por tipo de día (B2)
        bg = bg + pd.Series(x[n_src + 2 * H:], index=range(3)).reindex(bg.index).values
    return bg.groupby(level=0).mean().round(1).to_dict()


def normalized(boot=1000):
    d = pd.read_csv(ROOT / "data/interim/sunday_diag_days.csv", parse_dates=["day"])
    rng = np.random.default_rng(5)
    out = {}
    for name, num in {"observado (con fondo)": "obs", "contraste (sin fondo: media − p10)": "contrast"}.items():
        def r(x):
            g = x.groupby("dt")
            v = g[num].sum() / g.model.sum()
            return v.get(2, np.nan) / v[0], v.get(1, np.nan) / v[0]
        est = r(d)
        bs = np.array([r(d.iloc[rng.integers(0, len(d), len(d))]) for _ in range(boot)])
        out[name] = dict(domingo=est[0], ic=np.nanpercentile(bs[:, 0], [5, 95]).tolist(),
                         sabado=est[1], ic_sab=np.nanpercentile(bs[:, 1], [5, 95]).tolist())
    return out


def main():
    res = {"normalizado": normalized()}
    for k, v in res["normalizado"].items():
        print(f"Normalizado {k}: domingo {v['domingo']:.2f} ({v['ic'][0]:.2f}–{v['ic'][1]:.2f}), "
              f"sábado {v['sabado']:.2f} ({v['ic_sab'][0]:.2f}–{v['ic_sab'][1]:.2f})", flush=True)

    ir.configure(sigma30=True)
    base = rcl.build(START, END, "domain", no_industry=True, extras=True)
    b2 = split_background(base)
    N, b = rcl.solve(b2)
    x = np.linalg.solve(N, b)
    base["f0_ref"] = float(x[b2["n"] - 3])      # fondo de hábil en B2
    variants = [("B0", "Base (σθ 30°, industria agrupada, estaciones extra)", base, None),
                ("B1", "Sin festivos atípicos (20-nov, 24/25/31-dic)", drop_days(base, ODD_DAYS), None),
                ("B2", "Fondo por tipo de día + desviación horaria σ 3 ppb", b2, None),
                ("B3", f"Fondo atado a la emisión del tipo de día (f0 = {base['f0_ref']:.1f} ppb)", split_background(base, tied=True), None),
                ("B4", "A priori fuerte de Infovial (domingo 0.80 ± 0.05)", base, "strong")]
    rows = []
    for code, label, m, pr in variants:
        E = strong_prior(m, 0.05) if pr else None
        r = ir.evaluate(m, E)
        r["fondo"] = backgrounds(m, E)
        rows.append((code, label, r))
        print(code, label, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)

    ir.configure(sigma30=True, infovial_profile=True)
    mp = rcl.build(START, END, "puff", no_industry=True, extras=True)
    r = ir.evaluate(mp)
    r["fondo"] = backgrounds(mp)
    rows.append(("P1", "Puffs + perfil Infovial por tipo de día + σθ 30°", r))
    print("P1", r, flush=True)
    puff.TAU_CHEM_H = 12.0
    mp = rcl.build(START, END, "puff", no_industry=True, extras=True)
    r = ir.evaluate(mp)
    r["fondo"] = backgrounds(mp)
    rows.append(("P2", "P1 con vida media química de 12 h (más arrastre de la mañana)", r))
    print("P2", r, flush=True)
    puff.TAU_CHEM_H = 4.0
    ir.configure()

    res["variantes"] = [dict(code=c, label=l, **{k: (float(v) if isinstance(v, (float, np.floating)) else v)
                                                for k, v in r.items()}) for c, l, r in rows]
    (ROOT / "data/interim/sunday_fix.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    print("\n| Variante | RMSE LOO modelo / IDW / híbrido | Híbrido < IDW | Domingo/hábil (IC 90 %) | Fondo hábil / sáb / dom (ppb) |")
    print("|---|---|---|---|---|")
    for c, l, r in rows:
        f = r["fondo"]
        print(f"| {c}. {l} | {r['rm']:.1f} / {r['ri']:.1f} / {r['rh']:.1f} | {r['win']} de {r['n_st']} | "
              f"{r['sun']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) | {f.get(0, np.nan)} / {f.get(1, np.nan)} / {f.get(2, np.nan)} |")


if __name__ == "__main__":
    main()
