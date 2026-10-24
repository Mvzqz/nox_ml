"""Road-emission proxy: class weights, scaling to the prior, 3x3 regions and the research cell table."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

from nox_ml.data import roads

ROADS_GPKG = Path(__file__).resolve().parents[3] / "data" / "interim" / "roads.gpkg"
BOUNDS = (0.0, 0.0, 5500.0, 5500.0)  # 6 x 6 cells of 1 km, so each of the 9 regions is 2 x 2 cells


def make_roads(*lines: tuple[str, list[tuple[float, float]]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"highway": [h for h, _ in lines], "geometry": [LineString(c) for _, c in lines]}, crs=roads.UTM
    )


def cells_of(*lines, total=1000.0) -> pd.DataFrame:
    return roads.road_emission_cells(make_roads(*lines), total=total, bounds=BOUNDS)


def test_default_total_is_80_percent_of_the_zmvm_vehicular_prior():
    assert pytest.approx(99_292) == roads.ROAD_PRIOR_TOTAL


def test_cells_add_up_to_the_scaled_prior():
    cells = cells_of(("motorway", [(0, 500), (5500, 500)]), ("tertiary", [(300, 5200), (1700, 5200)]))

    assert cells.weight.sum() == pytest.approx(1000)


def test_class_weights_split_the_total_in_proportion_to_length_times_weight():
    # 1 km of each class, one per cell in a row: 3 : 3 : 2 : 1.5 : 1
    classes = ["motorway", "trunk", "primary", "secondary", "tertiary"]
    lines = [(c, [(1000 * i + 100, 500), (1000 * i + 1100 - 200, 500)]) for i, c in enumerate(classes)]

    cells = cells_of(*lines, total=105)

    assert cells.weight.tolist() == pytest.approx([30, 30, 20, 15, 10])


def test_links_count_as_their_class_and_unlisted_classes_weigh_one():
    cells = cells_of(
        ("primary_link", [(100, 500), (900, 500)]),
        ("residential", [(1100, 500), (1900, 500)]),
        total=300,
    )

    assert cells.weight.tolist() == pytest.approx([200, 100])


def test_road_outside_the_domain_is_dropped():
    cells = cells_of(("motorway", [(500, 500), (900, 500)]), ("motorway", [(8000, 500), (8400, 500)]))

    assert len(cells) == 1
    assert cells.weight.iloc[0] == pytest.approx(1000)


def test_cell_is_identified_by_its_centre_in_utm_metres():
    cells = cells_of(("tertiary", [(2300, 3200), (2700, 3200)]))

    assert (cells.x.iloc[0], cells.y.iloc[0]) == (2500, 3500)


def test_every_cell_is_in_exactly_one_region_from_0_to_8():
    cells = cells_of(
        *[
            ("tertiary", [(x + 100, y + 500), (x + 900, y + 500)])
            for x in range(0, 5000, 1000)
            for y in range(0, 5000, 1000)
        ]
    )

    assert not cells.duplicated(["x", "y"]).any()
    assert cells.region.between(0, 8).all()
    assert cells.region.dtype.kind == "i"


def test_regions_are_the_3x3_split_of_the_domain():
    # one short road per cell of the 6 x 6 grid; region = column // 2 + 3 * (row // 2)
    lines = [
        ("tertiary", [(1000 * i + 400, 1000 * j + 400), (1000 * i + 600, 1000 * j + 400)])
        for i in range(6)
        for j in range(6)
    ]

    cells = cells_of(*lines)

    col, row = (cells.x // 1000).astype(int), (cells.y // 1000).astype(int)
    assert (cells.region == col // 2 + 3 * (row // 2)).all()
    assert cells.groupby("region").size().tolist() == [4] * 9
    assert cells.set_index(["x", "y"]).region[(500, 500)] == 0  # south-west
    assert cells.set_index(["x", "y"]).region[(5500, 5500)] == 8  # north-east


def test_reproduces_the_research_cell_table_on_a_small_fixture():
    # Expected values come from running the research `load_inputs` road code on the same lines.
    cells = cells_of(
        ("motorway", [(0, 500), (5500, 500)]),
        ("primary_link", [(2500, 0), (2500, 3000)]),
        ("tertiary", [(300, 5200), (1700, 5200)]),
        ("residential", [(4600, 4600), (4600, 5000)]),
        ("secondary", [(1000, 1000), (1300, 1400)]),
        ("trunk", [(5000, 5000), (9000, 5000)]),
    )

    expected = pd.DataFrame(
        {
            "x": [500, 500, 1500, 1500, 1500, 2500, 2500, 2500, 3500, 4500, 4500, 5500, 5500],
            "y": [500, 5500, 500, 1500, 5500, 500, 1500, 2500, 500, 500, 4500, 500, 5500],
            "weight": [
                112.99435,
                26.365348,
                112.99435,
                28.248588,
                26.365348,
                188.323917,
                75.329567,
                75.329567,
                112.99435,
                112.99435,
                15.065913,
                56.497175,
                56.497175,
            ],
            "region": [0, 6, 0, 0, 6, 1, 1, 4, 1, 2, 8, 2, 8],
        }
    )
    pd.testing.assert_frame_equal(
        cells.reset_index(drop=True), expected.astype({"x": float, "y": float}), check_exact=False, rtol=1e-6
    )


def test_domain_grid_is_57_by_58_cells_of_1_km():
    x0, y0, x1, y1 = roads.domain_bounds_utm()

    assert (int((x1 - x0) // 1000) + 1, int((y1 - y0) // 1000) + 1) == (57, 58)


@pytest.mark.slow
@pytest.mark.skipif(not ROADS_GPKG.exists(), reason="data not pulled")
def test_real_roads_give_the_research_cell_count_and_total():
    cells = roads.road_emission_cells(roads.read_roads(ROADS_GPKG))

    assert len(cells) == 2465
    assert cells.weight.sum() == pytest.approx(99_292)
    assert set(cells.region) == set(range(9))
