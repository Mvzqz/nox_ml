import pandas as pd
import pytest
from typer.testing import CliRunner

from nox_ml import cli
from nox_ml.models import REGISTRY
from nox_ml.models.base import ModelParams
from nox_ml.validation import experiment
from nox_ml.validation.compare import collect, markdown
from nox_ml.validation.experiment import ExperimentConfig, run_experiment
from nox_ml.validation.metrics import gap_to_range


class MeanReference:
    """The simplest reference: the mean NOx of the stations it was fitted with."""

    name = "mean_reference"
    role = "reference"
    Params = ModelParams
    n_params = 1

    def __init__(self, params=None):
        self.params = params or ModelParams()

    def fit(self, data, *, exclude_stations=()):
        seen = [
            h.nox[~pd.Index(ids).isin(exclude_stations)]
            for h, ids in zip(data.hours, data.station_ids, strict=True)
        ]
        self.mean = float(sum(x.sum() for x in seen) / sum(len(x) for x in seen))
        return self

    def predict_stations(self, data, stations):
        rows = [
            pd.DataFrame({"station": ids, "utc": h.hour, "nox_ppb_pred": self.mean})
            for h, ids in zip(data.hours, data.station_ids, strict=True)
        ]
        out = pd.concat(rows, ignore_index=True)
        return out[out["station"].isin(stations)].reset_index(drop=True)


def config(name: str, model: str = "inversion_plume", **params) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "name": name,
            "period": {"start": "2023-11-06", "end": "2023-11-19"},
            "model": {"name": model, "params": params},
            "placebo": {"n": 20, "refits": 2},
        }
    )


@pytest.fixture
def runs(tmp_path, monkeypatch, make_inputs):
    monkeypatch.setattr(experiment, "load_inputs", lambda *args: make_inputs())
    monkeypatch.setitem(REGISTRY, MeanReference.name, MeanReference)
    for cfg in (
        config("plume_15", bootstrap_n=5),
        config("plume_45", sigma_theta_deg=45.0, bootstrap_n=5),
        config("floor", "mean_reference"),
    ):
        run_experiment(cfg, tmp_path)
    (tmp_path / "comparison.csv").write_text("not a run\n")
    return tmp_path


def test_a_reference_run_has_no_emission_metrics_instead_of_invented_ones(runs):
    table, _ = collect([runs / "floor"])

    row = table.iloc[0]
    assert row["role"] == "reference"
    assert row[["sunday_ratio", "placebo_center", "placebo_halfwidth", "r_tempo"]].isna().all()
    assert row["eligible"] is None
    assert not (runs / "floor" / "emissions.parquet").exists()
    assert (runs / "floor" / "oof.parquet").exists()


def test_a_model_run_records_its_cost_and_the_placebo_gate(runs):
    row = collect([runs / "plume_15"])[0].iloc[0]

    assert row["fit_seconds"] > 0
    assert (
        row["n_params"] == 1 + 3 * 2
    )  # one point source plus a factor per day type and region of the fixture
    assert row["eligible"] == (abs(row["placebo_center"] - 1) <= 0.15)
    assert row["sunday_ratio_gap"] == pytest.approx(gap_to_range(row["sunday_ratio"]))


def test_collect_sorts_by_loo_rmse_and_skips_what_is_not_a_run(runs):
    table, skipped = collect(sorted(runs.iterdir()))

    assert table["loo_rmse_ppb"].is_monotonic_increasing
    assert set(table["run"]) == {"plume_15", "plume_45", "floor"}
    assert skipped == [runs / "comparison.csv"]


def test_markdown_shows_missing_emission_fields_as_a_dash(runs):
    text = markdown(collect([runs / "plume_15", runs / "floor"])[0])

    header, rule, *rows = text.splitlines()
    assert "loo_rmse_ppb" in header and "sunday_ratio_lo" not in header
    assert rule.count("---") == header.count("|") - 1
    floor = next(r for r in rows if r.startswith("| floor"))
    assert " - " in floor


def test_the_cli_writes_the_csv_and_the_markdown_table(runs):
    result = CliRunner().invoke(
        cli.app, ["compare", *map(str, sorted(runs.iterdir())), "--out-dir", str(runs)]
    )

    assert result.exit_code == 0, result.output
    assert "| plume_15" in result.stdout
    saved = pd.read_csv(runs / "comparison.csv")
    assert saved["loo_rmse_ppb"].is_monotonic_increasing


def test_the_cli_fails_when_nothing_is_a_run(tmp_path):
    result = CliRunner().invoke(cli.app, ["compare", str(tmp_path), "--out-dir", str(tmp_path)])

    assert result.exit_code == 1
