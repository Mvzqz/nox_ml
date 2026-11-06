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

Data arrive late: OpenAQ and TEMPO a few days after the day, so by default the update goes up to today minus
`PUBLICATION_LAG_DAYS`.
"""

import json
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from nox_ml.data import openaq, tempo, weather
from nox_ml.data.inputs import openaq_sources
from nox_ml.data.qc import Check
from nox_ml.time import utc_to_local
from nox_ml.validation import products

SEASONS = (("11-01", "12-31"), ("02-15", "05-31"), ("06-01", "10-31"))  # nov-dec, feb-may, rainy
PUBLICATION_LAG_DAYS = 3
OVERLAP_DAYS = 3  # OpenAQ days refetched before the last one stored
STATUS_FILE = "status.json"


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


def _last_raw_day(path: Path) -> pd.Timestamp | None:
    if not path.exists():
        return None
    hours = pd.read_parquet(path, columns=["h"])["h"]
    return None if hours.empty else hours.max().normalize()


def fetch_openaq_step(job: Job) -> Outcome:
    """Stations: the hours from the last day stored (minus `OVERLAP_DAYS`) to `through`, merged into the
    season's files."""
    raw = job.data_dir / "raw" / "openaq" / f"openaq_{job.start}_{job.after}.parquet"
    last = _last_raw_day(raw)
    first = job.start
    if last is not None:
        first = max(pd.Timestamp(job.start), last - pd.Timedelta(days=OVERLAP_DAYS)).date().isoformat()
    raw, table = openaq.run_fetch(first, job.through_exclusive, job.data_dir, (job.start, job.after))
    return Outcome(f"{first} to {job.through}", [raw, table])


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
    detail = f"{counts['found']} granules, {counts['new']} new, {counts['failed']} failed"
    if counts["failed"] and not counts["new"]:
        raise RuntimeError(detail)
    return Outcome(detail, [job.data_dir / "raw" / "tempo" / tempo.MANIFEST])


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
    return Outcome(detail, [interim / f"tempo_pixels_{job.start}_{job.end}.parquet"])


def flux_divergence_step(job: Job) -> Outcome:
    """Satellite-only emission of the city of each day, with its placebo."""
    record, daily = products.flux_divergence_record(job.data_dir, job.start, job.end)
    out = job.runs_dir / "flux_divergence"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{job.start}_{job.end}.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    daily.rename_axis("day").to_csv(path.with_suffix(".csv"))
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
    index.to_csv(path, index=False)
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


def run_steps(job: Job, steps: tuple[Step, ...] | None = None, log: Callable[[str], None] = print) -> dict:
    """Run `steps` in order. A step whose `needs` did not work is skipped; an exception only fails its step.
    Returns the record of every step: ``ok``, ``detail`` or ``error``, ``seconds``, ``files``."""
    results: dict[str, dict] = {}
    for step in steps or STEPS:
        missing = [n for n in step.needs if not results.get(n, {}).get("ok")]
        if missing:
            results[step.name] = {"ok": False, "skipped": True, "error": f"needs {', '.join(missing)}"}
            log(f"{step.name}: skipped (needs {', '.join(missing)})")
            continue
        started = time.time()
        try:
            outcome = step.run(job)
            results[step.name] = {
                "ok": True,
                "detail": outcome.detail,
                "files": [str(p) for p in outcome.paths],
            }
            log(f"{step.name}: {outcome.detail}")
        except Exception as error:  # a step is an external process in spirit: record it, go on
            results[step.name] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            log(f"{step.name}: FAILED {type(error).__name__}: {error}")
            log(traceback.format_exc(limit=3))
        results[step.name]["seconds"] = round(time.time() - started, 1)
    return results


def run_update(job: Job, steps: tuple[Step, ...] | None = None, log: Callable[[str], None] = print) -> dict:
    """Run the steps of `job`, write ``runs/monitor/status.json`` and return its content: the window, the
    last day with stations and with TEMPO, the steps, the files written and the time."""
    started = datetime.now(UTC)
    results = run_steps(job, steps, log)
    status = {
        "window": [job.start, job.end],
        "through": job.through,
        "last_day_stations": last_station_day(job),
        "last_day_tempo": last_tempo_day(job),
        "ok": all(r["ok"] for r in results.values()),
        "steps": results,
        "outputs": sorted({f for r in results.values() for f in r.get("files", [])}),
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    job.monitor_dir.mkdir(parents=True, exist_ok=True)
    (job.monitor_dir / STATUS_FILE).write_text(json.dumps(status, indent=2) + "\n")
    return status


def summary(status: dict) -> str:
    """The status as a few lines of text."""
    first, last = status["window"]
    lines = [
        f"Season {first} to {last}, updated through {status['through']} "
        f"({'ok' if status['ok'] else 'with failures'})",
        f"Last day with stations: {status['last_day_stations']}; with TEMPO: {status['last_day_tempo']}",
    ]
    for name, r in status["steps"].items():
        lines.append(f"  {name}: {'ok' if r['ok'] else 'FAILED'} - {r.get('detail') or r.get('error')}")
    return "\n".join(lines)
