"""Validación 2020: carga SIMAT 2019–2020 (NOₓ y viento) y revisa unidades del viento.

Los archivos anuales de 2019–2020 son gzip reales (no ZIP como 2023–2024), con encabezado en la
línea 11, fecha dd/mm/aaaa y hora 01–24 (la 24 es la 00 del día siguiente). Hora local GMT−6.

Uso: .venv/bin/python scripts/val2020_data.py
Salida: data/interim/simat_nox_2019_2020.parquet, data/interim/simat_wind_2019_2020.parquet
        y una tabla de unidades del viento en pantalla (REDMET central ÷ METAR MMMX por trimestre).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/simat"
OUT = ROOT / "data/interim"
YEARS = [2019, 2020]
CENTRAL = ["MER", "HGM", "BJU", "IZT", "UIZ", "NEZ", "FAR", "GAM", "LAA"]


def load(kind, y, params):
    df = pd.read_csv(RAW / f"{kind}_{y}.csv.gz", skiprows=10, dtype={"value": "float64"})
    df = df[df.id_parameter.isin(params)].copy()
    d = df.date.str.split(" ", expand=True)
    day = pd.to_datetime(d[0], format="%d/%m/%Y")
    hr = d[1].str.slice(0, 2).astype(int)
    df["local"] = day + pd.to_timedelta(hr, unit="h")  # la hora 24 pasa al día siguiente
    df["utc"] = df.local + pd.Timedelta(hours=6)
    return df.drop(columns="date")


def main():
    pol = pd.concat([load("contaminantes", y, ["NO", "NO2", "NOX"]) for y in YEARS])
    pol.loc[pol.value < 0, "value"] = np.nan
    nox = pol.pivot_table(index=["id_station", "local", "utc"], columns="id_parameter", values="value").reset_index()
    nox.columns.name = None
    nox["hour"] = nox.local.dt.hour
    nox["dow"] = nox.local.dt.dayofweek
    nox.to_parquet(OUT / "simat_nox_2019_2020.parquet")

    met = pd.concat([load("meteorologia", y, ["WSP", "WDR"]) for y in YEARS])
    w = met.pivot_table(index=["id_station", "local", "utc"], columns="id_parameter", values="value").reset_index()
    w.columns.name = None
    w.to_parquet(OUT / "simat_wind_2019_2020.parquet")
    print(f"NOₓ: {len(nox):,} filas, {nox.id_station.nunique()} estaciones; viento: {len(w):,} filas, "
          f"{w.id_station.nunique()} estaciones")

    # unidades: REDMET central ÷ METAR MMMX, tardes, por trimestre (2023 daba 0.59–0.63)
    m = pd.read_csv(ROOT / "data/raw/metar/MMMX_2019-2020.csv", parse_dates=["valid"]).dropna(subset=["sknt"])
    m["utc"] = m.valid.dt.floor("h")
    mm = m.groupby("utc").sknt.mean() * 0.5144
    r = w[w.id_station.isin(CENTRAL)].dropna(subset=["WSP"]).groupby("utc").WSP.mean()
    j = pd.concat({"redmet": r, "metar": mm}, axis=1, sort=True).dropna()
    j = j[((j.index - pd.Timedelta(hours=6)).hour >= 12) & ((j.index - pd.Timedelta(hours=6)).hour <= 17)]
    q = j.groupby(j.index.to_period("Q")).apply(lambda g: g.redmet.mean() / g.metar.mean())
    print("REDMET central ÷ METAR MMMX (tardes):", " ".join(f"{k}={v:.2f}" for k, v in q.items()))


if __name__ == "__main__":
    main()
