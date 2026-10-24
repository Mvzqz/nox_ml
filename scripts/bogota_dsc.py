"""Bogotá, versión ligera: el Día sin carro con el estimador normalizado por meteorología, solo con estaciones.

Igual que en la CDMX (val2020_ratio.py, contingencias_2024.py), el índice de cada hora es NOₓ observado ÷ NOₓ que
predice un modelo con la emisión fija; el cociente de ese índice entre el día del evento y jueves de referencia
estima el cambio de emisión ya descontada la ventilación. Diferencia: sin TEMPO ni red vial de Bogotá, el modelo
con emisión fija es una **caja bien mezclada**: C ∝ 1 / (U · H), con U = viento medio de las estaciones RMCAB
(mínimo 0.5 m/s) y H = capa límite ERA5 (mínimo 100 m). Para ene–jun 2024, Open-Meteo no trae capa límite: se usa
la mediana mes-hora de 2015–2023 (solo se normaliza por viento) y se marca.

Ventanas: mañana 06–11 h, tarde 12–17 h y día 06–19 h (la medida rige de 05:00 a 19:30), hora local UTC−5.
Referencias: jueves no festivos a ±35 días del evento, fuera de vacaciones escolares, sin otros eventos.
Ruido: placebo con jueves falsos del mismo grupo de referencias (mismo número de eventos).

Uso: .venv/bin/python scripts/bogota_dsc.py [--placebos 2000]
Salidas: data/interim/bogota/dsc_hourly.parquet, dsc_resultados.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/bogota"
OUT = ROOT / "data/interim/bogota"
rng = np.random.default_rng(2000)

# Fechas del Día sin carro (ver reports/bogota.md, sección "Versión ligera", para las fuentes).
EVENTS = {
    "2015": "2015-02-05", "2016": "2016-02-04", "2017": "2017-02-02", "2018": "2018-02-01",
    "2019": "2019-02-07", "2020": "2020-02-06", "2022s": "2022-09-22", "2023": "2023-02-02",
    "2023s": "2023-09-21", "2024": "2024-02-01",
}
# Días que no sirven de referencia: vacaciones escolares de inicio de año (hasta ~15 ene) y receso de octubre.
EXCLUDE_RANGES = [("01-01", "01-15"), ("10-03", "10-16")]
WINDOW = 35
HOURS = {"mañana": range(6, 12), "tarde": range(12, 18), "día": range(6, 20)}
U_MIN, H_MIN = 0.5, 100.0
SUF = {"nox": "", "co": "_co"}


def parse(path):
    j = json.load(open(path))
    can = j["canales"]
    df = pd.DataFrame(j["datos"])
    if df.empty:
        return None
    df = df[df.datetime.str.match(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}")]  # quita filas de resumen
    dts = df.pop("datetime").str.strip()
    day = pd.to_datetime(dts.str[:10], format="%d-%m-%Y")
    hr = dts.str[11:13].astype(int)
    df.index = day + pd.to_timedelta(hr, unit="h")  # "24:00" pasa al día siguiente
    df = df.rename(columns=can).apply(pd.to_numeric, errors="coerce")
    df = df[~df.index.duplicated()]
    out = pd.DataFrame(index=df.index)
    out["nox"] = df.get("NOX")
    ws = df.get("Vel Viento") if "Vel Viento" in df else df.get("Vel Viento 10M")
    out["ws"] = ws
    out["co"] = df.get("CO")
    out.loc[(out.nox < 0) | (out.nox > 1500), "nox"] = np.nan
    out.loc[(out.ws < 0) | (out.ws > 30), "ws"] = np.nan
    out["station"] = j["id"]
    out["name"] = j["estacion"]
    return out


def load_pbl():
    j = json.load(open(RAW / "era5/openmeteo_era5_bogota_2015_2024.json"))
    h = pd.DataFrame(j["hourly"])
    t = pd.to_datetime(h.time) - pd.Timedelta(hours=5)  # UTC → hora local (UTC−5, sin horario de verano)
    pbl = pd.Series(h.boundary_layer_height.values, index=t)
    p = pbl[pbl.index.year <= 2023]
    clim = p.groupby([p.index.month, p.index.hour]).median()
    gap = pbl.isna()
    filled = pbl.copy()
    filled[gap] = [clim.get((x.month, x.hour), np.nan) for x in pbl.index[gap]]
    # la capa límite de la hora h representa la mezcla entre h y h+1 (igual que en la CDMX)
    return ((filled + filled.shift(-1)) / 2).ffill(), gap


def build(var="nox"):
    frames = [f for f in (parse(p) for p in sorted((RAW / "dsc").glob("rmcab_*_*.json"))) if f is not None]
    st = pd.concat(frames)
    pbl, gap = load_pbl()
    rows = []
    for name, ev in EVENTS.items():
        ev = pd.Timestamp(ev)
        lo, hi = ev - pd.Timedelta(days=WINDOW), ev + pd.Timedelta(days=WINDOW + 1)
        w = st[(st.index >= lo) & (st.index < hi)]
        if w[var].notna().sum() == 0:
            continue
        # estaciones con ≥ 70 % de NOₓ entre 6 y 19 h en la ventana
        day = w[w.index.hour.isin(HOURS["día"])]
        cov = day.groupby("station")[var].apply(lambda s: s.notna().mean())
        good = cov[cov >= 0.7].index
        w = w[w.station.isin(good)]
        nox = w.pivot_table(index=w.index, columns="station", values=var)
        ws = w.pivot_table(index=w.index, columns="station", values="ws")
        # promedio de estaciones con anomalía por estación para que una estación faltante no sesgue el nivel
        lvl = nox.mean()
        frac = nox.notna().mean(axis=1)
        city = (nox / lvl).mean(axis=1) * lvl.mean()
        df = pd.DataFrame({"obs": city, "frac_est": frac, "n_est": len(good), "ws": ws.mean(axis=1)})
        df = df[df.frac_est >= 0.6]
        df["pbl"] = pbl.reindex(df.index)
        df["pbl_clim"] = gap.reindex(df.index).fillna(False).values
        df["modelo"] = 1.0 / (df.ws.clip(lower=U_MIN) * df.pbl.clip(lower=H_MIN))
        df["modelo_u"] = 1.0 / df.ws.clip(lower=U_MIN)  # sensibilidad: solo viento, sin capa límite
        df["evento"] = name
        df["dia"] = df.index.normalize()
        df["hora"] = df.index.hour
        rows.append(df.dropna(subset=["obs", "ws", "pbl"]))
    hourly = pd.concat(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(OUT / f"dsc_hourly{SUF[var]}.parquet")
    return hourly


def excluded(d):
    md = d.strftime("%m-%d")
    return any(a <= md <= b for a, b in EXCLUDE_RANGES)


def ref_days(h, name):
    ev = pd.Timestamp(EVENTS[name])
    others = {pd.Timestamp(v) for v in EVENTS.values()}
    days = pd.DatetimeIndex(h[h.evento == name].dia.unique())
    return [d for d in days if d.dayofweek == 3 and d not in others and not excluded(d)
            and abs((d - ev).days) <= WINDOW]


def ratio(h, name, ev_day, refs, hours, col="modelo"):
    """(Σ obs ÷ Σ modelo) del evento ÷ lo mismo en las referencias; con col=None, cociente crudo."""
    g = h[(h.evento == name) & h.hora.isin(hours)]
    e, r = g[g.dia == ev_day], g[g.dia.isin(refs)]
    if len(e) < 0.6 * len(hours) or r.dia.nunique() < 3:
        return np.nan
    if col is None:
        return e.obs.mean() / r.obs.mean()
    return (e.obs.sum() / e[col].sum()) / (r.obs.sum() / r[col].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placebos", type=int, default=2000)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--var", choices=["nox", "co"], default="nox", help="co: control con un trazador de gasolina")
    a = ap.parse_args()
    f = OUT / f"dsc_hourly{SUF[a.var]}.parquet"
    h = build(a.var) if (a.rebuild or not f.exists()) else pd.read_parquet(f)

    res = {"eventos": {}, "combinado": {}, "notas": {}}
    names = [n for n in EVENTS if (h.evento == n).any()]
    refs = {n: ref_days(h, n) for n in names}
    for n in names:
        ev = pd.Timestamp(EVENTS[n])
        r = {"fecha": EVENTS[n], "n_ref": len(refs[n]), "n_est": int(h[h.evento == n].n_est.iloc[0]),
             "pbl_climatologica": bool(h[(h.evento == n) & (h.dia == ev)].pbl_clim.any())}
        for w, hrs in HOURS.items():
            r[w] = {"emision": ratio(h, n, ev, refs[n], hrs), "crudo": ratio(h, n, ev, refs[n], hrs, None),
                    "solo_viento": ratio(h, n, ev, refs[n], hrs, "modelo_u")}
            # meteorología del evento frente a referencias (modelo con emisión fija)
            g = h[(h.evento == n) & h.hora.isin(hrs)]
            r[w]["meteo"] = g[g.dia == ev].modelo.mean() / g[g.dia.isin(refs[n])].modelo.mean()
        res["eventos"][n] = r

    # placebo: para cada evento, un jueves de referencia hace de evento falso frente a las demás referencias
    def one(n, fake, w, col):
        return ratio(h, n, fake, [d for d in refs[n] if d != fake], HOURS[w], col)

    for w in HOURS:
        for col, key in (("modelo", "emision"), (None, "crudo"), ("modelo_u", "solo_viento")):
            # placebos por evento (todos los jueves falsos posibles)
            per = {n: np.array([one(n, d, w, col) for d in refs[n]]) for n in names}
            for n in names:
                p = per[n][~np.isnan(per[n])]
                if len(p):
                    res["eventos"][n][w][f"placebo_{key}"] = [float(np.percentile(p, 5)), float(np.percentile(p, 95)), int(len(p))]
            # combinado: media geométrica de los eventos válidos frente a la misma media con jueves falsos
            valid = [n for n in names if not np.isnan(res["eventos"][n][w][key])]
            real = float(np.exp(np.mean([np.log(res["eventos"][n][w][key]) for n in valid])))
            sims = []
            for _ in range(a.placebos):
                vals = []
                for n in valid:
                    p = per[n][~np.isnan(per[n])]
                    if len(p):
                        vals.append(np.log(p[rng.integers(len(p))]))
                sims.append(np.exp(np.mean(vals)))
            sims = np.array(sims)
            res["combinado"].setdefault(w, {})[key] = {
                "estimado": real, "n_eventos": len(valid),
                "placebo_p5_p95": [float(np.percentile(sims, 5)), float(np.percentile(sims, 95))],
                "placebo_mediana": float(np.median(sims)),
                "p_unilateral": float((sims <= real).mean()),
                # intervalo de 90 % del cambio: estimado ÷ cuantiles del placebo (el placebo mide el ruido)
                "ic90": [float(real / np.percentile(sims, 95) * np.median(sims)),
                         float(real / np.percentile(sims, 5) * np.median(sims))]}
    res["notas"] = {"modelo": "caja bien mezclada: 1/(U·H); U = viento medio RMCAB (≥0.5 m/s); H = capa límite ERA5 (≥100 m)",
                    "pbl_2024": "ene–jun 2024 sin capa límite en Open-Meteo: mediana mes-hora 2015–2023"}
    (OUT / f"dsc_resultados{SUF[a.var]}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))

    for n, r in res["eventos"].items():
        line = f"{n:6s} {r['fecha']} est={r['n_est']:2d} ref={r['n_ref']}{' (PBL clim)' if r['pbl_climatologica'] else ''}"
        for w in HOURS:
            x = r[w]
            pe = x.get("placebo_emision", [np.nan, np.nan, 0])
            line += f" | {w}: emis {x['emision']:.2f} crudo {x['crudo']:.2f} meteo {x['meteo']:.2f} plac {pe[0]:.2f}–{pe[1]:.2f}"
        print(line)
    for w, v in res["combinado"].items():
        for k, x in v.items():
            print(f"combinado {w:6s} {k:8s} {x['estimado']:.2f} (IC90 {x['ic90'][0]:.2f}–{x['ic90'][1]:.2f}); "
                  f"placebo {x['placebo_p5_p95'][0]:.2f}–{x['placebo_p5_p95'][1]:.2f} med {x['placebo_mediana']:.2f}; "
                  f"p={x['p_unilateral']:.3f}; n={x['n_eventos']}")


if __name__ == "__main__":
    main()
