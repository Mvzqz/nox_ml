"""P1/P2: carga y control de calidad de SIMAT (RAMA + REDMET) según los criterios del plan.

Uso: .venv/bin/python scripts/qc_simat.py 2023 2024
Salida: data/interim/simat_{nox,wind}.parquet y reports/qc_simat.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/simat"
OUT = ROOT / "data/interim"
REP = ROOT / "reports"
from config import LAT, LON
DRY_MONTHS = [11, 12, 1, 2, 3, 4, 5]
AFTERNOON = range(12, 18)  # 12:00–17:00 local
MPH_TO_MS_FACTOR = 2.237  # REDMET 2024 reporta mph como m/s

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def check(ok, msg):
    say(f"- {'✅' if ok else '❌'} {msg}")


def load(kind, years):
    frames = []
    for y in years:
        df = pd.read_csv(RAW / f"{kind}_{y}.csv.gz", skiprows=9, dtype={"value": "float64"},
                         compression="zip")  # SIMAT sirve ZIP con extensión .gz
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # SIMAT: hora local GMT-6 sin horario de verano; la hora 24 ya viene como 00 del día siguiente
    df["local"] = pd.to_datetime(df["date"], format="mixed")
    df["utc"] = df["local"] + pd.Timedelta(hours=6)
    return df.drop(columns="date")


def main(years):
    OUT.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    say(f"# QC SIMAT {years[0]}–{years[-1]}\n")

    cat = pd.read_csv(RAW / "cat_estacion.csv", skiprows=1, encoding="latin1")
    cat = cat.rename(columns={"cve_estac": "station", "longitud": "lon", "latitud": "lat"})
    cat["in_domain"] = cat.lat.between(*LAT) & cat.lon.between(*LON)
    units = pd.read_csv(RAW / "cat_unidades.csv", encoding="latin1").set_index("id_unidad")["clave_unidad"]

    # ---------------- Contaminantes ----------------
    say("## NO / NO₂ / NOₓ (RAMA)\n")
    pol = load("contaminantes", years)
    pol = pol[pol.id_parameter.isin(["NO", "NO2", "NOX"])]
    unknown = set(pol.id_station) - set(cat.station)
    check(not unknown, f"Códigos de estación en catálogo (desconocidos: {sorted(unknown) or 'ninguno'})")
    u = pol.dropna(subset=["value"]).unit.map(units).unique()
    check(set(u) == {"ppb"}, f"Unidades NO/NO₂/NOₓ: {list(u)}")
    dups = pol.duplicated(["id_station", "id_parameter", "local"]).sum()
    check(dups == 0, f"Filas duplicadas estación-parámetro-hora: {dups}")
    neg = (pol.value < 0).sum()
    check(neg == 0, f"Valores negativos: {neg}")
    pol.loc[pol.value < 0, "value"] = np.nan
    wide = pol.pivot_table(index=["id_station", "local", "utc"], columns="id_parameter", values="value").reset_index()
    wide.columns.name = None
    hi = (wide[["NO", "NO2", "NOX"]] > 250).sum()
    say(f"- ℹ️ Horas > 250 ppb (se marcan, no se borran): NO={hi.NO}, NO₂={hi.NO2}, NOₓ={hi.NOX}")
    wide["flag_hi"] = wide.NOX > 250

    both = wide.dropna(subset=["NO", "NO2", "NOX"])
    both = both[both.NOX > 10]
    rel = ((both.NO + both.NO2) - both.NOX).abs() / both.NOX
    check(rel.median() < 0.05, f"NOₓ ≈ NO + NO₂: mediana dif. {rel.median():.1%}, "
          f"{(rel > 0.05).mean():.1%} de horas con dif > 5 %")

    # sensor pegado: >6 h seguidas con el mismo valor (no nulo, > 0)
    def stuck(s):
        s = s.dropna()
        if s.empty:
            return 0
        grp = (s != s.shift()).cumsum()
        runs = s.groupby(grp).transform("size")
        return int(((runs > 6) & (s > 1)).sum())

    stuck_n = wide.sort_values("local").groupby("id_station").NOX.apply(stuck)
    check(stuck_n.sum() == 0, f"Horas NOₓ en rachas > 6 h con valor idéntico: {stuck_n.sum()} "
          f"({', '.join(f'{k}:{v}' for k, v in stuck_n[stuck_n > 0].items()) or '—'})")

    # zona horaria: pico matutino 07–09 en todos los meses
    wide["hour"] = wide.local.dt.hour
    wide["month"] = wide.local.dt.to_period("M")
    peak = wide.groupby(["month", "hour"]).NOX.mean().unstack().idxmax(axis=1)
    bad = peak[~peak.between(7, 9)]
    check(bad.empty, f"Pico matutino de NOₓ entre 07 y 09 h en todos los meses (fuera: {dict(bad.astype(int)) or 'ninguno'})")

    # coherencia física
    wide["dow"] = wide.local.dt.dayofweek
    sun = wide[wide.dow == 6].NOX.mean()
    wk = wide[wide.dow < 5].NOX.mean()
    check(sun < wk, f"Domingo ({sun:.1f} ppb) < hábiles ({wk:.1f} ppb)")
    st = wide.groupby("id_station").NOX.mean()
    traffic = [s for s in ["MER", "CAM"] if s in st]
    periph = [s for s in ["AJM", "CUA"] if s in st]
    check(st[traffic].min() > st[periph].max(),
          f"Tráfico {dict(st[traffic].round(1))} > periféricas {dict(st[periph].round(1))}")

    # completitud por estación-mes (horas 12–17, temporada seca, dentro del dominio)
    dom_st = set(cat[cat.in_domain].station)
    say(f"- ℹ️ Estaciones del catálogo dentro del dominio: {len(dom_st)}")
    aft = wide[wide.hour.isin(AFTERNOON) & wide.local.dt.month.isin(DRY_MONTHS) & wide.id_station.isin(dom_st)]
    hours_per_month = aft.groupby("month").local.nunique()
    comp = aft.groupby(["month", "id_station"]).NOX.count().unstack(fill_value=0).div(hours_per_month, axis=0)
    ok_st = (comp >= 0.75).sum(axis=1)
    say("\n### Estaciones NOₓ válidas (≥ 75 % de horas 12–17 h) por mes de temporada seca\n")
    say("| Mes | Estaciones válidas | Estaciones con datos |")
    say("|---|---|---|")
    for m, n in ok_st.items():
        say(f"| {m} | {n} | {(comp.loc[m] > 0).sum()} |")
    wide.to_parquet(OUT / "simat_nox.parquet")
    comp.to_csv(OUT / "simat_nox_completeness.csv")

    # ---------------- Viento ----------------
    say("\n## Viento (REDMET)\n")
    met = load("meteorologia", years)
    met = met[met.id_parameter.isin(["WSP", "WDR"])]
    u = met.dropna(subset=["value"]).groupby("id_parameter").unit.unique().map(lambda x: [units[i] for i in x])
    check(list(u["WSP"]) == ["m/s"] and list(u["WDR"]) == ["°"], f"Unidades: WSP {u['WSP']}, WDR {u['WDR']}")
    w = met.pivot_table(index=["id_station", "local", "utc"], columns="id_parameter", values="value").reset_index()
    w.columns.name = None
    # REDMET 2024: la velocidad viene ≈ 2.2× más alta que en 2023 contra ERA5 y el METAR de MMMX,
    # con el salto exacto el 2024-01-01 y huecos de rejilla típicos de una conversión.
    # Se interpreta como mph etiquetadas como m/s. Se conserva el valor original en WSP_raw.
    w["WSP_raw"] = w.WSP
    w["wsp_fix_mph"] = w.local.dt.year == 2024
    w.loc[w.wsp_fix_mph, "WSP"] = w.loc[w.wsp_fix_mph, "WSP"] / MPH_TO_MS_FACTOR
    say(f"- ⚠️ Corrección aplicada: WSP de 2024 ÷ {MPH_TO_MS_FACTOR} ({w.wsp_fix_mph.sum():,} filas; original en WSP_raw)")
    check(w.WDR.dropna().between(0, 360).all(), f"Dirección en [0, 360]: rango {w.WDR.min()}–{w.WDR.max()}")
    med = w.groupby("local").WSP.median()
    check(med.between(1, 4).mean() > 0.6,
          f"Mediana horaria WSP entre 1 y 4 m/s en {med.between(1, 4).mean():.0%} de las horas (mediana global {med.median():.2f})")
    w["calm"] = w.WSP < 0.5
    say(f"- ℹ️ Calmas (< 0.5 m/s): {w.calm.mean():.1%} de las horas válidas")
    w["hour"] = w.local.dt.hour
    wa = w[w.hour.isin(AFTERNOON) & w.local.dt.month.isin(DRY_MONTHS) & w.id_station.isin(dom_st)]
    nval = wa.dropna(subset=["WSP", "WDR"]).groupby("local").id_station.nunique()
    nval_m = nval.groupby(nval.index.to_period("M")).apply(lambda s: (s >= 10).mean())
    say("\n### Horas 12–17 h con ≥ 10 estaciones de viento válidas (dominio)\n")
    say("| Mes | % horas OK | Mediana estaciones |")
    say("|---|---|---|")
    for m, v in nval_m.items():
        say(f"| {m} | {v:.0%} | {nval[nval.index.to_period('M') == m].median():.0f} |")
    # dirección dominante de la tarde (para contrastar con ERA5)
    rad = np.deg2rad(wa.WDR)
    dom = (np.rad2deg(np.arctan2((wa.WSP * np.sin(rad)).mean(), (wa.WSP * np.cos(rad)).mean())) + 360) % 360
    say(f"\n- ℹ️ Dirección vectorial media de la tarde (de dónde viene): {dom:.0f}° — contrastar con ERA5")
    w.to_parquet(OUT / "simat_wind.parquet")

    (REP / "qc_simat.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main([int(y) for y in sys.argv[1:]] or [2024])
