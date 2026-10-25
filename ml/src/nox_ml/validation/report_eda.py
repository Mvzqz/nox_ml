# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""What the exploration (Avance 1) and feature (Avance 2) notebooks show: tables and figures of the data as
the models see it.

Every function takes plain DataFrames (or the `Inputs` of the harness) and returns a DataFrame, a number or a
matplotlib `Figure`, so a notebook only calls them. Labels of the figures are in Spanish, as the notebooks.

Periods: the modelling decisions come from `MODEL_PERIOD` (Nov-Dec 2023). `TEST_PERIOD` (Feb-May 2024) is the
held-out period of the final report: it appears only in the data-quality checks (`quality_by_month`,
`tempo_filters`), never in a function that feeds a decision.
"""

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import NullFormatter
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler

from nox_ml.data import pbl as pbl_data
from nox_ml.data import simat, tempo
from nox_ml.data.inputs import Inputs
from nox_ml.data.pbl import ERA5_FILE, parse_era5
from nox_ml.inversion.linear import BACKGROUND_STATION, DAY_TYPE_NAMES, HOLIDAYS
from nox_ml.inversion.normalized import day_type
from nox_ml.models.pinn import equation
from nox_ml.models.rf_deweather import FLOOR_ABOVE_BACKGROUND_PPB, hour_table
from nox_ml.time import utc_to_local
from nox_ml.validation import diagnostics

MODEL_PERIOD = ("2023-11-01", "2023-12-31")
TEST_PERIOD = ("2024-02-15", "2024-05-31")
AFTERNOON = (12, 17)  # SIMAT hour labels (local) the models use
SIMAT_YEARS = [2023, 2024]
MIN_AFTERNOON_COMPLETENESS = simat.MIN_AFTERNOON_COMPLETENESS
OUTAGE_STATIONS = 10  # a day with fewer stations than this is a network-wide outage
ROBUST_Z = 3.5  # modified z-score (median/MAD) above which a value is an outlier (Iglewicz-Hoaglin)
TAU_HOURS = (4.0, 8.0, 12.0)  # NOx lifetimes the PINN range covers (equation.GAMMA_RANGE)
FEATURES = [
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
    "wind_sin",
    "wind_cos",
    "ventilation",
    "ventilation_3h",
    "ventilation_6h",
]
VENTILATION = ["ventilation", "ventilation_3h", "ventilation_6h"]


# --- Loading -----------------------------------------------------------------------------------------------


def find_data() -> Path:
    """``data/`` of the repository containing the working directory (``./data`` outside a repository)."""
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file():
            return folder / "data"
    return Path("data")


@dataclass(frozen=True)
class Tables:
    """The tables of the exploration, as written by the QC commands and read by the models."""

    nox_raw: pd.DataFrame  # NO, NO2, NOX per station-hour straight from the SIMAT files (stuck not masked)
    nox: pd.DataFrame  # `interim/simat_nox.parquet` (stuck masked)
    wind: pd.DataFrame  # `interim/simat_wind.parquet` (2024 speed in m/s)
    pbl: pd.DataFrame  # `interim/pbl_2023_2024.parquet` (ERA5 filled with MERRA-2)
    pixels: pd.DataFrame  # TEMPO pixels of `MODEL_PERIOD`, valid or not
    pixels_test: pd.DataFrame  # TEMPO pixels of `TEST_PERIOD`: data-quality checks only
    catalog: pd.DataFrame  # SIMAT station catalog, with ``in_domain`` (inside the study bounding box)


def load_tables(data_dir: Path) -> Tables:
    """Read the tables of `data_dir` (``interim/`` for the QC outputs, ``raw/`` for SIMAT before masking)."""
    interim = data_dir / "interim"
    raw = simat.load_table(data_dir / "raw" / "simat", "contaminantes", SIMAT_YEARS)
    catalog = simat.load_catalog(data_dir / "raw" / "simat")
    tempo_file = "tempo_pixels_{}_{}.parquet"
    return Tables(
        nox_raw=simat.clean_nox(raw[raw["id_parameter"].isin(simat.NOX_PARAMETERS)]),
        nox=pd.read_parquet(interim / "simat_nox.parquet"),
        wind=pd.read_parquet(interim / "simat_wind.parquet"),
        pbl=pd.read_parquet(interim / "pbl_2023_2024.parquet"),
        pixels=pd.read_parquet(interim / tempo_file.format(*MODEL_PERIOD)),
        pixels_test=pd.read_parquet(interim / tempo_file.format(*TEST_PERIOD)),
        catalog=catalog,
    )


def in_window(
    df: pd.DataFrame, period: tuple[str, str] = MODEL_PERIOD, hours: tuple[int, int] | None = None
) -> pd.DataFrame:
    """Rows of `df` (with a ``local`` timestamp) in the local days of `period` (both inclusive) and, with
    `hours`, in those SIMAT hour labels (inclusive)."""
    local = df["local"]
    keep = local.between(period[0], f"{period[1]} 23:59:59")
    if hours is not None:
        keep &= local.dt.hour.between(*hours)
    return df[keep]


# --- Structure and types ----------------------------------------------------------------------------------


def _period(df: pd.DataFrame) -> tuple[object, object]:
    for column in ("local", "utc"):
        if column in df:
            return df[column].min(), df[column].max()
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index.min(), df.index.max()
    return None, None


def structure(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per table: shape, period, count of columns by kind, share of missing cells and memory."""
    rows = []
    for name, df in frames.items():
        start, end = _period(df)
        kinds = df.dtypes.map(lambda d: "datetime" if d.kind == "M" else "bool" if d.kind == "b" else d.kind)
        rows.append(
            {
                "table": name,
                "rows": len(df),
                "columns": df.shape[1],
                "start": start,
                "end": end,
                "numeric": int(kinds.isin(["f", "i", "u"]).sum()),
                "datetime": int((kinds == "datetime").sum()),
                "bool": int((kinds == "bool").sum()),
                "text": int(kinds.isin(["O", "S", "U"]).sum()),
                "missing_pct": 100 * float(df.isna().to_numpy().mean()) if df.size else 0.0,
                "memory_mb": df.memory_usage(deep=True).sum() / 2**20,
            }
        )
    return pd.DataFrame(rows)


def column_types(df: pd.DataFrame) -> pd.DataFrame:
    """Type, non-missing count, missing share, distinct values and range of every column of `df`."""
    rows = []
    for column in df.columns:
        s = df[column]
        comparable = s.dtype.kind in "fiubM"
        rows.append(
            {
                "column": column,
                "dtype": str(s.dtype),
                "non_null": int(s.notna().sum()),
                "missing_pct": 100 * float(s.isna().mean()),
                "unique": int(s.nunique()),
                "min": s.min() if comparable and s.notna().any() else None,
                "max": s.max() if comparable and s.notna().any() else None,
            }
        )
    return pd.DataFrame(rows)


# --- Descriptive statistics ---------------------------------------------------------------------------------


def describe(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Count, missing share, mean, standard deviation, quartiles, extremes, skewness and kurtosis of the
    `columns` (one row each)."""
    rows = {}
    for c in columns:
        s = df[c].dropna()
        q = s.quantile([0.25, 0.5, 0.75])
        rows[c] = {
            "count": len(s),
            "missing_pct": 100 * float(df[c].isna().mean()),
            "mean": s.mean(),
            "std": s.std(),
            "min": s.min(),
            "q1": q[0.25],
            "median": q[0.5],
            "q3": q[0.75],
            "max": s.max(),
            "skew": s.skew(),
            "kurtosis": s.kurt(),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def station_summary(nox: pd.DataFrame, catalog: pd.DataFrame, column: str = "NOX") -> pd.DataFrame:
    """Per station of `nox` (already in the window and hours): valid hours, mean, median, 95th percentile and
    maximum, ordered by mean, with the station name from the `catalog`."""
    names = catalog.drop_duplicates("station").set_index("station")["nom_estac"]
    g = nox.groupby("id_station")[column]
    out = pd.DataFrame(
        {
            "name": names.reindex(g.size().index),
            "hours": g.count(),
            "mean": g.mean(),
            "median": g.median(),
            "p95": g.quantile(0.95),
            "max": g.max(),
        }
    )
    return out.sort_values("mean", ascending=False)


# --- Missing values ----------------------------------------------------------------------------------------


def missing_by_variable(
    frames: Mapping[str, pd.DataFrame], columns: Mapping[str, Sequence[str]]
) -> pd.DataFrame:
    """Missing count and share of the `columns` of each table in `frames`."""
    rows = [
        {"table": t, "variable": c, "rows": len(frames[t]), "missing": int(frames[t][c].isna().sum())}
        for t, cs in columns.items()
        for c in cs
    ]
    out = pd.DataFrame(rows)
    out["missing_pct"] = 100 * out["missing"] / out["rows"]
    return out


def completeness_matrix(nox: pd.DataFrame, period: tuple[str, str], column: str = "NOX") -> pd.DataFrame:
    """Share of the afternoon hours (``AFTERNOON``) with data, one row per local day and one column per
    station."""
    aft = in_window(nox, period, AFTERNOON)
    n_hours = AFTERNOON[1] - AFTERNOON[0] + 1
    day = aft["local"].dt.normalize()
    counts = aft.groupby([day, aft["id_station"]])[column].count().unstack(fill_value=0)
    days = pd.date_range(*period, freq="D")
    return (counts.reindex(days, fill_value=0) / n_hours).rename_axis("day")


def missing_patterns(nox: pd.DataFrame) -> pd.DataFrame:
    """How often each combination of NO, NO2 and NOX missing happens (``missing`` lists the absent ones)."""
    absent = nox[list(simat.NOX_PARAMETERS)].isna()
    label = absent.apply(lambda r: ", ".join(c for c in absent.columns if r[c]) or "none", axis=1)
    out = label.value_counts().rename_axis("missing").reset_index(name="rows")
    out["share_pct"] = 100 * out["rows"] / len(nox)
    return out


def missing_by_station(nox: pd.DataFrame, period: tuple[str, str]) -> pd.Series:
    """Share (%) of the afternoon hours of `period` without NOx, by station of the table. An hour without a
    row counts as missing, as does a station that never reports NOx (it only measures NO2)."""
    present = completeness_matrix(nox, period).mean().reindex(sorted(set(nox["id_station"])), fill_value=0.0)
    return (100 * (1 - present)).sort_values(ascending=False).rename("missing_pct")


def missing_by_hour(nox: pd.DataFrame, period: tuple[str, str]) -> pd.Series:
    """Share (%) of the hours of `period` without NOx, by local hour label, over the stations that report NOx
    at all. An hour without a row counts as missing."""
    part = in_window(nox, period).dropna(subset=["NOX"])
    n_days = len(pd.date_range(*period, freq="D"))
    per_station_hour = part.groupby([part["id_station"], part["local"].dt.hour]).size().unstack(fill_value=0)
    return (100 * (1 - per_station_hour.mean() / n_days)).rename_axis("hour").rename("missing_pct")


def network_outages(matrix: pd.DataFrame, min_stations: int = OUTAGE_STATIONS) -> pd.DataFrame:
    """Days of a `completeness_matrix` with fewer than `min_stations` stations with at least one hour of
    data, and how many they had."""
    present = (matrix > 0).sum(axis=1)
    return present[present < min_stations].rename("stations").reset_index()


def plot_completeness(matrix: pd.DataFrame) -> Figure:
    """The completeness matrix as a map: stations in rows, days in columns, darker is more complete."""
    fig = Figure(figsize=(11, 0.22 * matrix.shape[1] + 1.8), layout="constrained")
    ax = fig.subplots()
    image = ax.imshow(
        matrix.T.to_numpy(), aspect="auto", vmin=0, vmax=1, cmap="Blues", interpolation="nearest"
    )
    ax.set_yticks(range(matrix.shape[1]), matrix.columns)
    ticks = range(0, len(matrix), 7)
    ax.set_xticks(ticks, [f"{matrix.index[i]:%d-%b}" for i in ticks], rotation=45, ha="right")
    ax.set(title="NOₓ con dato en las tardes (12–17 h): estación por día", xlabel="día local")
    fig.colorbar(image, ax=ax, label="fracción de horas con dato", shrink=0.8)
    return fig


def plot_missing_profile(nox: pd.DataFrame, period: tuple[str, str]) -> Figure:
    """Missing NOx by station (afternoons) and by hour of the day, as `missing_by_station` and
    `missing_by_hour` count it."""
    fig = Figure(figsize=(11, 3.6), layout="constrained")
    a, b = fig.subplots(1, 2)
    by_station = missing_by_station(nox, period)
    a.bar(by_station.index.astype(str), by_station.to_numpy(), color="#4c78a8")
    a.set(title="NOₓ faltante por estación (tardes)", xlabel="estación", ylabel="% de las horas")
    a.tick_params(axis="x", rotation=90)
    by_hour = missing_by_hour(nox, period)
    b.bar(by_hour.index, by_hour.to_numpy(), color="#4c78a8")
    b.set(
        title="NOₓ faltante por hora (estaciones que miden NOₓ)",
        xlabel="hora local (etiqueta)",
        ylabel="% de las horas",
    )
    return fig


# --- Boundary layer height ---------------------------------------------------------------------------------


def _source_column(pbl: pd.DataFrame) -> str:
    return "fuente" if "fuente" in pbl else "source"


def pbl_sources(pbl: pd.DataFrame) -> pd.DataFrame:
    """Hours of each month by source of the boundary layer height (ERA5, corrected MERRA-2, missing)."""
    month = pbl.index.to_period("M")
    return pbl.groupby([month, pbl[_source_column(pbl)]]).size().unstack(fill_value=0)


def pbl_correction(data_dir: Path) -> tuple[pd.DataFrame, dict[str, float]]:
    """MERRA-2 against ERA5 where both exist (Jan-Jun 2023, the months of the 2024 gap): the afternoon
    agreement per hour and the out-of-sample error of the correction (`pbl.validate_correction`)."""
    days = pd.date_range(*pbl_data.MERRA_DAYS, freq="D")
    merra = pbl_data.merra_to_hourly(pbl_data.read_merra2(data_dir / "raw" / "merra2", days))
    era5 = parse_era5(json.loads((data_dir / "raw" / "era5_openmeteo" / ERA5_FILE).read_text()))
    both = pbl_data.paired(era5.loc[pbl_data.MERRA_DAYS[0] : f"{pbl_data.MERRA_DAYS[1]} 23:00"], merra)
    return pbl_data.afternoon_stats(both), pbl_data.validate_correction(both)


def plot_pbl(pbl: pd.DataFrame) -> Figure:
    """Boundary layer height at 14 h local, coloured by source: ERA5 for the modelling period, corrected
    MERRA-2 for 2024."""
    hour = utc_to_local(pbl.index).hour
    noon = pbl[hour == 14]
    fig = Figure(figsize=(11, 3.6), layout="constrained")
    ax = fig.subplots()
    for source, part in noon.groupby(_source_column(pbl)):
        ax.plot(part.index, part["pbl_m"], ".", ms=4, label=source)
    ax.set(title="Altura de la capa límite a las 14 h locales", ylabel="m")
    ax.legend()
    return fig


# --- Outliers ---------------------------------------------------------------------------------------------


def robust_z(values: pd.Series) -> pd.Series:
    """Modified z-score ``0.6745 (x - median) / MAD``; zero where the MAD is zero."""
    median = values.median()
    mad = (values - median).abs().median()
    return 0.6745 * (values - median) / mad if mad > 0 else values * 0.0


def outlier_table(nox: pd.DataFrame, column: str = "NOX") -> pd.DataFrame:
    """Per station: valid hours, hours above the 250 ppb flag, hours above the Tukey fence (1.5 IQR on the log
    of the value) and hours with a robust z above `ROBUST_Z` (also on the log)."""
    rows = {}
    for station, s in nox.groupby("id_station")[column]:
        s = s.dropna()
        s = s[s > 0]
        log = np.log(s)
        q1, q3 = log.quantile([0.25, 0.75])
        rows[station] = {
            "hours": len(s),
            "above_250_ppb": int((s > simat.HIGH_NOX_PPB).sum()),
            "above_tukey_fence": int((log > q3 + 1.5 * (q3 - q1)).sum()),
            "robust_z_high": int((robust_z(log) > ROBUST_Z).sum()),
        }
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("station")


def stuck_table(raw: pd.DataFrame, masked: pd.DataFrame) -> pd.DataFrame:
    """Stuck-sensor hours by station (runs of more than 6 identical readings), before and after the masking,
    and their share of the station's valid hours."""
    before = simat.stuck_hours_by_station(raw)
    after = simat.stuck_hours_by_station(masked)
    valid = raw.groupby("id_station")["NOX"].count()
    out = pd.DataFrame({"stuck_hours": before, "stuck_after_mask": after, "valid_hours": valid})
    out["stuck_pct"] = 100 * out["stuck_hours"] / out["valid_hours"]
    return out


def masked_hours(raw: pd.DataFrame, masked: pd.DataFrame, period: tuple[str, str]) -> pd.Series:
    """Station-hours of `period` whose NOx the stuck-sensor mask set to missing, by station (only those with
    any)."""
    gone = raw["NOX"].notna() & masked.loc[raw.index, "NOX"].isna()
    count = gone[raw["local"].between(period[0], f"{period[1]} 23:59:59")].groupby(raw["id_station"]).sum()
    return count[count > 0].astype(int)


def longest_stuck_run(
    raw: pd.DataFrame, column: str = "NOX"
) -> tuple[str, pd.Timestamp, pd.Timestamp, int] | None:
    """Station, first and last hour label and length of the longest run flagged as stuck; ``None`` without
    stuck hours."""
    best = None
    for station, g in raw.sort_values("local").groupby("id_station"):
        s = g.set_index("local")[column].dropna()
        run = (s != s.shift()).cumsum()
        stuck = s.groupby(run).transform("size") > simat.STUCK_MAX_RUN_HOURS
        stuck &= s > simat.STUCK_MIN_PPB
        if not stuck.any():
            continue
        sizes = run[stuck].value_counts()
        times = s.index[run == sizes.idxmax()]
        if best is None or sizes.max() > best[3]:
            best = (str(station), times[0], times[-1], int(sizes.max()))
    return best


def plot_stuck_example(raw: pd.DataFrame, margin_hours: int = 36) -> Figure | None:
    """The longest stuck run with `margin_hours` of context on each side; ``None`` without stuck hours."""
    run = longest_stuck_run(raw)
    if run is None:
        return None
    station, first, last, length = run
    pad = pd.Timedelta(hours=margin_hours)
    part = raw[(raw["id_station"] == station) & raw["local"].between(first - pad, last + pad)].sort_values(
        "local"
    )
    fig = Figure(figsize=(9, 3.4), layout="constrained")
    ax = fig.subplots()
    ax.plot(part["local"], part["NOX"], "-", color="#4c78a8", label="NOₓ medido")
    stuck = part[part["local"].between(first, last)]
    ax.plot(stuck["local"], stuck["NOX"], "o", color="#e45756", ms=4, label=f"atascado ({length} h)")
    ax.set(title=f"Sensor atascado en {station}", ylabel="ppb")
    ax.legend()
    return fig


def wind_unit_step(wind: pd.DataFrame) -> pd.DataFrame:
    """Monthly median wind speed as reported (``WSP_raw``) and after the mph correction (``WSP``)."""
    month = wind["local"].dt.to_period("M")
    return wind.groupby(month)[["WSP_raw", "WSP"]].median()


def wind_fix_gaps(wind: pd.DataFrame) -> pd.DataFrame:
    """Rows stamped in 2025 (hour 24 of 31 Dec 2024), which come from the 2024 file but are not corrected
    because the correction goes by the year of the stamp."""
    late = wind[wind["local"].dt.year > simat.WIND_FIX_YEAR]
    return late[~late["wsp_fix_mph"]]


def plot_wind_step(wind: pd.DataFrame) -> Figure:
    """Monthly median wind speed before and after the mph correction."""
    steps = wind_unit_step(wind[wind["local"].dt.year <= simat.WIND_FIX_YEAR])
    fig = Figure(figsize=(9, 3.4), layout="constrained")
    ax = fig.subplots()
    x = steps.index.to_timestamp()
    ax.plot(x, steps["WSP_raw"], "o-", color="#e45756", label="como la publica SIMAT")
    ax.plot(x, steps["WSP"], "o-", color="#4c78a8", label="corregida (2024 ÷ 2.237)")
    ax.set(title="Velocidad del viento: mediana mensual de las estaciones", ylabel="m/s")
    ax.legend()
    return fig


def tempo_filters(pixels: pd.DataFrame) -> pd.DataFrame:
    """The TEMPO quality filters applied in order: pixels left after the quality flag, the cloud fraction and
    the missing column (``valid``), with the share rejected by each filter on its own."""
    steps = {
        "pixels in the domain": pd.Series(True, index=pixels.index),
        "quality flag = 0": pixels["qf"] == 0,
        f"cloud fraction < {tempo.MAX_CLOUD_FRACTION}": pixels["cf"] < tempo.MAX_CLOUD_FRACTION,
        "column present": pixels["vcd"].notna(),
    }
    keep = pd.Series(True, index=pixels.index)
    rows = []
    for name, ok in steps.items():
        keep &= ok
        rows.append({"filter": name, "left": int(keep.sum()), "alone_rejects_pct": 100 * float((~ok).mean())})
    out = pd.DataFrame(rows)
    out["left_pct"] = 100 * out["left"] / len(pixels)
    return out


def tempo_column_summary(pixels: pd.DataFrame) -> pd.DataFrame:
    """The tropospheric column of the valid and of the rejected pixels: count, quantiles and share of
    negative values (retrieval noise around a small column), in molecules/cm2."""
    rows = {}
    for name, part in {"valid": pixels[pixels["valid"]], "rejected": pixels[~pixels["valid"]]}.items():
        v = part["vcd"].dropna()
        rows[name] = {
            "pixels": len(v),
            "q01": v.quantile(0.01),
            "median": v.median(),
            "q99": v.quantile(0.99),
            "negative_pct": 100 * float((v < 0).mean()),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def tempo_by_month(pixels: pd.DataFrame) -> pd.DataFrame:
    """Granules, pixels, valid share and median valid column by local month."""
    month = pixels["local"].dt.to_period("M")
    valid = pixels[pixels["valid"]]
    return pd.DataFrame(
        {
            "granules": pixels.groupby(month)["granule"].nunique(),
            "pixels": pixels.groupby(month).size(),
            "valid_pct": 100 * pixels.groupby(month)["valid"].mean(),
            "median_vcd": valid.groupby(valid["local"].dt.to_period("M"))["vcd"].median(),
        }
    )


# --- Univariate plots ---------------------------------------------------------------------------------------


def plot_histograms(series: Mapping[str, pd.Series], log: Collection[str] = ()) -> Figure:
    """One histogram per series; the names in `log` use a logarithmic x axis."""
    fig = Figure(figsize=(4 * len(series), 3.4), layout="constrained")
    for ax, (name, s) in zip(fig.subplots(1, len(series), squeeze=False)[0], series.items(), strict=True):
        s = s.dropna()
        if name in log:
            s = s[s > 0]
            ax.hist(s, bins=np.geomspace(s.min(), s.max(), 50), color="#4c78a8")
            ax.set_xscale("log")
        else:
            ax.hist(s, bins=50, color="#4c78a8")
        ax.axvline(s.median(), color="#e45756", ls="--", label=f"mediana {s.median():.3g}")
        ax.set(title=name, ylabel="frecuencia")
        ax.legend(fontsize=8)
    return fig


def plot_station_boxplots(nox: pd.DataFrame, column: str = "NOX") -> Figure:
    """NOx by station (log axis), ordered by median."""
    order = nox.groupby("id_station")[column].median().dropna().sort_values().index
    data = [nox.loc[nox["id_station"] == s, column].dropna().to_numpy() for s in order]
    fig = Figure(figsize=(11, 3.8), layout="constrained")
    ax = fig.subplots()
    ax.boxplot(data, tick_labels=list(order), flierprops={"markersize": 2, "alpha": 0.4})
    ax.set(title="NOₓ por estación (tardes, nov–dic 2023)", ylabel="ppb", yscale="log")
    ax.tick_params(axis="x", rotation=60)
    return fig


# --- Model-ready rows -----------------------------------------------------------------------------------


def hourly_table(data: Inputs) -> pd.DataFrame:
    """One row per hour of the inputs: ``utc``, ``local``, ``day``, ``hour``, ``day_type``, stations with
    data, mean station NOx (ppb), wind speed (m/s), boundary layer height (m), mean TEMPO column and pixels,
    with the hour features of the models."""
    features = hour_table(data)
    local = utc_to_local(pd.DatetimeIndex([h.hour for h in data.hours]))
    return features.assign(
        utc=[h.hour for h in data.hours],
        local=local,
        day=local.normalize(),
        hour=local.hour,
        n_stations=[len(h.nox) for h in data.hours],
        nox=[h.nox.mean() for h in data.hours],
        speed=[np.hypot(*h.wind) for h in data.hours],
        pbl=[h.pbl for h in data.hours],
        vcd=[h.no2.mean() if len(h.no2) else np.nan for h in data.hours],
        n_pixels=[len(h.no2) for h in data.hours],
    )


def feature_rows(data: Inputs) -> pd.DataFrame:
    """One row per station-hour of the inputs: ``station``, ``utc``, ``day``, ``nox`` and the hour features
    of the models (`hourly_table`)."""
    hours = hourly_table(data)
    counts = [len(ids) for ids in data.station_ids]
    rows = hours.loc[hours.index.repeat(counts)].reset_index(drop=True)
    rows["station"] = np.concatenate(data.station_ids)
    rows["nox"] = np.concatenate([h.nox for h in data.hours])
    return rows


# --- Bivariate and multivariate ---------------------------------------------------------------------------


def ventilation_relation(rows: pd.DataFrame, bins: int = 10) -> tuple[pd.DataFrame, float, float]:
    """NOx by decile of ventilation (median and quartiles), the Spearman correlation of the two and the slope
    of log NOx on log ventilation (-1 if the concentration were emission over ventilation)."""
    deciles = pd.qcut(rows["ventilation"], bins, duplicates="drop")
    g = rows.groupby(deciles, observed=True)
    table = pd.DataFrame(
        {
            "ventilation_median": g["ventilation"].median(),
            "nox_q1": g["nox"].quantile(0.25),
            "nox_median": g["nox"].median(),
            "nox_q3": g["nox"].quantile(0.75),
            "rows": g.size(),
        }
    ).reset_index(drop=True)
    rho = float(stats.spearmanr(rows["ventilation"], rows["nox"]).statistic)
    slope = float(np.polyfit(np.log(rows["ventilation"]), np.log(rows["nox"]), 1)[0])
    return table, rho, slope


def plot_ventilation(rows: pd.DataFrame) -> Figure:
    """NOx against ventilation (log-log): the station-hours, the median by decile and the 1/x line through the
    medians' geometric centre."""
    table, rho, slope = ventilation_relation(rows)
    fig = Figure(figsize=(11, 3.8), layout="constrained")
    a, b = fig.subplots(1, 2)
    a.plot(rows["ventilation"], rows["nox"], ".", ms=2, alpha=0.2, color="#9ecae9")
    a.fill_between(table["ventilation_median"], table["nox_q1"], table["nox_q3"], color="#4c78a8", alpha=0.3)
    a.plot(table["ventilation_median"], table["nox_median"], "o-", color="#4c78a8", label="mediana por decil")
    centre = np.exp(np.log(table["ventilation_median"]).mean()), np.exp(np.log(table["nox_median"]).mean())
    x = np.geomspace(rows["ventilation"].min(), rows["ventilation"].max(), 50)
    a.plot(x, centre[0] * centre[1] / x, "--", color="#e45756", label="∝ 1 / ventilación")
    a.set(xscale="log", yscale="log", xlabel="ventilación = viento × capa límite (m²/s)", ylabel="NOₓ (ppb)")
    a.set_title(f"NOₓ frente a ventilación (Spearman {rho:.2f}, pendiente log-log {slope:.2f})")
    a.xaxis.set_minor_formatter(NullFormatter())
    a.legend()
    hourly = rows.groupby("hour")[["ventilation", "nox"]].median()
    b.plot(hourly.index, hourly["nox"], "o-", color="#4c78a8", label="NOₓ")
    b.set(
        xlabel="hora local (inicio de la hora)",
        ylabel="NOₓ mediano (ppb)",
        title="Tarde: NOₓ y ventilación por hora",
    )
    c = b.twinx()
    c.plot(hourly.index, hourly["ventilation"], "s-", color="#f58518", label="ventilación")
    c.set_ylabel("ventilación mediana (m²/s)")
    return fig


def day_type_names(days: pd.DatetimeIndex) -> pd.Series:
    """Name of the day type (weekday, saturday, sunday_holiday) of each local day."""
    return pd.Series(np.array(DAY_TYPE_NAMES)[day_type(days, HOLIDAYS)], index=days)


def day_type_table(rows: pd.DataFrame) -> pd.DataFrame:
    """By day type: days, station-hours, mean NOx and ventilation, and the ratios to the weekday. The raw
    ratio mixes the change in emissions with the weather of those days; it is not an estimate of it."""
    kinds = day_type_names(pd.DatetimeIndex(rows["day"])).to_numpy()
    g = rows.groupby(kinds)
    out = pd.DataFrame(
        {
            "days": g["day"].nunique(),
            "rows": g.size(),
            "nox_mean": g["nox"].mean(),
            "ventilation_mean": g["ventilation"].mean(),
        }
    ).reindex(DAY_TYPE_NAMES)
    out["nox_ratio"] = out["nox_mean"] / out.loc["weekday", "nox_mean"]
    out["ventilation_ratio"] = out["ventilation_mean"] / out.loc["weekday", "ventilation_mean"]
    return out


def daily_cycle(nox: pd.DataFrame, period: tuple[str, str] = MODEL_PERIOD) -> pd.DataFrame:
    """Mean NOx of the stations by hour label (columns: day type), over all the hours of the day."""
    part = in_window(nox, period)
    days = part["local"].dt.normalize()
    kinds = day_type_names(pd.DatetimeIndex(days.unique())).reindex(days).to_numpy()
    return (
        part.groupby([part["local"].dt.hour, kinds])["NOX"].mean().unstack().reindex(columns=DAY_TYPE_NAMES)
    )


def plot_daily_cycle(cycle: pd.DataFrame) -> Figure:
    """Daily cycle of NOx by day type, with the hours the models use shaded."""
    fig = Figure(figsize=(8, 3.6), layout="constrained")
    ax = fig.subplots()
    for kind in cycle.columns:
        ax.plot(cycle.index, cycle[kind], "o-", ms=3, label=kind)
    ax.axvspan(AFTERNOON[0] - 0.5, AFTERNOON[1] + 0.5, color="gray", alpha=0.15, label="horas de los modelos")
    ax.set(title="Ciclo diario del NOₓ", xlabel="hora local (etiqueta SIMAT)", ylabel="ppb")
    ax.legend()
    return fig


def tempo_station_pairs(tables: Tables) -> pd.DataFrame:
    """Station NO2 paired with the nearest valid TEMPO pixel (within 3 km, same hour) in `MODEL_PERIOD`."""
    no2 = tables.nox[["id_station", "utc", "NO2"]]
    stations = tables.catalog[tables.catalog["in_domain"]]
    return tempo.match_stations(tables.pixels[tables.pixels["valid"]], no2, stations)


def pair_correlations(pairs: pd.DataFrame) -> pd.DataFrame:
    """Correlation of station NO2 with the TEMPO column: over all pairs (Pearson and Spearman), within each
    granule (median over granules with at least 5 stations) and between station means."""
    means = pairs.groupby("station")[["no2_ppb", "vcd"]].mean()
    within = pd.Series([g["no2_ppb"].corr(g["vcd"]) for _, g in pairs.groupby("granule") if len(g) >= 5])
    rows = {
        "all pairs, Pearson": (pairs["no2_ppb"].corr(pairs["vcd"]), len(pairs)),
        "all pairs, Spearman": (pairs["no2_ppb"].corr(pairs["vcd"], method="spearman"), len(pairs)),
        "within granule, median": (within.median(), int(within.notna().sum())),
        "station means": (means["no2_ppb"].corr(means["vcd"]), len(means)),
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=["r", "n"])


def plot_tempo_pairs(pairs: pd.DataFrame) -> Figure:
    """TEMPO column against station NO2: every pair and the mean of each station."""
    means = pairs.groupby("station")[["no2_ppb", "vcd"]].mean()
    fig = Figure(figsize=(11, 3.8), layout="constrained")
    a, b = fig.subplots(1, 2)
    a.plot(pairs["no2_ppb"], pairs["vcd"], ".", ms=3, alpha=0.3, color="#4c78a8")
    a.set(xlabel="NO₂ en estación (ppb)", ylabel="columna troposférica TEMPO (molec/cm²)")
    a.set_title(f"Pares hora–estación (r = {pairs['no2_ppb'].corr(pairs['vcd']):.2f})")
    b.plot(means["no2_ppb"], means["vcd"], "o", color="#4c78a8")
    for station, r in means.iterrows():
        b.annotate(
            str(station), (r["no2_ppb"], r["vcd"]), fontsize=7, xytext=(3, 3), textcoords="offset points"
        )
    b.set(xlabel="NO₂ medio (ppb)", ylabel="columna media (molec/cm²)")
    b.set_title(f"Medias por estación (r = {means['no2_ppb'].corr(means['vcd']):.2f})")
    return fig


def correlation_matrix(df: pd.DataFrame, columns: Sequence[str], method: str = "spearman") -> pd.DataFrame:
    """Correlation of the `columns` of `df`."""
    return df[list(columns)].corr(method=method)


def plot_correlation(corr: pd.DataFrame, title: str = "Correlación de Spearman") -> Figure:
    """Heat map of a correlation matrix with the coefficients written in."""
    n = len(corr)
    fig = Figure(figsize=(0.75 * n + 2.5, 0.65 * n + 1.5), layout="constrained")
    ax = fig.subplots()
    image = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(n), corr.columns, rotation=60, ha="right")
    ax.set_yticks(range(n), corr.index)
    for i in range(n):
        for j in range(n):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, shrink=0.8)
    return fig


# --- Temporal trends ---------------------------------------------------------------------------------------


def daily_series(rows: pd.DataFrame) -> pd.DataFrame:
    """Mean NOx of the afternoon of each local day (over stations and hours), its stations and the mean
    ventilation, with the day type."""
    g = rows.groupby("day")
    out = pd.DataFrame(
        {"nox": g["nox"].mean(), "ventilation": g["ventilation"].mean(), "stations": g["station"].nunique()}
    )
    out["day_type"] = day_type_names(pd.DatetimeIndex(out.index)).to_numpy()
    return out


def plot_daily_trend(daily: pd.DataFrame) -> Figure:
    """Daily mean NOx with its 7-day rolling mean (Saturdays and Sundays/holidays marked) above the daily
    mean ventilation."""
    fig = Figure(figsize=(11, 5.2), layout="constrained")
    ax, vent = fig.subplots(2, 1, sharex=True, height_ratios=(3, 2))
    ax.plot(daily.index, daily["nox"], "o-", ms=3, lw=0.8, color="#9ecae9", label="media diaria")
    ax.plot(daily.index, rolling(daily["nox"]), color="#4c78a8", lw=2, label="media móvil 7 días")
    rest = daily[daily["day_type"] != "weekday"]
    ax.plot(rest.index, rest["nox"], "s", ms=5, color="#e45756", label="sábado, domingo o festivo")
    ax.set(title="NOₓ medio de las tardes por día", ylabel="ppb")
    ax.legend()
    vent.plot(daily.index, daily["ventilation"], "o-", ms=3, lw=0.8, color="#fdd0a2")
    vent.plot(daily.index, rolling(daily["ventilation"]), color="#f58518", lw=2)
    vent.set(title="Ventilación media de las tardes", ylabel="m²/s")
    return fig


def rolling(series: pd.Series, window: int = 7) -> pd.Series:
    """Centered rolling mean of `window` days (at least 4 days at the edges)."""
    return series.rolling(window, center=True, min_periods=4).mean()


def weekly_cycle(rows: pd.DataFrame) -> pd.DataFrame:
    """Mean NOx and ventilation by day of the week (0 = Monday), with the days behind each."""
    weekday = pd.DatetimeIndex(rows["day"]).day_of_week
    g = rows.groupby(weekday)
    return pd.DataFrame(
        {"days": g["day"].nunique(), "nox_mean": g["nox"].mean(), "ventilation_mean": g["ventilation"].mean()}
    ).rename_axis("weekday")


def plot_weekly_cycle(weekly: pd.DataFrame) -> Figure:
    """NOx and ventilation by day of the week."""
    names = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    fig = Figure(figsize=(8, 3.4), layout="constrained")
    ax = fig.subplots()
    ax.bar(names, weekly["nox_mean"].reindex(range(7)), color="#4c78a8")
    ax.set(title="Ciclo semanal (tardes, nov–dic 2023)", ylabel="NOₓ medio (ppb)")
    c = ax.twinx()
    c.plot(names, weekly["ventilation_mean"].reindex(range(7)), "s-", color="#f58518")
    c.set_ylabel("ventilación media (m²/s)")
    return fig


def quality_by_month(tables: Tables) -> pd.DataFrame:
    """Data-quality indicators by month, Nov 2023 to May 2024: stations reporting NOx in the afternoons, those
    with at least 75 % of the hours, the mean completeness of the reporting ones, the share of afternoon hours
    with enough wind stations, the share of boundary layer hours from MERRA-2 and the TEMPO valid share.
    ``period`` says whether the month is modelling data or the held-out period (these numbers never feed a
    decision)."""
    aft = in_window(tables.nox, ("2023-11-01", "2024-05-31"), AFTERNOON)
    stations = set(tables.catalog.loc[tables.catalog["in_domain"], "station"])
    completeness = simat.afternoon_completeness(aft[aft["id_station"].isin(stations)], stations)
    reporting = completeness.where(completeness > 0)
    wind = simat.wind_station_coverage(tables.wind, stations)
    out = pd.DataFrame(
        {
            "reporting_stations": reporting.count(axis=1),
            "valid_stations": (completeness >= MIN_AFTERNOON_COMPLETENESS).sum(axis=1),
            "completeness_pct": 100 * reporting.mean(axis=1),
            "wind_ok_pct": 100 * wind["share_hours_ok"],
        }
    )
    sources = pbl_sources(tables.pbl)
    out["pbl_merra_pct"] = 100 * (1 - sources.get("ERA5", 0) / sources.sum(axis=1))
    pixels = pd.concat([tables.pixels, tables.pixels_test])
    out["tempo_valid_pct"] = tempo_by_month(pixels)["valid_pct"]
    out = out.loc["2023-11":"2024-05"]
    out["period"] = np.where(
        out.index.astype(str) <= MODEL_PERIOD[1][:7], "modelado", "prueba (solo calidad)"
    )
    return out


def preprocessing_impact(tables: Tables) -> pd.DataFrame:
    """What each preprocessing decision touched, in numbers: the stuck hours masked, the wind rows corrected
    from mph, the boundary layer hours filled with MERRA-2 and the TEMPO pixels rejected."""
    stuck = int(stuck_table(tables.nox_raw, tables.nox)["stuck_hours"].sum())
    model_wind = in_window(tables.wind, MODEL_PERIOD)
    pbl = pbl_sources(tables.pbl)
    merra_hours = int(pbl.drop(columns="ERA5", errors="ignore").sum().sum())
    px = tables.pixels
    rows = [
        ("Sensores atascados enmascarados", "SIMAT 2023–2024", f"{stuck} horas-estación de NOₓ"),
        (
            "Viento 2024 de mph a m/s",
            "SIMAT 2024",
            f"{int(tables.wind['wsp_fix_mph'].sum()):,} filas; nov–dic 2023 no se toca "
            f"({int(model_wind['wsp_fix_mph'].sum())} filas corregidas)",
        ),
        (
            "Capa límite con MERRA-2 corregido",
            "2024",
            f"{merra_hours:,} horas de {len(tables.pbl):,}; nov–dic 2023: 0",
        ),
        (
            "Filtros de calidad de TEMPO",
            "nov–dic 2023",
            f"{100 * (1 - px['valid'].mean()):.0f} % de los píxeles rechazados "
            f"({int(px['valid'].sum()):,} válidos)",
        ),
    ]
    return pd.DataFrame(rows, columns=["decision", "applies_to", "amount"])


# --- Feature construction (Avance 2) ------------------------------------------------------------------------


def feature_summary(rows: pd.DataFrame, columns: Sequence[str] = FEATURES) -> pd.DataFrame:
    """Minimum, median, maximum and missing count of each feature."""
    d = describe(rows, columns)
    return d[["min", "median", "max"]].assign(missing=[int(rows[c].isna().sum()) for c in columns])


def cyclic_check(period: int = 24) -> pd.DataFrame:
    """Distance between consecutive values of a cyclic variable of `period` steps, as the raw number and as
    the point (sin, cos) on the circle: the circle makes the last step to the first as short as any other."""
    step = np.arange(period)
    angle = 2 * np.pi * step / period
    nxt = (step + 1) % period
    circle = np.hypot(
        np.sin(angle) - np.sin(2 * np.pi * nxt / period), np.cos(angle) - np.cos(2 * np.pi * nxt / period)
    )
    return pd.DataFrame(
        {"from": step, "to": nxt, "raw_distance": np.abs(nxt - step), "circle_distance": circle}
    )


def plot_wind_rose(hours: pd.DataFrame) -> Figure:
    """Where the wind comes from (degrees clockwise from north) in the hours of the inputs, as a rose, and the
    two components that encode it (`wind_sin`, `wind_cos`, which point where the wind goes)."""
    towards = np.arctan2(hours["wind_sin"], hours["wind_cos"])
    fig = Figure(figsize=(9, 3.8), layout="constrained")
    rose = fig.add_subplot(1, 2, 1, projection="polar")
    counts, edges = np.histogram((np.pi - towards + np.pi / 2) % (2 * np.pi), bins=16, range=(0, 2 * np.pi))
    rose.bar(
        edges[:-1] + np.diff(edges) / 2, counts, width=np.diff(edges), color="#4c78a8", edgecolor="white"
    )
    rose.set_theta_zero_location("N")
    rose.set_theta_direction(-1)
    rose.set_title("Rosa de vientos (de dónde sopla)", pad=14)
    comp = fig.add_subplot(1, 2, 2)
    comp.plot(hours["wind_cos"], hours["wind_sin"], ".", ms=3, alpha=0.5, color="#4c78a8")
    comp.set(xlabel="wind_cos", ylabel="wind_sin", title="Dirección como punto del círculo", aspect="equal")
    return fig


def floor_share(nox: pd.Series) -> float:
    """Share of the NOx values that the target of E6 floors (within 1 ppb of the background)."""
    return float((transformed_target(nox.dropna()) <= 0).mean())


def ventilation_gain(rows: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlation of station NOx with each weather variable alone and with the ventilation
    (wind × boundary layer height) and its sums: the product explains more than either factor."""
    columns = {"speed": "viento", "pbl": "capa límite", **{v: v for v in VENTILATION}}
    rho = {label: stats.spearmanr(rows[c], rows["nox"]).statistic for c, label in columns.items()}
    return pd.Series(rho, name="spearman_with_nox").to_frame()


def road_proxy(zones: pd.DataFrame, station_xy: pd.DataFrame, radius_m: float) -> pd.Series:
    """Road emission (t/yr of the OSM proxy) within `radius_m` of each station: the sum of the weights of the
    road cells whose centre is that close."""
    dx = station_xy["x"].to_numpy()[:, None] - zones["x"].to_numpy()[None, :]
    dy = station_xy["y"].to_numpy()[:, None] - zones["y"].to_numpy()[None, :]
    near = np.hypot(dx, dy) <= radius_m
    return pd.Series(
        near @ zones["weight"].to_numpy(), index=station_xy.index, name=f"road_{radius_m / 1000:g}km"
    )


def station_level(rows: pd.DataFrame) -> pd.Series:
    """Mean log of the NOx above the background of each station: its level, as the models' target sees it."""
    return transformed_target(rows["nox"]).groupby(rows["station"]).mean()


def proxy_relation(
    zones: pd.DataFrame,
    station_xy: pd.DataFrame,
    rows: pd.DataFrame,
    radii_m: Sequence[float] = (500, 1000, 2000, 3000, 5000),
) -> pd.DataFrame:
    """Spearman correlation (and p-value) between the station levels and the road proxy at several radii, over
    the stations with data."""
    level = station_level(rows)
    xy = station_xy.loc[level.index]
    out = []
    for radius in radii_m:
        proxy = road_proxy(zones, xy, radius)
        result = stats.spearmanr(proxy, level)
        out.append(
            {
                "radius_m": radius,
                "stations": len(level),
                "spearman": result.statistic,
                "p_value": result.pvalue,
            }
        )
    return pd.DataFrame(out)


def plot_road_proxy(
    zones: pd.DataFrame, station_xy: pd.DataFrame, rows: pd.DataFrame, radius_m: float
) -> Figure:
    """Road-cell map with the stations sized by level, and level against proxy at `radius_m`."""
    level = station_level(rows)
    xy = station_xy.loc[level.index]
    proxy = road_proxy(zones, xy, radius_m)
    fig = Figure(figsize=(11, 4.2), layout="constrained")
    a, b = fig.subplots(1, 2)
    a.scatter(
        zones["x"] / 1000, zones["y"] / 1000, c=np.log10(zones["weight"]), s=6, cmap="Greys", marker="s"
    )
    sizes = 20 + 150 * (level - level.min()) / (level.max() - level.min())
    a.scatter(xy["x"] / 1000, xy["y"] / 1000, s=sizes, c="#e45756", alpha=0.7, edgecolor="k")
    a.set(
        title="Celdas con calle (gris) y estaciones (tamaño = nivel de NOₓ)",
        xlabel="este UTM (km)",
        ylabel="norte UTM (km)",
    )
    a.set_aspect("equal")
    b.plot(proxy, level, "o", color="#4c78a8")
    for station in level.index:
        b.annotate(
            str(station),
            (proxy[station], level[station]),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    rho = stats.spearmanr(proxy, level).statistic
    b.set(xlabel=f"proxy vial en {radius_m / 1000:g} km (t/año)", ylabel="log(NOₓ − fondo) medio")
    b.set_title(f"Nivel de la estación frente al proxy (Spearman {rho:.2f})")
    return fig


# --- Transformations ---------------------------------------------------------------------------------------


def transformed_target(nox: pd.Series, background_ppb: float = BACKGROUND_STATION[0]) -> pd.Series:
    """The target of the random forest (E6): log of the NOx above the background, floored at 1 ppb."""
    return np.log(np.maximum(nox - background_ppb, FLOOR_ABOVE_BACKGROUND_PPB))


def transform_effect(nox: pd.Series) -> pd.DataFrame:
    """Skewness, and the share of the total squared deviation held by the highest 5 % of the values, for the
    NOx in ppb and for the transformations considered: the more a few values dominate, the more the fit
    follows them."""
    candidates = {
        "ppb": nox,
        "raíz cuadrada": np.sqrt(nox),
        "log(NOₓ)": np.log(nox),
        "log(NOₓ − fondo), piso 1 ppb (E6)": transformed_target(nox),
    }
    rows = {}
    for name, s in candidates.items():
        s = s.dropna()
        dev = (s - s.mean()) ** 2
        top = s >= s.quantile(0.95)
        rows[name] = {"skew": s.skew(), "top5pct_share_of_variance": float(dev[top].sum() / dev.sum())}
    return pd.DataFrame.from_dict(rows, orient="index")


def plot_transform(nox: pd.Series) -> Figure:
    """Histogram of the NOx in ppb and of the target of E6."""
    fig = Figure(figsize=(9, 3.4), layout="constrained")
    for ax, (name, s) in zip(
        fig.subplots(1, 2),
        {"NOₓ (ppb)": nox, "log(NOₓ − fondo), piso 1 ppb": transformed_target(nox)}.items(),
        strict=True,
    ):
        ax.hist(s.dropna(), bins=60, color="#4c78a8")
        ax.set(title=f"{name}: asimetría {s.skew():.2f}", ylabel="frecuencia")
    return fig


def nondimensional_table() -> pd.DataFrame:
    """The scales of the PINN equation (`models.pinn.equation`): what each dimensional variable becomes."""
    rows = [
        ("posición a lo largo del viento x_a", "m", "A = x_a / L", f"L = {equation.L_M:,.0f} m"),
        ("posición transversal x_c", "m", "C = x_c / L", f"L = {equation.L_M:,.0f} m"),
        (
            "viento |u|, vida del NOₓ τ",
            "m/s, s",
            "γ = L / (|u| τ)",
            f"γ entre {equation.GAMMA_RANGE[0]} y {equation.GAMMA_RANGE[1]}",
        ),
        (
            "difusividad por unidad de viento κ",
            "m",
            "ε = κ / L",
            f"ε = {equation.EPS:g} (κ = {equation.KAPPA_M:,.0f} m)",
        ),
        (
            "columna por fuente unitaria F",
            "g/m² por g/s ·m/s",
            "G = F / (|u| L)",
            "una sola función F(A, C, γ)",
        ),
    ]
    return pd.DataFrame(rows, columns=["variable", "units", "nondimensional", "scale"])


def gamma_coverage(speed: pd.Series, tau_hours: Sequence[float] = TAU_HOURS) -> pd.DataFrame:
    """γ = L / (|u| τ) of the wind speeds `speed` (m/s) for each NOx lifetime: its quartiles and the share of
    hours inside the range the network is trained on."""
    low, high = equation.GAMMA_RANGE
    rows = {}
    for tau in tau_hours:
        gamma = equation.L_M / (speed.clip(lower=1e-6) * tau * 3600)
        rows[f"τ = {tau:g} h"] = {
            "gamma_q1": gamma.quantile(0.25),
            "gamma_median": gamma.median(),
            "gamma_q3": gamma.quantile(0.75),
            "inside_range_pct": 100 * float(gamma.between(low, high).mean()),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def plot_green_function(gammas: Sequence[float] = equation.GAMMA_CHECKS) -> Figure:
    """The exact nondimensional column ``F(A, 0)`` along the wind axis for several γ: every wind and lifetime
    of the data falls on one of these curves."""
    fig = Figure(figsize=(8, 3.6), layout="constrained")
    ax = fig.subplots()
    for gamma in gammas:
        a, c, field = equation.exact(gamma)
        ax.plot(a, field[:, np.argmin(np.abs(c))], label=f"γ = {gamma}")
    ax.set(xlim=equation.A_RANGE, xlabel="A = distancia a lo largo del viento / L", ylabel="F(A, C = 0)")
    ax.set_title("Función de Green adimensional de la ecuación del PINN")
    ax.legend()
    return fig


# --- Selection and extraction ---------------------------------------------------------------------------


def collinear_pairs(corr: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Pairs of features whose absolute correlation reaches `threshold`, strongest first."""
    pairs = [
        {"a": a, "b": b, "corr": corr.loc[a, b]}
        for i, a in enumerate(corr.columns)
        for b in corr.columns[i + 1 :]
        if abs(corr.loc[a, b]) >= threshold
    ]
    return pd.DataFrame(pairs, columns=["a", "b", "corr"]).sort_values(
        "corr", key=abs, ascending=False, ignore_index=True
    )


def variance_table(rows: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Standard deviation, coefficient of variation (of the absolute mean), distinct values and the share of
    the most frequent value of each column: a column with no spread carries no information."""
    out = {}
    for c in columns:
        s = rows[c]
        mean = abs(s.mean())
        out[c] = {
            "std": s.std(),
            "cv": s.std() / mean if mean > 0 else np.nan,
            "unique": int(s.nunique()),
            "top_value_share": float(s.value_counts(normalize=True).iloc[0]),
        }
    return pd.DataFrame.from_dict(out, orient="index")


def pca_table(rows: pd.DataFrame, columns: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """PCA of the standardized `columns`: ``(explained, loadings)``, with the explained variance (share and
    cumulative) of each component and the weight of every column in it."""
    pca = PCA().fit(StandardScaler().fit_transform(rows[list(columns)]))
    names = [f"PC{i + 1}" for i in range(len(columns))]
    explained = pd.DataFrame(
        {"explained": pca.explained_variance_ratio_, "cumulative": np.cumsum(pca.explained_variance_ratio_)},
        index=names,
    )
    return explained, pd.DataFrame(np.asarray(pca.components_).T, index=list(columns), columns=names)


def feature_relevance(rows: pd.DataFrame, columns: Sequence[str] = FEATURES, seed: int = 0) -> pd.DataFrame:
    """Relevance of each feature for the target of E6 (`transformed_target`): absolute Spearman correlation
    and mutual information (nats), ordered by the latter. Both see one feature at a time."""
    target = transformed_target(rows["nox"])
    mi = mutual_info_regression(rows[list(columns)], target, random_state=seed)
    out = pd.DataFrame(
        {
            "abs_spearman": [abs(stats.spearmanr(rows[c], target).statistic) for c in columns],
            "mutual_info": mi,
        },
        index=list(columns),
    )
    return out.sort_values("mutual_info", ascending=False)


def station_pca(rows: pd.DataFrame, min_share: float = 0.8) -> pd.DataFrame:
    """PCA of the log NOx of the stations, hour by hour: how many independent spatial patterns the network
    sees. Only stations present in at least `min_share` of the hours, and hours with all of them."""
    wide = transformed_target(rows["nox"]).groupby([rows["utc"], rows["station"]]).mean().unstack()
    wide = wide.loc[:, wide.notna().mean() >= min_share].dropna()
    pca = PCA().fit(StandardScaler().fit_transform(wide))
    explained = pd.DataFrame(
        {"explained": pca.explained_variance_ratio_, "cumulative": np.cumsum(pca.explained_variance_ratio_)}
    )
    explained.index = [f"PC{i + 1}" for i in range(len(explained))]
    explained.attrs["stations"], explained.attrs["hours"] = wide.shape[1], wide.shape[0]
    return explained


def plot_pca(explained: pd.DataFrame, station_explained: pd.DataFrame, loadings: pd.DataFrame) -> Figure:
    """Scree of the weather block, loadings of its first two components and scree of the stations."""
    fig = Figure(figsize=(12, 3.6), layout="constrained")
    a, b, c = fig.subplots(1, 3)
    _scree(a, explained, "Bloque de clima")
    loadings[["PC1", "PC2"]].plot.barh(ax=b, color=["#4c78a8", "#f58518"])
    b.set_title("Pesos de los dos primeros componentes")
    _scree(c, station_explained.head(12), "NOₓ de las estaciones")
    return fig


def _scree(ax: Axes, explained: pd.DataFrame, title: str) -> None:
    ax.bar(explained.index, 100 * explained["explained"], color="#4c78a8")
    ax.plot(explained.index, 100 * explained["cumulative"], "o-", color="#e45756")
    ax.set(title=title, ylabel="% de la varianza (barras) y acumulado (línea)", ylim=(0, 105))
    ax.tick_params(axis="x", rotation=60)


def observation_information(data: Inputs) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Variance reduction of every unknown and degrees of freedom for signal with the stations only, TEMPO
    only and both, for the baseline inversion (`diagnostics.information_by_observation`)."""
    from nox_ml.models.inversion_plume import InversionPlume

    systems = diagnostics.model_systems(data, InversionPlume())
    return diagnostics.information_by_observation(systems, data.points, data.n_regions)


def plot_information(dofs: pd.DataFrame) -> Figure:
    """Degrees of freedom for signal by group of unknowns, for each source of observations."""
    groups = [c for c in dofs.columns if c not in ("source", "dofs")]
    frame = dofs.set_index("source")[groups]
    fig = Figure(figsize=(8, 3.6), layout="constrained")
    ax = fig.subplots()
    frame.plot.bar(ax=ax, rot=0, color=["#bab0ac", "#4c78a8", "#f58518", "#54a24b"][: len(groups)])
    ax.set(title="Información por tipo de observación", xlabel="", ylabel="grados de libertad para la señal")
    ax.set_ylim(0, 1.3 * frame.to_numpy().max())
    ax.legend(ncol=len(groups), loc="upper center")
    return fig
