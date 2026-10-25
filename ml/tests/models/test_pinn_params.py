import pytest
import yaml
from pydantic import ValidationError

from nox_ml.models.pinn.cache import BUNDLED
from nox_ml.models.pinn.params import PinnParams


def test_params_round_trip_through_yaml():
    params = PinnParams(layers=3, width=32, learning_rate=1e-3, seed=5)

    assert PinnParams.model_validate(yaml.safe_load(yaml.safe_dump(params.model_dump()))) == params


def test_params_reject_unknown_fields_so_a_typo_does_not_train_the_default():
    with pytest.raises(ValidationError, match="widht"):
        PinnParams.model_validate({"widht": 32})


@pytest.mark.parametrize(
    "changes", [{"layers": 0}, {"width": 0}, {"learning_rate": 0}, {"tau_h": -1}, {"kappa": 0}, {"kappa": -5}]
)
def test_params_reject_values_that_make_no_sense(changes):
    with pytest.raises(ValidationError):
        PinnParams(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"layers": 3},
        {"width": 32},
        {"learning_rate": 1e-3},
        {"physics_weight": 2.0},
        {"adam_steps": 10},
        {"lbfgs_rounds": 1},
        {"seed": 1},
        {"kappa": 3000.0},
    ],
)
def test_every_training_field_changes_the_cache_key(changes):
    assert PinnParams(**changes).training_key() != PinnParams().training_key()


def test_the_transport_fields_do_not_retrain_the_network():
    assert PinnParams(tau_h=6.0, u_min=2.0).training_key() == PinnParams().training_key()


def test_the_default_diffusivity_is_the_research_one_and_keeps_the_key_of_the_bundled_network():
    assert PinnParams().kappa == 1500.0
    assert PinnParams(kappa=1500).training_key() == PinnParams().training_key()
    assert (BUNDLED.directory / f"kernel-{PinnParams().training_key()}.pt").exists()


def test_every_diffusivity_has_its_own_cache_entry():
    keys = {PinnParams(kappa=k).training_key() for k in (500.0, 1000.0, 1500.0, 3000.0)}

    assert len(keys) == 4
