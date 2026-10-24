"""Configuración y carga de datos para la prueba en Los Ángeles (comparación con CDMX).

Dominio ~55 × 55 km centrado en el centro de LA; periodo nov–dic 2023 (igual que CDMX).
Hora local: PST = UTC−8 (sin horario de verano en nov–dic salvo hasta el 5 de nov; se usa UTC−8).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/la"
INT = ROOT / "data/interim/la"
BBOX = (-118.55, 33.80, -117.95, 34.30)
LON, LAT = (BBOX[0], BBOX[2]), (BBOX[1], BBOX[3])
DOMAIN = box(*BBOX)
UTM = "EPSG:32611"
START, END = "2023-11-01", "2023-12-31"
LOCAL_OFFSET_H = -8
AFTERNOON = range(12, 18)


def extract_aqs(zip_name, params, out_name):
    """Filtra un archivo horario de EPA AQS al dominio y periodo; guarda parquet."""
    INT.mkdir(parents=True, exist_ok=True)
    cols = ["State Name", "County Code", "Site Num", "Parameter Code", "POC", "Latitude", "Longitude",
            "Date GMT", "Time GMT", "Date Local", "Time Local", "Sample Measurement", "Units of Measure"]
    keep = []
    for ch in pd.read_csv(RAW / zip_name, usecols=cols, chunksize=2_000_000, dtype={"County Code": str, "Site Num": str}):
        ch = ch[(ch["State Name"] == "California") & ch["Parameter Code"].isin(params)
                & ch.Latitude.between(*LAT) & ch.Longitude.between(*LON)]
        if len(ch):
            keep.append(ch)
    df = pd.concat(keep, ignore_index=True)
    df["site"] = df["County Code"] + "-" + df["Site Num"]
    df["utc"] = pd.to_datetime(df["Date GMT"] + " " + df["Time GMT"])
    df["local"] = pd.to_datetime(df["Date Local"] + " " + df["Time Local"])
    df = df[(df.local >= START) & (df.local < pd.Timestamp(END) + pd.Timedelta(days=1))]
    df.to_parquet(INT / out_name)
    return df
