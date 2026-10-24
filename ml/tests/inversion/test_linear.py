from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

from nox_ml.inversion.jacobian import Receptors, jacobian_hour_plume
from nox_ml.inversion.linear import (
    BACKGROUND_PIXEL,
    BACKGROUND_STATION,
    N_DAY_TYPES,
    SIGMA_PIXEL,
    SIGMA_STATION,
    SIGMA_THETA,
    U_MIN,
    HourData,
    baseline_point_sources,
    invert,
    marginalized_block,
    road_sources,
)

REFERENCE = Path(__file__).parents[1] / "fixtures" / "baseline_reference.npz"
RATIO = 0.8


def ts(text: str) -> pd.Timestamp:
    return cast(pd.Timestamp, pd.Timestamp(text))


def receptors(x, y) -> Receptors:
    return Receptors(np.atleast_1d(np.asarray(x, float)), np.atleast_1d(np.asarray(y, float)))


def points_table(x, y, prior, sd) -> pd.DataFrame:
    return pd.DataFrame({"name": [f"P{i}" for i in range(len(x))], "x": x, "y": y, "prior": prior, "sd": sd})


# --- reproduces the research output ---------------------------------------------------------------------

reference = np.load(REFERENCE)
ref_zones = pd.DataFrame(
    {
        "x": reference["cell_x"],
        "y": reference["cell_y"],
        "weight": reference["cell_prior"],
        "region": reference["cell_region"],
    }
)
ref_points = points_table(
    reference["point_x"], reference["point_y"], reference["point_prior"], reference["point_sd"]
)


def reference_hours(only_research_hours: bool = False) -> list[HourData]:
    used = {ts(str(h)) for h in reference["used_hours"]}
    out = []
    for k, hour in enumerate(reference["hours"]):
        if only_research_hours and ts(str(hour)) not in used:
            continue
        st = reference["station_present"][k]
        px = reference["pixels_present"][k]
        out.append(
            HourData(
                ts(str(hour)),
                (float(reference["u"][k]), float(reference["v"][k])),
                float(reference["pbl"][k]),
                receptors(reference["station_x"][st], reference["station_y"][st]),
                reference["nox"][k][st],
                receptors(reference["pixel_x"], reference["pixel_y"]) if px else receptors([], []),
                reference["vcd"][k] if px else np.zeros(0),
            )
        )
    return out


def max_rel_diff(actual, expected) -> float:
    return float(np.max(np.abs(actual - expected) / np.maximum(np.abs(expected), 1e-300)))


@pytest.mark.regression
@pytest.mark.parametrize("k", range(len(reference["hours"])), ids=list(reference["hours"]))
def test_jacobian_reproduces_the_research_output_within_1e_9(k):
    """`feasibility_linear.jacobian_hour` in the baseline configuration (15 degrees, 1 m/s floor), from
    `make_baseline_reference.py`: winds under the floor, hours without stations or pixels."""
    hour = reference_hours()[k]
    sources = road_sources(ref_zones, ref_points, 4)
    jac = jacobian_hour_plume(
        hour.wind, hour.pbl, sources, hour.stations, hour.pixels, RATIO, SIGMA_THETA, U_MIN
    )
    for actual, expected in (
        (jac.stations, reference[f"stations_{k}"]),
        (jac.pixels, reference[f"pixels_{k}"]),
    ):
        assert actual.shape == expected.shape
        if expected.size:
            assert max_rel_diff(actual, expected) < 1e-9


@pytest.mark.regression
def test_posterior_reproduces_the_research_output_within_1e_9():
    """`real_check_linear.build` + `solve` solve for one background per hour and kind; the package integrates
    them out, and the posterior of the sources, mean and covariance, agrees. The research leaves out the hours
    without station rows, even with TEMPO pixels; so does this comparison."""
    post = invert(
        reference_hours(True), ref_zones, ref_points, RATIO, n_regions=4, holidays=reference["holidays"]
    )
    assert max_rel_diff(post.mean, reference["mean"]) < 1e-9
    scale = np.sqrt(np.outer(np.diag(post.cov), np.diag(post.cov)))
    assert float(np.max(np.abs(post.cov - reference["cov"]) / scale)) < 1e-9


# --- the pieces -----------------------------------------------------------------------------------------


def test_marginalized_block_equals_the_inverse_of_the_full_covariance():
    rng = np.random.default_rng(0)
    k, y = rng.normal(size=(7, 3)), rng.normal(size=7)
    sigma, (mean, sd) = 2.0, (0.5, 3.0)
    r = np.linalg.inv(sigma**2 * np.eye(7) + sd**2 * np.ones((7, 7)))
    info, gradient = marginalized_block(k, y, sigma, (mean, sd))
    assert_allclose(info, k.T @ r @ k, rtol=1e-12)
    assert_allclose(gradient, k.T @ r @ (y - mean), rtol=1e-12)


def test_baseline_point_sources_are_the_two_power_plants_and_the_two_airports():
    points = baseline_point_sources()
    assert list(points["name"]) == [
        "Nonoalco",
        "Valle de México (CC) + Valle de México (Vapor)",
        "AIFA (NLU)",
        "AICM (MEX)",
    ]
    assert list(points["prior"]) == [277, 2615, 500, 500]
    assert list(points["sd"]) == [277, 2615, 1000, 1000]
    assert points["x"].between(400_000, 600_000).all() and points["y"].between(2_100_000, 2_200_000).all()


def test_wind_under_the_floor_gives_the_matrix_of_the_floor_speed():
    sources = road_sources(ref_zones, ref_points, 4)
    st = receptors(reference["station_x"], reference["station_y"])
    slow = jacobian_hour_plume((0.3, 0.4), 900.0, sources, st, st, RATIO, SIGMA_THETA, U_MIN)
    floor = jacobian_hour_plume((0.6, 0.8), 900.0, sources, st, st, RATIO, SIGMA_THETA, U_MIN)
    assert_allclose(slow.stations, floor.stations, rtol=1e-12)
    assert np.all(floor.stations >= 0) and floor.stations.any()


# --- properties of the posterior ------------------------------------------------------------------------


def test_posterior_is_the_prior_when_there_is_no_data():
    post = invert([], ref_zones, ref_points, RATIO, n_regions=4)
    assert_allclose(post.mean, np.r_[ref_points["prior"], np.ones(3 * 4)])
    assert_allclose(post.sd, np.r_[ref_points["sd"], np.full(3 * 4, 0.5)])


def test_posterior_is_the_prior_when_the_hours_have_no_receptors():
    empty = HourData(
        ts("2023-11-17 19:00"),
        (2.0, 1.0),
        900.0,
        receptors([], []),
        np.zeros(0),
        receptors([], []),
        np.zeros(0),
    )
    post = invert([empty], ref_zones, ref_points, RATIO, n_regions=4)
    assert_allclose(post.sd, invert([], ref_zones, ref_points, RATIO, n_regions=4).sd)


def test_posterior_does_not_learn_about_a_day_type_without_data():
    holiday = [h for h in reference_hours() if h.hour.date() == ts("2023-11-20").date() and h.hour.hour >= 18]
    post = invert(holiday, ref_zones, ref_points, RATIO, n_regions=4, holidays=["2023-11-20"])
    factors, prior_sd = post.road_factors(), post.prior_sd[post.n_points :].reshape(N_DAY_TYPES, 4)
    assert_allclose(factors[[0, 1]], 1.0)  # weekday and Saturday: no data, still the prior
    assert np.any(factors[2] != 1.0)  # a holiday counts as Sunday
    assert np.all(post.sd[post.n_points :].reshape(N_DAY_TYPES, 4)[2] <= prior_sd[2])


def test_posterior_shrinks_to_the_prior_as_the_observations_lose_weight(monkeypatch):
    hours = reference_hours()
    tight = invert(hours, ref_zones, ref_points, RATIO, n_regions=4)
    monkeypatch.setattr("nox_ml.inversion.linear.SIGMA_STATION", 1e9)
    monkeypatch.setattr("nox_ml.inversion.linear.SIGMA_PIXEL", 1e9 * 1e15)
    loose = invert(hours, ref_zones, ref_points, RATIO, n_regions=4)
    prior_mean = np.r_[ref_points["prior"], np.ones(12)]
    assert np.max(np.abs(loose.mean - prior_mean) / loose.prior_sd) < 1e-6
    assert np.all(loose.sd >= tight.sd)


# --- synthetic twin -------------------------------------------------------------------------------------


def twin_scene(seed: int = 3):
    """Four point sources, 40 road cells in 3 regions, 6 stations and 8 pixels; 42 days of 6 afternoon hours
    (UTC 18-23): 30 weekdays, 6 Saturdays and 6 Sundays. Observations from known emissions plus noise."""
    rng = np.random.default_rng(seed)
    x0, y0 = 480_000.0, 2_130_000.0
    zones = pd.DataFrame(
        {
            "x": x0 + rng.uniform(0, 30_000, 40),
            "y": y0 + rng.uniform(0, 30_000, 40),
            "weight": rng.uniform(300, 900, 40),  # t/yr per cell
            "region": np.arange(40) % 3,
        }
    )
    points = points_table(
        x0 + rng.uniform(0, 30_000, 4),
        y0 + rng.uniform(0, 30_000, 4),
        [300.0, 1500.0, 500.0, 500.0],
        [300, 1500, 1000, 1000],
    )
    truth = np.r_[[400.0, 1200.0, 900.0, 300.0], np.repeat([1.0, 0.8, 0.5], 3)]
    truth[4:] *= np.tile([1.1, 0.9, 1.0], 3)  # regions differ, day types differ
    sources = road_sources(zones, points, 3)
    stx, sty = x0 + rng.uniform(0, 30_000, 6), y0 + rng.uniform(0, 30_000, 6)
    pxx, pxy = x0 + rng.uniform(0, 30_000, 8), y0 + rng.uniform(0, 30_000, 8)
    days = pd.date_range("2023-11-13", periods=42)  # Mon 13 Nov, six full weeks; holidays are not used
    hours = []
    for day in days:
        kind = 2 if day.day_of_week == 6 else 1 if day.day_of_week == 5 else 0
        columns = np.r_[np.arange(4), 4 + 3 * kind + np.arange(3)]
        for hour in range(18, 24):
            wind = (float(rng.uniform(-4, 4)), float(rng.uniform(-4, 4)))
            pbl = float(rng.uniform(600, 1800))
            jac = jacobian_hour_plume(
                wind, pbl, sources, receptors(stx, sty), receptors(pxx, pxy), RATIO, SIGMA_THETA, U_MIN
            )
            nox = (
                jac.stations @ truth[columns]
                + rng.normal(*BACKGROUND_STATION)
                + SIGMA_STATION * rng.standard_normal(6)
            )
            no2 = (
                jac.pixels @ truth[columns]
                + rng.normal(*BACKGROUND_PIXEL)
                + SIGMA_PIXEL * rng.standard_normal(8)
            )
            hours.append(
                HourData(
                    day + pd.Timedelta(hours=hour),  # UTC; 12-17 h local is the next hours' pbl, not used
                    wind,
                    pbl,
                    receptors(stx, sty),
                    nox,
                    receptors(pxx, pxy),
                    no2,
                )
            )
    return zones, points, truth, hours


def test_twin_recovers_the_known_road_factors():
    """The emission of each day type (the factors weighted by their regions' prior) is recovered within 10 %,
    the weekday factors within 0.15, and the truth is inside the posterior. The weekend factors of single
    regions are less certain: their posterior sd is still 0.2-0.3."""
    zones, points, truth, hours = twin_scene()
    post = invert(hours, zones, points, RATIO, n_regions=3, holidays=[])
    weight = np.asarray(zones.groupby("region")["weight"].sum())
    road = slice(post.n_points, None)

    def totals(x):
        return np.array([weight @ x[road][3 * d : 3 * d + 3] for d in range(N_DAY_TYPES)])

    assert_allclose(totals(post.mean), totals(truth), rtol=0.10)
    assert_allclose(post.road_factors()[0], truth[road][:3], atol=0.15)
    assert np.all(np.abs(post.mean - truth) < 4 * post.sd)
    assert np.all(post.sd[road] < 0.5)  # the data informed every factor
