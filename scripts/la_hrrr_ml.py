"""LA: viento HRRR promediado en la capa de mezcla (superficie → altura de capa límite) para los puffs.

Hipótesis: el viento a 10 m no es el de transporte. Por la tarde la capa de mezcla mide ~0.5–1.5 km y el NOₓ viaja
con el viento medio de toda la capa. El producto `sfc` de HRRR trae viento a 10 m, 80 m y en 1000, 925 y 850 hPa,
la altura geopotencial de 1000 y 850 hPa, la temperatura de 1000 y 925 hPa, la orografía y la capa límite (HPBL);
con eso basta para el perfil de los primeros ~1.5 km sin bajar el producto de niveles de presión completo.

Por punto de malla:
  alturas sobre el terreno: 10 m, 80 m, z1000 = gh1000 − orog, z925 = z1000 + (Rd/g)·T̄·ln(1000/925)
  (hipsométrica con la media de T1000 y T925), z850 = gh850 − orog; se descartan niveles bajo el terreno;
  viento medio = promedio vertical (trapecios, interpolación lineal en z) de u y v entre 10 m y max(HPBL, 100 m).
Por encima del nivel más alto disponible se mantiene constante el último valor.

Mismos tiempos que `hrrr_field_*.nc` (tarde) y `hrrr_field_manana_*.nc` (05–11 h), mismo recorte y rotación a norte
verdadero (`la_hrrr_field.fetch`). Se guardan u_ml, v_ml (y u10, v10, hpbl para comparar).

Uso: .venv/bin/python scripts/la_hrrr_ml.py
Salida: data/raw/la/hrrr_field/hrrr_ml_2023-11-01_2023-12-31.nc (+ manifest_ml.csv)
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

import cfgrib
import numpy as np
import pandas as pd
import xarray as xr
from herbie import Herbie

import la_hrrr_field as hf
from la_common import END, START

SEARCH = (":(?:UGRD|VGRD):(?:10 m above|80 m above|1000 mb|925 mb|850 mb)|:HGT:(?:1000 mb|850 mb|surface)"
          "|:TMP:(?:1000 mb|925 mb)|:HPBL:")
SCRATCH = Path(str(hf.SCRATCH) + "_ml")
RD_G = 287.05 / 9.80665
OUT_NC = hf.OUT / f"hrrr_ml_{START}_{END}.nc"
GRIB_LOCK = threading.Lock()  # eccodes/cfgrib no es seguro entre hilos: se descarga en paralelo y se decodifica en serie


def ml_mean(z, u, H, nz=24):
    """Promedio vertical de u (niveles × puntos) entre 10 m y H (puntos), interpolando linealmente en z."""
    out = np.empty(u.shape[1])
    for p in range(u.shape[1]):
        zz, uu = z[:, p], u[:, p]
        ok = np.isfinite(zz) & (zz >= 10)
        zz, uu = zz[ok], uu[ok]
        o = np.argsort(zz)
        grid = np.linspace(10, max(H[p], 100.0), nz)
        out[p] = np.trapezoid(np.interp(grid, zz[o], uu[o]), grid) / (grid[-1] - grid[0])
    return out


def _decode(dss, sl, get):
    for d in dss:
        for k in d.data_vars:
            a = d[k]
            if "isobaricInhPa" in a.dims:
                for lev in a.isobaricInhPa.values:
                    get[(k, int(lev))] = a.sel(isobaricInhPa=lev).values[sl]
            elif "isobaricInhPa" in a.coords:
                get[(k, int(a.isobaricInhPa.values))] = a.values[sl]
            elif "heightAboveGround" in a.coords:
                get[(k, float(a.heightAboveGround.values))] = a.values[sl]
            else:
                get[(k, "sfc")] = a.values[sl]
        d.close()


def fetch(t, cache):
    err = ""
    for _ in range(3):
        try:
            H = Herbie(t.strftime("%Y-%m-%d %H:%M"), model="hrrr", product="sfc", fxx=0, save_dir=str(SCRATCH),
                       priority=["aws"], verbose=False)
            f = H.download(SEARCH, verbose=False)
            sl = cache["sl"]
            get = {}
            with GRIB_LOCK:
                dss = cfgrib.open_datasets(str(f), backend_kwargs={"indexpath": ""})
                _decode(dss, sl, get)
            Path(f).unlink(missing_ok=True)
            orog, hpbl = get[("orog", "sfc")], get[("blh", "sfc")]
            z1000 = get[("gh", 1000)] - orog
            z925 = z1000 + RD_G * (get[("t", 1000)] + get[("t", 925)]) / 2 * np.log(1000 / 925)
            z850 = get[("gh", 850)] - orog
            shp = orog.shape
            z = np.stack([np.full(shp, 10.0), np.full(shp, 80.0), z1000, z925, z850]).reshape(5, -1)
            ug = np.stack([get[("u10", 10.0)], get[("u", 80.0)], get[("u", 1000)], get[("u", 925)], get[("u", 850)]]).reshape(5, -1)
            vg = np.stack([get[("v10", 10.0)], get[("v", 80.0)], get[("v", 1000)], get[("v", 925)], get[("v", 850)]]).reshape(5, -1)
            Hm = hpbl.ravel()
            um, vm = ml_mean(z, ug, Hm).reshape(shp), ml_mean(z, vg, Hm).reshape(shp)
            # rotación de la malla Lambert a norte verdadero (como la_hrrr_field)
            a = np.deg2rad(np.sin(np.deg2rad(hf.LATIN)) * (cache["lon"] - hf.LOV))
            rot = lambda uu, vv: (np.cos(a) * uu + np.sin(a) * vv, -np.sin(a) * uu + np.cos(a) * vv)
            u_ml, v_ml = rot(um, vm)
            u10, v10 = rot(get[("u10", 10.0)], get[("v10", 10.0)])
            return t, [x.astype("float32") for x in (u_ml, v_ml, u10, v10, hpbl)], "ok"
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"[:160]
    return t, None, err


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ref = [xr.open_dataset(hf.OUT / f"hrrr_field_{START}_{END}.nc"), xr.open_dataset(hf.OUT / f"hrrr_field_manana_{START}_{END}.nc")]
    times = sorted(set(pd.DatetimeIndex(ref[0].time.values)) | set(pd.DatetimeIndex(ref[1].time.values)))
    lat, lon = ref[0].latitude.values, ref[0].longitude.values
    prev = xr.load_dataset(OUT_NC) if OUT_NC.exists() else None
    have = set(pd.DatetimeIndex(prev.time.values)) if prev is not None else set()
    todo = [t for t in times if t not in have]
    print(f"{len(times)} análisis; ya bajados {len(have)}; por bajar {len(todo)}", flush=True)
    # recorte: mismo que la_hrrr_field (busca la caja lat/lon en la malla completa con el primer archivo)
    cache = {}
    H = Herbie(todo[0].strftime("%Y-%m-%d %H:%M") if todo else times[0].strftime("%Y-%m-%d %H:%M"), model="hrrr",
               product="sfc", fxx=0, save_dir=str(SCRATCH), priority=["aws"], verbose=False)
    f = H.download(":HPBL:", verbose=False)
    d = xr.open_dataset(f, engine="cfgrib", backend_kwargs={"indexpath": ""})
    LAT = d.latitude.values
    LON = ((d.longitude.values + 180) % 360) - 180
    d.close()
    Path(f).unlink(missing_ok=True)
    m = np.isin(np.round(LAT, 4), np.round(lat, 4)) & np.isin(np.round(LON, 4), np.round(lon, 4))
    r, c = np.where(m)
    cache["sl"] = (slice(r.min(), r.max() + 1), slice(c.min(), c.max() + 1))
    cache["lon"] = LON[cache["sl"]]
    assert cache["lon"].shape == lon.shape and np.allclose(LAT[cache["sl"]], lat, atol=1e-3), "recorte distinto"
    res = []
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(fetch, t, cache) for t in todo]
        for i, fu in enumerate(as_completed(futs), 1):
            res.append(fu.result())
            if i % 50 == 0:
                print(f"[{i}/{len(todo)}] ok={sum(r[2] == 'ok' for r in res)}", flush=True)
    ok = [(t, arrs) for t, arrs, s in res if s == "ok"]
    if prev is not None:
        ok += [(t, [prev[k].values[i] for k in ("u_ml", "v_ml", "u10", "v10", "hpbl")])
               for i, t in enumerate(pd.DatetimeIndex(prev.time.values))]
    ok.sort(key=lambda r: r[0])
    status = pd.DataFrame([(t, s) for t, _, s in res] + [(t, "ok") for t in have], columns=["valid_utc", "status"])
    status.sort_values("valid_utc").to_csv(hf.OUT / "manifest_ml.csv", index=False)
    names = ("u_ml", "v_ml", "u10", "v10", "hpbl")
    ds = xr.Dataset({k: (("time", "y", "x"), np.stack([a[i] for _, a in ok])) for i, k in enumerate(names)}
                    | {"latitude": (("y", "x"), lat), "longitude": (("y", "x"), lon)},
                    coords={"time": [t for t, _ in ok]},
                    attrs={"source": "NOAA HRRR sfc análisis (fxx=0), s3://noaa-hrrr-bdp-pds vía Herbie",
                           "note": "u_ml/v_ml: viento medio entre 10 m y la capa límite (10 m, 80 m, 1000/925/850 hPa); "
                                   "rotados a norte verdadero (m/s); tiempo = validez UTC"})
    ds.to_netcdf(OUT_NC, encoding={k: {"zlib": True} for k in names})
    print(f"OK {len(ok)} de {len(times)}; fallidos en esta corrida {sum(s != 'ok' for *_, s in res)}", flush=True)
    for t, _, s in res:
        if s != "ok":
            print("  falló", t, s)


if __name__ == "__main__":
    main()
