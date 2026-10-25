# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import copy

import pytest
from matplotlib.figure import Figure

from nox_ml import report
from nox_ml.validation import diagnostics
from nox_ml.validation.experiment import ExperimentConfig, evaluate

N_REGIONS = 2


def config() -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "name": "t",
            "period": {"start": "2023-11-06", "end": "2023-11-19"},
            "model": {"name": "inversion_plume", "params": {"bootstrap_n": 4}},
            "placebo": {"n": 20, "refits": 2},
        }
    )


@pytest.fixture
def inputs(make_inputs):
    return make_inputs()


@pytest.fixture
def metrics(inputs):
    return evaluate(inputs, config()).metrics


def test_find_root_locates_the_repository_from_a_subfolder(tmp_path):
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    (root / "pyproject.toml").write_text("")
    (root / "deliverables").mkdir()
    assert report.find_root(root / "deliverables") == root


def test_find_root_fails_outside_a_repository(tmp_path):
    with pytest.raises(FileNotFoundError):
        report.find_root(tmp_path)


def test_load_config_reads_the_baseline_with_the_data_of_the_repository():
    config = report.load_config("baseline")
    assert config.model.name == "inversion_plume"
    assert config.data_dir == report.find_root() / "data"


def test_data_overview_counts_what_the_inputs_hold(inputs):
    table = report.data_overview(inputs, config())
    assert list(table.columns) == ["dato", "contenido"]
    assert "3 estaciones" in table.loc[0, "contenido"]
    assert "14 días" in table.loc[table["dato"] == "Periodo", "contenido"].item()


def test_capacity_table_gives_the_pixels_per_parameter(metrics):
    table = report.capacity_table(metrics).set_index("concepto")["valor"]
    assert table["Parámetros del modelo"] == str(metrics["summary"]["n_params"])


def passes(table, criterion):
    return table.set_index("criterio").loc[criterion, "cumple"]


def test_minimum_performance_checks_each_criterion_on_the_summary(metrics):
    run = copy.deepcopy(metrics)
    run["summary"] |= {
        "placebo_center": 1.08,
        "sunday_ratio": 0.42,
        "sunday_ratio_lo": 0.35,
        "sunday_ratio_hi": 0.54,
    }
    run["loo"]["rmse"] |= {"model": 13.6, "idw": 11.6}
    table = report.minimum_performance(run)
    assert passes(table, "Placebo centrado en 1")
    assert passes(table, "Dirección del domingo")
    assert not passes(table, "Magnitud del domingo (referencia)")
    assert passes(table, "Cercanía a IDW")


def test_minimum_performance_fails_a_placebo_off_center_and_a_model_far_from_idw(metrics):
    run = copy.deepcopy(metrics)
    run["summary"]["placebo_center"] = 1.3
    run["loo"]["rmse"] |= {"model": 20.0, "idw": 11.6}
    table = report.minimum_performance(run)
    assert not passes(table, "Placebo centrado en 1")
    assert not passes(table, "Cercanía a IDW")


def test_in_sample_vs_held_out_has_a_row_per_station(inputs, metrics):
    table = report.in_sample_vs_held_out(inputs, config(), metrics)
    assert list(table.index) == ["AAA", "BBB", "CCC"]
    assert table[["rmse_en_muestra", "rmse_oculta"]].notna().all().all()


def test_the_figures_of_the_run_are_figures(inputs, metrics):
    held = report.in_sample_vs_held_out(inputs, config(), metrics)
    figures = [
        report.plot_domain(inputs),
        report.plot_daily_context(inputs),
        report.plot_loo_by_station(metrics),
        report.plot_level_and_rhythm(metrics),
        report.plot_emission_metrics(metrics),
        report.plot_in_sample_vs_held_out(held),
    ]
    assert all(isinstance(fig, Figure) for fig in figures)


def test_the_figures_of_the_diagnostics_are_figures(inputs):
    cfg = config()
    systems = diagnostics.model_systems(inputs, cfg.model.build())
    reduction, dofs = diagnostics.information_by_observation(systems, inputs.points, N_REGIONS)
    ablation = diagnostics.ablation(inputs, cfg, station_counts=(2,), wind_biases=(15.0,), seeds=range(2))
    curve = diagnostics.learning_curve(
        inputs, cfg.model.build, day_counts=(7, 14), station_counts=(2, 3), seeds=range(2)
    )
    figures = [
        report.plot_information(reduction, dofs),
        report.plot_ablation(ablation),
        report.plot_learning_curves(curve),
    ]
    assert all(isinstance(fig, Figure) for fig in figures)


def test_load_metrics_and_diagnostics_read_what_the_runner_wrote(tmp_path):
    (tmp_path / "diagnostics").mkdir()
    (tmp_path / "metrics.json").write_text('{"a": 1}')
    for name in ("variance_reduction", "degrees_of_freedom", "ablation", "learning_curve"):
        (tmp_path / "diagnostics" / f"{name}.csv").write_text("x\n1\n")
    assert report.load_metrics(tmp_path) == {"a": 1}
    assert set(report.load_diagnostics(tmp_path)) == {"reduction", "dofs", "ablation", "curve"}
