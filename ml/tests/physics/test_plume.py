import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.testing import assert_allclose

from nox_ml.physics.plume import U_MIN, X_MAX, plume, speed

coords = st.floats(-20e3, 20e3)
wind_component = st.floats(-10, 10)
bearing = st.floats(0, 2 * np.pi)
PBL = 1200.0


def _points(values):
    return np.array(values, dtype=float)


def test_standard_wind_floor_is_two_meters_per_second():
    assert U_MIN == 2.0


@given(mag=st.floats(0, 50), floor=st.floats(0.1, 5))
def test_speed_never_goes_below_the_floor(mag, floor):
    assert speed(mag, floor) >= floor
    assert speed(mag, floor) >= mag


@given(mag=st.floats(U_MIN, 50))
def test_speed_equals_the_wind_when_it_is_above_the_floor(mag):
    assert speed(mag) == mag


@given(
    speeds=st.tuples(st.floats(0.05, U_MIN * 0.999), st.floats(0.05, U_MIN * 0.999)),
    angle=bearing,
    receiver=st.tuples(coords, coords),
)
def test_plume_does_not_depend_on_weak_wind_speed_when_below_the_floor(speeds, angle, receiver):
    xs, ys = _points([0.0]), _points([0.0])
    xr, yr = _points([receiver[0]]), _points([receiver[1]])
    first, second = (plume(xs, ys, xr, yr, s * np.cos(angle), s * np.sin(angle), PBL)[1] for s in speeds)
    assert_allclose(first, second, rtol=1e-9, atol=1e-30)


@given(mag=st.floats(0.0, U_MIN * 0.999), angle=bearing, distance=st.floats(1_000, 30_000))
def test_plume_column_is_bounded_by_the_floor_speed_when_wind_is_weak(mag, angle, distance):
    ex, ey = np.cos(angle), np.sin(angle)
    xs, ys = _points([0.0]), _points([0.0])
    _, col = plume(xs, ys, _points([distance * ex]), _points([distance * ey]), mag * ex, mag * ey, PBL)
    sy_min = 0.32 * 300 / np.sqrt(1 + 0.0004 * 300)  # smallest lateral spread of the model
    assert col[0, 0] <= 1 / (np.sqrt(2 * np.pi) * sy_min * U_MIN)


@given(source=st.tuples(coords, coords), receiver=st.tuples(coords, coords))
def test_plume_is_zero_without_wind(source, receiver):
    g, col = plume(
        _points([source[0]]),
        _points([source[1]]),
        _points([receiver[0]]),
        _points([receiver[1]]),
        0.0,
        0.0,
        PBL,
    )
    assert not g.any()
    assert not col.any()


@given(angle=bearing, distance=st.floats(1.0, 30_000))
def test_plume_is_zero_upwind_of_the_source(angle, distance):
    ex, ey = np.cos(angle), np.sin(angle)
    g, col = plume(
        _points([0.0]),
        _points([0.0]),
        _points([-distance * ex]),
        _points([-distance * ey]),
        3 * ex,
        3 * ey,
        PBL,
    )
    assert g[0, 0] == 0.0 and col[0, 0] == 0.0


def test_plume_is_zero_beyond_the_maximum_distance():
    _, col = plume(_points([0.0]), _points([0.0]), _points([X_MAX + 1]), _points([0.0]), 3.0, 0.0, PBL)
    assert col[0, 0] == 0.0


@given(
    u=st.floats(-10, 10),
    v=st.floats(-10, 10),
    along=st.floats(1_000, 30_000),
    extra_sy=st.floats(0, 2_000),
)
def test_plume_conserves_mass_across_a_wind_perpendicular_line(u, v, along, extra_sy):
    mag = np.hypot(u, v)
    if mag < 0.1:
        return
    ex, ey = u / mag, v / mag
    cross = np.arange(-150e3, 150e3, 250.0)
    xr, yr = along * ex - cross * ey, along * ey + cross * ex
    _, col = plume(_points([0.0]), _points([0.0]), xr, yr, u, v, PBL, extra_sy=extra_sy)
    flux = col.sum() * 250.0 * speed(mag)  # (g/m2) * (m) * (m/s) = g/s emitted
    assert_allclose(flux, 1.0, rtol=1e-3)


@given(
    sources=st.lists(st.tuples(coords, coords), min_size=2, max_size=5),
    emissions=st.lists(st.floats(0, 100), min_size=5, max_size=5),
    scale=st.floats(0, 10),
    wind=st.tuples(wind_component, wind_component),
)
@settings(max_examples=50)
def test_concentration_is_linear_in_emission(sources, emissions, scale, wind):
    xs, ys = _points([p[0] for p in sources]), _points([p[1] for p in sources])
    q = _points(emissions[: len(sources)])
    xr, yr = _points([-3_000.0, 4_000.0, 12_000.0]), _points([500.0, -2_000.0, 7_000.0])

    def concentration(emission):
        g, col = plume(xs, ys, xr, yr, wind[0], wind[1], PBL)
        return g @ emission, col @ emission

    base = concentration(q)
    for scaled, reference in zip(concentration(scale * q), base, strict=True):
        assert_allclose(scaled, scale * reference, rtol=1e-9, atol=1e-30)
    # superposition: each source contributes on its own, whatever the others emit
    for j in range(len(sources)):
        alone = np.zeros_like(q)
        alone[j] = q[j]
        g_alone, _ = plume(xs[[j]], ys[[j]], xr, yr, wind[0], wind[1], PBL)
        assert_allclose(concentration(alone)[0], g_alone[:, 0] * q[j], rtol=1e-9, atol=1e-30)


def test_plume_reproduces_the_research_reference_value():
    # Value from scripts/feasibility_linear.py (research-archive): 5 km downwind, 3 m/s, pbl 1,000 m.
    g, col = plume(_points([0.0]), _points([0.0]), _points([5_000.0]), _points([0.0]), 3.0, 0.0, 1_000.0)
    assert_allclose(g[0, 0], 4.79004711e-08, rtol=1e-7)
    assert_allclose(col[0, 0], 4.79004711e-05, rtol=1e-7)
