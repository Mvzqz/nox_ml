# pyright: reportArgumentType=false
# (fakes stand in for inputs, models and the network; behavior is covered by the tests)
"""`nox-ml update`: season, order of the steps, failures and the status file, with every step mocked."""

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from nox_ml import monitor
from nox_ml.cli import app


@pytest.mark.parametrize(
    ("day", "season"),
    [
        ("2026-11-03", ("2026-11-01", "2026-12-31")),
        ("2026-12-31", ("2026-11-01", "2026-12-31")),
        ("2027-03-10", ("2027-02-15", "2027-05-31")),
        ("2026-06-01", ("2026-06-01", "2026-10-31")),
        ("2026-10-31", ("2026-06-01", "2026-10-31")),
        ("2027-01-20", None),
        ("2027-02-14", None),
    ],
)
def test_the_season_of_a_day(day, season):
    assert monitor.season_of(day) == season


def test_the_default_last_day_is_today_minus_the_lag():
    assert monitor.default_through(pd.Timestamp("2026-11-05").date()) == "2026-11-02"


def make_job(tmp_path: Path, through="2026-11-10") -> monitor.Job:
    return monitor.Job("2026-11-01", "2026-12-31", through, tmp_path / "data", tmp_path / "runs")


def recorder(calls: list[str], name: str, fail: bool = False) -> monitor.Step:
    def run(job: monitor.Job) -> monitor.Outcome:
        calls.append(name)
        if fail:
            raise RuntimeError(f"{name} broke")
        return monitor.Outcome(f"{name} done", [job.runs_dir / f"{name}.csv"])

    return monitor.Step(name, run)


def steps_like(calls, failing=()):
    """The real names and dependencies, with recording actions."""
    return tuple(
        monitor.Step(s.name, recorder(calls, s.name, s.name in failing).run, s.needs) for s in monitor.STEPS
    )


def test_the_steps_run_in_order_and_the_status_is_written(tmp_path):
    calls: list[str] = []
    job = make_job(tmp_path)
    interim = job.data_dir / "interim"
    interim.mkdir(parents=True)
    pd.DataFrame(
        {"utc": [pd.Timestamp("2026-11-09 05:00"), pd.Timestamp("2026-11-10 04:00")], "NOX": [10.0, 20.0]}
    ).to_parquet(interim / f"openaq_nox_2026-11-01_{job.after}.parquet")
    pd.DataFrame({"local": [pd.Timestamp("2026-11-08 14:00")]}).to_parquet(
        interim / "tempo_pixels_2026-11-01_2026-12-31.parquet"
    )

    status = monitor.run_update(job, steps_like(calls), log=lambda _: None)

    assert calls == ["openaq", "weather", "tempo", "qc_tempo", "flux_divergence", "weekly_index"]
    assert status["ok"] and job.after == "2027-01-01"
    assert status["last_day_stations"] == "2026-11-09"  # 04:00 UTC is the evening before, local time
    assert status["last_day_tempo"] == "2026-11-08"
    assert status["window"] == ["2026-11-01", "2026-12-31"] and status["through"] == "2026-11-10"
    assert len(status["outputs"]) == 6
    assert json.loads((job.runs_dir / "monitor" / "status.json").read_text()) == status
    assert "finished_utc" in status and status["steps"]["openaq"]["detail"] == "openaq done"


def test_a_failed_step_skips_what_needs_it_and_not_the_independent_ones(tmp_path):
    calls: list[str] = []

    status = monitor.run_update(make_job(tmp_path), steps_like(calls, failing={"tempo"}), log=lambda _: None)

    assert calls == ["openaq", "weather", "tempo", "weekly_index"]  # qc_tempo and flux need tempo
    assert not status["ok"]
    assert status["steps"]["tempo"]["error"] == "RuntimeError: tempo broke"
    assert status["steps"]["qc_tempo"]["skipped"]
    assert status["steps"]["flux_divergence"]["skipped"]
    assert status["steps"]["weekly_index"]["ok"]
    assert status["last_day_stations"] is None  # nothing was fetched


def test_the_summary_lists_the_steps(tmp_path):
    status = monitor.run_update(make_job(tmp_path), steps_like([], failing={"openaq"}), log=lambda _: None)

    text = monitor.summary(status)

    assert "with failures" in text and "openaq: FAILED" in text and "weather: ok" in text


def test_the_command_takes_the_season_from_the_day_and_clamps_through_to_its_end(tmp_path, monkeypatch):
    seen = []

    def run_update(job, steps=None, log=print):
        seen.append(job)
        return {"ok": True, "window": [job.start, job.end], "through": job.through, "last_day_stations": None,
                "last_day_tempo": None, "steps": {}}  # fmt: skip

    monkeypatch.setattr(monitor, "run_update", run_update)
    runner = CliRunner()

    first = runner.invoke(app, ["update", "--through", "2026-11-10", "--data-dir", str(tmp_path)])
    custom = runner.invoke(
        app,
        [
            "update",
            "--through",
            "2027-03-01",
            "--season",
            "2026-11-01:2026-12-31",
            "--data-dir",
            str(tmp_path),
        ],
    )

    assert first.exit_code == 0 and custom.exit_code == 0
    assert (seen[0].start, seen[0].end, seen[0].through) == ("2026-11-01", "2026-12-31", "2026-11-10")
    assert seen[1].through == "2026-12-31"


def test_the_command_does_nothing_between_seasons_and_refuses_simat_years(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "run_update", lambda *a, **k: pytest.fail("must not run"))
    runner = CliRunner()

    gap = runner.invoke(app, ["update", "--through", "2027-01-20"])
    old = runner.invoke(app, ["update", "--through", "2024-03-01"])

    assert gap.exit_code == 0 and "nothing to update" in gap.output
    assert old.exit_code == 2


def test_the_command_exits_1_when_a_step_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "STEPS", steps_like([], failing={"weather"}))
    result = CliRunner().invoke(
        app,
        [
            "update",
            "--through",
            "2026-11-10",
            "--data-dir",
            str(tmp_path / "d"),
            "--runs-dir",
            str(tmp_path / "r"),
        ],
    )

    assert result.exit_code == 1
    assert "weather: FAILED" in result.output
    assert json.loads((tmp_path / "r" / "monitor" / "status.json").read_text())["ok"] is False


def test_the_weekly_index_fits_each_week_against_the_other_business_days(monkeypatch):
    from types import SimpleNamespace

    from nox_ml.validation import events, products

    business = pd.DatetimeIndex(["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-09", "2026-11-10"])
    groups = events.Groups(business, business, business[:0], business[:0], business[:0])
    fits = []

    def fit(days_inputs, make_model, relabeled):
        fits.append((list(days_inputs), list(relabeled)))
        return 1.0 + 0.1 * len(relabeled), None

    monkeypatch.setattr(events, "split_days", lambda inputs, requested, active: groups)
    monkeypatch.setattr(events, "_fit_ratio", fit)
    inputs = SimpleNamespace(on_days=lambda days: list(days))

    index = products.weekly_index(inputs, lambda: None, pd.DatetimeIndex([]))

    assert index["week"].tolist() == ["2026-11-02", "2026-11-09"]
    assert index["n_days"].tolist() == [3, 2]
    assert index["change"].tolist() == pytest.approx([0.3, 0.2])
    days, relabeled = fits[1]
    assert len(days) == 5 and [d.day for d in relabeled] == [9, 10]


def test_a_few_failed_tempo_granules_do_not_stop_the_season(tmp_path, monkeypatch):
    job = monitor.Job("2026-11-01", "2026-12-31", "2026-11-10", tmp_path, tmp_path / "runs")

    monkeypatch.setattr(monitor.tempo, "fetch_window", lambda *a: {"found": 30, "new": 28, "failed": 2})
    assert "2 failed" in monitor.fetch_tempo_step(job).detail
    monkeypatch.setattr(monitor.tempo, "fetch_window", lambda *a: {"found": 30, "new": 0, "failed": 3})
    with pytest.raises(RuntimeError):
        monitor.fetch_tempo_step(job)
