import geopandas as gpd
import numpy as np
from shapely.geometry import box

from nox_ml.data.zones import assign_zones, read_zones

SQUARES = gpd.GeoDataFrame(
    {"grupo": ["west", "east"]}, geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs="EPSG:32614"
)


def test_points_inside_a_polygon_get_its_index():
    zone = assign_zones(np.array([2.0, 15.0, 9.0]), np.array([5.0, 5.0, 1.0]), SQUARES)

    assert zone.tolist() == [0, 1, 0]


def test_points_outside_every_polygon_go_to_the_nearest_zone():
    zone = assign_zones(np.array([-5.0, 30.0, 12.0]), np.array([5.0, 5.0, 40.0]), SQUARES)

    assert zone.tolist() == [0, 1, 1]


def test_a_point_on_the_border_gets_a_single_zone():
    zone = assign_zones(np.array([10.0]), np.array([5.0]), SQUARES)

    assert zone.shape == (1,) and zone[0] in (0, 1)


def test_zones_are_read_from_the_layer_of_the_scheme_in_row_order(tmp_path):
    path = tmp_path / "zonas.gpkg"
    SQUARES.to_file(path, layer="admin_grupos")
    SQUARES.iloc[::-1].to_file(path, layer="other")

    assert read_zones(path)["grupo"].tolist() == ["west", "east"]
    assert read_zones(path, "other")["grupo"].tolist() == ["east", "west"]
