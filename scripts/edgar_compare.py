"""Compara EDGAR v8.1 NOx con nuestro a priori vial y con la inversión por zona administrativa.

Entradas: data/raw/edgar/edgar_nox_{cdmx,la,bogota}_{2018,2022}.nc (scripts/edgar_extract.py),
data/interim/zonas_admin.gpkg, data/interim/municipios.gpkg, data/interim/inventario_2018_nox.csv.
Los α por zona y el vial a priori por zona vienen de reports/zonas_admin.md (puffs, configuración estándar).
Reparto de cada celda de 0.1° a las zonas por fracción de área: supone emisión uniforme dentro de la celda.
Salida: data/interim/edgar/edgar_compare.json (tablas para reports/edgar.md).
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from scipy.stats import pearsonr, spearmanr
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from config import DOMAIN, UTM  # noqa: E402

RAW, INT = ROOT / "data/raw/edgar", ROOT / "data/interim"
OUT = INT / "edgar"
OUT.mkdir(exist_ok=True)

# Sectores EDGAR agrupados como en el inventario de la ZMVM.
GRUPOS = {
    "transporte_carretero": ["TRO"],
    "energia": ["ENE"],
    "industria": ["IND", "CHE", "IRO", "NFE", "NMM", "PRO_FFF", "REF_TRF", "FOO_PAP", "MNM"],
    "residencial_comercial": ["RCO"],
    "aviacion": ["TNR_Aviation_LTO"],
    "otros": ["TNR_Other", "TNR_Ship", "AGS", "AWB", "SWD_INC"],
}

# reports/zonas_admin.md: vial a priori de día hábil por zona (t/año) y α hábil a posteriori (puffs, grupos).
ZONAS = ["CDMX Centro", "CDMX Poniente", "CDMX Norte", "CDMX Oriente", "CDMX Sur", "Naucalpan–Huixquilucan",
         "Tlalnepantla–Atizapán", "Ecatepec", "Neza–Chimalhuacán", "Chalco–Ixtapaluca", "Texcoco",
         "Cuautitlán–Tultitlán", "Tecámac–Acolman"]
PRIOR = [7593, 9170, 6425, 7605, 7514, 8196, 8695, 6571, 7523, 5016, 5698, 11479, 7806]
ALFA = {"nov–dic 2023": [0.76, 0.56, 1.60, 1.06, 0.49, 0.73, 1.08, 0.61, 0.50, 0.39, 0.68, 0.83, 0.64],
        "feb–may 2024": [0.42, 0.20, 0.68, 0.49, 0.18, 0.43, 0.67, 0.49, 0.35, 0.14, 0.44, 0.65, 0.61]}


def celdas(ds):
    """GeoDataFrame de celdas de 0.1° con una columna por grupo de sectores (t/año)."""
    lon, lat = np.meshgrid(ds.lon.values, ds.lat.values)
    d = {"lon": lon.ravel(), "lat": lat.ravel()}
    for g, secs in GRUPOS.items():
        d[g] = sum(ds[s].values.ravel() for s in secs if s in ds)
    d["total"] = ds["TOTALS"].values.ravel()
    geo = [box(x - .05, y - .05, x + .05, y + .05) for x, y in zip(d["lon"], d["lat"])]
    return gpd.GeoDataFrame(d, geometry=geo, crs=4326).to_crs(UTM)


def reparte(cel, zonas, col_zona):
    """Suma por zona la emisión de cada celda proporcional a la fracción de su área dentro de la zona."""
    cel = cel.assign(area_celda=cel.area)
    x = gpd.overlay(cel, zonas[[col_zona, "geometry"]], how="intersection")
    f = x.area / x.area_celda
    cols = list(GRUPOS) + ["total"]
    return x[cols].mul(f, axis=0).groupby(x[col_zona]).sum()


def cdmx(anio):
    ds = xr.open_dataset(RAW / f"edgar_nox_cdmx_{anio}.nc")
    cel = celdas(ds)
    dom = gpd.GeoDataFrame(geometry=[DOMAIN], crs=4326).to_crs(UTM).assign(z="dominio")
    zonas = gpd.read_file(INT / "zonas_admin.gpkg", layer="admin_grupos").to_crs(UTM)
    mun = gpd.read_file(INT / "municipios.gpkg").to_crs(UTM)
    mun["entidad"] = np.where(mun.CVE_ENT == "09", "CDMX", "Edomex")
    mun = gpd.overlay(mun, dom[["geometry"]], how="intersection")
    ent = mun.dissolve("entidad").reset_index()
    return {"dominio": reparte(cel, dom, "z"), "zona": reparte(cel, zonas, "grupo").reindex(ZONAS),
            "entidad": reparte(cel, ent, "entidad")}


def resumen_ciudad(ciudad, anio, bbox):
    ds = xr.open_dataset(RAW / f"edgar_nox_{ciudad}_{anio}.nc")
    sub = ds.sel(lon=slice(bbox[0], bbox[2]), lat=slice(bbox[1], bbox[3]))
    out = {g: float(sum(sub[s].sum() for s in secs if s in sub)) for g, secs in GRUPOS.items()}
    out["total"] = float(sub["TOTALS"].sum())
    return out


def main():
    res = {}
    for anio in ("2018", "2022"):
        r = cdmx(anio)
        dom = r["dominio"].iloc[0]
        res[f"cdmx_{anio}"] = {
            "dominio": dom.round(0).to_dict(),
            "fraccion_transporte": round(dom.transporte_carretero / dom.total, 3),
            "entidad": r["entidad"].round(0).to_dict(orient="index"),
            "cdmx_edomex_transporte": round(r["entidad"].loc["CDMX", "transporte_carretero"]
                                            / r["entidad"].loc["Edomex", "transporte_carretero"], 3),
            "cdmx_edomex_total": round(r["entidad"].loc["CDMX", "total"] / r["entidad"].loc["Edomex", "total"], 3),
            "zona": r["zona"].round(0).to_dict(orient="index"),
        }
    # Patrón espacial por zona (EDGAR 2022 frente al a priori y a la inversión)
    z = pd.DataFrame(res["cdmx_2022"]["zona"]).T.reindex(ZONAS)
    tro, tot = z.transporte_carretero.values, z.total.values
    prior = np.array(PRIOR, float)
    comp = {"a_priori_osm": {"spearman_tro": spearmanr(prior, tro)[0], "pearson_tro": pearsonr(prior, tro)[0],
                             "spearman_total": spearmanr(prior, tot)[0]}}
    tabla = pd.DataFrame({"zona": ZONAS, "a_priori": prior, "edgar_tro": tro, "edgar_total": tot})
    for per, a in ALFA.items():
        post = prior * np.array(a)
        comp[per] = {
            "spearman_tro": spearmanr(post, tro)[0], "pearson_tro": pearsonr(post, tro)[0],
            "spearman_total": spearmanr(post, tot)[0],
            # ¿La inversión movió las zonas en la dirección de EDGAR? α frente a EDGAR/a priori
            "spearman_alfa_vs_edgar_entre_prior": spearmanr(a, tro / prior)[0],
            "spearman_alfa_vs_edgar_total_entre_prior": spearmanr(a, tot / prior)[0],
        }
        tabla[f"post_{per}"] = post
    res["patron_por_zona"] = {k: {kk: round(float(vv), 3) for kk, vv in v.items()} for k, v in comp.items()}
    tabla["edgar_tro_%"] = 100 * tabla.edgar_tro / tabla.edgar_tro.sum()
    tabla["a_priori_%"] = 100 * tabla.a_priori / tabla.a_priori.sum()
    for per in ALFA:
        tabla[f"post_{per}_%"] = 100 * tabla[f"post_{per}"] / tabla[f"post_{per}"].sum()
    tabla["edgar_no_vial_%_zona"] = 100 * (1 - tabla.edgar_tro / tabla.edgar_total)
    res["tabla_zonas"] = tabla.round(1).to_dict(orient="records")
    # Inventario 2018
    inv = pd.read_csv(INT / "inventario_2018_nox.csv")
    zmvm = inv.groupby("tipo_fuente").nox_t_anio.sum()
    res["inventario_2018"] = {"moviles": round(zmvm["moviles"]), "total": round(zmvm.sum()),
                              "fraccion_moviles": round(zmvm["moviles"] / zmvm.sum(), 3)}
    # LA y Bogotá (solo dominio)
    res["la_2022"] = resumen_ciudad("la", "2022", (-118.55, 33.80, -117.95, 34.30))
    res["bogota_2022"] = resumen_ciudad("bogota", "2022", (-74.25, 4.45, -73.98, 4.85))
    json.dump(res, open(OUT / "edgar_compare.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("patron_por_zona", "inventario_2018", "la_2022", "bogota_2022")},
                     ensure_ascii=False, indent=1))
    for anio in ("2018", "2022"):
        r = res[f"cdmx_{anio}"]
        print(anio, r["dominio"], r["fraccion_transporte"], r["cdmx_edomex_transporte"], r["cdmx_edomex_total"])
    print(tabla.round(1).to_string())


if __name__ == "__main__":
    main()
