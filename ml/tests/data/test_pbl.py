# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
import json

import numpy as np
import pandas as pd
import pytest

from nox_ml.data import pbl


def test_merra_request_builds_the_daily_opendap_url_and_cache_name():
    url, name = pbl.merra_request(pd.Timestamp("2023-04-05"))

    assert name == "MERRA2_400.tavg1_2d_flx_Nx.20230405_cdmx.nc4"
    assert "M2T1NXFLX.5.12.4%3AMERRA2_400.tavg1_2d_flx_Nx.20230405.nc4.dap.nc4" in url
    assert "PBLH%5B0:1:23%5D%5B218:1:220%5D%5B128:1:130%5D" in url


def test_parse_era5_reads_hourly_boundary_layer_height():
    payload = {
        "hourly": {"time": ["2023-01-01T00:00", "2023-01-01T01:00"], "boundary_layer_height": [75, None]}
    }

    era = pbl.parse_era5(payload)

    assert era.index.tolist() == [pd.Timestamp("2023-01-01 00:00"), pd.Timestamp("2023-01-01 01:00")]
    assert era.iloc[0] == 75
    assert np.isnan(era.iloc[1])


def test_merra_to_hourly_averages_each_reading_with_the_previous_one():
    m2 = pd.Series([100.0, 200.0, 400.0], index=pd.date_range("2023-01-01 00:30", periods=3, freq="h"))

    on_hour = pbl.merra_to_hourly(m2)

    assert on_hour.loc["2023-01-01 01:00"] == 150.0
    assert on_hour.loc["2023-01-01 02:00"] == 300.0
    assert np.isnan(on_hour.loc["2023-01-01 00:00"])


def test_merra_to_hourly_stamps_a_linear_ramp_at_its_own_time():
    # A reading stamped hh:30 is the mean over [hh:00, hh+1:00]; for a ramp equal to the hour of the day
    # that mean is hh + 0.5, and the value at hh:00 must come out as hh (no lag against an on-the-hour one).
    readings = pd.date_range("2023-01-01 00:30", periods=6, freq="h")
    m2 = pd.Series(np.arange(6) + 0.5, index=readings)

    on_hour = pbl.merra_to_hourly(m2).dropna()

    np.testing.assert_allclose(on_hour.to_numpy(), on_hour.index.hour.to_numpy())


def test_merra_to_hourly_drops_duplicate_hours_when_days_overlap():
    day = pd.date_range("2023-01-01 00:30", periods=3, freq="h")
    m2 = pd.concat([pd.Series([1.0, 2.0, 3.0], index=day), pd.Series([1.0, 2.0, 3.0], index=day)])

    assert pbl.merra_to_hourly(m2).index.is_unique


def two_sources(era5, merra2, start="2023-01-01 18:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(era5), freq="D")
    return pbl.paired(pd.Series(era5, index=idx, dtype=float), pd.Series(merra2, index=idx, dtype=float))


def test_paired_keeps_only_hours_present_in_both_sources_with_local_hour():
    era = pd.Series([1.0, 2.0], index=pd.date_range("2023-01-01 18:00", periods=2, freq="h"))
    merra = pd.Series([3.0, np.nan], index=era.index)

    both = pbl.paired(era, merra)

    assert both.index.tolist() == [pd.Timestamp("2023-01-01 18:00")]
    assert both["h_local"].tolist() == [12]


def test_hourly_factor_is_the_median_ratio_per_local_hour():
    both = two_sources([100, 200, 300], [200, 400, 300])  # ratios 0.5, 0.5, 1.0, all at 12 h local

    assert pbl.hourly_factor(both).to_dict() == {12: 0.5}


def test_hourly_factor_floors_small_merra_values_at_50_m():
    both = two_sources([100.0], [1.0])

    assert pbl.hourly_factor(both).to_dict() == {12: 2.0}  # 100 / 50, not 100 / 1


def test_apply_factor_scales_each_value_by_the_factor_of_its_local_hour():
    merra = pd.Series([1000.0, 1000.0], index=pd.DatetimeIndex(["2023-01-01 18:00", "2023-01-01 19:00"]))

    corrected = pbl.apply_factor(merra, pd.Series({12: 0.9, 13: 0.5}))

    assert corrected.tolist() == [900.0, 500.0]


def test_apply_factor_gives_nan_for_hours_without_factor():
    merra = pd.Series([1000.0], index=pd.DatetimeIndex(["2023-01-01 18:00"]))

    assert np.isnan(pbl.apply_factor(merra, pd.Series({13: 0.5})).iloc[0])


def synthetic_half_year(factor=0.5) -> pd.DataFrame:
    """Jan-Jun 2023, hourly: ERA5 is `factor` times MERRA-2 at every hour."""
    idx = pd.date_range("2023-01-01", "2023-06-30 23:00", freq="h")
    merra = pd.Series(1000 + 500 * np.sin(np.arange(len(idx)) / 5.0), index=idx)
    return pbl.paired(merra * factor, merra)


def test_afternoon_stats_has_one_row_per_afternoon_local_hour():
    stats = pbl.afternoon_stats(synthetic_half_year())

    assert stats.index.tolist() == [12, 13, 14, 15, 16, 17]
    assert stats["factor"].round(6).unique().tolist() == [0.5]
    assert stats["n"].unique().tolist() == [181]


def test_validate_correction_removes_a_constant_bias_out_of_sample():
    result = pbl.validate_correction(synthetic_half_year())

    assert result["raw_abs_err_m"] > 100
    assert result["corrected_abs_err_m"] == pytest.approx(0.0, abs=1e-6)
    assert result["r"] == pytest.approx(1.0)


def test_fill_gap_uses_era5_first_then_corrected_merra_then_marks_missing(monkeypatch):
    monkeypatch.setattr(pbl, "OUTPUT_PERIOD", ("2024-03-01", "2024-03-01 03:00"))
    idx = pd.date_range("2024-03-01", periods=4, freq="h")
    era = pd.Series([100.0, np.nan, np.nan, np.nan], index=idx)
    merra = pd.Series([999.0, 200.0, np.nan, np.nan], index=idx)

    out = pbl.fill_gap(era, merra)

    assert out["pbl_m"].tolist()[:2] == [100.0, 200.0]
    assert np.isnan(out["pbl_m"].iloc[2])
    assert out["source"].tolist() == ["ERA5", "MERRA-2 corrected", "missing", "missing"]
    assert out.index.name == "utc"


def test_fill_gap_covers_every_hour_between_november_2023_and_june_2024():
    out = pbl.fill_gap(pd.Series(dtype=float), pd.Series(dtype=float))

    assert out.index[0] == pd.Timestamp("2023-11-01 00:00")
    assert out.index[-1] == pd.Timestamp("2024-06-30 23:00")
    assert len(out) == 243 * 24  # 61 + 31 + 29 + 31 + 30 + 31 + 30 days


# --- I/O ----------------------------------------------------------------------------------------------------


class FakeRun:
    def __init__(self, returncode: int):
        self.returncode = returncode


def test_fetch_day_downloads_with_netrc_and_reports_ok(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeRun(0)

    monkeypatch.setattr(pbl.subprocess, "run", fake_run)

    path, status = pbl.fetch_day(pd.Timestamp("2023-01-01"), tmp_path)

    assert status == "ok"
    assert path.name == "MERRA2_400.tavg1_2d_flx_Nx.20230101_cdmx.nc4"
    assert "-n" in calls[0]  # credentials come from ~/.netrc, never from the command line
    assert str(path) in calls[0]


def test_fetch_day_skips_files_already_downloaded(tmp_path, monkeypatch):
    (tmp_path / "MERRA2_400.tavg1_2d_flx_Nx.20230101_cdmx.nc4").write_bytes(b"x" * 2000)
    monkeypatch.setattr(pbl.subprocess, "run", lambda *a, **k: pytest.fail("should not download"))

    assert pbl.fetch_day(pd.Timestamp("2023-01-01"), tmp_path)[1] == "cache"


def test_fetch_day_redownloads_truncated_files(tmp_path, monkeypatch):
    (tmp_path / "MERRA2_400.tavg1_2d_flx_Nx.20230101_cdmx.nc4").write_bytes(b"x" * 10)
    monkeypatch.setattr(pbl.subprocess, "run", lambda *a, **k: FakeRun(0))

    assert pbl.fetch_day(pd.Timestamp("2023-01-01"), tmp_path)[1] == "ok"


def test_fetch_merra2_returns_only_the_days_that_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        pbl, "fetch_day", lambda day, raw_dir: (raw_dir / "f", "curl 22" if day.day == 2 else "ok")
    )

    failed = pbl.fetch_merra2(tmp_path / "new", pd.date_range("2023-01-01", periods=3, freq="D"))

    assert failed == [(pd.Timestamp("2023-01-02"), "curl 22")]
    assert (tmp_path / "new").is_dir()


def test_read_merra_file_returns_the_chosen_cell_stamped_at_half_hours(tmp_path, write_merra_file):
    path = write_merra_file(tmp_path / "day.nc4", "2023-01-01", np.arange(24) * 100.0)

    m2 = pbl.read_merra_file(path)

    assert m2.index[0] == pd.Timestamp("2023-01-01 00:30")
    assert m2.index[-1] == pd.Timestamp("2023-01-01 23:30")
    assert m2.iloc[5] == 500.0


def test_read_merra2_fails_clearly_when_nothing_was_downloaded(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch-merra2"):
        pbl.read_merra2(tmp_path, pd.date_range("2023-01-01", periods=2, freq="D"))


def test_read_merra2_skips_missing_days_and_orders_by_time(tmp_path, write_merra_file):
    write_merra_file(
        tmp_path / pbl.merra_request(pd.Timestamp("2023-01-02"))[1], "2023-01-02", np.full(24, 2.0)
    )
    write_merra_file(
        tmp_path / pbl.merra_request(pd.Timestamp("2023-01-01"))[1], "2023-01-01", np.full(24, 1.0)
    )

    m2 = pbl.read_merra2(tmp_path, pd.date_range("2023-01-01", periods=3, freq="D"))

    assert len(m2) == 48
    assert m2.index.is_monotonic_increasing
    assert m2.iloc[0] == 1.0


@pytest.fixture
def pbl_inputs(tmp_path, write_merra_file, monkeypatch):
    """Jan-Jun 2023 of MERRA-2 (1000 m) and ERA5 (500 m), except ERA5 is missing on 2023-06-02."""
    merra_dir, era5_dir = tmp_path / "merra2", tmp_path / "era5"
    merra_dir.mkdir()
    era5_dir.mkdir()
    days = pd.date_range("2023-01-01", "2023-06-30", freq="D")
    for day in days:
        write_merra_file(merra_dir / pbl.merra_request(day)[1], f"{day:%Y-%m-%d}", np.full(24, 1000.0))
    hours = pd.date_range("2023-01-01", "2023-06-30 23:00", freq="h")
    hours = hours[hours.date != pd.Timestamp("2023-06-02").date()]
    payload = {
        "hourly": {
            "time": [f"{t:%Y-%m-%dT%H:%M}" for t in hours],
            "boundary_layer_height": [500.0] * len(hours),
        }
    }
    (era5_dir / pbl.ERA5_FILE).write_text(json.dumps(payload))
    monkeypatch.setattr(pbl, "MERRA_DAYS", ("2023-01-01", "2023-06-30"))
    monkeypatch.setattr(pbl, "OUTPUT_PERIOD", ("2023-06-01", "2023-06-03 23:00"))
    return merra_dir, era5_dir


def test_run_fill_uses_era5_and_fills_its_gap_with_corrected_merra2(pbl_inputs, tmp_path):
    merra_dir, era5_dir = pbl_inputs
    out_dir = tmp_path / "interim"

    pbl.run_fill(merra_dir, era5_dir, out_dir)

    out = pd.read_parquet(out_dir / "pbl_2023_2024.parquet")
    by_day = out.groupby(out.index.day)
    assert by_day["source"].agg(lambda s: s.unique().tolist()).to_dict() == {
        1: ["ERA5"],
        2: ["MERRA-2 corrected"],
        3: ["ERA5"],
    }
    gap = out[out.index.day == 2]["pbl_m"].dropna()
    assert gap.iloc[0] == pytest.approx(500.0)  # factor 0.5 maps constant 1000 m to ERA5's 500 m
    assert (out_dir / "pbl_merra2_vs_era5.csv").exists()
