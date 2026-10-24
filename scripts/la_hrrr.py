"""LA: viento HRRR (3 km, análisis horario) interpolado a las estaciones de viento.

Descarga solo U/V a 10 m (subconjunto por rango de bytes con Herbie, bucket público de NOAA en AWS)
para las horas de la tarde local del periodo, toma el punto de malla más cercano a cada estación y
rota el viento de la malla Lambert a coordenadas terrestres (HRRR da viento relativo a la malla).
El HRRR válido a h+1 se empareja con la hora h de la estación (ASOS reporta ~hh:53).

Uso: .venv/bin/python scripts/la_hrrr.py
Salida: data/interim/la/hrrr_at_stations.parquet (u, v rotados y sin rotar)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from herbie import Herbie

from la_common import AFTERNOON, END, INT, LOCAL_OFFSET_H, START

SCRATCH = Path("/tmp/claude-1000/-home-mnlvzqz-code-contaminacion/038cbb41-11f4-49fa-bec5-98301c123620/scratchpad/hrrr")
LOV, LATIN = -97.5, 38.5  # proyección Lambert de HRRR
SEARCH = ":[UV]GRD:10 m above"


def valid_times():
    hs = pd.date_range(START, pd.Timestamp(END) + pd.Timedelta(hours=23), freq="h")
    hs = hs[hs.hour.isin(AFTERNOON)]                      # hora local
    return [h - pd.Timedelta(hours=LOCAL_OFFSET_H) + pd.Timedelta(hours=1) for h in hs]  # UTC, h+1


def fetch(t):
    try:
        H = Herbie(t.strftime("%Y-%m-%d %H:%M"), model="hrrr", product="sfc", fxx=0, save_dir=str(SCRATCH), verbose=False)
        return t, H.download(SEARCH)
    except Exception as e:  # noqa: BLE001
        return t, None


def main():
    st = pd.read_parquet(INT / "wind_stations.parquet").groupby("sid")[["lat", "lon"]].first()
    times = valid_times()
    with ThreadPoolExecutor(6) as ex:
        files = list(ex.map(fetch, times))
    idx, rows = None, []
    for t, f in files:
        if f is None:
            continue
        ds = xr.open_dataset(f, engine="cfgrib", backend_kwargs={"indexpath": ""})
        if idx is None:
            lat, lon = ds.latitude.values, ((ds.longitude.values + 180) % 360) - 180
            idx = {}
            for s, r in st.iterrows():
                d = (lat - r.lat) ** 2 + ((lon - r.lon) * np.cos(np.deg2rad(r.lat))) ** 2
                idx[s] = np.unravel_index(np.argmin(d), d.shape)
            ang = {s: np.deg2rad(np.sin(np.deg2rad(LATIN)) * (lon[ij] - LOV)) for s, ij in idx.items()}
        u, v = ds.u10.values, ds.v10.values
        for s, ij in idx.items():
            ug, vg, a = u[ij], v[ij], ang[s]
            rows.append(dict(sid=s, h=t - pd.Timedelta(hours=1), u_grid=ug, v_grid=vg,
                             u=np.cos(a) * ug + np.sin(a) * vg, v=-np.sin(a) * ug + np.cos(a) * vg))
        ds.close()
        Path(f).unlink(missing_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(INT / "hrrr_at_stations.parquet")
    ok = sum(f is not None for _, f in files)
    print(f"Horas HRRR: {ok} de {len(times)}; filas: {len(df):,}")


if __name__ == "__main__":
    main()
