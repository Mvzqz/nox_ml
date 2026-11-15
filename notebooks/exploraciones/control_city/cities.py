"""Control cities for the drift test: a box the size of the ZMVM domain around each city centre.

The ZMVM domain (`nox_ml.data.domain.BBOX`) is 0.54 x 0.52 degrees; every city gets a box of the same size so
the flux divergence sums the same area. Toluca is only a contrast: it is close enough to receive ZMVM air.
"""

HALF_LON, HALF_LAT = 0.27, 0.26

# name -> (lon, lat) of the city centre; zmvm is the centre of `domain.BBOX`
CENTRES = {
    "zmvm": (-99.08, 19.51),
    "monterrey": (-100.32, 25.69),
    "puebla": (-98.21, 19.05),
    "toluca": (-99.65, 19.29),
    "guadalajara": (-103.35, 20.67),
}

# ERA5 cell used for the wind of each city (Open-Meteo archive); the ZMVM one is the cell of the existing file
WIND_POINT = {name: (lon, lat) for name, (lon, lat) in CENTRES.items()}


def bbox(name: str) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) of the city box."""
    if name == "zmvm":
        return (-99.35, 19.25, -98.81, 19.77)
    lon, lat = CENTRES[name]
    return (lon - HALF_LON, lat - HALF_LAT, lon + HALF_LON, lat + HALF_LAT)
