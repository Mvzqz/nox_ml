"""Prueba rápida: ¿la química NO–NO2–O3 explica la caída de primavera de la columna TEMPO?

TEMPO ve NO2 en columna; el modelo es inerte con cociente NO2/NOx fijo y da 0.98–1.07 de feb a may, mientras la
columna observada cae a 0.81/0.70/0.67 (mar/abr/may, `reports/placebo_tempo.md`). Se descompone por mes (tardes
12–17 h locales, feb 15–may 31 2024):
  1. partición en superficie: NO2/NOx medido en SIMAT (lo que haría Leighton con O3 y radiación);
  2. O3 medido y j(NO2) implícito por el estado fotoestacionario, frente a la radiación de onda corta (ERA5);
  3. cociente columna TEMPO / NO2 de superficie en las estaciones (mezcla vertical, vida media y retrieval);
  4. capa límite.
Salida: reports/multifisica_leighton.md y data/interim/multifisica_leighton.csv.
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, INT, REP = ROOT / "data/raw", ROOT / "data/interim", ROOT / "reports"
START, END = "2024-02-15", "2024-05-31"
HOURS = range(12, 18)


def simat():
    c = pd.read_csv(RAW / "simat/contaminantes_2024.csv.gz", skiprows=9, compression="zip")
    c = c[c.id_parameter.isin(["NO", "NO2", "NOX", "NOx", "O3"])]
    c["date"] = pd.to_datetime(c.date, format="ISO8601")
    c = c[(c.date >= START) & (c.date < pd.Timestamp(END) + pd.Timedelta(days=1)) & c.date.dt.hour.isin(HOURS)]
    w = c.pivot_table(index=["date", "id_station"], columns="id_parameter", values="value").reset_index().rename(columns={"NOX": "NOx"})
    return w


def shortwave():
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=19.43&longitude=-99.13"
           f"&start_date={START}&end_date={END}&hourly=shortwave_radiation&timezone=America%2FMexico_City")
    d = json.load(urllib.request.urlopen(url, timeout=60))["hourly"]
    s = pd.Series(d["shortwave_radiation"], index=pd.to_datetime(d["time"]))
    return s[s.index.hour.isin(HOURS)]


def tempo_at_stations():
    t = pd.read_parquet(INT / "tempo_pixels_2024-02-15_2024-05-31.parquet")
    t = t[t.valid & t.local.dt.hour.isin(HOURS)]
    est = pd.read_csv(RAW / "simat/cat_estacion.csv", skiprows=1, encoding="latin1")
    est = est.rename(columns=str.strip)[["cve_estac", "latitud", "longitud"]].dropna()
    rows = []
    for _, e in est.iterrows():
        near = t[(np.abs(t.lat - e.latitud) < 0.03) & (np.abs(t.lon - e.longitud) < 0.03)]
        if len(near):
            g = near.groupby("granule").agg(vcd=("vcd", "mean"), local=("local", "first"))
            g["id_station"] = e.cve_estac
            rows.append(g)
    g = pd.concat(rows)
    g["date"] = g.local.dt.floor("h")
    return g


def main():
    w = simat()
    w["ratio"] = w.NO2 / w.NOx
    w = w[(w.NOx > 5) & w.ratio.between(0.05, 1.0)]
    # j(NO2) implícito por Leighton: j = k[O3][NO]/[NO2]; k a ~780 hPa y 293 K, en ppb⁻¹ s⁻¹
    k = 1.8e-14 * 2.46e10 * (780 / 1013) * (298 / 293)
    w["j_impl"] = k * w.O3 * w.NO / w.NO2
    w["mes"] = w.date.dt.month
    sw = shortwave()
    pbl = pd.read_parquet(INT / "pbl_2023_2024.parquet").pbl_m
    pbl.index = pbl.index - pd.Timedelta(hours=6)  # UTC → local
    pbl = pbl[pbl.index.hour.isin(HOURS) & (pbl.index >= START) & (pbl.index <= END + " 23:00")]
    tp = tempo_at_stations().merge(w[["date", "id_station", "NO2"]], on=["date", "id_station"])
    tp = tp[tp.NO2 > 2]
    tp["col_sup"] = tp.vcd / tp.NO2 / 1e14
    tp["mes"] = tp.local.dt.month

    m = pd.DataFrame({
        "NO2/NOx sup": w.groupby("mes").ratio.median(),
        "O3 (ppb)": w.groupby("mes").O3.median(),
        "NOx sup (ppb)": w.groupby("mes").NOx.median(),
        "j(NO2) impl (1/s)": w.groupby("mes").j_impl.median(),
        "onda corta (W/m²)": sw.groupby(sw.index.month).mean(),
        "capa límite (m)": pbl.groupby(pbl.index.month).median(),
        "columna/sup (1e14)": tp.groupby("mes").col_sup.median(),
        "columna TEMPO (1e15)": tp.groupby("mes").vcd.median() / 1e15,
    })
    rel = m / m.loc[2]
    m.to_csv(INT / "multifisica_leighton.csv")
    print(m.round(4)); print(rel.round(2))
    obs = {3: 0.81, 4: 0.70, 5: 0.67}
    lines = ["# Prueba rápida: química NO–NO₂–O₃ y la caída de primavera de TEMPO", "",
             "Tardes 12–17 h, 15 feb–31 may 2024. Medianas por mes de todas las estaciones de SIMAT con NO, NO₂, NOₓ y O₃; "
             "columna TEMPO en píxeles válidos a < ~3 km de cada estación, emparejada por hora con el NO₂ de superficie. "
             "Onda corta: ERA5 (Open-Meteo) en el centro. j(NO₂) implícito por el estado fotoestacionario "
             "j = k[O₃][NO]/[NO₂] (k a 780 hPa). Script: `scripts/multifisica_leighton.py`.", "",
             "## Valores por mes", "", m.round(3).to_markdown(), "", "## Relativo a febrero", "",
             rel.round(2).to_markdown(), "",
             "Caída del exceso de columna TEMPO respecto a febrero (de `placebo_tempo.md`): marzo 0.81, abril 0.70, mayo 0.67; "
             "el modelo inerte da 0.98–1.07.", ""]
    (REP / "multifisica_leighton.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
