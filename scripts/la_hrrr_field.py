"""LA: campo HRRR (3 km, análisis horario) sobre el dominio: viento a 10 m (U/V) y capa límite (HPBL).

Descarga solo esos tres campos (subconjunto por rango de bytes según el índice .idx, con Herbie, del
bucket público noaa-hrrr-bdp-pds en AWS), recorta la malla al dominio con un margen de ~0.1° y rota el
viento de la malla Lambert a norte verdadero. Se guardan los análisis de las horas que cubren la tarde
local civil (12–17 h, America/Los_Angeles: PDT = UTC−7 hasta el 5 nov 2023, después PST = UTC−8): para
cada hora AQS [h, h+1) se bajan los análisis válidos a h y h+1, que luego se promedian.

Uso: .venv/bin/python scripts/la_hrrr_field.py
Salida: data/raw/la/hrrr_field/hrrr_field_2023-11-01_2023-12-31.nc (+ MANIFEST.md, manifest.csv)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from herbie import Herbie

from la_common import END, LAT, LON, RAW, START

OUT = RAW / "hrrr_field"
SCRATCH = Path("/tmp/claude-1000/-home-mnlvzqz-code-contaminacion/038cbb41-11f4-49fa-bec5-98301c123620/scratchpad/hrrr_field")
LOV, LATIN = -97.5, 38.5  # proyección Lambert de HRRR
SEARCH = ":(?:UGRD|VGRD):10 m above|:HPBL:"
PAD = 0.1
TZ = "America/Los_Angeles"


def afternoon_hours_utc():
    """Inicio (UTC, sin zona) de cada hora de tarde local civil 12–17 h."""
    loc = pd.date_range(START, pd.Timestamp(END) + pd.Timedelta(hours=23), freq="h").tz_localize(TZ, nonexistent="shift_forward", ambiguous="NaT")
    loc = loc[loc.notna() & loc.hour.isin(range(12, 18))]
    return loc.tz_convert("UTC").tz_localize(None)


def fetch(t, idx_cache):
    for attempt in range(3):
        try:
            H = Herbie(t.strftime("%Y-%m-%d %H:%M"), model="hrrr", product="sfc", fxx=0, save_dir=str(SCRATCH),
                       priority=["aws"], verbose=False)
            f = H.download(SEARCH, verbose=False)
            dss = [xr.open_dataset(f, engine="cfgrib", backend_kwargs={"indexpath": "", "filter_by_keys": k})
                   for k in ({"typeOfLevel": "heightAboveGround"}, {"shortName": "blh"})]
            if idx_cache.get("sl") is None:
                lat = dss[0].latitude.values
                lon = ((dss[0].longitude.values + 180) % 360) - 180
                m = (lat >= LAT[0] - PAD) & (lat <= LAT[1] + PAD) & (lon >= LON[0] - PAD) & (lon <= LON[1] + PAD)
                r, c = np.where(m)
                idx_cache["sl"] = (slice(r.min(), r.max() + 1), slice(c.min(), c.max() + 1))
                idx_cache["lat"], idx_cache["lon"] = lat[idx_cache["sl"]], lon[idx_cache["sl"]]
            sl = idx_cache["sl"]
            ug, vg = dss[0].u10.values[sl], dss[0].v10.values[sl]
            blh = dss[1].blh.values[sl]
            for d in dss:
                d.close()
            Path(f).unlink(missing_ok=True)
            a = np.deg2rad(np.sin(np.deg2rad(LATIN)) * (idx_cache["lon"] - LOV))
            u = np.cos(a) * ug + np.sin(a) * vg
            v = -np.sin(a) * ug + np.cos(a) * vg
            return t, u.astype("float32"), v.astype("float32"), blh.astype("float32"), "ok"
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:120]
    return t, None, None, None, err


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    hs = afternoon_hours_utc()
    times = sorted(set(hs) | set(hs + pd.Timedelta(hours=1)))
    print(f"{len(hs)} horas de tarde; {len(times)} análisis HRRR a bajar", flush=True)
    cache = {}
    # la primera, sola, para fijar el recorte
    res = [fetch(times[0], cache)]
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(fetch, t, cache) for t in times[1:]]
        for i, f in enumerate(as_completed(futs), 2):
            res.append(f.result())
            if i % 50 == 0:
                print(f"[{i}/{len(times)}] ok={sum(r[4] == 'ok' for r in res)}", flush=True)
    res.sort(key=lambda r: r[0])
    pd.DataFrame([(r[0], r[4]) for r in res], columns=["valid_utc", "status"]).to_csv(OUT / "manifest.csv", index=False)
    ok = [r for r in res if r[4] == "ok"]
    ds = xr.Dataset({"u10": (("time", "y", "x"), np.stack([r[1] for r in ok])),
                     "v10": (("time", "y", "x"), np.stack([r[2] for r in ok])),
                     "hpbl": (("time", "y", "x"), np.stack([r[3] for r in ok])),
                     "latitude": (("y", "x"), cache["lat"]), "longitude": (("y", "x"), cache["lon"])},
                    coords={"time": [r[0] for r in ok]},
                    attrs={"source": "NOAA HRRR sfc análisis (fxx=0), s3://noaa-hrrr-bdp-pds vía Herbie",
                           "note": "u10/v10 rotados a norte verdadero (m/s); hpbl en m; tiempo = validez UTC"})
    ds.to_netcdf(OUT / f"hrrr_field_{START}_{END}.nc", encoding={k: {"zlib": True} for k in ("u10", "v10", "hpbl")})
    print(f"Análisis OK: {len(ok)} de {len(times)}; malla {cache['lat'].shape}", flush=True)
    for r in res:
        if r[4] != "ok":
            print("  falló", r[0], r[4])


if __name__ == "__main__":
    main()
