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

    def run_update(job, steps=None, log=print, closing=()):
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

    gap = runner.invoke(app, ["update", "--through", "2027-02-10"])
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


# --- Season rollover ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "today", "window"),
    [
        ("2026-11-01", "2026-11-05", ("2026-06-01", "2026-10-31")),  # the rainy season is still closing
        ("2026-11-01", "2026-11-21", ("2026-06-01", "2026-10-31")),  # the last day of the period
        ("2026-11-01", "2026-11-22", None),
        ("2027-01-20", "2027-01-20", ("2026-11-01", "2026-12-31")),  # between seasons
        ("2027-02-15", "2027-02-20", None),  # nov-dec closed 46 days ago
        ("2026-06-01", "2026-06-05", None),  # feb-may ended 5 days before: closing
    ],
)
def test_the_previous_season_closes_for_a_period_after_it_ends(before, today, window):
    expected = window if window else None
    if before == "2026-06-01":
        expected = ("2026-02-15", "2026-05-31")
    assert monitor.closing_window(before, today) == expected


def test_the_command_also_closes_the_previous_season(tmp_path, monkeypatch):
    seen = []

    def run_update(job, steps=None, log=print, closing=()):
        seen.append((job, closing))
        return {"ok": True, "window": [job.start, job.end], "through": job.through, "last_day_stations": None,
                "last_day_tempo": None, "steps": {}}  # fmt: skip

    monkeypatch.setattr(monitor, "run_update", run_update)
    runner = CliRunner()

    runner.invoke(app, ["update", "--through", "2026-11-10", "--data-dir", str(tmp_path)])
    runner.invoke(app, ["update", "--through", "2027-01-20", "--data-dir", str(tmp_path)])  # between seasons
    runner.invoke(
        app, ["update", "--through", "2026-11-10", "--season", "2026-11-01:2026-12-31", "--data-dir", "x"]
    )

    (job, closing), (gap_job, gap_closing), (_, explicit_closing) = seen
    assert (job.start, job.through) == ("2026-11-01", "2026-11-10")
    assert [(c.start, c.end, c.through) for c in closing] == [("2026-06-01", "2026-10-31", "2026-10-31")]
    assert (gap_job.start, gap_job.through, gap_closing) == ("2026-11-01", "2026-12-31", ())
    assert explicit_closing == ()  # an explicit season is the only one updated


def station_files(job: monitor.Job, hours: dict[int, str]) -> None:
    raw = job.data_dir / "raw" / "openaq"
    raw.mkdir(parents=True)
    pd.DataFrame(
        {"sensor": list(hours), "h": [pd.Timestamp(h) for h in hours.values()], "value": 0.01}
    ).to_parquet(raw / f"openaq_{job.start}_{job.after}.parquet")


def test_the_refetch_starts_before_the_laggiest_live_sensor_and_ignores_dead_ones(tmp_path):
    job = make_job(tmp_path, through="2026-11-20")
    station_files(
        job,
        {1: "2026-11-15 10:00", 2: "2026-11-09 23:00", 3: "2026-11-02 08:00", 4: "2026-11-01 05:00"},
    )
    path = job.data_dir / "raw" / "openaq" / f"openaq_{job.start}_{job.after}.parquet"

    first = monitor.openaq_refetch_start(path, job.start)

    # sensor 4 is 14 days behind (alive): it sets the start, bounded by the season
    assert first == "2026-11-01"
    station_files_dead = pd.DataFrame(
        {
            "sensor": [1, 2],
            "h": [pd.Timestamp("2026-12-20 10:00"), pd.Timestamp("2026-11-02 10:00")],
            "value": 0.01,
        }
    )
    station_files_dead.to_parquet(path)
    assert (
        monitor.openaq_refetch_start(path, job.start)
        == (pd.Timestamp("2026-12-20") - pd.Timedelta(days=monitor.OVERLAP_DAYS)).date().isoformat()
    )  # sensor 2 is dead (48 days behind): it does not pull the window back
    assert monitor.openaq_refetch_start(tmp_path / "missing.parquet", job.start) == "2026-11-01"


def test_the_openaq_step_with_nothing_new_is_ok_and_with_nothing_at_all_blocks_its_dependents(
    tmp_path, monkeypatch
):
    job = make_job(tmp_path, through="2026-11-02")
    interim = job.data_dir / "interim"

    monkeypatch.setattr(
        monitor.openaq, "run_fetch", lambda *a: monitor.openaq.Fetched(None, None, 0, ["sensor 10 skipped"])
    )
    nothing = monitor.fetch_openaq_step(job)
    assert nothing.blocked and "no table of the season" in nothing.detail

    raw, table = job.runs_dir / "raw.parquet", interim / "t.parquet"
    monkeypatch.setattr(monitor.openaq, "run_fetch", lambda *a: monitor.openaq.Fetched(raw, table, 0, []))
    quiet = monitor.fetch_openaq_step(job)
    assert not quiet.blocked and quiet.detail.endswith("0 new hours") and quiet.paths == [raw, table]

    def blocked_openaq(job):
        return monitor.Outcome("nothing yet", [], ["nothing yet"], blocked=True)

    steps = tuple(
        monitor.Step(s.name, blocked_openaq if s.name == "openaq" else recorder([], s.name).run, s.needs)
        for s in monitor.STEPS
    )
    status = monitor.run_update(job, steps, log=lambda _: None)

    assert status["ok"]  # waiting is not a failure
    assert status["steps"]["openaq"]["level"] == "warn"
    for name in ("qc_tempo", "flux_divergence", "weekly_index"):
        assert status["steps"][name]["skipped"] and status["steps"][name]["level"] == "skipped"
    assert status["steps"]["weather"]["level"] == "ok" and status["steps"]["tempo"]["level"] == "ok"


def test_run_update_also_runs_the_closing_season_with_its_own_end_as_through(tmp_path):
    calls: list[tuple[str, str]] = []

    def run(job):
        calls.append((job.start, job.through))
        return monitor.Outcome("done")

    steps = (monitor.Step("openaq", run),)
    closing = monitor.Job("2026-06-01", "2026-10-31", "2026-10-31", tmp_path / "data", tmp_path / "runs")

    status = monitor.run_update(
        make_job(tmp_path, "2026-11-02"), steps, log=lambda _: None, closing=(closing,)
    )

    assert calls == [("2026-11-01", "2026-11-02"), ("2026-06-01", "2026-10-31")]
    assert status["closing"][0]["window"] == ["2026-06-01", "2026-10-31"] and status["ok"]
    assert "Closing season 2026-06-01 to 2026-10-31" in monitor.summary(status)


# --- Lock, atomic writes, honest status ---------------------------------------------------------------------


def test_a_second_update_is_refused_while_the_first_holds_the_lock(tmp_path):
    job = make_job(tmp_path)

    with monitor.update_lock(job.monitor_dir):
        with pytest.raises(monitor.UpdateRunningError, match="already running"):
            monitor.run_update(job, steps_like([]), log=lambda _: None)
        refused = CliRunner().invoke(
            app,
            [
                "update",
                "--through",
                "2026-11-10",
                "--data-dir",
                str(job.data_dir),
                "--runs-dir",
                str(job.runs_dir),
            ],
        )
    assert refused.exit_code == 3 and "already running" in refused.output

    monitor.run_update(job, steps_like([]), log=lambda _: None)  # the lock was released


def test_a_writer_that_raises_midway_leaves_the_old_file_intact(tmp_path):
    from nox_ml.atomic import atomic_path, write_text

    path = tmp_path / "table.csv"
    path.write_text("old\n")

    with pytest.raises(OSError), atomic_path(path) as tmp:
        tmp.write_text("new but half")
        raise OSError("disk full")

    assert path.read_text() == "old\n" and [p.name for p in tmp_path.iterdir()] == ["table.csv"]
    write_text(path, "new\n")
    assert path.read_text() == "new\n" and [p.name for p in tmp_path.iterdir()] == ["table.csv"]


def test_warnings_make_a_step_warn_and_the_status_counts_staleness_without_failing(tmp_path):
    job = make_job(tmp_path, through="2026-11-10")
    interim = job.data_dir / "interim"
    interim.mkdir(parents=True)
    pd.DataFrame({"utc": [pd.Timestamp("2026-11-03 18:00")], "NOX": [10.0]}).to_parquet(
        interim / f"openaq_nox_2026-11-01_{job.after}.parquet"
    )

    def noisy(job):
        return monitor.Outcome("done", [], ["2 checks fail: r = -0.1", "granule X: error: ValueError"])

    steps = (monitor.Step("tempo", noisy), monitor.Step("quiet", lambda job: monitor.Outcome("fine")))

    status = monitor.run_update(job, steps, log=lambda _: None)

    assert status["ok"] is True
    assert status["steps"]["tempo"]["level"] == "warn" and status["steps"]["quiet"]["level"] == "ok"
    assert [w["message"] for w in status["warnings"]] == [
        "2 checks fail: r = -0.1",
        "granule X: error: ValueError",
    ]
    assert status["warnings"][0]["step"] == "tempo"
    assert status["stale_days"] == {"stations": 7, "tempo": None}
    assert "with warnings" in monitor.summary(status) and "tempo: WARN" in monitor.summary(status)


def test_the_qc_and_tempo_steps_report_their_problems_as_warnings(tmp_path, monkeypatch):
    from nox_ml.data import qc, simat

    job = make_job(tmp_path)
    checks = [qc.Check(True, "fine"), qc.Check(False, "TEMPO vs station NO2: r = -0.2")]
    monkeypatch.setattr(monitor.tempo, "run_qc", lambda *a, **k: checks)
    monkeypatch.setattr(simat, "load_catalog", lambda *a: None)
    qc_outcome = monitor.qc_tempo_step(job)
    assert qc_outcome.warnings == ["TEMPO vs station NO2: r = -0.2"]

    counts = {"found": 5, "new": 3, "failed": 1, "redownloaded": 1, "errors": ["g1: error: ValueError"]}
    monkeypatch.setattr(monitor.tempo, "fetch_window", lambda *a: counts)
    fetched = monitor.fetch_tempo_step(job)
    assert "1 downloaded again" in fetched.detail
    assert fetched.warnings[0] == "g1: error: ValueError" and "without their file" in fetched.warnings[1]
