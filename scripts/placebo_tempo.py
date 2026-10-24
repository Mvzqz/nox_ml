"""Placebo con TEMPO: ¿el estimador normalizado por meteorología ve cambios donde no los hay?

Equivalente para columnas del estimador de val2020_ratio.py (observado ÷ modelo con emisión fija).
Para cada granulo TEMPO (12–17 h) se calcula la columna que daría la emisión a priori fija (vialidades +
fuentes puntuales) con el viento medio de las estaciones de esa hora. La columna integrada no depende de
la capa límite, solo del viento, que es lo que hay que descontar. El factor de emisión de un grupo de
días es la pendiente de observado contra modelo dentro de cada granulo (el fondo de cada granulo se
cancela al restar medias):

    k = Σ_g Σ_i (m_i − m̄_g)(o_i − ō_g) / Σ_g Σ_i (m_i − m̄_g)²

y el cambio entre dos grupos es k₁ / k₀ (IC 90 % por bootstrap de días). Como comparación sin normalizar
se usa el contraste crudo centro − periferia de cada granulo (píxeles en el cuartil alto vs bajo de
densidad vial), promediado por grupo.

Pruebas:
  1. Placebo: pares de bloques de ~2 semanas de días hábiles sin cambio esperado (sin festivos,
     vacaciones ni contingencias). Distribución nula del cambio aparente.
  2. Ruido puro: divisiones aleatorias de días hábiles de la misma temporada, por tamaño de grupo.
  3. Cambios reales: domingos y sábados vs hábiles, vacaciones de diciembre, Semana Santa.

Uso: .venv/bin/python scripts/placebo_tempo.py [--boot 1000]
Salida: data/interim/placebo_tempo_granules.parquet, data/interim/placebo_tempo.json, reports/placebo_tempo.md
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from feasibility_linear import MOLEC_CM2_PER_GM2, SIGMA_THETA, T_PER_YR_TO_GS, load_inputs, plume

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
rng = np.random.default_rng(2023)
PERIODS = [("2023-11-01", "2023-12-31"), ("2024-02-15", "2024-05-31")]
F = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2  # NO₂/NOₓ constante: no se usa el cociente de estaciones por periodo

# Días sin actividad normal (no se usan en los bloques placebo)
HOLIDAYS = {"2023-11-02", "2023-11-20", "2023-12-12", "2024-02-05", "2024-03-18", "2024-05-01"}
DEC_VAC = pd.date_range("2023-12-18", "2023-12-31").strftime("%Y-%m-%d")
SEMANA_SANTA = pd.date_range("2024-03-25", "2024-04-05").strftime("%Y-%m-%d")  # vacaciones escolares SEP
CONTING = set(pd.read_csv(ROOT / "data/raw/contingencias/contingencias_ozono_2024.csv").fecha)

BLOCKS = {  # bloques de ~2 semanas, solo días hábiles "normales"
    "nov 1–15": ("2023-11-01", "2023-11-15"), "nov 16–30": ("2023-11-16", "2023-11-30"),
    "dic 1–15": ("2023-12-01", "2023-12-15"),
    "feb 15–29": ("2024-02-15", "2024-02-29"), "mar 1–15": ("2024-03-01", "2024-03-15"),
    "abr 8–19": ("2024-04-08", "2024-04-19"), "abr 22–may 3": ("2024-04-22", "2024-05-03"),
    "may 6–17": ("2024-05-06", "2024-05-17"), "may 20–31": ("2024-05-20", "2024-05-31"),
}
SEASON = {"otoño": ["nov 1–15", "nov 16–30", "dic 1–15"],
          "primavera": ["feb 15–29", "mar 1–15", "abr 8–19", "abr 22–may 3", "may 6–17", "may 20–31"]}


def granule_stats():
    """Estadísticos suficientes por granulo: Sxy, Sxx (pendiente) y contraste crudo centro − periferia."""
    out = INT / "placebo_tempo_granules.parquet"
    if out.exists():
        return pd.read_parquet(out)
    rows, dens_ref = [], None
    for start, end in PERIODS:
        cand, prior_pt, _, cells, *_, wind, _, px = load_inputs(start, end)
        xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
        xc, yc, wc = cells.x.values, cells.y.values, cells.w.values
        # densidad vial (t/año a ≤ 3 km) en cada píxel: define centro y periferia fijos
        tree = cKDTree(np.c_[xc, yc])
        px["dens"] = [wc[i].sum() for i in tree.query_ball_point(px[["x", "y"]].values, 3000)]
        if dens_ref is None:
            dens_ref = np.quantile(px.dens, [0.25, 0.75])
        for gr, g in px.groupby("granule"):
            h = g.h.iloc[0]
            if h not in wind.index or len(g) < 30:
                continue
            u, v = wind.loc[h].values
            xr, yr = g.x.values, g.y.values
            _, cr = plume(xc, yc, xr, yr, u, v, 1000.0, extra_sy=1300)
            _, cp = plume(xs_p, ys_p, xr, yr, u, v, 1000.0, extra_sy=1300)
            m = (cr @ wc + cp @ prior_pt) * F
            o = g.vcd.values
            dm, do = m - m.mean(), o - o.mean()
            core, peri = g.dens.values >= dens_ref[1], g.dens.values <= dens_ref[0]
            rows.append({"granule": gr, "local": g.local.iloc[0], "day": g.local.iloc[0].strftime("%Y-%m-%d"),
                         "n": len(g), "sxy": float(dm @ do), "sxx": float(dm @ dm), "ws": float(np.hypot(u, v)),
                         "m_mean": float(m.mean()), "o_mean": float(o.mean()),
                         "m_p10": float(np.percentile(m, 10)), "o_p10": float(np.percentile(o, 10)),
                         "ok_cp": bool(core.sum() >= 5 and peri.sum() >= 5),
                         "o_core": float(o[core].mean()) if core.any() else np.nan,
                         "o_peri": float(o[peri].mean()) if peri.any() else np.nan,
                         "m_core": float(m[core].mean()) if core.any() else np.nan,
                         "m_peri": float(m[peri].mean()) if peri.any() else np.nan})
        print(start, end, len(rows))
    df = pd.DataFrame(rows)
    df.to_parquet(out)
    return df


# Estimadores: cociente de sumas Σ numerador / Σ denominador sobre los granulos del grupo.
# Los "normalizados" dividen entre el modelo con emisión fija; los "crudos" solo cuentan granulos.
EST = {
    "pendiente": ("sxy", "sxx"),                # pendiente obs vs modelo dentro del granulo
    "masa": ("exc_o", "exc_m"),                 # columna media sobre el percentil 10, obs ÷ modelo
    "contraste": ("cp_o", "cp_m"),              # centro − periferia, obs ÷ modelo
    "masa_cruda": ("exc_o", "uno"),
    "contraste_crudo": ("cp_o", "uno_cp"),
}
NORM = ["pendiente", "masa", "contraste"]


def per_day(df):
    d = df.assign(exc_o=df.o_mean - df.o_p10, exc_m=df.m_mean - df.m_p10, uno=1.0,
                  cp_o=np.where(df.ok_cp, df.o_core - df.o_peri, 0.0),
                  cp_m=np.where(df.ok_cp, df.m_core - df.m_peri, 0.0), uno_cp=df.ok_cp.astype(float))
    return d.groupby("day")[["sxy", "sxx", "exc_o", "exc_m", "uno", "cp_o", "cp_m", "uno_cp"]].sum()


def est(d):
    s = d.sum()
    return np.array([s[a] / s[b] for a, b in EST.values()])


def compare(D, days0, days1, boot):
    a, b = D.loc[D.index.intersection(days0)], D.loc[D.index.intersection(days1)]
    if len(a) < 3 or len(b) < 3:
        return None
    r = est(b) / est(a)
    bs = np.array([est(b.iloc[rng.integers(0, len(b), len(b))]) / est(a.iloc[rng.integers(0, len(a), len(a))])
                   for _ in range(boot)])
    lo, hi = np.percentile(bs, [5, 95], axis=0)
    return {"dias": [len(a), len(b)], **{k: {"cambio": r[i], "ic90": [lo[i], hi[i]]} for i, k in enumerate(EST)}}


def main(boot):
    df = granule_stats()
    D = per_day(df)
    dates = pd.to_datetime(D.index)
    wd = pd.Series(dates.dayofweek, index=D.index)
    bad = HOLIDAYS | set(DEC_VAC) | set(SEMANA_SANTA) | CONTING
    normal = [d for d in D.index if wd[d] < 5 and d not in bad]

    def block(name):
        s, e = BLOCKS[name]
        return [d for d in normal if s <= d <= e]

    res = {"granulos": len(df), "dias": len(D), "dias_habiles_normales": len(normal),
           "sigma_theta_deg": float(np.rad2deg(SIGMA_THETA)), "placebo": {}, "entre_temporadas": {},
           "ruido": {}, "reales": {}}
    # 1. placebo dentro de cada temporada (todos los pares de bloques)
    for season, names in SEASON.items():
        for n0, n1 in itertools.combinations(names, 2):
            r = compare(D, block(n0), block(n1), boot)
            if r:
                r["temporada"] = season
                res["placebo"][f"{n1} / {n0}"] = r
    # entre temporadas: cambio de química y capa límite que el modelo no representa
    autumn = sum((block(n) for n in SEASON["otoño"]), [])
    spring = sum((block(n) for n in SEASON["primavera"]), [])
    res["entre_temporadas"]["primavera / otoño"] = compare(D, autumn, spring, boot)
    # 2. ruido puro: divisiones aleatorias de días hábiles normales de la misma temporada
    for season, pool in (("otoño", autumn), ("primavera", spring)):
        pool = [d for d in pool if d in D.index]
        for n in (5, 10, 20):
            if 2 * n > len(pool):
                continue
            r = []
            for _ in range(1000):
                pick = rng.permutation(pool)
                r.append(est(D.loc[pick[n:2 * n]]) / est(D.loc[pick[:n]]))
            lo, hi = np.percentile(np.array(r), [5, 95], axis=0)
            res["ruido"][f"{season}, {n} días por grupo"] = {k: [lo[i], hi[i]] for i, k in enumerate(EST)}
    # 3. cambios reales conocidos
    for season, s, e in (("otoño", "2023-11-01", "2023-12-15"), ("primavera", "2024-02-15", "2024-05-31")):
        span = [d for d in D.index if s <= d <= e and d not in bad]
        base = [d for d in span if wd[d] < 5]
        for name, dow in (("sábados", 5), ("domingos", 6)):
            res["reales"][f"{name} / hábiles ({season})"] = compare(D, base, [d for d in span if wd[d] == dow], boot)
    near_dec = [d for d in normal if "2023-11-27" <= d <= "2023-12-15"]
    res["reales"]["vacaciones dic 18–29 / hábiles nov 27–dic 15"] = compare(
        D, near_dec, [d for d in DEC_VAC if pd.Timestamp(d).dayofweek < 5 and d not in {"2023-12-25"}], boot)
    near_ss = [d for d in normal if "2024-03-04" <= d <= "2024-03-22" or "2024-04-08" <= d <= "2024-04-26"]
    res["reales"]["Semana Santa mar 25–abr 5 / hábiles vecinos"] = compare(
        D, near_ss, [d for d in SEMANA_SANTA if pd.Timestamp(d).dayofweek < 5], boot)
    res["reales"]["contingencias / hábiles normales (primavera)"] = compare(
        D, spring, [d for d in CONTING if d in D.index and pd.Timestamp(d).dayofweek < 5], boot)
    res["viento_medio"] = {k: float(df[df.day.isin(v)].ws.mean()) for k, v in
                           (("otoño", autumn), ("primavera", spring))}

    def conv(o):
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple, np.ndarray)):
            return [conv(v) for v in o]
        return float(o) if isinstance(o, (np.floating, np.integer)) else o
    (INT / "placebo_tempo.json").write_text(json.dumps(conv(res), ensure_ascii=False, indent=1))
    for sec in ("placebo", "entre_temporadas", "reales"):
        print("==", sec)
        for k, v in res[sec].items():
            if v:
                print(f"  {k:46s} {v['dias']}  " + "  ".join(
                    f"{e[:6]} {v[e]['cambio']:.2f} ({v[e]['ic90'][0]:.2f}–{v[e]['ic90'][1]:.2f})" for e in EST))
    print("== ruido")
    for k, v in res["ruido"].items():
        print(f"  {k:30s} " + "  ".join(f"{e[:6]} {v[e][0]:.2f}–{v[e][1]:.2f}" for e in EST))
    print(res["viento_medio"])



if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    main(ap.parse_args().boot)
