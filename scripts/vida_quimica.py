"""Vida química del NOₓ dependiente de mes y hora, y placebo entre temporadas.

Tasa de pérdida diurna de NOₓ por OH + NO₂ → HNO₃:
    k_NOx(t) = k_OH+NO2 · [OH](t) · f_NO2,   f_NO2 = NO₂/NOₓ de la tarde ≈ 0.85 (multifisica_leighton.md)
    [OH](t) = OH_REF · (P(t) / P_ref)^B,       P = j(O¹D) · O₃ · H₂O  (producción primaria de OH)
- j(O¹D) con la parametrización del MCM (J1: l·cosχ^m·exp(−n/cosχ)) y el ángulo cenital en el centro;
- O₃, temperatura y humedad relativa: medianas horarias de las estaciones de SIMAT;
- OH_REF = 6×10⁶ cm⁻³ al mediodía (12–13 h) de abril, del orden de lo medido en MCMA-2003 (abril) y MILAGRO 2006;
  k_OH+NO2 = 9.3×10⁻¹² cm³ s⁻¹ (JPL a ~780 hPa). De noche OH ≈ 0: la pérdida nocturna (N₂O₅) se ignora.
Nada se ajusta con los datos de NOₓ que se usan para evaluar.

Modos:
  --serie           calcula y guarda la serie horaria (data/interim/vida_quimica_kloss.parquet)
  --tamizado        modelo con emisión fija solo en estaciones, por variante: cociente observado/modelo por mes
  --completo VAR    inversión completa (estaciones + TEMPO) con la variante, nov–dic 2023 y feb–may 2024, más el placebo
                    entre temporadas (subperiodos con la misma matriz y pesos por día)
  --reporte         tablas para reports/vida_quimica.md
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feasibility_linear as fl  # noqa: E402
import puff  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW, INT = ROOT / "data/raw", ROOT / "data/interim"
OUT = INT / "vida_quimica"
LAT0, LON0 = 19.43, -99.13
K_OH_NO2 = 9.3e-12
F_NO2 = 0.85
OH_REF = 6e6
PERIODS = {"nov23": ("2023-11-01", "2023-12-31"), "prim24": ("2024-02-15", "2024-05-31")}
# Variantes: (vida, MAX_AGE_H). "fija4": vida constante de 4 h (estándar actual).
VARIANTS = {
    "fija4_6h": dict(loss=None, tau=4.0, age=6),
    "fija4_24h": dict(loss=None, tau=4.0, age=24),
    "oh_6h": dict(loss=(OH_REF, 1.0), age=6),
    "oh_24h": dict(loss=(OH_REF, 1.0), age=24),
    "oh_b05_24h": dict(loss=(OH_REF, 0.5), age=24),
    "oh_alto_24h": dict(loss=(9e6, 1.0), age=24),
    "oh_bajo_24h": dict(loss=(4e6, 1.0), age=24),
    # sensibilidad: pérdida adicional constante (PAN, nitratos orgánicos, N₂O₅ nocturno, depósito) de 1/12 h
    "oh_k12_24h": dict(loss=(OH_REF, 1.0, 1 / (12 * 3600)), age=24),
}


# ---------------------------------------------------------------- serie de pérdida
def cos_zenith(t_utc):
    """cos del ángulo cenital en el centro de la ciudad (aprox. de Spencer)."""
    doy = t_utc.dayofyear.values
    g = 2 * np.pi / 365 * (doy - 1 + (t_utc.hour.values + 0.5 - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g)
                    - 0.040849 * np.sin(2 * g))
    tst = (t_utc.hour.values + 0.5) * 60 + eqt + 4 * LON0
    ha = np.deg2rad(tst / 4 - 180)
    lat = np.deg2rad(LAT0)
    return np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)


def j_o1d(cz):
    """MCM J1 (O₃ → O¹D): 6.073e-5 · cosχ^1.743 · exp(−0.474 / cosχ); 0 de noche."""
    cz = np.asarray(cz)
    out = np.zeros_like(cz, dtype=float)
    d = cz > 0.02
    out[d] = 6.073e-5 * cz[d] ** 1.743 * np.exp(-0.474 / cz[d])
    return out


def read_simat(f):
    """Lee un archivo anual de SIMAT y agrega la hora UTC (h = local + 6, como qc_simat y val2020_data).
    2023–2024: ZIP aunque terminen en .gz, fecha ISO; 2019–2020: gzip, una línea más de encabezado, fecha
    dd/mm/aaaa HH:MM (la hora 24 pasa al día siguiente)."""
    if open(f, "rb").read(2) == b"PK":
        d = pd.read_csv(f, skiprows=9, compression="zip")
        d["h"] = pd.to_datetime(d.date, format="ISO8601") + pd.Timedelta(hours=6)
    else:
        d = pd.read_csv(f, skiprows=10, compression="gzip", dtype={"value": "float64"})
        p = d.date.str.split(" ", expand=True)
        d["h"] = pd.to_datetime(p[0], format="%d/%m/%Y") + pd.to_timedelta(p[1].str.slice(0, 2).astype(int) + 6, unit="h")
    return d


def simat_hourly(years=(2023, 2024)):
    rows = []
    for y in years:
        c = read_simat(RAW / f"simat/contaminantes_{y}.csv.gz")
        c = c[c.id_parameter == "O3"]
        m = read_simat(RAW / f"simat/meteorologia_{y}.csv.gz")
        m = m[m.id_parameter.isin(["RH", "TMP"])]
        for d in (c, m):
            rows.append(d.groupby(["h", "id_parameter"]).value.median().unstack())
    d = pd.concat(rows, axis=0).sort_index()
    return d.T.groupby(level=0).first().T.groupby(level=0).first()   # une columnas repetidas y años


def loss_series(oh_ref=OH_REF, b=1.0, k_extra=0.0):
    f = INT / "vida_quimica_insumos.parquet"
    if f.exists():
        d = pd.read_parquet(f)
    else:
        parts = []
        # dos bloques (validación 2019–2020 y periodo de estudio), cada uno con su propio relleno
        for years, (i0, i1) in (((2019, 2020), ("2019-01-01", "2021-01-01")), ((2023, 2024), ("2023-10-01", "2024-06-01"))):
            d = simat_hourly(years).reindex(pd.date_range(i0, i1, freq="h"))
            d = d.interpolate(limit=6)
            # huecos largos: climatología mes-hora
            for col in d.columns:
                clim = d[col].groupby([d.index.month, d.index.hour]).transform("median")
                d[col] = d[col].fillna(clim)
            parts.append(d)
        d = pd.concat(parts)
        d["jo1d"] = j_o1d(cos_zenith(d.index))
        es = 6.112 * np.exp(17.67 * d.TMP / (d.TMP + 243.5))
        d["h2o"] = d.RH / 100 * es                                   # presión de vapor (hPa) ∝ H₂O
        d["P"] = d.jo1d * d.O3.clip(lower=1) * d.h2o
        d.to_parquet(f)
    loc = d.index - pd.Timedelta(hours=6)
    ref = d.P[(loc.year == 2024) & (loc.month == 4) & (loc.hour == 12)].mean()   # mediodía de abril de 2024
    oh = oh_ref * (d.P / ref).clip(lower=0) ** b
    return (K_OH_NO2 * oh * F_NO2 + k_extra).rename("k_nox")


STANDARD = "oh_24h"   # variante adoptada como estándar (reports/vida_quimica.md)


def covered(start, end):
    """¿La serie de pérdida cubre el periodo (con 1 día de margen para los puffs de 24 h)?"""
    k = loss_series()
    return k.index.min() <= pd.Timestamp(start) - pd.Timedelta(days=1) and k.index.max() >= pd.Timestamp(end) + pd.Timedelta(days=1)


def apply_variant(v):
    cfg = VARIANTS[v]
    puff.MAX_AGE_H = cfg["age"]
    puff.TAU_CHEM_H = cfg.get("tau", 4.0)
    puff.LOSS_RATE = None if cfg["loss"] is None else loss_series(*cfg["loss"])
    puff._loss_cache.clear()


def serie():
    k = loss_series()
    loc = k.index - pd.Timedelta(hours=6)
    tau = 1 / k.replace(0, np.nan) / 3600
    d = pd.read_parquet(INT / "vida_quimica_insumos.parquet")
    t = pd.DataFrame({"mes": loc.month, "hora": loc.hour, "tau_h": tau, "O3": d.O3, "h2o": d.h2o, "jo1d": d.jo1d})
    t = t[t.hora.between(8, 17)]
    tab = t.groupby(["mes", "hora"]).tau_h.median().unstack()
    print(tab.round(1).to_string())
    OUT.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT / "tau_mes_hora.csv")
    m = t[t.hora.between(12, 13)].groupby("mes")[["O3", "h2o", "jo1d", "tau_h"]].median()
    print(m.to_string())
    m.to_csv(OUT / "insumos_mediodia.csv")


# ---------------------------------------------------------------- tamizado: modelo con emisión fija en estaciones
def extended_profile():
    """puff.PROFILE donde existe (6–17 h); fuera de esas horas, perfil de Infovial (hábil), para puffs de > 6 h."""
    import puffs_cdmx as pc
    import real_check_linear as rcl
    inf = pc.infovial_profile()
    def f(h):
        hl = (h + pd.Timedelta(hours=-6)).hour
        return puff.PROFILE.get(hl, inf[rcl.day_type(h)][hl])
    return f


def fixed_station_series(period, variant):
    import puffs_cdmx as pc
    import real_check_linear as rcl
    start, end = PERIODS[period]
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    apply_variant(variant)
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = fl.load_inputs(start, end, True)
    keep = (cand.tipo != "industria").values
    cand, prior_pt = cand[keep].reset_index(drop=True), prior_pt[keep].copy()
    for nm, (p, s) in pc.NEW_PRIORS.items():
        prior_pt[next(i for i, c in enumerate(cand.nombre) if nm in c)] = p
    tr = pc.Transport("domain", extended_profile(), traj=puff.Trajectories(wind))
    hours = [h for h in sorted(set(nox.h) & set(wind.index)) if h in pbl.index]
    est_ids = set(nox[nox.est].id_station)
    rows = []
    empty = px.iloc[:0]
    n_pt = len(cand)
    for h in hours:
        nh = nox[(nox.h == h) & ~nox.id_station.isin(est_ids)]
        if not len(nh):
            continue
        (_, K), = pc.jacobian_puff_mx(h, tr, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, empty, ratio)
        fixed = K[:, :n_pt] @ prior_pt + K[:, n_pt:].sum(1)
        rows += [(h, s, o, f) for s, o, f in zip(nh.id_station.values, nh.NOX.values, fixed)]
    d = pd.DataFrame(rows, columns=["h", "sid", "obs", "fixed"])
    d["day"] = [rcl.local_day(h) for h in d.h]
    d["dt"] = [rcl.day_type(h) for h in d.h]
    return d


def tamizado(variants):
    OUT.mkdir(parents=True, exist_ok=True)
    for v in variants:
        parts = []
        for p in PERIODS:
            t0 = time.time()
            d = fixed_station_series(p, v)
            d["periodo"] = p
            parts.append(d)
            print(f"[{v}] {p}: {len(d)} obs en {time.time() - t0:.0f} s", flush=True)
        pd.concat(parts).to_parquet(OUT / f"tamizado_{v}.parquet")


def seasonal_table(d):
    """Cociente observado/modelo (hábiles) por mes y por bloque, relativo a feb–mar 2024."""
    d = d[d.dt == 0].copy()
    loc = pd.to_datetime(d.day)
    d["mes"] = loc.dt.month
    d["bloque"] = np.select([loc < "2024-01-01", loc < "2024-04-01"], ["nov–dic", "feb–mar"], "abr–may")
    days = d.groupby("day").agg(obs=("obs", "sum"), fixed=("fixed", "sum"), bloque=("bloque", "first"), mes=("mes", "first"))
    r = lambda g: g.obs.sum() / g.fixed.sum()
    ref = r(days[days.bloque == "feb–mar"])
    out = {"mes": {int(m): r(g) / ref for m, g in days.groupby("mes")},
           "bloque": {b: r(g) / ref for b, g in days.groupby("bloque")}}
    rng = np.random.default_rng(3)
    bs = {"abr–may": [], "nov–dic": []}
    for _ in range(1000):
        q = days.iloc[rng.integers(0, len(days), len(days))]
        rf = r(q[q.bloque == "feb–mar"])
        for b in bs:
            bs[b].append(r(q[q.bloque == b]) / rf)
    out["ic"] = {b: np.percentile(v, [5, 95]).tolist() for b, v in bs.items()}
    return out


# ---------------------------------------------------------------- inversión completa con la variante
def completo(variant, boot):
    import la_real as lr
    import puffs_cdmx as pc
    import real_check_linear as rcl
    apply_variant(variant)
    res = {}
    for period, (start, end) in PERIODS.items():
        t0 = time.time()
        fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
        rcl.set_tempo_weight(3, 0)
        inp = list(fl.load_inputs(start, end, extras=True))
        cand, prior_pt, sd_pt = inp[0], inp[1].copy(), inp[2].copy()
        for nm, (p, s) in pc.NEW_PRIORS.items():
            i = next(i for i, c in enumerate(cand.nombre) if nm in c)
            prior_pt[i], sd_pt[i] = p, s
        inp[1], inp[2] = prior_pt, sd_pt
        wind = inp[9]
        rcl.load_inputs = lambda *_a, _inp=inp, **_k: tuple(_inp)
        tr = pc.Transport("domain", extended_profile() if puff.MAX_AGE_H > 6 else pc.profile_fn("supuesto"),
                          traj=puff.Trajectories(wind))
        rcl.Trajectories = lambda *_a, _tr=tr: _tr
        rcl.jacobian_hour_puff = pc.jacobian_puff_mx
        m = rcl.build(start, end, "puff", no_industry=True, extras=True)
        tb = time.time() - t0
        m.pop("E", None)
        x0, free = pc.free_sunday(m, boot)
        m["E"] = pc.ratio_constraint(m, x0)
        r = lr.metrics(m, boot)
        r.update(free)
        r["sub"] = subperiods(m)
        r["segundos_jacobiano"], r["segundos_total"] = tb, time.time() - t0
        res[period] = r
        print(f"[{variant}] {period} ({time.time() - t0:.0f} s): LOO {r['loo_model']:.1f}/{r['loo_hybrid']:.1f}, "
              f"vial {r['vial_habil'] / r['vial_apriori']:.0%}, domingo {r['domingo']:.2f}, norm {r['norm_domingo']:.2f}, "
              f"r TEMPO {r['muestra_r_tempo']:.2f}", flush=True)
        tag = "" if fl.REGION_SCHEME == "3x3_ecatepec" else f"_{fl.REGION_SCHEME}"
        (OUT / f"completo_{variant}_{period}{tag}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=float))
    return res


def subperiods(m):
    """Por subperiodo (meses): total vial hábil invertido (misma matriz, pesos por día), estimador normalizado en
    estaciones y en TEMPO (exceso sobre el p10 de cada escaneo), solo días hábiles."""
    import real_check_linear as rcl
    n_pt, nr = m["n_pt"], m["n_reg"]
    H = len(m["hours"])
    n_src = n_pt + 3 * nr
    days = sorted({d for d, *_ in m["blocks"]})
    mon = {d: pd.Timestamp(d).month for d in days}
    groups = {}
    for d in days:
        groups.setdefault({11: "nov", 12: "dic", 2: "feb", 3: "mar", 4: "abr", 5: "may"}[mon[d]], []).append(d)
    st = pd.DataFrame([(h, yy, float(kr[:n_pt] @ m["prior_pt"] + kr[n_pt:n_pt + nr].sum()))
                       for s, h, idx, kr, yy in m["st_rows"] if s not in m["est_ids"]], columns=["h", "obs", "fixed"])
    st["day"] = [rcl.local_day(h) for h in st.h]
    st["dt"] = [rcl.day_type(h) for h in st.h]
    tp = []
    for idx, Kf, y in m["tp_rows"]:
        k = idx[-1] - n_src - H
        h = m["hours"][k]
        f = Kf[:, :n_pt] @ m["prior_pt"] + Kf[:, n_pt:n_pt + nr].sum(1)
        if len(y) >= 30:
            tp.append((rcl.local_day(h), rcl.day_type(h), y.mean() - np.percentile(y, 10), f.mean() - np.percentile(f, 10)))
    tp = pd.DataFrame(tp, columns=["day", "dt", "obs", "fixed"])
    out = {}
    for g, ds in groups.items():
        N, b = rcl.solve(m, weights={d: 1 for d in ds})
        N = N + m["E"]
        x = np.linalg.solve(N, b)
        tot = rcl.road_totals(m, x)
        s = st[st.day.isin(ds) & (st.dt == 0)]
        t = tp[tp.day.isin(ds) & (tp.dt == 0)]
        out[g] = {"vial_habil": float(tot[0]), "norm_est": float(s.obs.sum() / s.fixed.sum()),
                  "norm_tempo": float(t.obs.sum() / t.fixed.sum()) if len(t) else None, "dias": len(ds)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serie", action="store_true")
    ap.add_argument("--tamizado", nargs="*")
    ap.add_argument("--completo")
    ap.add_argument("--boot", type=int, default=200)
    a = ap.parse_args()
    if a.serie:
        serie()
    if a.tamizado is not None:
        tamizado(a.tamizado or list(VARIANTS))
    if a.completo:
        completo(a.completo, a.boot)


if __name__ == "__main__":
    main()
