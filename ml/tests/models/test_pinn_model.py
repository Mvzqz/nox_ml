# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
import dataclasses
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pinn_kernel_fixture import reference_kernel
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import HOLIDAYS, road_sources
from nox_ml.inversion.normalized import day_type
from nox_ml.models import REGISTRY
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.pinn import cache as cache_module
from nox_ml.models.pinn.cache import BUNDLED, KernelCache, obtain_kernel
from nox_ml.models.pinn.kernel import train_kernel
from nox_ml.models.pinn.model import PinnPlume
from nox_ml.models.pinn.params import PinnParams
from nox_ml.time import local_day
from nox_ml.validation.experiment import read_config

CONFIGS = Path(__file__).parents[3] / "configs" / "experiments"
TINY = PinnParams(layers=2, width=16, adam_steps=20, lbfgs_rounds=1)
WEEKDAY_FACTORS, SUNDAY_OVER_WEEKDAY = np.array([1.3, 0.7]), 0.5
ROAD_SCALE = 30.0  # the roads of the toy scene are strong enough for the data to speak louder than the prior


@pytest.fixture
def fresh_memory(monkeypatch):
    """An empty in-memory cache of kernels, and a count of the trainings."""
    trainings = []

    def counting(params, progress=None):
        trainings.append(params)
        return train_kernel(params, progress)

    monkeypatch.setattr(cache_module, "_IN_MEMORY", {})
    monkeypatch.setattr(cache_module, "train_kernel", counting)
    return trainings


def synthetic(base: Inputs, seed: int = 0) -> tuple[Inputs, float]:
    """The small inputs with the observations simulated by the PINN transport from known sources (the contract
    fixture uses the plume): road factors `WEEKDAY_FACTORS`, half of them on Sundays, 5 ppb of background and
    a little noise. Returns the inputs and the true weekday road total (t/yr)."""
    inputs = dataclasses.replace(base, zones=base.zones.assign(weight=base.zones["weight"] * ROAD_SCALE))
    rng = np.random.default_rng(seed)
    transport = PinnPlume().transport()
    sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
    kinds = day_type(pd.DatetimeIndex([local_day(h.hour) for h in inputs.hours]), HOLIDAYS)
    hours = []
    for hour, kind in zip(inputs.hours, kinds, strict=True):
        factors = WEEKDAY_FACTORS * (SUNDAY_OVER_WEEKDAY if kind == 2 else 1.0)
        state = np.r_[inputs.points["prior"].to_numpy(), factors]
        jac = transport(hour.wind, hour.pbl, sources, hour.stations, hour.pixels, inputs.no2_nox_ratio)
        nox = jac.stations @ state + 5.0 + rng.normal(0, 0.3, len(hour.nox))
        no2 = jac.pixels @ state + 5e15 + rng.normal(0, 3e14, len(hour.no2))
        hours.append(dataclasses.replace(hour, nox=nox, no2=no2))
    weekday_total = float(WEEKDAY_FACTORS @ inputs.zones.groupby("region")["weight"].sum().to_numpy())
    return dataclasses.replace(inputs, hours=hours), weekday_total


# --- registration --------------------------------------------------------------------------------------


def test_the_model_is_registered_under_its_name_and_is_a_model():
    assert REGISTRY["pinn_plume"] is PinnPlume
    assert (PinnPlume.name, PinnPlume.role) == ("pinn_plume", "model")


def test_the_pinn_is_the_baseline_inversion_with_anothertransport():
    assert issubclass(PinnPlume, InversionPlume)
    assert PinnPlume.Params is PinnParams


def test_the_pinn_yaml_is_the_baseline_with_the_pinn_model():
    baseline, pinn = read_config(CONFIGS / "baseline.yaml"), read_config(CONFIGS / "pinn_plume.yaml")

    assert pinn.model.name == "pinn_plume"
    assert PinnParams.model_validate(pinn.model.params).model_dump(exclude={"kernel_dir"}) == (
        PinnParams().model_dump(exclude={"kernel_dir"})
    )
    assert pinn.model_copy(update={"name": "baseline", "model": baseline.model}) == baseline


def test_a_typo_in_the_pinn_params_does_not_train_the_default_network():
    with pytest.raises(ValueError, match="widht"):
        PinnParams.model_validate({"widht": 8})


# --- the kernels ---------------------------------------------------------------------------------------


def test_the_default_network_is_bundled_for_the_default_parameters():
    kernel = BUNDLED.load(PinnParams())

    assert kernel is not None
    assert kernel.validation["0.25"]["median_rel_error"] < 0.07


def test_the_default_parameters_never_train(fresh_memory):
    obtain_kernel(PinnParams())

    assert fresh_memory == []


def test_a_kernel_is_trained_once_per_process_whatever_the_number_of_models(fresh_memory):
    first, second = obtain_kernel(TINY), obtain_kernel(TINY)

    assert first is second
    assert len(fresh_memory) == 1


def test_a_disk_cache_keeps_the_network_for_the_next_process(fresh_memory, tmp_path, monkeypatch):
    obtain_kernel(TINY, tmp_path)
    monkeypatch.setattr(cache_module, "_IN_MEMORY", {})  # a new process

    obtain_kernel(TINY, tmp_path)

    assert len(fresh_memory) == 1
    assert KernelCache(tmp_path).load(TINY) is not None


def test_changing_only_thetransport_fields_reuses_the_network(fresh_memory):
    obtain_kernel(TINY)
    obtain_kernel(PinnParams(**{**TINY.model_dump(), "tau_h": 6.0, "u_min": 2.0}))

    assert len(fresh_memory) == 1


def test_the_pinn_with_other_training_parameters_trains_its_own_network(fresh_memory, make_inputs):
    PinnPlume(TINY).fit(make_inputs())

    assert fresh_memory == [TINY]


def test_n_params_counts_the_unknowns_and_the_weights_of_the_network(make_inputs):
    data = make_inputs()
    weights = sum(w.numel() for w in reference_kernel().net.parameters())

    assert PinnPlume().fit(data).n_params == InversionPlume().fit(data).n_params + weights


# --- it recovers what it simulates ---------------------------------------------------------------------


def test_the_twin_with_its_own_physics_recovers_the_road_emission_and_the_sunday_ratio(make_inputs):
    data, weekday_total = synthetic(make_inputs())

    estimate = PinnPlume().fit(data).estimate_emissions()

    total = estimate.table.groupby("day_type")["mean"].sum()
    assert total["weekday"] == pytest.approx(weekday_total, rel=0.10)
    assert estimate.day_type_ratio("sunday_holiday") == pytest.approx(SUNDAY_OVER_WEEKDAY, rel=0.10)
    low, high = estimate.day_type_interval("sunday_holiday")
    assert low < estimate.day_type_ratio("sunday_holiday") < high


def test_the_station_left_out_is_predicted_from_the_others(make_inputs):
    data, _ = synthetic(make_inputs())
    model = PinnPlume().fit(data, exclude_stations=["CCC"])
    observed = np.concatenate(
        [h.nox[ids == "CCC"] for h, ids in zip(data.hours, data.station_ids, strict=True)]
    )

    pred = model.predict_stations(data, ["CCC"])

    assert np.corrcoef(pred["nox_ppb_pred"], observed)[0, 1] > 0.9


def test_the_pinntransport_gives_other_numbers_than_the_plume(make_inputs):
    data, _ = synthetic(make_inputs())

    pinn = PinnPlume().fit(data).predict_stations(data, ["AAA"])
    plume = InversionPlume().fit(data).predict_stations(data, ["AAA"])

    assert not np.allclose(pinn["nox_ppb_pred"], plume["nox_ppb_pred"])


# --- the CLI -------------------------------------------------------------------------------------------


def write_config(path, model):
    path.write_text(
        yaml.safe_dump({"name": "t", "period": {"start": "2023-11-06", "end": "2023-11-19"}, "model": model})
    )
    return path


def test_the_cli_trains_a_kernel_and_prints_its_validation(tmp_path, fresh_memory):
    params = TINY.model_copy(update={"kernel_dir": str(tmp_path / "kernels")}).model_dump()
    path = write_config(tmp_path / "pinn.yaml", {"name": "pinn_plume", "params": params})

    result = CliRunner().invoke(cli.app, ["train-pinn", str(path)])

    assert result.exit_code == 0, result.output
    assert f"Kernel {TINY.training_key()}" in result.stdout
    assert "median_rel_error" in result.stdout and "0.25" in result.stdout
    assert list((tmp_path / "kernels").glob("kernel-*.pt"))


def test_the_cli_refuses_a_config_of_another_model(tmp_path):
    path = write_config(tmp_path / "plume.yaml", {"name": "inversion_plume"})

    result = CliRunner().invoke(cli.app, ["train-pinn", str(path)])

    assert result.exit_code == 2
    assert "not 'pinn_plume'" in result.output


def test_without_torch_the_other_models_still_register_and_the_pinn_does_not():
    code = (
        # as if torch were not installed (a None in sys.modules breaks the array API probe of scipy)
        "import sys\n"
        "class NoTorch:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'torch':\n"
        "            raise ModuleNotFoundError(\"No module named 'torch'\", name='torch')\n"
        "sys.meta_path.insert(0, NoTorch())\n"
        "from nox_ml.models import REGISTRY\n"
        "print(sorted(REGISTRY))\n"
    )

    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert out.stdout.strip() == (
        "['convex_ensemble', 'idw', 'inversion_plume', 'inversion_puff', 'kriging', 'lognormal_map', "
        "'normalized_ratio', 'regularized_ls', 'rf_deweather']"
    )


def test_pinn_and_plume_jacobians_never_share_a_cache_entry(make_inputs):
    inputs = make_inputs()
    plume, pinn = InversionPlume(), PinnPlume()

    assert plume.transport_key() != pinn.transport_key()
    plume.fit(inputs)
    pinn.fit(inputs)

    assert len(inputs.jacobian_cache) == 2


def test_the_diffusivity_changes_the_transport_key_and_the_default_keeps_it():
    default = PinnParams()

    assert PinnPlume().transport_key() == ("pinn", default.training_key(), 12.0, 1.0)
    assert PinnPlume(PinnParams(kappa=1500.0)).transport_key() == PinnPlume().transport_key()
    assert PinnPlume(PinnParams(kappa=3000.0)).transport_key() != PinnPlume().transport_key()


def test_an_explicit_default_diffusivity_is_the_bundled_network_and_gives_its_table():
    explicit = obtain_kernel(PinnParams(kappa=1500.0))

    assert explicit is obtain_kernel(PinnParams())
    np.testing.assert_array_equal(explicit.table.values, reference_kernel().table.values)
