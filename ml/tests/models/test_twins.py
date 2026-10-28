"""Twin experiments: simulated observations with a known emission on the real receptors."""

from dataclasses import replace

import numpy as np
import pytest

from nox_ml.inversion.normalized import SUNDAY_HOLIDAY, WEEKDAY
from nox_ml.models.ensemble import MemberConfig
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.validation import twins


@pytest.fixture
def generator():
    return InversionPlume()


def make(inputs, generator, scenario="clean", seed=0):
    return twins.twin(
        inputs, generator.transport_key(), generator.transport(), twins.SCENARIOS[scenario], seed=seed
    )


def test_a_clean_twin_with_the_estimators_physics_is_recovered(make_inputs, generator):
    # the fixture's roads are weak against its 30 ppb: strengthened, the road factors are of order 1 and the
    # prior does not pull them (as in `synthetic.synthetic_dataset`)
    inputs = make_inputs()
    inputs = replace(inputs, zones=inputs.zones.assign(weight=inputs.zones["weight"] * 20))
    data = make(inputs, generator)

    (row,) = twins.recovery(data, [MemberConfig(name="inversion_plume")])

    truth = twins.TRUTH[SUNDAY_HOLIDAY] / twins.TRUTH[WEEKDAY]
    assert row["sunday_holiday"]["truth"] == pytest.approx(truth)
    assert row["sunday_holiday"]["estimate"] == pytest.approx(truth, abs=0.08)


def test_the_twin_keeps_the_receptors_and_the_matrices_and_matches_the_weekday_level(make_inputs, generator):
    inputs = make_inputs()

    data = make(inputs, generator)

    assert [len(h.nox) for h in data.hours] == [len(h.nox) for h in inputs.hours]
    assert data.jacobian_cache is inputs.jacobian_cache
    weekday = [k for k, h in enumerate(inputs.hours) if h.hour.day_of_week < 5]
    real = np.mean([inputs.hours[k].nox.mean() for k in weekday])
    twin = np.mean([data.hours[k].nox.mean() for k in weekday])
    assert twin == pytest.approx(real, rel=0.15)


def test_the_realistic_scenario_adds_background_and_noise(make_inputs, generator):
    inputs = make_inputs()

    clean, realistic = make(inputs, generator), make(inputs, generator, "realistic")

    spread = [np.std(np.log(r.nox / c.nox)) for c, r in zip(clean.hours, realistic.hours, strict=True)]
    assert np.mean(spread) > 0.15
    assert make(inputs, generator, "realistic", seed=1).hours[0].nox[0] != realistic.hours[0].nox[0]
