"""LA: análisis HRRR de las horas previas a la tarde (05–11 h local civil) para las trayectorias de los puffs.

`la_hrrr_field.py` bajó solo las horas que cubren la tarde (12–18 h). Los puffs de `la_puff.py` viajan con el viento
de las 6 horas anteriores, así que hacen falta también los análisis de 05 a 11 h. Mismo recorte, rotación y
variables (reutiliza `la_hrrr_field.fetch`).

Uso: .venv/bin/python scripts/la_hrrr_morning.py
Salida: data/raw/la/hrrr_field/hrrr_field_manana_2023-11-01_2023-12-31.nc (+ manifest_manana.csv)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import xarray as xr

import la_hrrr_field as hf
from la_common import END, START


def morning_hours_utc():
    loc = pd.date_range(START, pd.Timestamp(END) + pd.Timedelta(hours=23), freq="h").tz_localize(
        hf.TZ, nonexistent="shift_forward", ambiguous="NaT")
    loc = loc[loc.notna() & loc.hour.isin(range(5, 12))]
    return loc.tz_convert("UTC").tz_localize(None)


def main():
    hf.SCRATCH.mkdir(parents=True, exist_ok=True)
    have = set(pd.DatetimeIndex(xr.open_dataset(hf.OUT / f"hrrr_field_{START}_{END}.nc").time.values))
    out_nc = hf.OUT / f"hrrr_field_manana_{START}_{END}.nc"
    prev = xr.load_dataset(out_nc) if out_nc.exists() else None  # reintento: conservar lo ya bajado
    if prev is not None:
        have |= set(pd.DatetimeIndex(prev.time.values))
    times = [t for t in morning_hours_utc() if t not in have]
    if not times:
        print("nada que bajar")
        return
    print(f"{len(times)} análisis HRRR de la mañana a bajar", flush=True)
    cache = {}
    res = [hf.fetch(times[0], cache)]
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(hf.fetch, t, cache) for t in times[1:]]
        for i, f in enumerate(as_completed(futs), 2):
            res.append(f.result())
            if i % 50 == 0:
                print(f"[{i}/{len(times)}] ok={sum(r[4] == 'ok' for r in res)}", flush=True)
    res.sort(key=lambda r: r[0])
    ok = [r for r in res if r[4] == "ok"]
    status = pd.DataFrame([(r[0], r[4]) for r in res], columns=["valid_utc", "status"])
    if prev is not None:
        status = pd.concat([pd.DataFrame({"valid_utc": pd.DatetimeIndex(prev.time.values), "status": "ok"}), status])
        cache.setdefault("lat", prev.latitude.values)
        cache.setdefault("lon", prev.longitude.values)
        ok = [(t, prev.u10.values[i], prev.v10.values[i], prev.hpbl.values[i], "ok")
              for i, t in enumerate(pd.DatetimeIndex(prev.time.values))] + ok
        ok.sort(key=lambda r: r[0])
    status.sort_values("valid_utc").to_csv(hf.OUT / "manifest_manana.csv", index=False)
    ds = xr.Dataset({"u10": (("time", "y", "x"), np.stack([r[1] for r in ok])),
                     "v10": (("time", "y", "x"), np.stack([r[2] for r in ok])),
                     "hpbl": (("time", "y", "x"), np.stack([r[3] for r in ok])),
                     "latitude": (("y", "x"), cache["lat"]), "longitude": (("y", "x"), cache["lon"])},
                    coords={"time": [r[0] for r in ok]},
                    attrs={"source": "NOAA HRRR sfc análisis (fxx=0), s3://noaa-hrrr-bdp-pds vía Herbie",
                           "note": "horas 05–11 h local civil; u10/v10 rotados a norte verdadero (m/s); hpbl en m; tiempo = validez UTC"})
    ds.to_netcdf(out_nc, encoding={k: {"zlib": True} for k in ("u10", "v10", "hpbl")})
    print(f"Análisis OK en total: {len(ok)}; fallidos en esta corrida: {sum(r[4] != 'ok' for r in res)}", flush=True)
    for r in res:
        if r[4] != "ok":
            print("  falló", r[0], r[4])


if __name__ == "__main__":
    main()
