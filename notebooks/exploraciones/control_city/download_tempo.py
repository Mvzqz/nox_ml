"""Download TEMPO NO2 L2 V04 granules and keep a subset around each control city.

Reuses `nox_ml.data.tempo` (CMR search by month, the afternoon filter, curl with ~/.netrc, the subset with its
margin and variables, the manifest fields), with the city box in place of the ZMVM domain. The difference with
`tempo.fetch_window`: each ~150 MB granule is downloaded once and cut for every city it covers (Monterrey,
Puebla and Toluca fall in the same granules as the ZMVM). One manifest per city,
`data/raw/tempo_<city>/manifest.csv`; subsets end in `_<city>.nc`.

Usage: .venv/bin/python notebooks/exploraciones/control_city/download_tempo.py 2025-02-15 2025-05-31 \
    monterrey puebla toluca [--workers 3]
"""

import argparse
import csv
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from nox_ml.data import tempo

sys.path.insert(0, str(Path(__file__).parent))
from cities import bbox

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw"
LOCK = threading.Lock()  # netCDF4/HDF5 is not thread safe, and the box is a module constant of `tempo`


@contextmanager
def city_box(city: str):
    """`tempo.BBOX` set to the city box (the CMR search and the subset read it)."""
    saved = tempo.BBOX
    tempo.BBOX = bbox(city)
    try:
        yield
    finally:
        tempo.BBOX = saved


def target(city: str, href: str) -> Path:
    return RAW / f"tempo_{city}" / href.rsplit("/", 1)[1].replace(".nc", f"_{city}.nc")


def fetch(scan: pd.Timestamp, href: str, cities: list[str], tmp_root: Path) -> list[tuple[str, dict]]:
    name = href.rsplit("/", 1)[1]
    base = {"granule": name, "time_utc": scan.isoformat(), "url": href}
    started = time.time()
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
        src = Path(tmp) / name
        try:
            tempo.download_granule(href, src)
        except RuntimeError as error:
            return [(c, base | {"status": f"error: {error}"}) for c in cities]
        rows = []
        for c in cities:
            dst = target(c, href)
            with LOCK, city_box(c):
                pixels = tempo.subset_granule(src, dst.with_suffix(".part"))
            if pixels:
                dst.with_suffix(".part").rename(dst)
            rows.append(
                (c, base | {
                    "original_bytes": src.stat().st_size,
                    "pixels_with_margin": pixels,
                    "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "seconds": round(time.time() - started),
                    "status": "ok" if pixels else "no pixels",
                })
            )  # fmt: skip
        return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("cities", nargs="+")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    todo: dict[str, tuple[pd.Timestamp, str, list[str]]] = {}
    for c in a.cities:
        folder = RAW / f"tempo_{c}"
        folder.mkdir(parents=True, exist_ok=True)
        known = {
            n
            for n, r in tempo.read_manifest(folder / tempo.MANIFEST).items()
            if r["status"] in tempo.DONE_STATUSES
        }
        with city_box(c):
            found = tempo.list_granules(a.start, a.end)
        for t, href in found:
            if not target(c, href).exists() and href.rsplit("/", 1)[1] not in known:
                todo.setdefault(href, (t, href, []))[2].append(c)
    print(f"{len(todo)} granules to fetch in {a.start}..{a.end} for {a.cities}", flush=True)
    tmp_root = RAW / ".tempo_tmp"
    tmp_root.mkdir(exist_ok=True)
    handles, writers = {}, {}
    for c in a.cities:
        path = RAW / f"tempo_{c}" / tempo.MANIFEST
        new = not path.exists()
        fields = (
            tempo.MANIFEST_FIELDS if new else path.read_text().splitlines()[0].split(",")
        )  # keep the header
        handles[c] = path.open("a", newline="")
        writers[c] = csv.DictWriter(handles[c], fields, restval="", extrasaction="ignore")
        if new:
            writers[c].writeheader()
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        futures = [ex.submit(fetch, t, h, cs, tmp_root) for t, h, cs in sorted(todo.values())]
        for done, f in enumerate(as_completed(futures), 1):
            for c, row in f.result():
                writers[c].writerow(row)
                handles[c].flush()
            if done % 50 == 0:
                print(f"[{done}/{len(todo)}] {time.time() - t0:.0f}s", flush=True)
    for h in handles.values():
        h.close()
    tmp_root.rmdir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
