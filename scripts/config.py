"""Parámetros compartidos del POC."""
from shapely.geometry import box

# Dominio (lon_min, lat_min, lon_max, lat_max). Ampliado 2026-10-20 ~10 km al N y al E para que la
# central Valle de México (Acolman) no quede en la frontera y entren CUT, CHO y MON.
BBOX = (-99.35, 19.25, -98.81, 19.77)
LON = (BBOX[0], BBOX[2])
LAT = (BBOX[1], BBOX[3])
DOMAIN = box(*BBOX)
UTM = "EPSG:32614"
