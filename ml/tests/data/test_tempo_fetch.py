# pyright: reportArgumentType=false
# (fakes stand in for inputs, models and the network; behavior is covered by the tests)
"""Downloading TEMPO granules without the network: CMR and the download are replaced by fakes."""

import json
from pathlib import Path

import netCDF4
import numpy as np
import pytest

from nox_ml.data import tempo

HREF = "https://data.example/TEMPO/{day}/TEMPO_NO2_L2_V04_{stamp}_S010G06.nc"
INSIDE = (19.5, -99.1)  # lat, lon in the domain
OUTSIDE = (30.0, -90.0)


def entry(stamp: str) -> dict:
    t = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}.000Z"
    day = f"{stamp[:4]}.{stamp[4:6]}.{stamp[6:8]}"
    links = [
        {"href": "s3://bucket/x.nc"},
        {"href": HREF.format(day=day, stamp=stamp)},
        {"href": "https://x/y.png"},
    ]
    return {"time_start": t, "links": links}


def feed(*stamps: str) -> bytes:
    return json.dumps({"feed": {"entry": [entry(s) for s in stamps]}}).encode()


def write_full_granule(path: Path, where=INSIDE) -> None:
    """A 4 x 5 granule (scanlines x pixels) with the variables of `tempo.KEEP`; the pixel at (1, 2) and its
    neighbours are at `where`, the rest far away."""
    lat = np.full((4, 5), OUTSIDE[0])
    lon = np.full((4, 5), OUTSIDE[1])
    lat[1:3, 2:4], lon[1:3, 2:4] = where
    with netCDF4.Dataset(path, "w") as ds:
        ds.title = "full granule"
        ds.createDimension("mirror_step", 4)
        ds.createDimension("xtrack", 5)
        ds.createDimension("corner", 4)
        for group, names in tempo.KEEP.items():
            g = ds.createGroup(group)
            for name in names:
                dims = ("mirror_step",) if name == "time" else ("mirror_step", "xtrack")
                if name.endswith("_bounds"):
                    dims += ("corner",)
                v = g.createVariable(name, "f8", dims, fill_value=-9e30)
                shape = tuple(ds.dimensions[d].size for d in dims)
                if name == "latitude":
                    v[:] = lat
                elif name == "longitude":
                    v[:] = lon
                else:
                    v[:] = np.ones(shape)


def fake_download(calls: list[str], fail: set[str] = frozenset()):
    def download(href: str, dst: Path) -> None:
        calls.append(href)
        if href in fail:
            raise RuntimeError("curl error 22")
        with tempo.HDF5_LOCK:  # the real download is curl; netCDF4 is not thread-safe
            write_full_granule(dst, OUTSIDE if "T190000Z" in href else INSIDE)

    return download


def test_months_of_a_window_are_cut_to_it():
    assert tempo.month_windows("2026-10-20", "2026-12-05") == [
        ("2026-10-20", "2026-10-31"),
        ("2026-11-01", "2026-11-30"),
        ("2026-12-01", "2026-12-05"),
    ]
    assert tempo.month_windows("2026-11-03", "2026-11-04") == [("2026-11-03", "2026-11-04")]


def test_only_afternoon_scans_with_an_https_link_are_kept():
    entries = [entry(s) for s in ("20261101T125519Z", "20261101T185519Z", "20261101T235519Z")]
    entries.append({"time_start": "2026-11-01T20:00:00.000Z", "links": [{"href": "s3://only/this.nc"}]})

    found = tempo.afternoon_granules(entries)

    assert [t.hour for t, _ in found] == [18, 23]
    assert all(href.startswith("https") for _, href in found)


def test_cmr_is_asked_month_by_month_and_a_full_page_is_an_error(monkeypatch):
    urls = []

    def get(url: str) -> bytes:
        urls.append(url)
        return feed("20261031T200000Z") if "2026-10-31T23" in url else feed("20261101T200000Z")

    found = tempo.list_granules("2026-10-31", "2026-11-01", get)

    assert len(urls) == 2 and len(found) == 2
    assert "temporal=2026-10-31T00:00:00Z,2026-10-31T23:59:59Z" in urls[0]
    assert "bounding_box=-99.35,19.25,-98.81,19.77" in urls[0]
    monkeypatch.setattr(tempo, "CMR_PAGE", 1)
    with pytest.raises(RuntimeError, match="split the window"):
        tempo.list_granules("2026-11-01", "2026-11-02", lambda url: feed("20261101T200000Z"))


def test_the_subset_keeps_the_box_around_the_domain_and_the_variables_the_qc_reads(tmp_path):
    src, dst = tmp_path / "TEMPO_NO2_L2_V04_20261101T200000Z_S010G06.nc", tmp_path / "subset.nc"
    write_full_granule(src)

    pixels = tempo.subset_granule(src, dst)

    assert pixels == 4
    with netCDF4.Dataset(dst) as ds:
        assert ds["product/vertical_column_troposphere"].shape == (2, 2)
        assert ds["geolocation/latitude_bounds"].shape == (2, 2, 4)
        assert ds.subset_rows == "1:3" and ds.subset_cols == "2:4"
        assert ds.source_granule == src.name and ds.title == "full granule"


def test_a_granule_with_no_pixel_in_the_domain_leaves_no_file(tmp_path):
    src = tmp_path / "g.nc"
    write_full_granule(src, OUTSIDE)

    assert tempo.subset_granule(src, tmp_path / "subset.nc") == 0
    assert not (tmp_path / "subset.nc").exists()


def test_fetch_window_stores_subsets_and_a_second_call_downloads_nothing(tmp_path):
    raw = tmp_path / "tempo"
    get = lambda url: feed("20261101T195519Z", "20261101T205519Z", "20261101T190000Z")  # noqa: E731
    calls: list[str] = []

    first = tempo.fetch_window(raw, "2026-11-01", "2026-11-01", get, fake_download(calls))
    second = tempo.fetch_window(raw, "2026-11-01", "2026-11-01", get, fake_download(calls))

    assert first == {"found": 3, "new": 3, "failed": 0, "skipped": 0}
    assert second == {"found": 3, "new": 0, "failed": 0, "skipped": 3}
    assert len(calls) == 3  # the one with no pixels is in the manifest, so it is not downloaded again
    assert sorted(p.name for p in raw.glob("*_zmvm.nc")) == [
        "TEMPO_NO2_L2_V04_20261101T195519Z_S010G06_zmvm.nc",
        "TEMPO_NO2_L2_V04_20261101T205519Z_S010G06_zmvm.nc",
    ]
    rows = tempo.read_manifest(raw / tempo.MANIFEST)
    assert {r["status"] for r in rows.values()} == {"ok", "no pixels"}
    assert not list(raw.glob("*.part"))


def test_files_without_a_manifest_row_are_skipped_and_a_failed_granule_is_retried(tmp_path):
    raw = tmp_path / "tempo"
    raw.mkdir()
    existing = raw / "TEMPO_NO2_L2_V04_20261101T195519Z_S010G06_zmvm.nc"
    existing.write_bytes(b"older download, no manifest row")
    get = lambda url: feed("20261101T195519Z", "20261101T205519Z")  # noqa: E731
    bad = HREF.format(day="2026.11.01", stamp="20261101T205519Z")
    calls: list[str] = []

    first = tempo.fetch_window(raw, "2026-11-01", "2026-11-01", get, fake_download(calls, {bad}))
    second = tempo.fetch_window(raw, "2026-11-01", "2026-11-01", get, fake_download(calls))

    assert first == {"found": 2, "new": 0, "failed": 1, "skipped": 1}
    assert second == {"found": 2, "new": 1, "failed": 0, "skipped": 1}
    assert existing.read_bytes() == b"older download, no manifest row"
    assert tempo.read_manifest(raw / tempo.MANIFEST)[bad.rsplit("/", 1)[1]]["status"] == "ok"
