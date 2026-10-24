"""Utilidades compartidas de estancamiento_*: tabla diaria del estimador con el modelo estándar, placebos y días de contingencia."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contingencias_2024 as c24  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
AFT = (11, 16)   # hora local de inicio de la tarde del estimador (etiqueta SIMAT 12–17 h)
MOR = (6, 10)    # mañana: etiqueta 7–11 h


def load_hourly(f="estancamiento_horario.parquet"):
    h = pd.read_parquet(INT / f)
    h["hl"] = (h.h - pd.Timedelta(hours=6)).dt.hour
    h["day"] = (h.h - pd.Timedelta(hours=6)).dt.normalize()
    h["vel"] = np.hypot(h.u, h.v)
    return h


def daily_from(h, mod="modelo", min_h=4):
    """Misma estructura que contingencias_2024.daily (obs, modelo, horas, ...) para las horas de la tarde."""
    a = h[h.hl.between(*AFT)].copy()
    a["modelo"] = a[mod]
    d = a.groupby("day").agg(obs=("obs", "sum"), modelo=("modelo", "sum"), horas=("h", "size"), pbl=("pbl", "mean"),
                             viento=("vel", "mean"))
    d = d[d.horas >= min_h]
    d["ds"] = d.index.strftime("%Y-%m-%d")
    d["dow"] = d.index.dayofweek
    d["festivo"] = d.ds.isin(c24.HOLIDAYS)
    d["o3max"] = c24.ozone_daily().reindex(d.index)
    d["vent"] = d.modelo / d.horas
    return d


def contingency_days(d, shift=0):
    cont = pd.to_datetime(pd.read_csv(c24.RAW / "contingencias/contingencias_ozono_2024.csv").fecha)
    cont = sorted(x for x in set(cont + pd.Timedelta(days=shift)) if x in d.index)
    excl = set(cont) | {x + pd.Timedelta(days=1) for x in cont}
    habiles = [x for x in cont if x.dayofweek < 5 and x.strftime("%Y-%m-%d") not in c24.HOLIDAYS]
    return cont, habiles, excl


def rel_single(d, days, excl):
    """Índice de cada día / índice medio de sus referencias (mismo día de la semana ±4 semanas): placebo de un día."""
    out = {}
    for day in days:
        r = c24.refs_for(d, day, excl)
        if not r:
            continue
        x, y = d.loc[day], d.loc[r]
        out[day] = (x.obs / x.modelo) / (y.obs.sum() / y.modelo.sum())
    return pd.Series(out)


def ols(y, X):
    """MCO con constante: devuelve (coeficientes, t, R²) como dicts."""
    X = pd.DataFrame(X)
    A = np.column_stack([np.ones(len(X)), X.values])
    b, *_ = np.linalg.lstsq(A, y.values, rcond=None)
    res = y.values - A @ b
    s2 = res @ res / (len(y) - A.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(A.T @ A)))
    names = ["const"] + list(X.columns)
    r2 = 1 - res @ res / ((y.values - y.values.mean()) ** 2).sum()
    return dict(zip(names, b)), dict(zip(names, b / se)), r2


_SOND = {}


def sondeos(desde="2023-10-15", hasta="2025-01-01"):
    """Δθ (700 hPa − superficie, K) de los radiosondeos IGRA del AICM 2024: 00 UTC (18 h locales) y 12 UTC (06 h locales).
    El archivo solo trae temperatura en superficie (~773 hPa) y 700 hPa (~900 m sobre el suelo); el resto son vientos."""
    import io
    import zipfile
    if (desde, hasta) in _SOND:
        return _SOND[(desde, hasta)]
    z = zipfile.ZipFile(ROOT / "data/raw/igra/MXM00076679-data.txt.zip")
    rows, cur = [], None
    for l in io.TextIOWrapper(z.open(z.namelist()[0])):
        if l.startswith("#"):
            p = l.split()
            cur = pd.Timestamp(int(p[1]), int(p[2]), int(p[3]), int(p[4])) if int(p[4]) < 24 else None
            continue
        if cur is None or cur < pd.Timestamp(desde) or cur > pd.Timestamp(hasta):
            continue
        lev, pr, t = l[0:2], int(l[9:15]), int(l[22:27])
        if t != -9999 and (lev == "21" or (lev == "10" and pr == 70000)):
            rows.append((cur, lev, pr / 100, t / 10))
    s = pd.DataFrame(rows, columns=["t", "lev", "p", "T"])
    s["th"] = (s["T"] + 273.15) * (1000 / s.p) ** 0.286
    w = s.pivot_table(index="t", columns="lev", values="th")
    w["dth"] = w["10"] - w["21"]
    w = w.dropna(subset=["dth"])
    # hora local del lanzamiento: 00 UTC del día D+1 = 18 h del día D; 12 UTC del día D = 06 h del día D
    out = pd.DataFrame(index=sorted(set((w.index - pd.Timedelta(hours=6)).normalize())))
    for t, v in w.dth.items():
        loc = t - pd.Timedelta(hours=6)
        out.loc[loc.normalize(), "dth18" if loc.hour >= 12 else "dth06"] = v
    _SOND[(desde, hasta)] = out
    return out


def features(d, h, days, excl):
    """Por día: rel (índice del día ÷ índice de sus referencias) y candidatos explicativos (todo relativo a las referencias)."""
    morning = h[h.hl.between(*MOR)].groupby("day").agg(mobs=("obs", "mean"), mmod=("modelo", "mean"))
    aft = h[h.hl.between(*AFT)].groupby("day").agg(o=("obs", "mean"), m=("modelo", "mean"))
    wd = h[h.hl.between(6, 16)].groupby("day").agg(su=("u", "sum"), sv=("v", "sum"), ss=("vel", "sum"))
    R = np.hypot(wd.su, wd.sv) / wd.ss
    sond = sondeos()
    rows = {}
    for day in days:
        r = c24.refs_for(d, day, excl)
        if not r:
            continue
        x, y = d.loc[day], d.loc[r]
        iref = y.obs.sum() / y.modelo.sum()
        yh = y.horas.sum()
        f = {"rel": (x.obs / x.modelo) / iref, "met": (x.modelo / x.horas) / (y.modelo.sum() / yh),
             "conc": (x.obs / x.horas) / (y.obs.sum() / yh), "wind": x.viento / (y.viento * y.horas).sum() * yh,
             "pbl": x.pbl / (y.pbl * y.horas).sum() * yh}
        # mañana relativa a las referencias
        mr = morning.reindex(r)
        if day in morning.index and mr.mobs.notna().any():
            f["mI"] = (morning.mobs[day] / morning.mmod[day]) / (mr.mobs.sum() / mr.mmod.sum())
        pd1 = day - pd.Timedelta(days=1)
        if pd1 in aft.index:
            f["prevI"] = (aft.o[pd1] / aft.m[pd1]) / iref
            f["prev_met"] = aft.m[pd1] / (aft.m.reindex(r).mean())
        f["R"] = R.get(day, np.nan)
        f["dth06"] = sond.dth06.get(day, np.nan)
        f["dth18"] = sond.dth18.get(day, np.nan)
        rows[day] = f
    out = pd.DataFrame(rows).T
    for c in ("rel", "met", "conc", "wind", "pbl", "mI", "prevI", "prev_met"):
        out["l" + c] = np.log(out[c].astype(float))
    return out
