"""Capa límite 2023-11 a 2024-06: ERA5 (Open-Meteo) donde existe y MERRA-2 corregido en el hueco de ene–jun 2024.

1. Descarga PBLH de MERRA-2 (M2T1NXFLX, horario, promedio de hora centrado en :30) por OPeNDAP en la nube
   de NASA, solo 3 × 3 celdas alrededor de la CDMX (~35 KB por día). Requiere ~/.netrc de Earthdata.
2. Pasa MERRA-2 a valores "en punto" (promedio de :30 anterior y :30 siguiente), igual convención que ERA5.
3. Compara con ERA5 en la celda de Open-Meteo (19.5 N, 99.25 O) donde ambos existen y ajusta una
   corrección multiplicativa por hora local (mediana del cociente ERA5/MERRA-2) con ene–jun 2023, los
   mismos meses del hueco; se valida ajustando con ene–mar 2023 y evaluando en abr–jun 2023.
4. Escribe data/interim/pbl_2023_2024.parquet (índice UTC horario; pbl_m, fuente).

Uso: .venv/bin/python scripts/pbl_fill.py
"""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/merra2"
OUT = ROOT / "data/interim/pbl_2023_2024.parquet"
COLL = "C1276812838-GES_DISC"
# índices de la malla MERRA-2 (lat −90:0.5:90, lon −180:0.625:179.375): lat 19.0–20.0, lon −100.0 a −98.75
LAT_I, LON_I = "218:1:220", "128:1:130"
CELL = (1, 1)  # 19.5 N, 99.375 O: la más cercana a la celda ERA5 de Open-Meteo (19.5 N, 99.25 O)
DAYS = pd.date_range("2023-01-01", "2024-06-30", freq="D")  # ene–jun 2023: misma estación que el hueco, para ajustar
AFTERNOON_LOCAL = range(12, 18)


def url(day):
    name = f"MERRA2_400.tavg1_2d_flx_Nx.{day:%Y%m%d}.nc4"
    ce = f"/PBLH%5B0:1:23%5D%5B{LAT_I}%5D%5B{LON_I}%5D;/lat%5B{LAT_I}%5D;/lon%5B{LON_I}%5D;/time"
    return (f"https://opendap.earthdata.nasa.gov/collections/{COLL}/granules/M2T1NXFLX.5.12.4%3A{name}"
            f".dap.nc4?dap4.ce={ce}"), RAW / name.replace(".nc4", "_cdmx.nc4")


def fetch(day):
    u, dst = url(day)
    if dst.exists() and dst.stat().st_size > 1000:
        return dst, "cache"
    cookies = str(Path.home() / ".urs_cookies")
    r = subprocess.run(["curl", "-sfL", "-n", "-c", cookies, "-b", cookies, "--retry", "3", "-m", "300",
                        "-o", str(dst), u], capture_output=True)
    return dst, "ok" if r.returncode == 0 else f"curl {r.returncode}"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(fetch, DAYS))
    bad = [(d, s) for d, (_, s) in zip(DAYS, res) if s not in ("ok", "cache")]
    if bad:
        print("Fallaron:", bad[:5], len(bad))
    frames = []
    for dst, s in res:  # lectura en serie: netCDF4/HDF5 no es thread-safe
        if s not in ("ok", "cache"):
            continue
        with netCDF4.Dataset(dst) as d:
            t0 = pd.Timestamp(d["time"].units.split("since ")[1])
            t = t0 + pd.to_timedelta(d["time"][:], unit="min")
            frames.append(pd.Series(d["PBLH"][:, CELL[0], CELL[1]].filled(np.nan), index=t))
    m2 = pd.concat(frames).sort_index()  # valores en hh:30 (promedio de la hora)
    m2_on = ((m2 + m2.shift(1)) / 2)  # a hh:00 desde los :30 vecinos
    m2_on.index = m2_on.index.floor("h") + pd.Timedelta(hours=1)
    m2_on = m2_on[~m2_on.index.duplicated()]

    e = json.loads((ROOT / "data/raw/era5_openmeteo/pbl_wind_center_2023-2024_full.json").read_text())["hourly"]
    era = pd.Series(e["boundary_layer_height"], index=pd.to_datetime(e["time"]), dtype=float)
    era = era["2023-01-01":"2024-06-30 23:00"]

    both = pd.concat({"era5": era, "merra2": m2_on}, axis=1).dropna()
    both["h_local"] = (both.index - pd.Timedelta(hours=6)).hour
    aft = both.loc["2023-01":"2023-06"][both.loc["2023-01":"2023-06"].h_local.isin(AFTERNOON_LOCAL)]
    stats = aft.groupby("h_local").apply(lambda g: pd.Series({
        "n": len(g), "era5_med": g.era5.median(), "merra2_med": g.merra2.median(),
        "sesgo_m": (g.merra2 - g.era5).median(), "r": g.era5.corr(g.merra2),
        "factor": (g.era5 / g.merra2).median()}))
    fac = lambda d: d.groupby("h_local").apply(lambda g: (g.era5 / g.merra2.clip(lower=50)).median())
    spring = both.loc["2023-01":"2023-06"]
    allh = fac(spring)
    print("Factor por hora local (ene–jun 2023):", allh.round(2).to_dict())
    print("Factor por hora local (nov–dic 2023):", fac(both.loc["2023-11":"2023-12"]).round(2).to_dict())
    print(stats.round(2).to_string())
    print(f"Tarde total: r = {aft.era5.corr(aft.merra2):.2f}, sesgo mediano MERRA-2 − ERA5 = "
          f"{(aft.merra2 - aft.era5).median():.0f} m, factor mediano ERA5/MERRA-2 = {(aft.era5 / aft.merra2).median():.2f}")

    # corrección: factor por hora local (todas las horas), aplicado solo en el hueco
    corr = m2_on * pd.Series((m2_on.index - pd.Timedelta(hours=6)).hour, index=m2_on.index).map(allh).values
    # validación fuera de muestra: factor de ene–mar 2023 evaluado en abr–jun 2023 (tarde)
    tr, te = both.loc["2023-01":"2023-03"], both.loc["2023-04":"2023-06"]
    te_c = te.merra2 * te.h_local.map(fac(tr))
    a = te.h_local.isin(AFTERNOON_LOCAL)
    print(f"Validación abr–jun 2023 (factor de ene–mar), tarde: error abs. mediano sin corregir "
          f"{(te.merra2 - te.era5)[a].abs().median():.0f} m ({((te.merra2 - te.era5)[a].abs() / te.era5[a]).median():.0%}), "
          f"corregido {(te_c - te.era5)[a].abs().median():.0f} m ({((te_c - te.era5)[a].abs() / te.era5[a]).median():.0%}); "
          f"r = {te.era5[a].corr(te.merra2[a]):.2f}")

    idx = pd.date_range("2023-11-01", "2024-06-30 23:00", freq="h")
    out = pd.DataFrame(index=idx)
    out["pbl_m"] = era.reindex(idx)
    out["fuente"] = np.where(out.pbl_m.notna(), "ERA5", "MERRA-2 corregido")
    gap = out.pbl_m.isna()
    out.loc[gap, "pbl_m"] = corr.reindex(idx)[gap]
    out.loc[out.pbl_m.isna(), "fuente"] = "sin dato"
    out.index.name = "utc"
    out.to_parquet(OUT)
    print(out.fuente.value_counts().to_string())
    stats.to_csv(ROOT / "data/interim/pbl_merra2_vs_era5.csv")


if __name__ == "__main__":
    main()
