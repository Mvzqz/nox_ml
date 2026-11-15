"""East share of the road NOx from independent sources, on the 3x3 regions of `nox_ml.data.roads`.

East = regions 2, 5, 8 (the east column of the domain). Sources:

- INECC MOVES-Mexico 2016, on-road NOx by municipality (`data/raw/inventario_2020/moves2016.pdf`, text
  from `pdftotext -layout moves2016.pdf moves2016.txt`). The CDMX is one row (no borough split): its total
  is spread over the regions with a proxy (census locality population, DENUE units or area), and each
  Edomex municipality is split with the same proxy.
- EDGAR v8.1 road transport (TRO) and totals, 0.1 degree cells split by area.
- DENUE units (all, commerce SCIAN 43-46, transport SCIAN 48-49, road freight and bus 484-485).
- Census 2020 population by locality (ITER), geocoded localities only.

Usage: inventory_compare.py [moves_text_file]. Writes CSVs to `out/`.
"""

import io
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from nox_ml.data import roads
from nox_ml.data.domain import BBOX

RAW = Path("data/raw")
OUT = Path(__file__).parent / "out"
EAST = (2, 5, 8)
N = roads.N_SPLIT


def norm(s: str) -> str:
    """Lowercase, no accents, single spaces."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def region_of(x, y) -> np.ndarray:
    """Region (0-8) of UTM points; -1 outside the domain."""
    x0, y0, x1, y1 = roads.domain_bounds_utm()
    x, y = np.asarray(x, float), np.asarray(y, float)
    inside = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
    nx, ny = int((x1 - x0) // roads.CELL_M) + 1, int((y1 - y0) // roads.CELL_M) + 1
    ix = np.clip(((x - x0) // roads.CELL_M).astype(int), 0, nx - 1)
    iy = np.clip(((y - y0) // roads.CELL_M).astype(int), 0, ny - 1)
    return np.where(inside, ix * N // nx + N * (iy * N // ny), -1)


def lonlat_to_utm(lon, lat):
    pts = gpd.GeoSeries.from_xy(lon, lat, crs=4326).to_crs(roads.UTM)
    return pts.x.to_numpy(), pts.y.to_numpy()


def region_polygons() -> list[shapely.Polygon]:
    """The 9 regions as UTM rectangles (the split is on 1 km cells, so edges are at cell boundaries)."""
    x0, y0, x1, y1 = roads.domain_bounds_utm()
    nx, ny = int((x1 - x0) // roads.CELL_M) + 1, int((y1 - y0) // roads.CELL_M) + 1
    xs = [x0 + roads.CELL_M * (-(-k * nx // N)) for k in range(N + 1)]  # ceil(k nx / N) cells
    ys = [y0 + roads.CELL_M * (-(-k * ny // N)) for k in range(N + 1)]
    return [shapely.box(xs[r % N], ys[r // N], xs[r % N + 1], ys[r // N + 1]) for r in range(N * N)]


def east_share(by_region: pd.Series) -> float:
    by_region = by_region.reindex(range(N * N), fill_value=0.0)
    return float(by_region[list(EAST)].sum() / by_region.sum())


def moves_nox(text: str) -> dict[str, float]:
    """On-road NOx (t/yr, 2016) by normalised municipality name for Edomex, plus the CDMX total."""
    lines = text.splitlines()
    row = re.compile(r"^(México|Ciudad de)\s+(.+?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s")
    out: dict[str, float] = {}
    for i, line in enumerate(lines):
        m = row.match(line)
        if not m:
            continue
        name = m.group(2).strip()
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt.strip() and not re.search(r"\d", nxt) and not nxt.startswith(("México", "Ciudad", "Chiapas")):
            name += " " + nxt.strip()  # wrapped name
        key = ("cdmx" if m.group(1) == "Ciudad de" else "edomex") + "|" + norm(name)
        out.setdefault(key, float(m.group(6).replace(",", "")))
    return out


def municipalities() -> gpd.GeoDataFrame:
    """INEGI municipal polygons of CDMX and Edomex in UTM, with the municipality key."""
    frames = [gpd.read_file(RAW / "inegi" / f"{e}_2022.json") for e in ("cdmx", "edomex")]
    gdf = pd.concat(frames, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=4326).to_crs(roads.UTM)
    gdf["key"] = gdf.CVE_ENT + gdf.CVE_MUN
    return gdf


def denue_counts() -> pd.DataFrame:
    """DENUE units by municipality key, region and class (all, commerce, transport, road)."""
    cache = OUT / "denue_counts.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype={"key": str})
    parts = []
    for name in ("denue_09_csv", "denue_15_1_csv", "denue_15_2_csv"):
        with zipfile.ZipFile(RAW / "denue" / f"{name}.zip") as z:
            member = next(n for n in z.namelist() if n.endswith(".csv") and "conjunto_de_datos" in n)
            with z.open(member) as f:
                for ch in pd.read_csv(
                    io.TextIOWrapper(f, encoding="latin-1"),
                    usecols=["codigo_act", "cve_ent", "cve_mun", "latitud", "longitud"],
                    dtype=str,
                    chunksize=500_000,
                ):
                    parts.append(ch)
    d = pd.concat(parts, ignore_index=True)
    d["lat"], d["lon"] = pd.to_numeric(d.latitud, errors="coerce"), pd.to_numeric(d.longitud, errors="coerce")
    d = d.dropna(subset=["lat", "lon"])
    d = d[(d.lat.between(14, 33)) & (d.lon.between(-120, -85))]
    d["key"] = d.cve_ent.str.zfill(2) + d.cve_mun.str.zfill(3)
    x, y = lonlat_to_utm(d.lon.to_numpy(), d.lat.to_numpy())
    d["region"] = region_of(x, y)
    s2, s3 = d.codigo_act.str[:2], d.codigo_act.str[:3]
    d["all"] = 1
    d["commerce"] = s2.isin(["43", "46"]).astype(int)
    d["transport"] = s2.isin(["48", "49"]).astype(int)
    d["road"] = s3.isin(["484", "485"]).astype(int)
    res = d.groupby(["key", "region"])[["all", "commerce", "transport", "road"]].sum().reset_index()
    OUT.mkdir(exist_ok=True)
    res.to_csv(cache, index=False)
    return res


def census_population() -> pd.DataFrame:
    """Population by municipality key and region, geocoded localities only."""
    rows = []
    for e in ("09", "15"):
        with zipfile.ZipFile(RAW / "censo2020" / f"iter_{e}.zip") as z:
            member = next(n for n in z.namelist() if "conjunto_de_datos_iter" in n)
            df = pd.read_csv(
                z.open(member), usecols=["ENTIDAD", "MUN", "LOC", "LONGITUD", "LATITUD", "POBTOT"], dtype=str
            )
        rows.append(df)
    d = pd.concat(rows, ignore_index=True)
    d = d[d.LONGITUD.notna() & d.LATITUD.notna()].copy()

    def dms(s: pd.Series) -> pd.Series:
        p = s.str.extract(r"(\d+)°(\d+)'([\d.]+)\"\s*([NSWE])")
        v = p[0].astype(float) + p[1].astype(float) / 60 + p[2].astype(float) / 3600
        return v * p[3].isin(["S", "W"]).map({True: -1, False: 1})

    d["lon"], d["lat"] = dms(d.LONGITUD), dms(d.LATITUD)
    d["pop"] = pd.to_numeric(d.POBTOT, errors="coerce").fillna(0)
    d = d.dropna(subset=["lon", "lat"])
    d["key"] = d.ENTIDAD.str.zfill(2) + d.MUN.str.zfill(3)
    x, y = lonlat_to_utm(d.lon.to_numpy(), d.lat.to_numpy())
    d["region"] = region_of(x, y)
    return d.groupby(["key", "region"])["pop"].sum().reset_index()


def area_fractions(muni: gpd.GeoDataFrame) -> pd.DataFrame:
    """Share of each municipality's area in each region (and outside the domain: region -1)."""
    polys = region_polygons()
    rows = []
    for key, geom in zip(muni.key, muni.geometry, strict=True):
        total = geom.area
        for r, p in enumerate(polys):
            a = geom.intersection(p).area
            if a > 0:
                rows.append((key, r, a))
        rows.append((key, -1, max(total - sum(a for k, _, a in rows if k == key), 0.0)))
    return pd.DataFrame(rows, columns=["key", "region", "area"])


def spread(weights: pd.DataFrame, col: str, totals: dict[str, float]) -> pd.Series:
    """Distribute municipal totals over regions with the municipal weights `col`; drops the outside part."""
    out = pd.Series(0.0, index=range(N * N))
    for key, total in totals.items():
        w = weights[weights.key == key].set_index("region")[col]
        if w.sum() == 0:
            continue
        for r, v in (w / w.sum() * total).items():
            if r >= 0:
                out[r] += v
    return out


def edgar_share(path: Path, var: str) -> tuple[float, float]:
    """East share of EDGAR `var` (cells split by area over the regions) and the domain total (t/yr)."""
    ds = xr.open_dataset(path)
    polys = region_polygons()
    by_region = pd.Series(0.0, index=range(N * N))
    for lat in ds.lat.values:
        for lon in ds.lon.values:
            val = float(ds[var].sel(lat=lat, lon=lon))
            cell = gpd.GeoSeries([shapely.box(lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05)], crs=4326)
            cell = cell.to_crs(roads.UTM).iloc[0]
            for r, p in enumerate(polys):
                by_region[r] += val * cell.intersection(p).area / cell.area
    return east_share(by_region), float(by_region.sum())


def main() -> None:
    OUT.mkdir(exist_ok=True)
    text_path = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW / "inventario_2020" / "moves2016.txt"
    text = text_path.read_text()
    nox = moves_nox(text)
    muni = municipalities()
    denue, pop, area = denue_counts(), census_population(), area_fractions(muni)
    print(f"DENUE units in domain: {int(denue[denue.region >= 0]['all'].sum())}")

    # MOVES: Edomex municipalities matched by name; CDMX total spread over the CDMX municipalities
    ed = muni[muni.CVE_ENT == "15"]
    totals, missing = {}, []
    for key, name in zip(ed.key, ed.NOMGEO, strict=True):
        v = nox.get("edomex|" + norm(name))
        if v is None:
            in_dom = denue[(denue.key == key) & (denue.region >= 0)]["all"].sum()
            if in_dom > 50:
                missing.append(name)
            continue
        totals[key] = v
    print("Edomex municipalities with units in the domain but not found in MOVES:", missing)
    cdmx_total = nox["cdmx|ciudad de mexico"]
    cdmx_keys = list(muni[muni.CVE_ENT == "09"].key)

    weights = {
        "population": pop.rename(columns={"pop": "w"}),
        "denue_all": denue.rename(columns={"all": "w"})[["key", "region", "w"]],
        "area": area.rename(columns={"area": "w"}),
    }
    rows = []
    for wname, w in weights.items():
        # CDMX: the total is spread over the whole CDMX (one proxy, all boroughs together)
        cd = w[w.key.isin(cdmx_keys)].assign(key="09")
        cd = cd.groupby(["key", "region"], as_index=False)["w"].sum()
        w2 = pd.concat([w[~w.key.isin(cdmx_keys)], cd])
        # fraction of the CDMX total that lies inside the domain: the share of the proxy inside it
        inside = cd[cd.region >= 0].w.sum() / cd.w.sum()
        by = spread(w2, "w", {**totals, "09": cdmx_total})
        # municipalities cut by the domain: part outside was dropped in `spread`
        rows.append((f"MOVES 2016 ({wname})", east_share(by), float(by.sum()), inside))
        ed_only = spread(w2, "w", totals)
        rows.append((f"MOVES 2016 Edomex only ({wname})", east_share(ed_only), float(ed_only.sum()), np.nan))

    for year in (2018, 2022):
        p = RAW / "edgar" / f"edgar_nox_cdmx_{year}.nc"
        for var in ("TRO", "TOTALS"):
            sh, tot = edgar_share(p, var)
            rows.append((f"EDGAR {year} {var}", sh, tot, np.nan))

    for cls in ("all", "commerce", "transport", "road"):
        d = denue[denue.region >= 0].groupby("region")[cls].sum()
        rows.append((f"DENUE {cls}", east_share(d), float(d.sum()), np.nan))
    p = pop[pop.region >= 0].groupby("region")["pop"].sum()
    rows.append(("Census 2020 population", east_share(p), float(p.sum()), np.nan))

    res = pd.DataFrame(rows, columns=["source", "east_share", "domain_total", "cdmx_inside"])
    res.to_csv(OUT / "inventory_compare.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.round(3).to_string(index=False))

    # per-region detail of the main MOVES variant
    w = weights["denue_all"]
    cd = w[w.key.isin(cdmx_keys)].assign(key="09").groupby(["key", "region"], as_index=False)["w"].sum()
    by = spread(pd.concat([w[~w.key.isin(cdmx_keys)], cd]), "w", {**totals, "09": cdmx_total})
    print((by / by.sum()).round(3).to_string())
    big = {k: nox.get(f"edomex|{norm(n)}") for k, n in zip(ed.key, ed.NOMGEO, strict=True)}
    print("BBOX", BBOX)
    for name in ("Ecatepec de Morelos", "Nezahualcóyotl", "Texcoco", "Chimalhuacán", "Chalco", "Ixtapaluca"):
        k = ed[ed.NOMGEO.eq(name)].key.iloc[0]
        d = denue[(denue.key == k)].set_index("region")["all"]
        print(name, big[k], (d / d.sum()).round(2).to_dict())


if __name__ == "__main__":
    main()
