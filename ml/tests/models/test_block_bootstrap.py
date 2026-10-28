"""The moving-block bootstrap of the inversion's day-type intervals."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from synthetic import synthetic_dataset

from nox_ml.models.inversion_plume import InversionPlume, InversionPlumeParams, block_draw


@given(st.integers(1, 80), st.integers(1, 20), st.integers(0, 10_000))
def test_a_draw_has_as_many_days_as_the_data(n_days, block, seed):
    counts = block_draw(n_days, block, np.random.default_rng(seed))

    assert counts.sum() == n_days and len(counts) == n_days and (counts >= 0).all()


def test_blocks_are_consecutive_days():
    rng = np.random.default_rng(0)

    counts = block_draw(28, 7, rng)

    drawn = np.flatnonzero(counts)
    runs = np.split(drawn, np.flatnonzero(np.diff(drawn) > 1) + 1)
    assert all(len(run) >= 7 for run in runs)  # whole weeks (overlapping blocks merge into longer runs)


def test_one_day_blocks_are_the_plain_bootstrap():
    rng_a, rng_b = np.random.default_rng(3), np.random.default_rng(3)

    counts = block_draw(30, 1, rng_a)

    expected = np.bincount(rng_b.integers(0, 30, size=30), minlength=30)
    np.testing.assert_array_equal(counts, expected)


def test_the_model_passes_the_block_to_its_intervals(make_inputs):
    data = synthetic_dataset(make_inputs()).data
    plain = (
        InversionPlume(InversionPlumeParams.model_validate({"bootstrap_n": 40, "bootstrap_block_days": 1}))
        .fit(data)
        .estimate_emissions()
    )
    weekly = InversionPlume(
        InversionPlumeParams.model_validate({"bootstrap_n": 40, "bootstrap_block_days": 7})
    ).fit(data)

    blocked = weekly.estimate_emissions()

    assert blocked.day_type_ratio("sunday_holiday") == pytest.approx(plain.day_type_ratio("sunday_holiday"))
    assert blocked.day_type_interval("sunday_holiday") != plain.day_type_interval("sunday_holiday")
