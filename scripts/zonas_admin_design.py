"""Zonas viales a partir de límites administrativos: grupos de alcaldías y municipios (reports/zonas_admin.md).

Criterios: cada grupo con al menos una estación de NOₓ o buena cobertura TEMPO, sin cruzar CDMX/Edomex, peso vial
a priori comparable. Las partes de municipios fuera del dominio se recortan; lo que no cae en ningún municipio
(bordes con Hidalgo) se asigna al grupo más cercano en feasibility_linear.assign_regions.

Escribe data/interim/zonas_admin.gpkg con una capa por versión (el nombre de la capa es el REGION_SCHEME):
  admin_grupos      13 grupos (versión 1)
  admin_grupos_v2   versión con grupos fusionados según el gemelo (si hace falta; --merge "A+B" ...)
  admin_mun         un municipio por zona (solo para la "verdad" heterogénea del gemelo; --municipios)

Uso: .venv/bin/python scripts/zonas_admin_design.py
     .venv/bin/python scripts/zonas_admin_design.py --layer admin_grupos_v2 --merge "CDMX Sur+CDMX Poniente"
"""
import argparse
from pathlib import Path

import geopandas as gpd

from config import DOMAIN, UTM

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
OUT = INT / "zonas_admin.gpkg"

# grupo → municipios (NOMGEO de INEGI). Orden = índice de región.
GROUPS = {
    "CDMX Centro": ["Cuauhtémoc", "Benito Juárez", "Venustiano Carranza"],
    "CDMX Poniente": ["Miguel Hidalgo", "Álvaro Obregón", "Cuajimalpa de Morelos"],
    "CDMX Norte": ["Azcapotzalco", "Gustavo A. Madero"],
    "CDMX Oriente": ["Iztapalapa", "Iztacalco", "Tláhuac"],
    "CDMX Sur": ["Coyoacán", "Tlalpan", "La Magdalena Contreras", "Xochimilco"],
    "Naucalpan–Huixquilucan": ["Naucalpan de Juárez", "Huixquilucan", "Jilotzingo", "Isidro Fabela", "Ocoyoacac"],
    "Tlalnepantla–Atizapán": ["Tlalnepantla de Baz", "Atizapán de Zaragoza", "Nicolás Romero"],
    "Ecatepec": ["Ecatepec de Morelos"],
    "Neza–Chimalhuacán": ["Nezahualcóyotl", "Chimalhuacán", "La Paz", "Chicoloapan"],
    "Chalco–Ixtapaluca": ["Chalco", "Valle de Chalco Solidaridad", "Ixtapaluca"],
    "Texcoco": ["Texcoco", "Atenco", "Chiconcuac", "Papalotla", "Tepetlaoxtoc", "Chiautla", "Tezoyuca"],
    "Cuautitlán–Tultitlán": ["Cuautitlán Izcalli", "Tultitlán", "Coacalco de Berriozábal", "Tultepec", "Cuautitlán",
                             "Tepotzotlán", "Teoloyucan", "Coyotepec", "Melchor Ocampo", "Huehuetoca"],
    "Tecámac–Acolman": ["Tecámac", "Acolman", "Teotihuacán", "San Martín de las Pirámides", "Nextlalpan", "Jaltenco",
                        "Tonanitla", "Zumpango", "Temascalapa", "Otumba", "Axapusco"],
}


def build(groups):
    dom = gpd.GeoSeries([DOMAIN], crs=4326).to_crs(UTM).iloc[0]
    mun = gpd.read_file(INT / "municipios.gpkg").to_crs(UTM)
    mun = mun[mun.intersects(dom)].copy()
    used = [m for ms in groups.values() for m in ms]
    missing = set(mun.NOMGEO) - set(used)
    unknown = set(used) - set(mun.NOMGEO)
    assert not unknown, f"municipios inexistentes: {unknown}"
    mun["geometry"] = mun.intersection(dom)
    rows = []
    for g, ms in groups.items():
        sub = mun[mun.NOMGEO.isin(ms)]
        rows.append({"grupo": g, "entidad": "/".join(sorted(set(sub.NOM_ENT))), "municipios": ", ".join(ms),
                     "geometry": sub.geometry.union_all()})
    z = gpd.GeoDataFrame(rows, crs=UTM)
    z["km2"] = z.area / 1e6
    return z, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="admin_grupos")
    ap.add_argument("--merge", nargs="*", default=[], help='fusiones "A+B" (nombre nuevo "A + B")')
    ap.add_argument("--municipios", action="store_true", help="un grupo por municipio (capa admin_mun, para el gemelo)")
    a = ap.parse_args()
    groups = dict(GROUPS)
    if a.municipios:
        groups, a.layer = {m: [m] for ms in GROUPS.values() for m in ms}, "admin_mun"
    for spec in a.merge:
        parts = spec.split("+")
        merged = [m for p in parts for m in groups.pop(p)]
        groups[" + ".join(parts)] = merged
    z, missing = build(groups)
    if missing:
        print("municipios del dominio sin grupo (irán al grupo más cercano):", missing)
    z.to_file(OUT, layer=a.layer, driver="GPKG")
    print(z.drop(columns="geometry").round(0).to_string())


if __name__ == "__main__":
    main()
