# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Keeping the current season up to date: `nox-ml update`.

One call extends, in order, the inputs of a season window (stations, weather, TEMPO) and the monitoring
outputs (satellite emission of the city, weekly index of the stations) up to a day. Each step is idempotent,
so the call can run from a timer every day; a step that fails does not stop the independent ones, and
`status.json` says what worked.

File naming: every table keeps the name of the **full** season window (``openaq_nox_2026-11-01_2027-01-01``,
``tempo_pixels_2026-11-01_2026-12-31``, ``flux_divergence/2026-11-01_2026-12-31``), the one the analyses read
(`inputs.openaq_sources`, `products.sources_for`), even when the data only reach mid-season. The files grow
in place: OpenAQ merges the new hours into the raw table and refetches the last `OVERLAP_DAYS` (the feed is
revised), the weather refetches the window (the ERA5 boundary layer arrives days after the winds) and TEMPO
adds the granules the manifest does not have. The satellite emission and the weekly index are recomputed.
Every write goes through a temporary file and `os.replace` (`nox_ml.atomic`), and a lock file under
``runs/monitor`` stops two updates from running at once.

Seasons end while the data still lag (OpenAQ ~2 weeks): for `CLOSING_DAYS` after a season ends, `run_update`
also runs the previous season with `through` = its end, so its last days are picked up when they arrive.

Data arrive late: OpenAQ and TEMPO a few days after the day, so by default the update goes up to today minus
`PUBLICATION_LAG_DAYS`.
"""

import fcntl
import json
import os
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from nox_ml.atomic import atomic_path, write_text
from nox_ml.data import openaq, tempo, weather
from nox_ml.data.inputs import openaq_sources
from nox_ml.data.qc import Check
from nox_ml.time import utc_to_local
from nox_ml.validation import products

SEASONS = (("11-01", "12-31"), ("02-15", "05-31"), ("06-01", "10-31"))  # nov-dec, feb-may, rainy
PUBLICATION_LAG_DAYS = 3
OVERLAP_DAYS = (
    7  # OpenAQ days refetched before the last hour of the laggiest live sensor (cheap: 24 rows a day)
)
DEAD_SENSOR_DAYS = (
    21  # a sensor whose last hour is this far behind the newest one does not set the refetch start
)
# after a season ends, the previous one is still updated for this many days (late OpenAQ data)
CLOSING_DAYS = 21
STATUS_FILE = "status.json"
LOCK_FILE = "update.lock"


@dataclass(frozen=True)
class Job:
    """What one update does: the season `start`..`end` (inclusive dates, the full window) up to `through`
    (inclusive), reading and writing `data_dir` and `runs_dir`."""

    start: str
    end: str
    through: str
    data_dir: Path
    runs_dir: Path

    @property
    def after(self) -> str:
        """The day after the window: the end (exclusive) that names the OpenAQ files."""
        return (pd.Timestamp(self.end) + pd.Timedelta(days=1)).date().isoformat()

    @property
    def through_exclusive(self) -> str:
        return (pd.Timestamp(self.through) + pd.Timedelta(days=1)).date().isoformat()

    @property
    def monitor_dir(self) -> Path:
        return self.runs_dir / "monitor"


@dataclass(frozen=True)
class Outcome:
    """What a step did: a short text and the files it wrote."""

    detail: str
    paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(
        default_factory=list
    )  # worked, but something to look at (status level "warn")
    blocked: bool = False  # worked, but produced nothing the steps that need it can read: they are skipped


Action = Callable[[Job], Outcome]


@dataclass(frozen=True)
class Step:
    name: str
    run: Action
    needs: tuple[str, ...] = ()  # steps that must have worked


def season_of(day: date | str) -> tuple[str, str] | None:
    """The season window (first, last day as ISO dates) that contains `day`, or None in January and the first
    half of February, which no season covers."""
    d = pd.Timestamp(day)
    for first, last in SEASONS:
        start, end = pd.Timestamp(f"{d.year}-{first}"), pd.Timestamp(f"{d.year}-{last}")
        if start <= d <= end:
            return start.date().isoformat(), end.date().isoformat()
    return None


def previous_season(day: date | str) -> tuple[str, str] | None:
    """The latest season (first, last day as ISO dates) that ended before `day`."""
    d = pd.Timestamp(day)
    ended = [
        (pd.Timestamp(f"{y}-{last}"), pd.Timestamp(f"{y}-{first}"))
        for y in (d.year - 1, d.year)
        for first, last in SEASONS
        if pd.Timestamp(f"{y}-{last}") < d
    ]
    if not ended:
        return None
    end, start = max(ended)
    return start.date().isoformat(), end.date().isoformat()


def closing_window(before: date | str, today: date | str, days: int = CLOSING_DAYS) -> tuple[str, str] | None:
    """The season that ended before `before` (the start of the one being updated) if it ended at most `days`
    days before `today`: its last days may still arrive."""
    previous = previous_season(before)
    if previous and 0 <= (pd.Timestamp(today) - pd.Timestamp(previous[1])).days <= days:
        return previous
    return None


def default_through(today: date, lag: int = PUBLICATION_LAG_DAYS) -> str:
    return (pd.Timestamp(today) - pd.Timedelta(days=lag)).date().isoformat()


# --- Status ------------------------------------------------------------------------------------------------


def last_station_day(job: Job) -> str | None:
    """The last local day with station NOx in the season's OpenAQ table."""
    path = job.data_dir / "interim" / f"openaq_nox_{job.start}_{job.after}.parquet"
    if not path.exists():
        return None
    table = pd.read_parquet(path, columns=["utc", "NOX"])
    utc = table.loc[table["NOX"].notna(), "utc"]
    return None if utc.empty else utc_to_local(utc.max()).date().isoformat()


def last_tempo_day(job: Job) -> str | None:
    """The last local day with TEMPO pixels in the season's table."""
    path = job.data_dir / "interim" / f"tempo_pixels_{job.start}_{job.end}.parquet"
    if not path.exists():
        return None
    local = pd.read_parquet(path, columns=["local"])["local"]
    return None if local.empty else local.max().date().isoformat()


# --- Steps -------------------------------------------------------------------------------------------------


def openaq_refetch_start(path: Path, season_start: str) -> str:
    """The first day to ask OpenAQ for: `OVERLAP_DAYS` before the earliest of the last hours of the sensors in
    the raw file at `path`, so a sensor that lags the others still gets its old hours. A sensor whose last
    hour is more than `DEAD_SENSOR_DAYS` behind the newest one is dead and does not count. The season start
    when there is no file."""
    if not path.exists():
        return season_start
    last = pd.read_parquet(path, columns=["sensor", "h"]).groupby("sensor")["h"].max()
    if last.empty:
        return season_start
    live = last[last >= last.max() - pd.Timedelta(days=DEAD_SENSOR_DAYS)]
    first = live.min().normalize() - pd.Timedelta(days=OVERLAP_DAYS)
    return max(pd.Timestamp(season_start), first).date().isoformat()


def fetch_openaq_step(job: Job) -> Outcome:
    """Stations: the hours from `openaq_refetch_start` to `through`, merged into the season's files. No new
    measurements is a valid outcome (the feed lags); with no table of the season either, the steps that need
    the stations wait (`Outcome.blocked`)."""
    raw = job.data_dir / "raw" / "openaq" / f"openaq_{job.start}_{job.after}.parquet"
    first = min(openaq_refetch_start(raw, job.start), job.through)
    fetched = openaq.run_fetch(first, job.through_exclusive, job.data_dir, (job.start, job.after))
    if fetched.raw is None or fetched.interim is None:
        message = f"no measurements for {first} to {job.through} and no table of the season yet"
        return Outcome(message, warnings=[message, *fetched.skipped], blocked=True)
    return Outcome(
        f"{first} to {job.through}: {fetched.new_hours} new hours",
        [fetched.raw, fetched.interim],
        fetched.skipped,
    )


def fetch_weather_step(job: Job) -> Outcome:
    """Airport reports and ERA5 of the window up to `through`, merged into the files of 2024-2026."""
    sources = openaq_sources(job.start, job.after)
    covered = weather.run_fetch(
        job.start, job.through_exclusive, job.data_dir / "raw", sources.metar, sources.era5
    )
    paths = [job.data_dir / "raw" / "metar" / name for name in sources.metar]
    paths.append(job.data_dir / "raw" / "era5_openmeteo" / sources.era5)
    return Outcome("; ".join(f"{name}: to {last}" for name, (_, last) in covered.items()), paths)


def fetch_tempo_step(job: Job) -> Outcome:
    """TEMPO granules of the window up to `through` that `raw/tempo` does not have. A few failed downloads
    do not stop the season (the next update tries them again); only when every new granule failed."""
    counts = tempo.fetch_window(job.data_dir / "raw" / "tempo", job.start, job.through)
    redownloaded = counts.get("redownloaded", 0)
    detail = f"{counts['found']} granules, {counts['new']} new, {counts['failed']} failed"
    if redownloaded:
        detail += f", {redownloaded} downloaded again (file missing)"
    if counts["failed"] and not counts["new"]:
        raise RuntimeError(detail)
    warnings = list(counts.get("errors", []))
    if counts["failed"] and not warnings:
        warnings = [f"{counts['failed']} granules failed"]
    if redownloaded:
        warnings.append(f"{redownloaded} granules were in the manifest without their file")
    return Outcome(detail, [job.data_dir / "raw" / "tempo" / tempo.MANIFEST], warnings)


def qc_tempo_step(job: Job) -> Outcome:
    """Pixels of the window against the season's station table."""
    from nox_ml.data import simat

    interim = job.data_dir / "interim"
    checks: list[Check] = tempo.run_qc(
        job.data_dir / "raw" / "tempo",
        interim,
        simat.load_catalog(job.data_dir / "raw" / "simat"),
        job.start,
        job.through,
        f"openaq_nox_{job.start}_{job.after}.parquet",
        table_end=job.end,
    )
    failed = [c.message for c in checks if c.ok is False]
    detail = "all checks pass" if not failed else f"{len(failed)} checks fail: " + "; ".join(failed)
    return Outcome(detail, [interim / f"tempo_pixels_{job.start}_{job.end}.parquet"], failed)


def flux_divergence_step(job: Job) -> Outcome:
    """Satellite-only emission of the city of each day, with its placebo."""
    record, daily = products.flux_divergence_record(job.data_dir, job.start, job.end)
    out = job.runs_dir / "flux_divergence"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{job.start}_{job.end}.json"
    write_text(path, json.dumps(record, indent=2) + "\n")
    with atomic_path(path.with_suffix(".csv")) as tmp:
        daily.rename_axis("day").to_csv(tmp)
    return Outcome(f"{len(daily)} days", [path, path.with_suffix(".csv")])


def weekly_index_step(job: Job) -> Outcome:
    """Weekly index of the stations: E7 change of each week over the normal business days of the season."""
    inputs = products.season_inputs(
        job.data_dir, job.start, job.end, products.sources_for(job.start, job.end)
    )
    excluded = products.reference_exclusions(job.data_dir, job.start, job.end, pd.DatetimeIndex([]))
    index = products.weekly_index(inputs, products.estimator("change"), excluded)
    job.monitor_dir.mkdir(parents=True, exist_ok=True)
    path = job.monitor_dir / f"weekly_index_{job.start}_{job.end}.csv"
    with atomic_path(path) as tmp:
        index.to_csv(tmp, index=False)
    return Outcome(f"{len(index)} weeks", [path])


STEPS = (
    Step("openaq", fetch_openaq_step),
    Step("weather", fetch_weather_step),
    Step("tempo", fetch_tempo_step),
    Step("qc_tempo", qc_tempo_step, ("openaq", "tempo")),
    Step("flux_divergence", flux_divergence_step, ("openaq", "weather", "qc_tempo")),
    Step("weekly_index", weekly_index_step, ("openaq", "weather")),
)


# --- Orchestration -----------------------------------------------------------------------------------------


class UpdateRunningError(RuntimeError):
    """Another `nox-ml update` holds the lock."""


@contextmanager
def update_lock(monitor_dir: Path) -> Iterator[None]:
    """Hold ``<monitor_dir>/update.lock`` (`fcntl.flock`, non-blocking) while the body runs. The operating
    system drops the lock if the process dies. Raises `UpdateRunningError` when someone else has it."""
    monitor_dir.mkdir(parents=True, exist_ok=True)
    path = monitor_dir / LOCK_FILE
    with open(path, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            handle.seek(0)
            owner = handle.read().strip()
            raise UpdateRunningError(
                f"another update is already running{f' (pid {owner})' if owner else ''}: lock {path}"
            ) from error
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _level(record: dict) -> str:
    """``failed``, ``skipped`` (waiting for a step that produced nothing), ``warn`` (worked, with warnings) or
    ``ok``."""
    if not record["ok"]:
        return "failed"
    if record.get("skipped"):
        return "skipped"
    return "warn" if record.get("warnings") else "ok"


def run_steps(job: Job, steps: tuple[Step, ...] | None = None, log: Callable[[str], None] = print) -> dict:
    """Run `steps` in order. A step whose `needs` did not work is skipped; an exception only fails its step.
    Returns the record of every step: ``ok``, ``level``, ``detail`` or ``error``, ``warnings``, ``seconds``,
    ``files``. ``ok`` is false only for failures: a step that worked with warnings, or that waits for a
    step with nothing to offer yet (``blocked``), is ok."""
    results: dict[str, dict] = {}
    for step in steps or STEPS:
        missing = [n for n in step.needs if not results.get(n, {}).get("ok") or results[n].get("blocked")]
        if missing:
            failed = [n for n in missing if not results.get(n, {}).get("ok")]
            reason = f"needs {', '.join(missing)}"
            if failed:
                results[step.name] = {"ok": False, "skipped": True, "error": reason}
            else:  # the needed steps worked but have nothing yet: wait, not a failure
                results[step.name] = {"ok": True, "skipped": True, "blocked": True, "detail": reason}
            results[step.name]["level"] = _level(results[step.name])
            log(f"{step.name}: skipped ({reason})")
            continue
        started = time.time()
        try:
            outcome = step.run(job)
            results[step.name] = {
                "ok": True,
                "detail": outcome.detail,
                "files": [str(p) for p in outcome.paths],
                "warnings": list(outcome.warnings),
            }
            if outcome.blocked:
                results[step.name]["blocked"] = True
            log(f"{step.name}: {outcome.detail}")
            for warning in outcome.warnings:
                log(f"{step.name}: warning: {warning}")
        except Exception as error:  # a step is an external process in spirit: record it, go on
            results[step.name] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            log(f"{step.name}: FAILED {type(error).__name__}: {error}")
            log(traceback.format_exc(limit=3))
        results[step.name]["level"] = _level(results[step.name])
        results[step.name]["seconds"] = round(time.time() - started, 1)
    return results


def stale_days(through: str, last_day: str | None) -> int | None:
    """Days between `through` and the last day a source has data (None without data; 0 if up to date)."""
    if last_day is None:
        return None
    return max(0, (pd.Timestamp(through) - pd.Timestamp(last_day)).days)


def _job_status(job: Job, steps: tuple[Step, ...] | None, log: Callable[[str], None]) -> dict:
    results = run_steps(job, steps, log)
    stations, tempo_day = last_station_day(job), last_tempo_day(job)
    return {
        "window": [job.start, job.end],
        "through": job.through,
        "last_day_stations": stations,
        "last_day_tempo": tempo_day,
        "stale_days": {
            "stations": stale_days(job.through, stations),
            "tempo": stale_days(job.through, tempo_day),
        },
        "ok": all(r["ok"] for r in results.values()),
        "warnings": [
            {"season": job.start, "step": name, "message": w}
            for name, r in results.items()
            for w in r.get("warnings", [])
        ],
        "steps": results,
        "outputs": sorted({f for r in results.values() for f in r.get("files", [])}),
    }


def run_update(
    job: Job,
    steps: tuple[Step, ...] | None = None,
    log: Callable[[str], None] = print,
    closing: tuple[Job, ...] = (),
) -> dict:
    """Run the steps of `job`, then of each job in `closing` (the previous season, `closing_window`), write
    ``runs/monitor/status.json`` and return its content: the window, the last day with stations and with
    TEMPO and how many days they are behind `through` (``stale_days``), the steps (each ``ok``, ``warn``,
    ``skipped`` or ``failed`` in ``level``), the ``warnings``, the files written and the time. The closing
    seasons are listed in ``closing`` with the same fields. ``ok`` is false only when a step failed; warnings
    leave it true. Raises `UpdateRunningError` if another update holds the lock."""
    with update_lock(job.monitor_dir):
        started = datetime.now(UTC)
        status = _job_status(job, steps, log)
        status["closing"] = [_job_status(c, steps, log) for c in closing]
        parts = [status, *status["closing"]]
        status["ok"] = all(p["ok"] for p in parts)
        status["warnings"] = [w for p in parts for w in p["warnings"]]
        status["outputs"] = sorted({f for p in parts for f in p["outputs"]})
        status["started_utc"] = started.isoformat(timespec="seconds")
        status["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
        write_text(job.monitor_dir / STATUS_FILE, json.dumps(status, indent=2) + "\n")
    return status


def summary(status: dict) -> str:
    """The status as a few lines of text."""
    first, last = status["window"]
    verdict = "with failures" if not status["ok"] else "with warnings" if status.get("warnings") else "ok"
    lines = [f"Season {first} to {last}, updated through {status['through']} ({verdict})"]
    for part in [status, *status.get("closing", [])]:
        if part is not status:
            lines.append(
                f"Closing season {part['window'][0]} to {part['window'][1]} (through {part['through']})"
            )
        stale = part.get("stale_days", {})
        lines.append(
            f"Last day with stations: {part['last_day_stations']} ({stale.get('stations')} days behind); "
            f"with TEMPO: {part['last_day_tempo']} ({stale.get('tempo')} days behind)"
        )
        for name, r in part["steps"].items():
            label = {"ok": "ok", "warn": "WARN", "skipped": "skipped", "failed": "FAILED"}[r["level"]]
            lines.append(f"  {name}: {label} - {r.get('detail') or r.get('error')}")
    return "\n".join(lines)
