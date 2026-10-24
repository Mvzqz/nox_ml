# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""SIMAT air-quality network (Mexico City): RAMA pollutants and REDMET meteorology.

Raw files are ZIP archives named `*.csv.gz`, with 9 header lines before the column names. Values are hourly,
in local time (UTC-6, no DST), stamped at the end of the hour; hour 24 already comes as 00 of the next day.
Catalogs are latin1.

The module has two layers: pure functions that parse and clean in-memory data, and a thin I/O layer at the end
(`load_*`, `run_qc`) that reads and writes files.
"""

import io
import zipfile
from pathlib import Path
from typing import IO

import numpy as np
import pandas as pd

from nox_ml.data.domain import AFTERNOON_HOURS, DRY_MONTHS, LAT, LON
from nox_ml.data.qc import Check
from nox_ml.time import local_to_utc

HEADER_LINES = 9
# REDMET 2024 reports wind speed in mph labelled as m/s (step at 2024-01-01, ~2.2x ERA5 and METAR MMMX).
MPH_TO_MS_FACTOR = 2.237
WIND_FIX_YEAR = 2024

NOX_PARAMETERS = ("NO", "NO2", "NOX")
WIND_PARAMETERS = ("WSP", "WDR")
HIGH_NOX_PPB = 250  # hours above this are flagged, not dropped
STUCK_MAX_RUN_HOURS = 6
STUCK_MIN_PPB = 1  # a flat series at ~0 is a real clean-air reading, not a stuck sensor
TRAFFIC_STATIONS = ("MER", "CAM")
PERIPHERAL_STATIONS = ("AJM", "CUA")
MIN_AFTERNOON_COMPLETENESS = 0.75
MIN_WIND_STATIONS = 10
CALM_MS = 0.5


# --- Parsing (pure) ----------------------------------------------------------------------------------------


def parse_table(source: IO[bytes]) -> pd.DataFrame:
    """Parse a SIMAT hourly table; adds `local` and `utc` timestamps and drops `date`."""
    df = pd.read_csv(source, skiprows=HEADER_LINES, dtype={"value": "float64"})
    df["local"] = pd.to_datetime(df["date"], format="mixed")
    df["utc"] = local_to_utc(df["local"])
    return df.drop(columns="date")


def parse_catalog(source: IO[bytes]) -> pd.DataFrame:
    """Parse the station catalog; adds `in_domain` (station inside the study bounding box)."""
    cat = pd.read_csv(source, skiprows=1, encoding="latin1")
    cat = cat.rename(columns={"cve_estac": "station", "longitud": "lon", "latitud": "lat"})
    cat["in_domain"] = cat["lat"].between(*LAT) & cat["lon"].between(*LON)
    return cat


def parse_units(source: IO[bytes]) -> pd.Series:
    """Map unit id -> unit symbol (e.g. 3 -> 'm/s')."""
    return pd.read_csv(source, encoding="latin1").set_index("id_unidad")["clave_unidad"]


# --- Cleaning (pure) ---------------------------------------------------------------------------------------


def pivot_hourly(df: pd.DataFrame, parameters: tuple[str, ...]) -> pd.DataFrame:
    """Long table -> one row per station-hour with one column per parameter (duplicates are averaged).

    Every requested parameter is a column, even when it has no valid value.
    """
    long = df[df["id_parameter"].isin(parameters)]
    wide = long.pivot_table(index=["id_station", "local", "utc"], columns="id_parameter", values="value")
    wide = wide.reset_index()
    wide.columns.name = None
    return wide.reindex(columns=["id_station", "local", "utc", *parameters])  # all-NaN columns are dropped


def clean_nox(pol: pd.DataFrame) -> pd.DataFrame:
    """NO, NO2 and NOX per station-hour. Negative values become NaN; hours above 250 ppb get `flag_hi`."""
    pol = pol[pol["id_parameter"].isin(NOX_PARAMETERS)].copy()
    pol.loc[pol["value"] < 0, "value"] = np.nan
    wide = pivot_hourly(pol, NOX_PARAMETERS)
    wide["flag_hi"] = wide["NOX"] > HIGH_NOX_PPB
    return wide


def stuck_mask(values: pd.Series, max_run: int = STUCK_MAX_RUN_HOURS, min_value: float = STUCK_MIN_PPB):
    """True where a sensor repeats the same value for more than `max_run` consecutive readings.

    Rows must be in time order. Missing readings are skipped (never flagged), so a run bridges them.
    Values at or below `min_value` are never flagged.
    """
    s = values.dropna()
    run_id = (s != s.shift()).cumsum()
    run_length = s.groupby(run_id).transform("size")
    mask = (run_length > max_run) & (s > min_value)
    return mask.reindex(values.index, fill_value=False)


def stuck_hours_by_station(wide: pd.DataFrame, column: str = "NOX") -> pd.Series:
    ordered = wide.sort_values("local")
    return ordered.groupby("id_station")[column].apply(lambda s: int(stuck_mask(s).sum()))


def clean_wind(met: pd.DataFrame) -> pd.DataFrame:
    """WSP and WDR per station-hour; WSP of 2024 is converted from mph to m/s (see `fix_wind_speed`)."""
    return fix_wind_speed(pivot_hourly(met, WIND_PARAMETERS))


def fix_wind_speed(w: pd.DataFrame) -> pd.DataFrame:
    """Divide 2024 wind speed by 2.237. Keeps the original in `WSP_raw`; `wsp_fix_mph` marks the rows."""
    w = w.copy()
    w["WSP_raw"] = w["WSP"]
    w["wsp_fix_mph"] = w["local"].dt.year == WIND_FIX_YEAR
    w.loc[w["wsp_fix_mph"], "WSP"] = w.loc[w["wsp_fix_mph"], "WSP"] / MPH_TO_MS_FACTOR
    w["calm"] = w["WSP"] < CALM_MS
    return w


def mean_wind_direction(wsp: pd.Series, wdr: pd.Series) -> float:
    """Vector-mean direction (degrees, where the wind comes from), weighted by speed."""
    rad = np.deg2rad(wdr)
    return float((np.rad2deg(np.arctan2((wsp * np.sin(rad)).mean(), (wsp * np.cos(rad)).mean())) + 360) % 360)


def _afternoon_dry(df: pd.DataFrame, stations: set[str]) -> pd.DataFrame:
    local = df["local"].dt
    keep = local.hour.isin(AFTERNOON_HOURS) & local.month.isin(DRY_MONTHS) & df["id_station"].isin(stations)
    return df[keep]


def afternoon_completeness(wide: pd.DataFrame, stations: set[str], column: str = "NOX") -> pd.DataFrame:
    """Share of dry-season afternoon hours with data, per month (rows) and station (columns)."""
    aft = _afternoon_dry(wide, stations)
    month = aft["local"].dt.to_period("M")
    hours_per_month = aft.groupby(month)["local"].nunique()
    counts = aft.groupby([month, aft["id_station"]])[column].count().unstack(fill_value=0)
    return counts.div(hours_per_month, axis=0)


def wind_station_coverage(w: pd.DataFrame, stations: set[str]) -> pd.DataFrame:
    """Per month: share of afternoon hours with >= 10 valid wind stations, and the median station count."""
    aft = _afternoon_dry(w, stations).dropna(subset=["WSP", "WDR"])
    n_valid = aft.groupby("local")["id_station"].nunique()
    month = n_valid.index.to_period("M")
    return pd.DataFrame(
        {
            "share_hours_ok": n_valid.groupby(month).apply(lambda s: (s >= MIN_WIND_STATIONS).mean()),
            "median_stations": n_valid.groupby(month).median(),
        }
    )


# --- Quality control (pure) --------------------------------------------------------------------------------


def nox_checks(pol: pd.DataFrame, wide: pd.DataFrame, catalog: pd.DataFrame, units: pd.Series) -> list[Check]:
    """QC of the raw long table `pol` (NO/NO2/NOX rows) and its cleaned wide version."""
    checks: list[Check] = []
    unknown = sorted(set(pol["id_station"]) - set(catalog["station"]))
    checks.append(Check(not unknown, f"Stations in catalog (unknown: {unknown or 'none'})"))

    present_units = set(pol.dropna(subset=["value"])["unit"].map(units).unique())
    checks.append(Check(present_units == {"ppb"}, f"NO/NO2/NOX units: {sorted(present_units)}"))

    dups = int(pol.duplicated(["id_station", "id_parameter", "local"]).sum())
    checks.append(Check(dups == 0, f"Duplicate station-parameter-hour rows: {dups}"))
    neg = int((pol["value"] < 0).sum())
    checks.append(Check(neg == 0, f"Negative values: {neg}"))
    hi = (wide[list(NOX_PARAMETERS)] > HIGH_NOX_PPB).sum()
    checks.append(
        Check(None, f"Hours > {HIGH_NOX_PPB} ppb (flagged): NO={hi['NO']}, NO2={hi['NO2']}, NOX={hi['NOX']}")
    )

    both = wide.dropna(subset=list(NOX_PARAMETERS))
    both = both[both["NOX"] > 10]
    rel = ((both["NO"] + both["NO2"]) - both["NOX"]).abs() / both["NOX"]
    checks.append(
        Check(
            bool(rel.median() < 0.05),
            f"NOX ~ NO + NO2: median diff {rel.median():.1%}, "
            f"{(rel > 0.05).mean():.1%} of hours differ > 5 %",
        )
    )

    stuck = stuck_hours_by_station(wide)
    detail = ", ".join(f"{k}:{v}" for k, v in stuck[stuck > 0].items()) or "-"
    checks.append(
        Check(
            int(stuck.sum()) == 0,
            f"NOX hours in runs > {STUCK_MAX_RUN_HOURS} h with identical value: {stuck.sum()} ({detail})",
        )
    )

    hour, month = wide["local"].dt.hour, wide["local"].dt.to_period("M")
    peak = wide.groupby([month, hour])["NOX"].mean().unstack().idxmax(axis=1)
    bad = peak[~peak.between(7, 9)]
    checks.append(
        Check(
            bad.empty, f"Morning NOX peak between 07 and 09 h in every month (outside: {dict(bad) or 'none'})"
        )
    )

    dow = wide["local"].dt.day_of_week
    sunday, weekday = wide[dow == 6]["NOX"].mean(), wide[dow < 5]["NOX"].mean()
    checks.append(Check(bool(sunday < weekday), f"Sunday ({sunday:.1f} ppb) < weekdays ({weekday:.1f} ppb)"))

    mean_by_station = wide.groupby("id_station")["NOX"].mean()
    traffic = [s for s in TRAFFIC_STATIONS if s in mean_by_station]
    peripheral = [s for s in PERIPHERAL_STATIONS if s in mean_by_station]
    if traffic and peripheral:
        checks.append(
            Check(
                bool(mean_by_station[traffic].min() > mean_by_station[peripheral].max()),
                f"Traffic {mean_by_station[traffic].round(1).to_dict()} > "
                f"peripheral {mean_by_station[peripheral].round(1).to_dict()}",
            )
        )
    return checks


def wind_checks(met: pd.DataFrame, w: pd.DataFrame, units: pd.Series) -> list[Check]:
    """QC of the raw long table `met` (WSP/WDR rows) and the cleaned (mph-corrected) wide table `w`."""
    by_param = met.dropna(subset=["value"]).groupby("id_parameter")["unit"].unique()
    symbols = {p: [units[i] for i in ids] for p, ids in by_param.items()}
    checks = [
        Check(
            symbols.get("WSP") == ["m/s"] and symbols.get("WDR") == ["°"],
            f"Units: WSP {symbols.get('WSP')}, WDR {symbols.get('WDR')}",
        ),
        Check(
            None,
            f"Correction applied: WSP of {WIND_FIX_YEAR} / {MPH_TO_MS_FACTOR} "
            f"({int(w['wsp_fix_mph'].sum()):,} rows; original in WSP_raw)",
        ),
        Check(
            bool(w["WDR"].dropna().between(0, 360).all()),
            f"Direction within [0, 360]: range {w['WDR'].min()}-{w['WDR'].max()}",
        ),
    ]
    median_wsp = w.groupby("local")["WSP"].median()
    plausible = median_wsp.between(1, 4).mean()
    checks.append(
        Check(
            bool(plausible > 0.6),
            f"Hourly median WSP between 1 and 4 m/s in {plausible:.0%} of hours "
            f"(overall median {median_wsp.median():.2f})",
        )
    )
    checks.append(Check(None, f"Calms (< {CALM_MS} m/s): {w['calm'].mean():.1%} of valid hours"))
    return checks


# --- I/O ---------------------------------------------------------------------------------------------------


def read_zip_member(path: Path) -> bytes:
    """Read the single CSV inside a SIMAT archive (served as ZIP even when named `.csv.gz`)."""
    with zipfile.ZipFile(path) as z:
        return z.read(z.namelist()[0])


def load_table(raw_dir: Path, kind: str, years: list[int]) -> pd.DataFrame:
    """Concatenate `<kind>_<year>.csv.gz` for the given years; `kind` is 'contaminantes' or 'meteorologia'."""
    frames = [parse_table(io.BytesIO(read_zip_member(raw_dir / f"{kind}_{y}.csv.gz"))) for y in years]
    return pd.concat(frames, ignore_index=True)


def load_catalog(raw_dir: Path) -> pd.DataFrame:
    with open(raw_dir / "cat_estacion.csv", "rb") as f:
        return parse_catalog(f)


def load_units(raw_dir: Path) -> pd.Series:
    with open(raw_dir / "cat_unidades.csv", "rb") as f:
        return parse_units(f)


def run_qc(raw_dir: Path, out_dir: Path, years: list[int]) -> list[Check]:
    """Load, clean and check SIMAT NOx and wind; write `simat_nox.parquet`, `simat_wind.parquet` and
    `simat_nox_completeness.csv` to `out_dir`. Returns all checks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog, units = load_catalog(raw_dir), load_units(raw_dir)
    domain_stations = set(catalog.loc[catalog["in_domain"], "station"])

    pol = load_table(raw_dir, "contaminantes", years)
    pol = pol[pol["id_parameter"].isin(NOX_PARAMETERS)]
    wide = clean_nox(pol)
    checks = [Check(None, f"SIMAT {years[0]}-{years[-1]}")]
    checks += nox_checks(pol, wide, catalog, units)
    checks.append(Check(None, f"Catalog stations inside the domain: {len(domain_stations)}"))
    completeness = afternoon_completeness(wide, domain_stations)
    n_valid = (completeness >= MIN_AFTERNOON_COMPLETENESS).sum(axis=1)
    checks += [
        Check(None, f"{m}: {n} valid NOX stations of {(completeness.loc[m] > 0).sum()}")
        for m, n in n_valid.items()
    ]
    wide.to_parquet(out_dir / "simat_nox.parquet")
    completeness.to_csv(out_dir / "simat_nox_completeness.csv")

    met = load_table(raw_dir, "meteorologia", years)
    met = met[met["id_parameter"].isin(WIND_PARAMETERS)]
    w = clean_wind(met)
    checks += wind_checks(met, w, units)
    afternoon = _afternoon_dry(w, domain_stations)
    checks.append(
        Check(
            None,
            "Mean afternoon wind direction (from): "
            f"{mean_wind_direction(afternoon['WSP'], afternoon['WDR']):.0f} deg",
        )
    )
    coverage = wind_station_coverage(w, domain_stations)
    checks += [
        Check(
            None, f"{m}: {r.share_hours_ok:.0%} of afternoon hours with >= {MIN_WIND_STATIONS} wind stations"
        )
        for m, r in coverage.iterrows()
    ]
    w.to_parquet(out_dir / "simat_wind.parquet")
    return checks
