import json

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from nox_ml.validation import report_final as rf

STATIONS = [f"S{k:02d}" for k in range(4)]
HOURS = pd.date_range("2023-11-01 18:00", periods=48, freq="h")


def summary(model, rmse, kind_run=None):
    return {
        "model": model,
        "role": "model",
        "loo_rmse_ppb": rmse,
        "loo_bias_ppb": 1.0,
        "loo_hourly_rmse_ppb": rmse - 1,
        "r_tempo": None,
        "sunday_ratio": 0.5,
        "sunday_ratio_lo": 0.4,
        "sunday_ratio_hi": 0.6,
        "sunday_ratio_gap": 0.15,
        "placebo_center": 1.0,
        "placebo_halfwidth": 0.1,
        "eligible": True,
        "fit_seconds": 10.0,
        "predict_seconds": 0.1,
        "n_params": 30,
    }


def observed():
    rng = np.random.default_rng(0)
    rows = pd.DataFrame([(s, h) for h in HOURS for s in STATIONS], columns=["station", "utc"])
    return rows.assign(
        obs=rng.uniform(10, 60, len(rows)),
        ventilation=rng.uniform(100, 5000, len(rows)),
        day=rows["utc"].dt.normalize(),
        hour=rows["utc"].dt.hour,
        day_type="weekday",
    )


def write_run(runs, name, model, rmse, oof=None, emissions=None, evaluation=None):
    folder = runs / name
    folder.mkdir(parents=True)
    metrics = {
        "summary": summary(model, rmse),
        "day_types": {"saturday_over_weekday": {"value": 0.8, "lo": 0.7, "hi": 0.9}},
    }
    if evaluation:
        metrics["evaluation"] = evaluation
    (folder / "metrics.json").write_text(json.dumps(metrics))
    (folder / "config.yaml").write_text(f"model:\n  name: {model}\n")
    if oof is not None:
        oof.to_parquet(folder / "oof.parquet")
    if emissions is not None:
        emissions.to_parquet(folder / "emissions.parquet")
    return folder


def oof_of(obs, noise, seed=1):
    rng = np.random.default_rng(seed)
    pred = obs["obs"] + rng.normal(0, noise, len(obs))
    return obs[["station", "utc"]].assign(nox_ppb_pred=pred)


def test_the_comparison_sorts_the_runs_and_uses_the_nested_error_of_a_stacking(tmp_path):
    obs = observed()
    write_run(tmp_path, "pinn_puff", "pinn_puff", 11.87)
    folder = write_run(tmp_path, "stacking", "convex_ensemble", 9.0)
    oof_of(obs, noise=20.0).to_parquet(folder / "nested_oof.parquet")
    write_run(tmp_path, "not_planned", "pinn_puff", 1.0)

    table = rf.comparison(tmp_path, obs)

    assert list(table["run"]) == ["pinn_puff", "stacking"]  # the nested error (~20) is worse than 11.87
    assert table.set_index("run").loc["stacking", "loo_source"] == "anidado"
    assert table.set_index("run").loc["stacking", "kind"] == "heterogéneo"
    assert rf.kinds_covered(table).to_dict() == {"homogéneo": 0, "heterogéneo": 1}
    assert "stacking" not in set(rf.missing(table)["run"])


def test_without_observations_the_comparison_keeps_the_error_of_the_run(tmp_path):
    folder = write_run(tmp_path, "stacking", "convex_ensemble", 9.0)
    oof_of(observed(), noise=12.0).to_parquet(folder / "nested_oof.parquet")

    assert rf.comparison(tmp_path).loc[0, "loo_source"] == "run"


def test_an_empty_runs_folder_has_everything_missing(tmp_path):
    table = rf.comparison(tmp_path)

    assert table.empty
    assert len(rf.missing(table)) == len(rf.PLANNED)
    assert rf.kinds_covered(table).sum() == 0


def test_only_runs_written_by_evaluate_are_test_period_runs(tmp_path):
    write_run(tmp_path, "pinn_puff", "pinn_puff", 11.87)
    write_run(tmp_path, "pinn_puff.test", "pinn_puff", 12.3, evaluation={"period": "test"})

    assert list(rf.test_period(tmp_path)["run"]) == ["pinn_puff.test"]


def test_held_out_rows_carry_the_residual_and_the_summary_matches_it(tmp_path):
    obs = observed()
    run = write_run(tmp_path, "pinn_puff", "pinn_puff", 1.0, oof=oof_of(obs, noise=3.0))

    table = rf.held_out(run, obs)
    s = rf.error_summary(table)

    assert len(table) == len(obs)
    assert bool(np.allclose(table["residual"], table["obs"] - table["pred"]))
    rmse = s["rmse_ppb"]
    residual = table["residual"].to_numpy(float)
    assert rmse == pytest.approx(float(np.sqrt(np.mean(residual**2))))
    assert 2 < rmse < 4


def absolute_emissions():
    rows = [
        {"zone": z, "day_type": d, "mean": 1000.0 + z, "sd": 50.0, "kind": "absolute"}
        for d in rf.DAY_ORDER
        for z in range(9)
    ]
    return pd.DataFrame(rows)


def relative_emissions():
    return pd.DataFrame(
        {
            "zone": [np.nan] * 3,
            "day_type": list(rf.DAY_ORDER),
            "mean": [1.0, 0.8, 0.5],
            "lo": [1.0, 0.7, 0.4],
            "hi": [1.0, 0.9, 0.6],
            "kind": "relative",
        }
    )


@pytest.mark.parametrize(
    "emissions", [absolute_emissions(), relative_emissions()], ids=["absolute", "relative"]
)
def test_the_emission_figure_draws_absolute_and_relative_estimates(tmp_path, emissions):
    run = write_run(tmp_path, "final", "pinn_puff", 1.0, emissions=emissions)

    assert isinstance(rf.plot_emission_map(run), Figure)


def test_the_figures_of_the_final_model_draw(tmp_path):
    obs = observed()
    run = write_run(tmp_path, "pinn_puff", "pinn_puff", 1.0, oof=oof_of(obs, noise=3.0))
    test = write_run(tmp_path, "pinn_puff.test", "pinn_puff", 1.0, evaluation={"period": "test"})
    table = rf.held_out(run, obs)
    weights = pd.DataFrame(
        {"pinn_puff": [0.7, 0.6], "inversion_puff": [0.3, 0.4]}, index=pd.Index(["A", "B"], name="station")
    )

    figures = [
        rf.plot_observed_vs_predicted(table),
        rf.plot_residuals(table),
        rf.plot_series(table, STATIONS[:2]),
        rf.plot_day_types({"nov–dic": run, "feb–may": test}),
        rf.plot_weights(weights),
    ]

    assert all(isinstance(f, Figure) for f in figures)


def test_missing_runs_and_data_give_no_observations(tmp_path, capsys):
    assert rf.observed_or_none(tmp_path / "none", tmp_path) is None
    assert "Sin corrida" in capsys.readouterr().out
