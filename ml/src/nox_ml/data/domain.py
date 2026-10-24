"""Study domain and conventions shared by the data loaders."""

# Domain (lon_min, lat_min, lon_max, lat_max): Mexico City metropolitan area plus ~10 km N and E,
# so the Valle de México power plant (Acolman) is not on the border.
BBOX = (-99.35, 19.25, -98.81, 19.77)
LON = (BBOX[0], BBOX[2])
LAT = (BBOX[1], BBOX[3])

# Urban core, used to compare TEMPO columns against their surroundings.
CORE_LAT, CORE_LON = (19.33, 19.53), (-99.20, -99.03)

DRY_MONTHS = (11, 12, 1, 2, 3, 4, 5)
AFTERNOON_HOURS = tuple(range(12, 18))  # 12:00-17:59 local, when TEMPO scans the domain
