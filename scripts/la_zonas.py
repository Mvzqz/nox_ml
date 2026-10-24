"""LA: zonas viales con límites administrativos (grupos de ciudades), con el criterio de cobertura de zonas_admin.

No encontramos una geometría pública de las Source Receptor Areas del South Coast AQMD (ver otras_ciudades.md), así
que se usan las subregiones de los consejos de gobierno (COG) del condado de Los Ángeles más el norte del condado de
Orange, armadas con los límites de ciudades del Censo 2023 (cb_2023_06_place_500k). La ciudad de Los Ángeles, que
cruza varias subregiones, se parte en Valle de San Fernando (lat ≥ 34.145), Puerto (lat < 33.93), Westside
(lon < −118.37) y Centro (resto). Las áreas no incorporadas (p. ej. Este de LA) y las ciudades que no están en la
lista van a la zona más cercana. Cada zona tiene al menos una estación de NOₓ de AQS.

Uso: .venv/bin/python scripts/la_zonas.py   (guarda data/interim/la/zonas_la.gpkg e imprime estaciones por zona)
"""
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from la_common import BBOX, INT, RAW, UTM

ZONAS = ["Westside", "Valle de San Fernando", "Centro de LA", "Valle de San Gabriel", "Gateway Cities",
         "South Bay y Puerto", "Norte de Orange"]
CIUDADES = {
    "Westside": ["Santa Monica", "Beverly Hills", "Culver City", "West Hollywood"],
    "Valle de San Fernando": ["San Fernando", "Burbank", "Glendale", "La Cañada Flintridge"],
    "Centro de LA": [],
    "Valle de San Gabriel": ["Pasadena", "South Pasadena", "San Marino", "Alhambra", "Monterey Park", "San Gabriel",
                             "Rosemead", "Temple City", "Arcadia", "Sierra Madre", "Monrovia", "Bradbury", "Duarte",
                             "Irwindale", "El Monte", "South El Monte", "Baldwin Park", "West Covina", "La Puente", "Industry"],
    "Gateway Cities": ["Pico Rivera", "Downey", "Whittier", "Norwalk", "Santa Fe Springs", "La Mirada", "Cerritos",
                       "Artesia", "Bellflower", "Lakewood", "Paramount", "Compton", "Lynwood", "South Gate",
                       "Huntington Park", "Bell", "Bell Gardens", "Cudahy", "Maywood", "Commerce", "Montebello",
                       "Vernon", "Hawaiian Gardens", "La Habra Heights"],
    "South Bay y Puerto": ["Long Beach", "Signal Hill", "Carson", "Torrance", "Gardena", "Hawthorne", "Inglewood",
                           "Lawndale", "El Segundo", "Manhattan Beach", "Hermosa Beach", "Redondo Beach", "Lomita",
                           "Palos Verdes Estates"],
    "Norte de Orange": ["La Habra", "Fullerton", "Anaheim", "Buena Park", "La Palma", "Cypress", "Stanton",
                        "Garden Grove", "Los Alamitos"],
}


def zones():
    dom = box(*BBOX)
    p = gpd.read_file(RAW / "limites/cb_2023_06_place_500k.zip")
    p = p[(p.LSAD == "25") & p.intersects(dom)].copy()
    p["geometry"] = p.intersection(dom)
    parts = []
    for z, names in CIUDADES.items():
        g = p[p.NAME.isin(names)]
        if len(g):
            parts.append((z, g.geometry.union_all()))
    la = p[p.NAME == "Los Angeles"].geometry.union_all()
    x0, y0, x1, y1 = BBOX
    valle = box(x0, 34.145, x1, y1)
    puerto = box(x0, y0, x1, 33.93)
    west = box(x0, y0, -118.37, y1).difference(valle).difference(puerto)
    parts += [("Valle de San Fernando", la.intersection(valle)), ("South Bay y Puerto", la.intersection(puerto)),
              ("Westside", la.intersection(west)), ("Centro de LA", la.difference(valle).difference(puerto).difference(west))]
    g = gpd.GeoDataFrame(parts, columns=["zona", "geometry"], crs=4326).dissolve("zona").reset_index()
    return g.to_crs(UTM)


def assign(cells, zg):
    """Zona (0…6, orden de ZONAS) de cada celda de 1 km; fuera de ciudades listadas: la zona más cercana."""
    pts = gpd.GeoSeries.from_xy(cells.x, cells.y, crs=UTM)
    zg = zg.set_index("zona").loc[ZONAS]
    d = np.stack([pts.distance(geom).values for geom in zg.geometry], 1)
    return d.argmin(1)


def main():
    zg = zones()
    zg.to_crs(4326).to_file(INT / "zonas_la.gpkg", layer="zonas_la", driver="GPKG")
    b = pd.read_parquet(INT / "aqs_nonox.parquet")
    b = b[b["Parameter Code"] == 42603].groupby("site")[["Latitude", "Longitude"]].first()
    st = gpd.GeoSeries.from_xy(b.Longitude, b.Latitude, crs=4326).to_crs(UTM)
    zi = zg.set_index("zona").loc[ZONAS]
    for s, pt in zip(b.index, st):
        print(s, ZONAS[int(np.argmin([pt.distance(g) for g in zi.geometry]))])
    print((zg.set_index("zona").area / 1e6).round(0).to_dict())


if __name__ == "__main__":
    main()
