# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Planetary boundary layer height (PBLH): ERA5 (Open-Meteo) filled with bias-corrected MERRA-2.

ERA5 from Open-Meteo is hourly and available for 2023 and early 2024, but has a gap in 2024. MERRA-2
(M2T1NXFLX, hourly averages centred at hh:30) covers it. MERRA-2 is converted to on-the-hour values, compared
with ERA5 where both exist (Jan-Jun 2023, the same months as the gap) and corrected with a multiplicative
factor per local hour (median ERA5 / MERRA-2). The correction is validated out of sample (fit Jan-Mar 2023,
evaluate Apr-Jun 2023).

Pure functions do the arithmetic; the I/O layer at the end downloads (NASA OPeNDAP, needs `~/.netrc` for
Earthdata) and reads files.
"""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data.domain import AFTERNOON_HOURS, LOCAL_UTC_OFFSET
from nox_ml.data.qc import Check

COLLECTION = "C1276812838-GES_DISC"
# MERRA-2 grid indices (lat -90:0.5:90, lon -180:0.625:179.375): lat 19.0-20.0, lon -100.0 to -98.75.
LAT_INDICES, LON_INDICES = "218:1:220", "128:1:130"
# Cell 19.5 N, 99.375 W: closest to the ERA5 Open-Meteo cell (19.5 N, 99.25 W).
CELL = (1, 1)
MERRA_DAYS = ("2023-01-01", "2024-06-30")
FIT_PERIOD = ("2023-01", "2023-06")
VALIDATION_TRAIN = ("2023-01", "2023-03")
VALIDATION_TEST = ("2023-04", "2023-06")
OUTPUT_PERIOD = ("2023-11-01", "2024-06-30 23:00")
MIN_MERRA_PBL_M = 50.0  # floor in the denominator, so near-zero night values do not blow up the ratio
ERA5_FILE = "pbl_wind_center_2023-2024_full.json"
ERA5_SOURCE, MERRA_SOURCE, MISSING_SOURCE = "ERA5", "MERRA-2 corrected", "missing"


# --- Pure functions ----------------------------------------------------------------------------------------


def merra_request(day: pd.Timestamp) -> tuple[str, str]:
    """OPeNDAP URL (3x3 cells around Mexico City, PBLH only) and local file name for one day."""
    name = f"MERRA2_400.tavg1_2d_flx_Nx.{day:%Y%m%d}.nc4"
    constraint = (
        f"/PBLH%5B0:1:23%5D%5B{LAT_INDICES}%5D%5B{LON_INDICES}%5D;/lat%5B{LAT_INDICES}%5D;"
        f"/lon%5B{LON_INDICES}%5D;/time"
    )
    url = (
        f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}/granules/M2T1NXFLX.5.12.4%3A{name}"
        f".dap.nc4?dap4.ce={constraint}"
    )
    return url, name.replace(".nc4", "_cdmx.nc4")


def parse_era5(payload: dict) -> pd.Series:
    """Hourly UTC series of boundary layer height (m) from an Open-Meteo response."""
    hourly = payload["hourly"]
    return pd.Series(hourly["boundary_layer_height"], index=pd.to_datetime(hourly["time"]), dtype=float)


def merra_to_hourly(m2: pd.Series) -> pd.Series:
    """MERRA-2 hour averages (stamped hh:30) -> on-the-hour values, the ERA5 convention.

    Averages each reading with the previous one, as the research script did. NOTE: that value belongs at
    hh:00 of the reading's own hour, but it is stamped one hour later (hh+1:00), so MERRA-2 lags ERA5 by
    an hour (correlation with ERA5 0.85, vs 0.89 with the stamp one hour earlier). Kept to reproduce the
    research numbers; see the PR.
    """
    on_hour = (m2 + m2.shift(1)) / 2
    on_hour.index = on_hour.index.floor("h") + pd.Timedelta(hours=1)
    return on_hour[~on_hour.index.duplicated()]


def local_hour(index: pd.DatetimeIndex) -> pd.Index:
    return pd.Index((index - LOCAL_UTC_OFFSET).hour)


def paired(era: pd.Series, merra: pd.Series) -> pd.DataFrame:
    """Hours with both ERA5 and MERRA-2 (columns `era5`, `merra2`, `h_local`)."""
    both = pd.concat({"era5": era, "merra2": merra}, axis=1, sort=True).dropna()
    both["h_local"] = local_hour(both.index)
    return both


def hourly_factor(both: pd.DataFrame) -> pd.Series:
    """Median ERA5 / MERRA-2 per local hour."""
    ratio = both["era5"] / both["merra2"].clip(lower=MIN_MERRA_PBL_M)
    return ratio.groupby(both["h_local"]).median()


def apply_factor(merra: pd.Series, factor: pd.Series) -> pd.Series:
    hours = pd.Series(local_hour(pd.DatetimeIndex(merra.index)), index=merra.index)
    return merra * hours.map(factor).to_numpy()


def afternoon_stats(both: pd.DataFrame) -> pd.DataFrame:
    """MERRA-2 vs ERA5 agreement per afternoon local hour (fit period)."""
    fit = both.loc[FIT_PERIOD[0] : FIT_PERIOD[1]]
    fit = fit[fit["h_local"].isin(AFTERNOON_HOURS)]
    rows = {
        h: {
            "n": len(g),
            "era5_med": g["era5"].median(),
            "merra2_med": g["merra2"].median(),
            "bias_m": (g["merra2"] - g["era5"]).median(),
            "r": g["era5"].corr(g["merra2"]),
            "factor": (g["era5"] / g["merra2"]).median(),
        }
        for h, g in fit.groupby("h_local")
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def validate_correction(both: pd.DataFrame) -> dict[str, float]:
    """Fit the factor on `VALIDATION_TRAIN`, evaluate on `VALIDATION_TEST` (afternoon hours)."""
    train = both.loc[VALIDATION_TRAIN[0] : VALIDATION_TRAIN[1]]
    test = both.loc[VALIDATION_TEST[0] : VALIDATION_TEST[1]]
    corrected = test["merra2"] * test["h_local"].map(hourly_factor(train))
    pm = test["h_local"].isin(AFTERNOON_HOURS)
    raw_err = (test["merra2"] - test["era5"])[pm].abs()
    corr_err = (corrected - test["era5"])[pm].abs()
    return {
        "raw_abs_err_m": float(raw_err.median()),
        "raw_rel_err": float((raw_err / test["era5"][pm]).median()),
        "corrected_abs_err_m": float(corr_err.median()),
        "corrected_rel_err": float((corr_err / test["era5"][pm]).median()),
        "r": float(test["era5"][pm].corr(test["merra2"][pm])),
    }


def fill_gap(era: pd.Series, corrected_merra: pd.Series) -> pd.DataFrame:
    """ERA5 where it exists, corrected MERRA-2 elsewhere, over `OUTPUT_PERIOD`. Columns `pbl_m`, `source`."""
    idx = pd.date_range(OUTPUT_PERIOD[0], OUTPUT_PERIOD[1], freq="h", name="utc")
    out = pd.DataFrame(index=idx)
    out["pbl_m"] = era.reindex(idx)
    out["source"] = np.where(out["pbl_m"].notna(), ERA5_SOURCE, MERRA_SOURCE)
    gap = out["pbl_m"].isna()
    out.loc[gap, "pbl_m"] = corrected_merra.reindex(idx)[gap]
    out.loc[out["pbl_m"].isna(), "source"] = MISSING_SOURCE
    return out


# --- I/O ---------------------------------------------------------------------------------------------------


def fetch_day(day: pd.Timestamp, raw_dir: Path) -> tuple[Path, str]:
    """Download one MERRA-2 day with curl and the Earthdata `~/.netrc`.

    Returns the file and a status: 'cache', 'ok' or 'curl <exit code>'.
    """
    url, name = merra_request(day)
    dst = raw_dir / name
    if dst.exists() and dst.stat().st_size > 1000:
        return dst, "cache"
    cookies = str(Path.home() / ".urs_cookies")
    cmd = [
        "curl",
        "-sfL",
        "-n",
        "-c",
        cookies,
        "-b",
        cookies,
        "--retry",
        "3",
        "-m",
        "300",
        "-o",
        str(dst),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return dst, "ok" if result.returncode == 0 else f"curl {result.returncode}"


def fetch_merra2(raw_dir: Path, days: pd.DatetimeIndex, workers: int = 6) -> list[tuple[pd.Timestamp, str]]:
    """Download missing days; returns the (day, status) pairs that failed."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(lambda d: fetch_day(d, raw_dir), days))
    return [(d, s) for d, (_, s) in zip(days, results, strict=True) if s not in ("ok", "cache")]


def read_merra_file(path: Path) -> pd.Series:
    """PBLH (m) of the `CELL` for one day, stamped at the hh:30 centre of each hour (UTC)."""
    import netCDF4

    with netCDF4.Dataset(path) as d:
        t0 = pd.Timestamp(d["time"].units.split("since ")[1])
        t = t0 + pd.to_timedelta(d["time"][:], unit="min")
        return pd.Series(d["PBLH"][:, CELL[0], CELL[1]].filled(np.nan), index=t)


def read_merra2(raw_dir: Path, days: pd.DatetimeIndex) -> pd.Series:
    files = [raw_dir / merra_request(d)[1] for d in days]
    present = [f for f in files if f.exists() and f.stat().st_size > 1000]
    if not present:
        raise FileNotFoundError(f"No MERRA-2 files in {raw_dir}; run `nox-ml fetch-merra2` first")
    return pd.concat([read_merra_file(f) for f in present]).sort_index()


def run_fill(merra_dir: Path, era5_dir: Path, out_dir: Path) -> list[Check]:
    """Build `pbl_2023_2024.parquet` and `pbl_merra2_vs_era5.csv` in `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(*MERRA_DAYS, freq="D")
    merra = merra_to_hourly(read_merra2(merra_dir, days))
    era = parse_era5(json.loads((era5_dir / ERA5_FILE).read_text()))
    era = era.loc[MERRA_DAYS[0] : f"{MERRA_DAYS[1]} 23:00"]

    both = paired(era, merra)
    fit = both.loc[FIT_PERIOD[0] : FIT_PERIOD[1]]
    factor = hourly_factor(fit)
    stats = afternoon_stats(both)
    check_val = validate_correction(both)
    afternoon = fit[fit["h_local"].isin(AFTERNOON_HOURS)]

    checks = [
        Check(
            None, f"Factor per local hour ({FIT_PERIOD[0]} to {FIT_PERIOD[1]}): {factor.round(2).to_dict()}"
        ),
        Check(
            None,
            f"Afternoon: r = {afternoon['era5'].corr(afternoon['merra2']):.2f}, median bias MERRA-2 - ERA5 = "
            f"{(afternoon['merra2'] - afternoon['era5']).median():.0f} m",
        ),
        Check(
            None,
            "Out-of-sample afternoon error, median: "
            f"{check_val['raw_abs_err_m']:.0f} m ({check_val['raw_rel_err']:.0%}) raw, "
            f"{check_val['corrected_abs_err_m']:.0f} m ({check_val['corrected_rel_err']:.0%}) corrected",
        ),
    ]
    out = fill_gap(era, apply_factor(merra, factor))
    checks += [Check(None, f"{src}: {n} hours") for src, n in out["source"].value_counts().items()]

    out.to_parquet(out_dir / "pbl_2023_2024.parquet")
    stats.to_csv(out_dir / "pbl_merra2_vs_era5.csv")
    return checks
