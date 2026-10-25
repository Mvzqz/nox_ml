# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""What the experiment notebooks of ``deliverables/experimentos/`` show. Each section is one notebook:

1. transport: the Gaussian plume, the kernel of the PINN and the puffs of both, side by side;
2. emission against weather: the normalized estimator and the random forest on a twin with a known answer, on
   real data, and the placebo that calibrates them;
3. PINN puff fit: the searches and trials of ``runs/`` (the runs exist only on the owner's machine);
4. ablation: the diagnostics of ``nox-ml diagnose``;
5. wind and objective: a twin with wind-direction errors and the real wind error.

The notebooks only call these functions; they compute with the rest of ``nox_ml`` and return DataFrames or
matplotlib figures (labels in Spanish, as the notebooks). Whatever reads ``runs/`` tolerates missing runs.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.data.inputs import Inputs
from nox_ml.data.pbl import ERA5_FILE
from nox_ml.data.roads import UTM
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import (
    HOLIDAYS,
    SIGMA_THETA,
    U_MIN,
    HourData,
    Posterior,
    hour_systems,
    solve,
)
from nox_ml.inversion.normalized import SATURDAY, SUNDAY_HOLIDAY, WEEKDAY, bootstrap_ratio, day_type, interval
from nox_ml.models import REGISTRY, Model
from nox_ml.models.inversion_plume import InversionPlume
from nox_ml.models.rf_deweather import RfDeweatherParams
from nox_ml.time import local_day, local_hour
from nox_ml.validation import compare, experiment, report
from nox_ml.validation.diagnostics import rotate_wind
from nox_ml.validation.placebo import split_placebo
from nox_ml.validation.report import NotebookFigure

Array = NDArray[np.float64]

KIND_NAMES = {WEEKDAY: "día hábil", SATURDAY: "sábado", SUNDAY_HOLIDAY: "domingo o festivo"}
KIND_COLORS = {WEEKDAY: "#4d4d4d", SATURDAY: "#d98f1f", SUNDAY_HOLIDAY: "#2a7fb8"}
TRAFFIC_BAND = (0.65, 0.73)  # Sunday over weekday from traffic counts (nox_ml.validation.metrics)


def _interval_text(lo: float, hi: float) -> str:
    return f"{lo:.2f}–{hi:.2f}"


# --- Synthetic twin: observations simulated from known emissions -----------------------------------------


@dataclass(frozen=True)
class Truth:
    """Emissions that generate a twin, in the unknowns of the inversion: the point sources (t/yr) and, per
    day type, one factor on the prior of each road region."""

    points: Array
    roads: Array  # (day type, region)

    def road_total(self, prior: Array, kind: int) -> float:
        """Road emission (t/yr) of a day type, all the regions together."""
        return float(self.roads[kind] @ prior)

    def ratio(self, prior: Array, kind: int) -> float:
        """Road emission of a day type over the weekday's."""
        return self.road_total(prior, kind) / self.road_total(prior, WEEKDAY)


def region_prior(inputs: Inputs) -> Array:
    """Prior road emission (t/yr) of each region."""
    by_region = inputs.zones.groupby("region")["weight"].sum()
    return by_region.reindex(range(inputs.n_regions), fill_value=0.0).to_numpy(float)


def make_truth(
    inputs: Inputs,
    seed: int = 0,
    saturday: float = 0.8,
    sunday: float = 0.5,
    point_spread: float = 0.5,
    zone_spread: float = 0.3,
) -> Truth:
    """Random emissions around the priors: every point source is its prior times a lognormal factor of
    spread `point_spread` and every road region a weekday factor of spread `zone_spread`; Saturday and Sunday
    are the weekday's times `saturday` and `sunday`, so the day-type ratios are known exactly."""
    rng = np.random.default_rng(seed)
    points = inputs.points["prior"].to_numpy(float) * np.exp(
        point_spread * rng.normal(size=len(inputs.points))
    )
    weekday = np.exp(zone_spread * rng.normal(size=inputs.n_regions))
    return Truth(points, np.vstack([weekday, saturday * weekday, sunday * weekday]))


def _kinds(inputs: Inputs) -> list[int]:
    days = pd.DatetimeIndex([local_day(h.hour) for h in inputs.hours])
    kinds = day_type(days, HOLIDAYS)
    return [(inputs.day_kinds or {}).get(d, int(k)) for d, k in zip(days, kinds, strict=True)]


def simulate_observations(
    inputs: Inputs,
    truth: Truth,
    model: InversionPlume | None = None,
    seed: int = 0,
    station_noise_ppb: float = 8.0,
    pixel_noise: float = 2e15,
    background: tuple[float, float] = (5.0, 3.0),
) -> Inputs:
    """The inputs with the observations replaced by the model's response to `truth` plus noise: station NOx
    (ppb) with an hourly background of mean and standard deviation `background`, and TEMPO columns with the
    same background in molecules/cm2 scaled by 1e15 (mean 5e15). The wind, boundary layer and receptors are
    the real ones; `model` (default: the baseline) is the forward model, so the twin has no model error."""
    model = model or InversionPlume()
    jacobians = inputs.jacobians(model.transport_key(), model.transport())
    rng = np.random.default_rng(seed)
    hours = []
    for data, jac, kind in zip(inputs.hours, jacobians, _kinds(inputs), strict=True):
        state = np.r_[truth.points, truth.roads[kind]]
        bg = np.maximum(rng.normal(*background), 0.0)
        nox = jac.stations @ state + bg + station_noise_ppb * rng.normal(size=len(data.nox))
        no2 = jac.pixels @ state + bg * 1e15 + pixel_noise * rng.normal(size=len(data.no2))
        hours.append(replace(data, nox=np.maximum(nox, 0.0), no2=np.maximum(no2, 0.0)))
    return replace(inputs, hours=hours)  # same wind: the cached Jacobians stay valid


def perturb_wind(inputs: Inputs, sigma_deg: float, seed: int = 0) -> Inputs:
    """The inputs with an independent random error of standard deviation `sigma_deg` degrees in the wind
    direction of every hour (the speed is kept): the wind the analyst has when the true one is different."""
    errors = np.random.default_rng(seed).normal(0.0, sigma_deg, len(inputs.hours))
    return rotate_wind(inputs, errors)


def invert(inputs: Inputs, model: InversionPlume | None = None) -> Posterior:
    """Posterior of the point sources and road factors of the inversion with the transport of `model`."""
    model = model or InversionPlume()
    systems = hour_systems(
        inputs.hours,
        inputs.zones,
        inputs.points,
        inputs.no2_nox_ratio,
        inputs.n_regions,
        HOLIDAYS,
        day_kinds=inputs.day_kinds,
        jacobians=inputs.jacobians(model.transport_key(), model.transport()),
    )
    return solve(systems, inputs.points, inputs.n_regions)


def recovery(inputs: Inputs, truth: Truth, model: InversionPlume | None = None) -> pd.DataFrame:
    """What the inversion of `inputs` recovers of `truth`: one row per quantity with its true value, the
    estimate and the relative error. Quantities: each point source, each road region on weekdays, the road
    total on weekdays and the Sunday and Saturday over weekday ratios."""
    post = invert(inputs, model)
    prior = region_prior(inputs)
    factors = post.road_factors()
    estimate_points = post.mean[: post.n_points]
    rows = [
        ("punto", str(name), true, est)
        for name, true, est in zip(inputs.points["name"], truth.points, estimate_points, strict=True)
    ]
    rows += [
        ("zona", f"zona {r}", truth.roads[WEEKDAY, r] * prior[r], factors[WEEKDAY, r] * prior[r])
        for r in range(inputs.n_regions)
        if prior[r] > 0
    ]
    rows.append(("total vial", "total vial", truth.road_total(prior, WEEKDAY), factors[WEEKDAY] @ prior))
    for label, kind in (("domingo/hábil", SUNDAY_HOLIDAY), ("sábado/hábil", SATURDAY)):
        rows.append(
            (label, label, truth.ratio(prior, kind), (factors[kind] @ prior) / (factors[WEEKDAY] @ prior))
        )
    table = pd.DataFrame(rows, columns=["quantity", "name", "truth", "estimate"])
    table["rel_error"] = (table["estimate"] - table["truth"]).abs() / table["truth"].abs()
    return table


def wind_error_twin(
    inputs: Inputs,
    sigmas: Sequence[float] = (0, 5, 10, 20, 30),
    seeds: Sequence[int] = (0, 1, 2),
    model: InversionPlume | None = None,
    **simulation: Any,
) -> pd.DataFrame:
    """The twin with wind-direction errors: for each seed, new true emissions generate the observations with
    the real wind and the inversion is run with the same wind turned by a random error of `sigma` degrees at
    every hour. Rows are `recovery` plus ``sigma`` and ``seed``. Each error builds its own Jacobians (about
    10 s on the full period)."""
    rows = []
    for seed in seeds:
        truth = make_truth(inputs, seed)
        twin = simulate_observations(inputs, truth, model, seed, **simulation)
        for sigma in sigmas:
            analyst = perturb_wind(twin, sigma, seed) if sigma else twin
            rows.append(recovery(analyst, truth, model).assign(sigma=float(sigma), seed=seed))
    return pd.concat(rows, ignore_index=True)


def twin_summary(twin: pd.DataFrame) -> pd.DataFrame:
    """Median relative error (%) of each kind of quantity at each wind error: rows ``sigma``, columns the
    quantities (a point source or region counts once per seed)."""
    errors = twin.groupby(["sigma", "quantity"])["rel_error"].median().unstack("quantity") * 100
    order = [q for q in ("punto", "zona", "total vial", "domingo/hábil", "sábado/hábil") if q in errors]
    return errors[order]


def plot_wind_twin(twin: pd.DataFrame) -> NotebookFigure:
    """Left: the error of each kind of unknown against the wind error. Right: the error of each point source
    (median over seeds)."""
    summary = twin_summary(twin)
    fig = NotebookFigure(figsize=(11, 4), layout="constrained")
    left, right = fig.subplots(1, 2)
    styles = {
        "punto": ("fuentes puntuales (cada una)", "#c0392b", "o"),
        "zona": ("zonas viales (cada una)", "#2a7fb8", "s"),
        "total vial": ("total vial", "#4d4d4d", "^"),
        "domingo/hábil": ("cociente domingo/hábil", "#d98f1f", "D"),
    }
    for column, (label, color, marker) in styles.items():
        if column in summary:
            left.plot(summary.index, summary[column], marker=marker, color=color, label=label)
    left.axhline(25, color="gray", linestyle="--", linewidth=1)
    left.text(summary.index.max(), 26, "meta de 25 %", ha="right", va="bottom", color="gray", fontsize=8)
    left.set(
        xlabel="error del viento (σ, grados)", ylabel="error relativo mediano (%)", title="Cuánto se pierde"
    )
    left.legend(fontsize=8)
    points = (
        twin[twin["quantity"] == "punto"].groupby(["sigma", "name"])["rel_error"].median().unstack("name")
    )
    for name in points:
        right.plot(points.index, points[name] * 100, marker="o", label=str(name)[:22])
    right.axhline(25, color="gray", linestyle="--", linewidth=1)
    right.set(xlabel="error del viento (σ, grados)", ylabel="error relativo (%)", title="Cada fuente puntual")
    right.legend(fontsize=8)
    return fig


# --- Estimators of the emission change -------------------------------------------------------------------


def jacobians_of_baseline(inputs: Inputs):
    """The matrices of every hour with the stationary plume of the harness (15 degrees, 1 m/s)."""
    return inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN))


def daily_normalized(inputs: Inputs) -> pd.DataFrame:
    """Per local day: observed station NOx (``obs``) and NOx modeled with the prior emission and no background
    (``model``), both summed over the hours (``hours``), the ``stagnation`` (modeled NOx per hour) and the
    day type ``kind``. Days with fewer than 4 hours are left out."""
    days = experiment.normalized_days(inputs, jacobians_of_baseline(inputs))
    kinds = day_type(pd.DatetimeIndex(days.index), HOLIDAYS)
    return days.assign(
        kind=[(inputs.day_kinds or {}).get(d, int(k)) for d, k in zip(days.index, kinds, strict=True)]
    )


def index_ratio(
    daily: pd.DataFrame, kind: int = SUNDAY_HOLIDAY, per_hour: bool = False, n_boot: int = 1000, seed: int = 0
) -> tuple[float, float, float]:
    """Index (observed over modeled) of the days of `kind` over the weekday's, with its 90 % bootstrap
    interval over whole days. With `per_hour` the model is the number of hours: the raw concentration ratio,
    with no correction for the weather."""
    frame = daily.reset_index(names="day").assign(group=lambda d: d["kind"])
    if per_hour:
        frame = frame.assign(model=frame["hours"].astype(float))
    value = float(
        (frame.loc[frame.group == kind, "obs"].sum() / frame.loc[frame.group == kind, "model"].sum())
        / (frame.loc[frame.group == WEEKDAY, "obs"].sum() / frame.loc[frame.group == WEEKDAY, "model"].sum())
    )
    boot = bootstrap_ratio(frame, WEEKDAY, kind, n_boot, np.random.default_rng(seed))
    lo, hi = interval(boot)
    return value, lo, hi


def model_ratio(model: Model, inputs: Inputs, kind: str = "sunday_holiday") -> tuple[float, float, float]:
    """Ratio of the road emission of a day type over the weekday's of a fitted model, with its interval (the
    point value twice if the model has none)."""
    estimate = model.fit(inputs).estimate_emissions()
    value = estimate.day_type_ratio(kind)
    bounds = estimate.day_type_interval(kind) or (value, value)
    return value, bounds[0], bounds[1]


def estimator_table(
    inputs: Inputs,
    n_boot: int = 1000,
    seed: int = 0,
    rf_params: Mapping[str, Any] | None = None,
    models: Sequence[str] = ("rf_deweather", "inversion_plume"),
) -> pd.DataFrame:
    """Sunday over weekday of each estimator on the same data: ``concentración`` (observed NOx with no
    weather correction), ``normalizado`` (observed over modeled with fixed emission) and the registered
    `models`. Columns ``estimator``, ``ratio``, ``lo``, ``hi`` (90 % intervals)."""
    daily = daily_normalized(inputs)
    rows = [
        ("concentración sin corregir clima", *index_ratio(daily, per_hour=True, n_boot=n_boot, seed=seed)),
        ("normalizado (observado ÷ modelo)", *index_ratio(daily, n_boot=n_boot, seed=seed)),
    ]
    for name in models:
        params = RfDeweatherParams.model_validate(rf_params or {}) if name == "rf_deweather" else None
        model = REGISTRY[name](params) if params else REGISTRY[name]()
        rows.append((name, *model_ratio(model, inputs)))
    return pd.DataFrame(rows, columns=["estimator", "ratio", "lo", "hi"])


def plot_estimators(
    table: pd.DataFrame, truth: float | None = None, band: tuple[float, float] | None = None
) -> NotebookFigure:
    """Each estimator's ratio with its interval, against the true ratio (`truth`, a twin) or the range implied
    by traffic counts (`band`, real data)."""
    fig = NotebookFigure(figsize=(7.5, 0.55 * len(table) + 1.6), layout="constrained")
    ax = fig.subplots()
    y = np.arange(len(table))[::-1]
    ax.errorbar(
        table["ratio"],
        y,
        xerr=[table["ratio"] - table["lo"], table["hi"] - table["ratio"]],
        fmt="o",
        color="#2a7fb8",
        capsize=3,
    )
    if truth is not None:
        ax.axvline(truth, color="#c0392b", label=f"valor verdadero ({truth:.2f})")
    if band is not None:
        ax.axvspan(*band, color="#d98f1f", alpha=0.25, label=f"conteos de tráfico ({band[0]}–{band[1]})")
    ax.axvline(1, color="gray", linestyle=":", linewidth=1)
    ax.set_yticks(y, list(table["estimator"]))
    ax.set(xlabel="domingo ÷ día hábil", title="Cociente de emisión domingo/hábil")
    ax.legend(fontsize=8, loc="lower right")
    return fig


def plot_obs_vs_model(daily: pd.DataFrame) -> NotebookFigure:
    """Each day's observed NOx against the NOx the weather alone would give with a fixed emission (``model``):
    the days of one type fall on a line through the origin whose slope is that type's emission index."""
    fig = NotebookFigure(figsize=(6.5, 4.6), layout="constrained")
    ax = fig.subplots()
    top = float(max(daily["model"].max(), daily["obs"].max()))
    for kind, name in KIND_NAMES.items():
        part = daily[daily["kind"] == kind]
        if part.empty:
            continue
        ax.scatter(part["model"], part["obs"], s=22, color=KIND_COLORS[kind], label=f"{name} ({len(part)})")
        slope = part["obs"].sum() / part["model"].sum()
        ax.plot([0, top], [0, slope * top], color=KIND_COLORS[kind], linewidth=1)
    ax.set(
        xlabel="NOx que daría solo el clima, con emisión fija (ppb·h)",
        ylabel="NOx observado (ppb·h)",
        title="Cada punto es un día; la pendiente es el índice de emisión",
        xlim=(0, top),
        ylim=(0, top),
    )
    ax.legend(fontsize=8)
    return fig


def plot_daily_index(daily: pd.DataFrame) -> NotebookFigure:
    """Daily index (observed over modeled) in time: the scatter among weekdays is what a placebo measures."""
    fig = NotebookFigure(figsize=(9, 3.6), layout="constrained")
    ax = fig.subplots()
    index = daily["obs"] / daily["model"]
    for kind, name in KIND_NAMES.items():
        part = index[daily["kind"] == kind]
        ax.scatter(part.index, part, s=22, color=KIND_COLORS[kind], label=name)
    weekday = index[daily["kind"] == WEEKDAY]
    ax.axhline(weekday.mean(), color=KIND_COLORS[WEEKDAY], linewidth=1, linestyle="--")
    ax.set(
        ylabel="índice del día (observado ÷ modelo)",
        title=f"Variación entre días hábiles: {weekday.std() / weekday.mean():.0%}",
    )
    ax.legend(fontsize=8)
    return fig


# --- Placebo -------------------------------------------------------------------------------------------


def fake_sunday_ratios(daily: pd.DataFrame, n: int = 2000, seed: int = 3) -> Array:
    """Index ratios of `n` random splits of the weekdays into as many fake Sundays as the period has and the
    rest: there is no emission change, so their spread is the width of a null result."""
    weekdays = daily[daily["kind"] == WEEKDAY]
    n_sundays = int((daily["kind"] == SUNDAY_HOLIDAY).sum())
    return split_placebo(weekdays, n_sundays, n, np.random.default_rng(seed))


PLACEBO_GATE = 0.15  # a placebo centered within 1 +- this passes (`nox_ml.validation.metrics`)


def placebo_summary(null: Array, model_null: Array | None = None, level: float = 0.90) -> pd.DataFrame:
    """Center, central interval and half width of the placebo ratios of the normalized estimator and, if
    given, of a model, and whether the center is within the gate of 1 (``pasa``)."""
    rows = []
    for name, ratios in (("normalizado", null), ("modelo", model_null)):
        if ratios is None:
            continue
        lo, hi = interval(ratios, level)
        center = float(np.median(ratios))
        rows.append((name, center, lo, hi, (hi - lo) / 2, abs(center - 1) <= PLACEBO_GATE))
    return pd.DataFrame(rows, columns=["estimador", "centro", "lo", "hi", "semiancho", "pasa"])


def model_placebo_ratios(
    inputs: Inputs, model: str = "rf_deweather", refits: int = 8, seed: int = 3, **params: Any
) -> Array:
    """Sunday over weekday of `model` refit `refits` times on weekdays with fake Sundays (`placebo_ratios` of
    the harness). The bootstrap of the model is reduced to one replicate: only the point value is used."""
    cls = REGISTRY[model]
    fields = cls.Params.model_fields
    values = {"bootstrap_n": 1} | params if "bootstrap_n" in fields else params
    return experiment.placebo_ratios(
        inputs, lambda: cls(cls.Params.model_validate(values)), experiment.Placebo(refits=refits, seed=seed)
    )


def plot_placebo(
    null: Array, real: tuple[float, float, float], model_null: Array | None = None, level: float = 0.90
) -> NotebookFigure:
    """Fake-Sunday ratios of the normalized estimator (histogram) and, if given, of a model (points), against
    the real ratio with its interval: a real change counts when it falls outside the null."""
    fig = NotebookFigure(figsize=(8, 3.8), layout="constrained")
    ax = fig.subplots()
    lo, hi = interval(null, level)
    ax.hist(null, bins=40, color="#b8c4cc", label="domingos falsos (normalizado)")
    ax.axvspan(lo, hi, color="#b8c4cc", alpha=0.35)
    top = ax.get_ylim()[1]
    if model_null is not None:
        ax.plot(
            model_null,
            np.full(len(model_null), 0.08 * top),
            "k|",
            markersize=14,
            label="domingos falsos (modelo)",
        )
    ax.axvline(1, color="gray", linestyle=":", linewidth=1)
    value, real_lo, real_hi = real
    ax.axvline(value, color="#2a7fb8", linewidth=2, label=f"domingo real: {value:.2f}")
    ax.axvspan(real_lo, real_hi, color="#2a7fb8", alpha=0.15)
    ax.set(
        xlabel="domingo ÷ día hábil",
        ylabel="repeticiones",
        title=f"Sin cambio de emisión el cociente cae en {_interval_text(lo, hi)} (90 %)",
    )
    ax.legend(fontsize=8)
    return fig


# --- Wind: how well the other stations predict one ---------------------------------------------------------

WIND_MIN_SPEED = 1.0  # m/s; the direction of a calm wind means nothing
MIN_DISTANCE_KM = 0.5  # floor of the distance in the IDW weights, as the NOx one (`nox_ml.validation.loo`)


def angle_difference(a: Array, b: Array) -> Array:
    """Absolute difference between two directions in degrees, in [0, 180]."""
    return np.abs((np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0)


def direction_from(u: Array, v: Array) -> Array:
    """Meteorological direction (degrees, where it comes from) of a wind vector blowing towards (u, v)."""
    return np.degrees(np.arctan2(-np.asarray(u), -np.asarray(v))) % 360.0


def station_winds(
    data_dir: Path, start: str, end: str, local_hours: tuple[int, int] = (12, 17)
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hourly wind of the SIMAT stations in the local days ``start`` to ``end`` at the SIMAT hour labels
    `local_hours` (as the NOx rows): columns ``station``, ``h`` (start of the hour, UTC), ``u``, ``v`` (m/s,
    blowing towards), ``speed`` and ``direction`` (degrees, from). Also the stations' positions (UTM, m)."""
    import geopandas as gpd

    interim = data_dir / "interim"
    catalog = gpd.read_file(interim / "estaciones.gpkg").to_crs(UTM).set_index("cve_estac")
    xy = pd.DataFrame({"x": catalog.geometry.x, "y": catalog.geometry.y})
    wind = pd.read_parquet(interim / "simat_wind.parquet")
    keep = (
        wind["local"].between(start, f"{end} 23:59")
        & wind["local"].dt.hour.between(*local_hours)
        & wind["id_station"].isin(xy.index)
        & wind["WSP"].notna()
        & wind["WDR"].notna()
    )
    wind = wind[keep]
    towards = np.deg2rad(wind["WDR"])
    table = pd.DataFrame(
        {
            "station": wind["id_station"].to_numpy(),
            "h": (wind["utc"] - pd.Timedelta(hours=1)).to_numpy(),  # SIMAT labels the end of the hour
            "u": (-wind["WSP"] * np.sin(towards)).to_numpy(),
            "v": (-wind["WSP"] * np.cos(towards)).to_numpy(),
            "speed": wind["WSP"].to_numpy(),
            "direction": wind["WDR"].to_numpy(),
        }
    )
    return table, xy


def wind_leave_one_out(
    winds: pd.DataFrame, station_xy: pd.DataFrame, min_speed: float = WIND_MIN_SPEED
) -> pd.DataFrame:
    """Predict the wind direction of every station and hour from the other stations of that hour, with the
    mean vector of the domain (what the inversion uses) and with the IDW of the vectors (1 / distance^2).
    Only the station-hours with an observed wind of at least `min_speed` are scored. Columns ``station``,
    ``h``, ``observed``, ``domain``, ``idw`` (degrees) and the absolute errors ``error_domain``,
    ``error_idw``."""
    stations = sorted(winds["station"].unique())
    u = winds.pivot(index="h", columns="station", values="u").reindex(columns=stations)
    v = winds.pivot(index="h", columns="station", values="v").reindex(columns=stations)
    speed = winds.pivot(index="h", columns="station", values="speed").reindex(columns=stations)
    present = u.notna().to_numpy(float)
    u0, v0 = u.fillna(0.0).to_numpy(), v.fillna(0.0).to_numpy()
    xy = station_xy.loc[stations, ["x", "y"]].to_numpy(float)
    km = np.maximum(np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1)) / 1000, MIN_DISTANCE_KM)
    weights = 1 / km**2
    np.fill_diagonal(weights, 0.0)  # weights[s, t]: how much station t counts for station s
    n_others = present.sum(axis=1, keepdims=True) - present
    with np.errstate(invalid="ignore", divide="ignore"):
        domain_u = (u0.sum(axis=1, keepdims=True) - u0) / n_others
        domain_v = (v0.sum(axis=1, keepdims=True) - v0) / n_others
        total = present @ weights.T
        idw_u, idw_v = (u0 @ weights.T) / total, (v0 @ weights.T) / total
    observed = direction_from(u.to_numpy(), v.to_numpy())
    domain, idw = direction_from(domain_u, domain_v), direction_from(idw_u, idw_v)
    scored = (speed.to_numpy() >= min_speed) & (n_others > 0)
    rows, cols = np.nonzero(scored)
    table = pd.DataFrame(
        {
            "station": np.array(stations)[cols],
            "h": u.index[rows],
            "observed": observed[rows, cols],
            "domain": domain[rows, cols],
            "idw": idw[rows, cols],
        }
    )
    table["error_domain"] = angle_difference(table["domain"], table["observed"])
    table["error_idw"] = angle_difference(table["idw"], table["observed"])
    return table


def era5_wind(data_dir: Path) -> pd.DataFrame:
    """Hourly ERA5 10 m wind of the cell over Mexico City (Open-Meteo): ``u``, ``v`` (m/s, blowing towards),
    indexed by the UTC hour, averaged with the next hour as the boundary layer height is."""
    payload = json.loads((data_dir / "raw" / "era5_openmeteo" / ERA5_FILE).read_text())["hourly"]
    index = pd.to_datetime(payload["time"])
    towards = np.deg2rad(pd.Series(payload["wind_direction_10m"], index, dtype=float))
    speed = pd.Series(payload["wind_speed_10m"], index, dtype=float)
    frame = pd.DataFrame({"u": -speed * np.sin(towards), "v": -speed * np.cos(towards)})
    return (frame + frame.shift(-1)) / 2


def era5_wind_errors(era5: pd.DataFrame, errors: pd.DataFrame) -> Array:
    """Absolute direction error of ERA5 at the station-hours of `errors` (same selection as the other
    methods), degrees; hours ERA5 does not have are left out."""
    hours = pd.DatetimeIndex(errors["h"])
    ok = hours.isin(era5.index)
    cell = era5.loc[hours[ok]]
    return angle_difference(
        direction_from(cell["u"].to_numpy(), cell["v"].to_numpy()), errors["observed"].to_numpy()[ok]
    )


def wind_error_summary(errors: pd.DataFrame, era5_errors: Array | None = None) -> pd.DataFrame:
    """Median, quartile and 90th percentile of the direction error (degrees) of each method."""
    columns = {
        "vector medio de las demás estaciones": errors["error_domain"],
        "IDW de las demás": errors["error_idw"],
    }
    if era5_errors is not None:
        columns["ERA5 (una celda de 0.25°)"] = pd.Series(era5_errors)
    rows = [
        {
            "método": name,
            "mediana": values.median(),
            "p75": values.quantile(0.75),
            "p90": values.quantile(0.90),
            "estaciones-hora": len(values),
        }
        for name, values in columns.items()
    ]
    return pd.DataFrame(rows)


def plot_wind_errors(errors: pd.DataFrame, era5_errors: Array | None = None) -> NotebookFigure:
    """Left: distribution of the direction error of each method with its median. Right: median error of the
    mean-vector prediction at each station."""
    fig = NotebookFigure(figsize=(11, 4), layout="constrained")
    left, right = fig.subplots(1, 2)
    series = [
        ("vector medio", errors["error_domain"].to_numpy(), "#2a7fb8"),
        ("IDW", errors["error_idw"].to_numpy(), "#d98f1f"),
    ]
    if era5_errors is not None:
        series.append(("ERA5", np.asarray(era5_errors), "#c0392b"))
    bins = np.arange(0, 181, 10)
    for name, values, color in series:
        left.hist(
            values,
            bins=bins,
            histtype="step",
            linewidth=1.8,
            color=color,
            density=True,
            label=f"{name}: mediana {np.median(values):.0f}°",
        )
    left.set(
        xlabel="error de dirección (grados)",
        ylabel="densidad",
        title="Error al predecir el viento de una estación",
    )
    left.legend(fontsize=8)
    per_station = errors.groupby("station")["error_domain"].median().sort_values()
    right.barh(per_station.index, per_station, color="#2a7fb8")
    right.axvline(float(errors["error_domain"].median()), color="gray", linestyle="--", linewidth=1)
    right.set(xlabel="error mediano (grados)", title="Por estación (vector medio)")
    right.tick_params(axis="y", labelsize=7)
    return fig


# --- Transport: plume, kernel and puffs -----------------------------------------------------------------

TRANSPORT_NAMES = ("plume", "kernel", "gauss_puffs", "kernel_puffs")
TRANSPORT_LABELS = {
    "plume": "Pluma gaussiana",
    "kernel": "Núcleo de la PINN",
    "gauss_puffs": "Puffs gaussianos",
    "kernel_puffs": "Puffs con el núcleo",
}
TRANSPORT_COLORS = {
    "plume": "#4d4d4d",
    "kernel": "#2a7fb8",
    "gauss_puffs": "#d98f1f",
    "kernel_puffs": "#c0392b",
}


def default_kernel():
    """The trained network of the default parameters (bundled with the package; needs the ``pinn`` extra)."""
    from nox_ml.models.pinn.cache import obtain_kernel
    from nox_ml.models.pinn.params import PinnParams

    return obtain_kernel(PinnParams())


class TransportSuite:
    """The four transports of the notebooks with the same inputs and the same physical constants, so that what
    differs between them is the transport itself: the stationary Gaussian plume, the kernel of the network
    (a stationary plume too), and the puffs of the previous hours with the Gaussian and with the kernel's
    profile. The speed floor `u_min`, the NOx lifetime `tau_h` (the plume of the Gaussian has none) and the
    wind-direction spread `sigma_theta_deg` of the Gaussian are the same for all of them where they apply."""

    def __init__(
        self,
        inputs: Inputs,
        kernel: Any = None,
        tau_h: float = 12.0,
        u_min: float = 2.0,
        sigma_theta_deg: float = 30.0,
        max_age_h: int = 24,
    ) -> None:
        from nox_ml.inversion.jacobian import Transport, road_emission_profile
        from nox_ml.inversion.linear import road_sources
        from nox_ml.physics.puff import Trajectories, fixed_lifetime, local_hour_profile

        self.inputs, self.kernel = inputs, kernel or default_kernel()
        self.tau_h, self.u_min, self.sigma_theta = tau_h, u_min, np.deg2rad(sigma_theta_deg)
        self.sources = road_sources(inputs.zones, inputs.points, inputs.n_regions)
        wind = inputs.wind
        if wind is None:
            index = pd.DatetimeIndex([h.hour for h in inputs.hours])
            wind = pd.DataFrame([h.wind for h in inputs.hours], columns=["u", "v"], index=index).sort_index()
        profile = (
            road_emission_profile(inputs.infovial, HOLIDAYS)
            if inputs.infovial is not None
            else local_hour_profile()
        )
        self.transport = Transport(
            Trajectories.from_wind(wind, u_min), fixed_lifetime(tau_h), profile, max_age_h
        )

    def jacobian(self, name: str, data: HourData):
        """The matrix of one hour (receptors in `data`) with the transport `name` (`TRANSPORT_NAMES`)."""
        from nox_ml.inversion.jacobian import jacobian_hour_plume, jacobian_hour_puff
        from nox_ml.models.pinn.puff import jacobian_hour_pinn_puff
        from nox_ml.models.pinn.transport import jacobian_hour_pinn

        ratio, table = self.inputs.no2_nox_ratio, self.kernel.table
        if name == "plume":
            return jacobian_hour_plume(
                data.wind,
                data.pbl,
                self.sources,
                data.stations,
                data.pixels,
                ratio,
                self.sigma_theta,
                self.u_min,
            )
        if name == "kernel":
            return jacobian_hour_pinn(
                data.wind,
                data.pbl,
                self.sources,
                data.stations,
                data.pixels,
                ratio,
                table,
                self.tau_h,
                self.u_min,
            )
        if name == "gauss_puffs":
            return jacobian_hour_puff(
                data.hour,
                data.wind,
                data.pbl,
                self.transport,
                self.sources,
                data.stations,
                data.pixels,
                ratio,
            )
        if name == "kernel_puffs":
            return jacobian_hour_pinn_puff(
                data.hour,
                data.wind,
                data.pbl,
                self.transport,
                self.sources,
                data.stations,
                data.pixels,
                ratio,
                table,
                self.tau_h,
                self.u_min,
            )
        raise ValueError(f"unknown transport {name!r}; use one of {TRANSPORT_NAMES}")


def pick_hour(inputs: Inputs, local: int = 15) -> int:
    """Position of a weekday hour that starts at the local hour `local` and whose wind speed is the median of
    those hours: a typical afternoon to draw."""
    days = pd.DatetimeIndex([local_day(h.hour) for h in inputs.hours])
    candidates = [
        i
        for i, h in enumerate(inputs.hours)
        if local_hour(h.hour) == local and day_type(days[i : i + 1], HOLIDAYS)[0] == WEEKDAY
    ]
    speeds = np.array([np.hypot(*inputs.hours[i].wind) for i in candidates])
    return candidates[int(np.argmin(np.abs(speeds - np.median(speeds))))]


@dataclass(frozen=True)
class Maps:
    """NOx (ppb) added by the prior emissions in one hour, on a grid, for each transport."""

    x: Array  # m, projected
    y: Array
    fields: dict[str, Array]  # name -> (len(y), len(x))
    stations: Array  # (n, 2)
    points: Array  # (n, 2)
    wind: tuple[float, float]
    hour: pd.Timestamp


def concentration_maps(suite: TransportSuite, index: int, n: int = 40, margin_m: float = 10_000.0) -> Maps:
    """Ground-level NOx of the prior emissions (points and every road region at its prior, weekday profile) in
    the hour at position `index` of the inputs, on an `n` x `n` grid around the road cells, per transport."""
    from nox_ml.inversion.jacobian import Receptors

    inputs, data = suite.inputs, suite.inputs.hours[index]
    x = np.linspace(inputs.zones["x"].min() - margin_m, inputs.zones["x"].max() + margin_m, n)
    y = np.linspace(inputs.zones["y"].min() - margin_m, inputs.zones["y"].max() + margin_m, n)
    gx, gy = np.meshgrid(x, y)
    nothing = np.empty(0)
    probe = replace(
        data,
        stations=Receptors(gx.ravel(), gy.ravel()),
        nox=np.zeros(gx.size),
        pixels=Receptors(nothing, nothing),
        no2=nothing,
    )
    state = np.r_[inputs.points["prior"].to_numpy(float), np.ones(inputs.n_regions)]
    fields = {name: (suite.jacobian(name, probe).stations @ state).reshape(n, n) for name in TRANSPORT_NAMES}
    return Maps(
        x,
        y,
        fields,
        inputs.station_xy[["x", "y"]].to_numpy(float),
        inputs.points[["x", "y"]].to_numpy(float),
        data.wind,
        data.hour,
    )


def plot_maps(maps: Maps) -> NotebookFigure:
    """Top: the four fields on a common logarithmic scale. Bottom: what each one adds to the Gaussian plume's
    field (difference in ppb; red where the transport gives more NOx)."""
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import LogNorm, TwoSlopeNorm

    fig = NotebookFigure(figsize=(15, 7.4), layout="constrained")
    axes = fig.subplots(2, 4)
    extent = (maps.x[0] / 1000, maps.x[-1] / 1000, maps.y[0] / 1000, maps.y[-1] / 1000)
    top = max(float(np.nanpercentile(f, 99.5)) for f in maps.fields.values())
    norm = LogNorm(vmin=top / 300, vmax=top)
    for ax, name in zip(axes[0], TRANSPORT_NAMES, strict=True):
        ax.imshow(
            np.maximum(maps.fields[name], top / 1e4), origin="lower", extent=extent, norm=norm, cmap="viridis"
        )
        ax.set_title(TRANSPORT_LABELS[name], color=TRANSPORT_COLORS[name])
    fig.colorbar(
        ScalarMappable(norm=norm, cmap="viridis"),
        ax=axes[0],
        label="NOx de la emisión a priori (ppb)",
        shrink=0.9,
    )
    others = [n for n in TRANSPORT_NAMES if n != "plume"]
    spread = max(float(np.nanpercentile(np.abs(maps.fields[n] - maps.fields["plume"]), 99)) for n in others)
    diff_norm = TwoSlopeNorm(0, vmin=-spread, vmax=spread)
    for ax, name in zip(axes[1, 1:], others, strict=True):
        ax.imshow(
            maps.fields[name] - maps.fields["plume"],
            origin="lower",
            extent=extent,
            cmap="RdBu_r",
            norm=diff_norm,
        )
        ax.set_title(f"{TRANSPORT_LABELS[name]} − pluma")
    fig.colorbar(
        ScalarMappable(norm=diff_norm, cmap="RdBu_r"),
        ax=list(axes[1, 1:]),
        label="diferencia (ppb)",
        shrink=0.9,
    )
    for ax in (*axes[0], *axes[1, 1:]):
        ax.plot(*(maps.stations.T / 1000), "w^", markersize=4, markeredgecolor="k", markeredgewidth=0.4)
        ax.plot(*(maps.points.T / 1000), "r*", markersize=8, markeredgecolor="k", markeredgewidth=0.4)
        ax.set_aspect("equal")
    for ax in axes[1]:
        ax.set_xlabel("este (km)")
    for ax in axes[:, 0]:
        ax.set_ylabel("norte (km)")
    u, v = maps.wind
    axes[1, 0].remove()
    fig.suptitle(
        f"{maps.hour:%Y-%m-%d}, {local_hour(maps.hour)} h local · viento hacia {direction_from(-u, -v):.0f}° "
        f"a {float(np.hypot(u, v)):.1f} m/s · △ estaciones, ★ fuentes puntuales"
    )
    return fig


# --- Transport: mass, kernel error and Jacobian differences --------------------------------------------


def crosswind_flux(
    kernel: Any,
    distances_km: Sequence[float] = (2, 5, 10, 20, 30, 40, 45),
    speed: float = 3.0,
    tau_h: float = 12.0,
    sigma_theta_deg: float = 30.0,
    u_min: float = 2.0,
) -> pd.DataFrame:
    """Mass flux (g/s per g/s emitted) through a line across a steady wind, at several distances from the
    source: the Gaussian plume, the kernel of the network and the exact solution of its equation, against the
    ``exp(-x / (u tau))`` that a lifetime `tau_h` alone would leave. A plume without loss carries 1."""
    from nox_ml.models.pinn.equation import L_M, exact
    from nox_ml.models.pinn.transport import column
    from nox_ml.physics.plume import plume

    step = 250.0
    across = np.arange(-120_000.0, 120_000.0 + step, step)
    gamma = L_M / (speed * tau_h * 3600)
    a, c, f_exact = exact(gamma, kappa=kernel.params.kappa)
    exact_flux = f_exact.sum(axis=1) * (c[1] - c[0])  # integral of F across the wind
    rows = []
    for d in distances_km:
        along = np.full_like(across, d * 1000.0)
        _, col_plume = plume(
            np.zeros(1), np.zeros(1), along, across, speed, 0.0, 1000.0,
            sigma_theta=np.deg2rad(sigma_theta_deg), u_min=u_min, x_max=60_000.0,
        )  # fmt: skip
        col_kernel, _ = column(along, across, speed, 0.0, kernel.table, tau_h, u_min)
        rows.append(
            {
                "distancia_km": float(d),
                "pluma gaussiana": float(speed * col_plume.sum() * step),
                "núcleo de la PINN": float(speed * col_kernel.sum() * step),
                "solución exacta": float(np.interp(d * 1000 / L_M, a, exact_flux)),
                "decaimiento esperado": float(np.exp(-d * 1000 / (speed * tau_h * 3600))),
            }
        )
    return pd.DataFrame(rows)


def puff_mass_check(
    kernel: Any,
    ages_h: Sequence[float] = (1.125, 2.125, 4.125, 6.125),
    speed: float = 3.0,
    tau_h: float = 12.0,
    sigma_theta_deg: float = 30.0,
    u_min: float = 2.0,
    half_width_m: float = 150_000.0,
    spacing_m: float = 2_000.0,
) -> pd.DataFrame:
    """Mass of a single sub-puff of each age, integrated on a grid around its centre, over the mass it should
    have (the 15 minutes it was emitted over, times the fraction left after its age): Gaussian puffs and puffs
    with the kernel's profile. A ratio of 1 means the puff conserves its mass. The ages must be ones of the
    sub-puffs of the sum (``1 + (k + 1/2) / 4`` hours)."""
    from nox_ml.models.pinn.puff import pinn_puffs
    from nox_ml.physics.puff import SUB_PER_H, Trajectories, fixed_lifetime, puffs

    hours = pd.date_range("2023-01-01", periods=60, freq="h")
    traj = Trajectories.from_wind(pd.DataFrame({"u": speed, "v": 0.0}, index=hours), u_min)
    t_target, survival = 30.0, fixed_lifetime(tau_h)
    grid = np.arange(-half_width_m, half_width_m + spacing_m, spacing_m)
    rows = []
    for age in ages_h:

        def only_this_puff(t_rel: float, age: float = age) -> float:
            return 1.0 if abs(t_rel - (t_target - age)) < 1e-9 else 0.0

        dx = traj.between(t_target - age, t_target)[0]
        gx, gy = np.meshgrid(dx + grid, grid)
        receptors = (gx.ravel(), gy.ravel())
        source = (np.zeros(1), np.zeros(1))
        max_age = int(np.ceil(age)) + 1
        _, gauss = puffs(
            *source, *receptors, traj, t_target, 1000.0, only_this_puff, 0.0, survival, max_age,
            sigma_theta=np.deg2rad(sigma_theta_deg),
        )  # fmt: skip
        _, learned = pinn_puffs(
            *source, *receptors, traj, t_target, 1000.0, only_this_puff, survival, max_age,
            kernel.table, tau_h,
        )  # fmt: skip
        expected = 3600 / SUB_PER_H * survival(t_target - age, t_target, age)
        rows.append(
            {
                "edad_h": age,
                "distancia_km": speed * age * 3.6,
                "puffs gaussianos": float(gauss.sum() * spacing_m**2 / expected),
                "puffs con el núcleo": float(learned.sum() * spacing_m**2 / expected),
            }
        )
    return pd.DataFrame(rows)


def plot_mass(flux: pd.DataFrame, puffs_mass: pd.DataFrame) -> NotebookFigure:
    """Left: flux across the wind against distance. Right: mass of a puff against its age."""
    fig = NotebookFigure(figsize=(11, 4), layout="constrained")
    left, right = fig.subplots(1, 2)
    d = flux["distancia_km"]
    left.plot(d, flux["pluma gaussiana"], "o-", color=TRANSPORT_COLORS["plume"], label="pluma gaussiana")
    left.plot(d, flux["núcleo de la PINN"], "o-", color=TRANSPORT_COLORS["kernel"], label="núcleo de la PINN")
    left.plot(d, flux["solución exacta"], "k--", label="solución exacta de la ecuación")
    left.plot(d, flux["decaimiento esperado"], ":", color="gray", label="exp(−x / uτ)")
    left.set(
        xlabel="distancia a la fuente (km)",
        ylabel="flujo ÷ emisión",
        title="Masa que cruza una línea",
        ylim=(0, 1.15),
    )
    left.legend(fontsize=8, loc="lower left")
    right.plot(
        puffs_mass["edad_h"],
        puffs_mass["puffs gaussianos"],
        "o-",
        color=TRANSPORT_COLORS["gauss_puffs"],
        label="puffs gaussianos",
    )
    right.plot(
        puffs_mass["edad_h"],
        puffs_mass["puffs con el núcleo"],
        "o-",
        color=TRANSPORT_COLORS["kernel_puffs"],
        label="puffs con el núcleo",
    )
    right.axhline(1, color="gray", linestyle=":")
    right.set(
        xlabel="edad del puff (h)",
        ylabel="masa integrada ÷ masa esperada",
        title="Masa de un puff",
        ylim=(0, 1.15),
    )
    right.legend(fontsize=8, loc="lower left")
    return fig


@dataclass(frozen=True)
class KernelError:
    """The network and the exact solution on the validation window, for one ``gamma = L / (u tau)``."""

    gamma: float
    a: Array  # along the wind, units of L
    c: Array  # across
    exact: Array  # (a, c)
    network: Array

    @property
    def relative_error(self) -> Array:
        """Relative error where the exact solution is above 5 % of its maximum (NaN elsewhere)."""
        big = self.exact > 0.05 * self.exact.max()
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(big, np.abs(self.network - self.exact) / self.exact, np.nan)


def kernel_error(kernel: Any, gamma: float) -> KernelError:
    """The window of `nox_ml.models.pinn.kernel.validate` (5 km upwind to 40 km downwind, 25 km across) with
    the exact solution and the network at `gamma`."""
    from nox_ml.models.pinn.equation import exact
    from nox_ml.models.pinn.kernel import evaluate

    a, c, f_exact = exact(gamma, kappa=kernel.params.kappa)
    in_a, in_c = (a >= -0.5) & (a <= 4.0), np.abs(c) <= 2.5
    aa, cc = np.meshgrid(a[in_a][::2], c[in_c][::2], indexing="ij")
    return KernelError(
        gamma, aa[:, 0], cc[0], f_exact[np.ix_(in_a, in_c)][::2, ::2], evaluate(kernel.net, aa, cc, gamma)
    )


def kernel_validation(kernel: Any) -> pd.DataFrame:
    """The error of the network against the exact solution that its training stored, one row per ``gamma``."""
    table = pd.DataFrame(kernel.validation).T
    table.index = table.index.astype(float)
    return table.rename_axis("gamma")[["median_rel_error", "p90_rel_error", "mass_error"]]


def plot_kernel_error(kernel: Any, gammas: Sequence[float] = (0.04, 0.25)) -> NotebookFigure:
    """For each ``gamma``: the exact solution, the network and the relative error (distances in km)."""
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import LogNorm

    from nox_ml.models.pinn.equation import L_M

    fig = NotebookFigure(figsize=(13, 3.6 * len(gammas)), layout="constrained")
    axes = fig.subplots(len(gammas), 3, squeeze=False)
    for row, gamma in zip(axes, gammas, strict=True):
        result = kernel_error(kernel, gamma)
        extent = (
            result.a[0] * L_M / 1000,
            result.a[-1] * L_M / 1000,
            result.c[0] * L_M / 1000,
            result.c[-1] * L_M / 1000,
        )
        norm = LogNorm(vmin=result.exact.max() / 1000, vmax=result.exact.max())
        for ax, field, title in zip(
            row[:2], (result.exact, result.network), ("solución exacta", "red"), strict=True
        ):
            ax.imshow(
                np.maximum(field.T, 1e-12),
                origin="lower",
                extent=extent,
                norm=norm,
                cmap="viridis",
                aspect="auto",
            )
            ax.set_title(f"{title} (γ = {gamma})")
        fig.colorbar(ScalarMappable(norm=norm, cmap="viridis"), ax=row[:2], shrink=0.9, label="F")
        error = row[2].imshow(
            result.relative_error.T * 100,
            origin="lower",
            extent=extent,
            cmap="magma_r",
            vmin=0,
            vmax=30,
            aspect="auto",
        )
        row[2].set_title(f"error relativo (mediana {np.nanmedian(result.relative_error):.1%})")
        fig.colorbar(error, ax=row[2], shrink=0.9, label="%")
        for ax in row:
            ax.set(xlabel="a lo largo del viento (km)", ylabel="a lo ancho (km)")
    return fig


def column_labels(inputs: Inputs) -> list[str]:
    """Short names of the columns of a Jacobian: the point sources, then the road regions."""
    return [str(name).split(" (")[0] for name in inputs.points["name"]] + [
        f"zona {r}" for r in range(inputs.n_regions)
    ]


ENTRY_FLOOR = 1e-3  # entries below this fraction of the largest one are numerically zero and not compared


def sample_jacobians(
    suite: TransportSuite, step: int = 23, names: Sequence[str] = TRANSPORT_NAMES
) -> dict[str, dict[str, Array]]:
    """Station and pixel rows of the Jacobians of every `step`-th hour of the inputs, for each transport,
    stacked (rows aligned across transports)."""
    stacks: dict[str, dict[str, list[Array]]] = {n: {"stations": [], "pixels": []} for n in names}
    for data in suite.inputs.hours[::step]:
        for name in names:
            jac = suite.jacobian(name, data)
            stacks[name]["stations"].append(jac.stations)
            stacks[name]["pixels"].append(jac.pixels)
    return {n: {k: np.vstack(v) for k, v in parts.items()} for n, parts in stacks.items()}


def jacobian_differences(
    stacks: dict[str, dict[str, Array]], labels: Sequence[str], reference: str = "plume"
) -> pd.DataFrame:
    """How each transport's matrix differs from the `reference` one, column by column (a point source or a
    road region) and for the station and pixel rows: ``correlation`` of the entries, ``median_ratio`` where
    both are positive and ``total_ratio`` of the sums."""
    rows = []
    for name, parts in stacks.items():
        if name == reference:
            continue
        for receptor, matrix in parts.items():
            base = stacks[reference][receptor]
            for j, label in enumerate(labels):
                a, b = base[:, j], matrix[:, j]
                floor = ENTRY_FLOOR * max(float(a.max()), float(b.max()), 1e-300)
                both = (a > floor) & (b > floor)
                rows.append(
                    {
                        "transport": name,
                        "receptor": receptor,
                        "column": label,
                        "correlation": float(np.corrcoef(a, b)[0, 1])
                        if a.std() > 0 and b.std() > 0
                        else np.nan,
                        "median_ratio": float(np.median(b[both] / a[both])) if both.any() else np.nan,
                        "total_ratio": float(b.sum() / a.sum()) if a.sum() > 0 else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def difference_summary(differences: pd.DataFrame) -> pd.DataFrame:
    """Median over the columns of `jacobian_differences`, by receptor and transport."""
    columns = ["correlation", "median_ratio", "total_ratio"]
    return differences.groupby(["receptor", "transport"])[columns].median()


def plot_jacobian_differences(
    stacks: dict[str, dict[str, Array]],
    differences: pd.DataFrame,
    reference: str = "plume",
    receptor: str = "stations",
) -> NotebookFigure:
    """Left: every entry of each transport's matrix against the reference's (logarithmic axes). Right: the
    median ratio to the reference of each column."""
    fig = NotebookFigure(figsize=(13, 4.6), layout="constrained")
    left, right = fig.subplots(1, 2, gridspec_kw={"width_ratios": [1, 1.6]})
    base = stacks[reference][receptor]
    rng = np.random.default_rng(0)
    low = np.inf
    for name, parts in stacks.items():
        if name == reference:
            continue
        a, b = base.ravel(), parts[receptor].ravel()
        floor = ENTRY_FLOOR * float(base.max())
        both = np.flatnonzero((a > floor) & (b > floor))
        pick = rng.choice(both, min(len(both), 3000), replace=False)
        left.scatter(
            a[pick], b[pick], s=4, alpha=0.35, color=TRANSPORT_COLORS[name], label=TRANSPORT_LABELS[name]
        )
        low = min(low, float(a[pick].min()), float(b[pick].min()))
    span = np.array([low, float(base.max())])
    left.plot(span, span, "k--", linewidth=1)
    left.set(
        xscale="log",
        yscale="log",
        xlabel=f"{TRANSPORT_LABELS[reference]} (ppb por t/año)",
        ylabel="otro transporte",
        title="Entradas de la matriz",
    )
    left.legend(fontsize=8, markerscale=3)
    shown = differences[differences["receptor"] == receptor].pivot(
        index="transport", columns="column", values="median_ratio"
    )
    shown = shown.reindex([n for n in TRANSPORT_NAMES if n in shown.index])[
        list(dict.fromkeys(differences["column"]))
    ]
    values = np.log2(shown.to_numpy(float))
    image = right.imshow(values, cmap="RdBu_r", vmin=-2, vmax=2, aspect="auto")
    right.set_xticks(range(shown.shape[1]), list(shown.columns), rotation=60, ha="right", fontsize=8)
    right.set_yticks(range(shown.shape[0]), [TRANSPORT_LABELS[n] for n in shown.index], fontsize=9)
    for i in range(shown.shape[0]):
        for j in range(shown.shape[1]):
            if np.isfinite(shown.iat[i, j]):
                right.text(j, i, f"{shown.iat[i, j]:.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=right, label="log₂ del cociente mediano", shrink=0.8)
    right.set_title(f"Cociente mediano a la {TRANSPORT_LABELS[reference].lower()} por columna")
    return fig


# --- Runs of the PINN puffs (they exist only on the owner's machine) ----------------------------------

TUNING_RUNS = ("pinn_puff.transport", "pinn_puff.kernel")  # `nox-ml tune` on the transport and kernel params
KAPPA_PREFIX = "pinn_puff_k"  # runs of the diffusivity grid: pinn_puff_k500, pinn_puff_k1000, ...
PUFF_RUNS = (
    ("pinn_plume", "nox-ml run configs/experiments/pinn_plume.yaml"),
    ("pinn_puff", "nox-ml run configs/experiments/pinn_puff.yaml"),
    (TUNING_RUNS[0], "nox-ml tune configs/experiments/pinn_puff.transport.search.yaml"),
    (TUNING_RUNS[1], "nox-ml tune configs/experiments/pinn_puff.kernel.search.yaml"),
)


def runs_status(runs_dir: Path) -> pd.DataFrame:
    """Which of the runs the PINN puff notebooks read exist, with the command that makes the ones that do not
    (the grid of ``kappa`` is listed by what is found)."""
    rows = [
        {"run": name, "exists": (runs_dir / name / "metrics.json").is_file(), "command": command}
        for name, command in PUFF_RUNS
    ]
    found = (
        sorted(p.name for p in runs_dir.glob(f"{KAPPA_PREFIX}*") if p.is_dir()) if runs_dir.is_dir() else []
    )
    rows += [{"run": name, "exists": True, "command": "(rejilla de kappa)"} for name in found]
    if not found:
        rows.append({"run": f"{KAPPA_PREFIX}*", "exists": False, "command": "nox-ml run <config con kappa>"})
    return pd.DataFrame(rows, columns=["run", "exists", "command"])


def kappa_runs(runs_dir: Path) -> pd.DataFrame:
    """The runs of the ``kappa`` grid in order of ``kappa``: ``run``, ``kappa`` (m, from the run's config) and
    the columns of `nox_ml.validation.compare`. Empty when there are none."""
    import yaml

    folders = (
        sorted(p for p in runs_dir.glob(f"{KAPPA_PREFIX}*") if (p / "metrics.json").is_file())
        if runs_dir.is_dir()
        else []
    )
    table, _ = compare.collect(folders)
    kappas = {
        p.name: yaml.safe_load((p / "config.yaml").read_text())["model"]["params"].get("kappa")
        for p in folders
        if (p / "config.yaml").is_file()
    }
    table.insert(1, "kappa", table["run"].map(kappas))
    return table.sort_values("kappa").reset_index(drop=True)


def plot_kappa(table: pd.DataFrame) -> NotebookFigure | None:
    """Error with a held-out station, Sunday over weekday (with its interval and the traffic range) and the
    placebo against the diffusivity ``kappa``; ``None`` without runs."""
    if table.empty:
        return None
    fig = NotebookFigure(figsize=(13, 3.6), layout="constrained")
    a, b, c = fig.subplots(1, 3)
    a.plot(table["kappa"], table["loo_rmse_ppb"], "o-", color="#2a7fb8")
    a.set(xlabel="κ (m)", ylabel="RMSE con estación oculta (ppb)", title="Error")
    b.errorbar(
        table["kappa"],
        table["sunday_ratio"],
        yerr=[
            table["sunday_ratio"] - table["sunday_ratio_lo"],
            table["sunday_ratio_hi"] - table["sunday_ratio"],
        ],
        fmt="o-",
        color="#2a7fb8",
        capsize=3,
    )
    b.axhspan(*TRAFFIC_BAND, color="#d98f1f", alpha=0.25)
    b.set(xlabel="κ (m)", ylabel="domingo ÷ hábil", title="Cociente de emisión (franja: tráfico)")
    c.errorbar(
        table["kappa"],
        table["placebo_center"],
        yerr=table["placebo_halfwidth"],
        fmt="o",
        color="#2a7fb8",
        capsize=3,
    )
    c.axhspan(0.85, 1.15, color="gray", alpha=0.2)
    c.set(xlabel="κ (m)", ylabel="centro del placebo", title="Placebo (franja: 1 ± 0.15)")
    return fig


def read_search(runs_dir: Path, name: str) -> pd.DataFrame | None:
    """The trials of the search ``runs/<name>/trials.csv``, or ``None`` if that search was not run."""
    path = runs_dir / name / "trials.csv"
    return pd.read_csv(path) if path.is_file() else None


def search_overview(trials: pd.DataFrame | None) -> pd.DataFrame:
    """What a search explored and where it ended: each searched param with its range, the number of distinct
    values tried and its value in the best trial. Empty without trials."""
    if trials is None:
        return pd.DataFrame(columns=["param", "min", "max", "values", "best"])
    space = report.search_space(trials)
    return space.assign(best=[report.best_trial(trials)[p] for p in space["param"]])


def pinn_family_table(runs_dir: Path) -> pd.DataFrame:
    """The comparison table (`nox_ml.validation.compare`) of the PINN runs that are not searches; empty when
    there are none."""
    table, _ = compare.collect(report.run_dirs(runs_dir))
    return table[table["model"].isin(["pinn_plume", "pinn_puff"])].reset_index(drop=True)


def plot_trial_params(trials: pd.DataFrame | None, title: str = "") -> NotebookFigure | None:
    """Error of every trial against each searched param: where the optimum lies and which params matter;
    ``None`` without trials."""
    if trials is None:
        return None
    params = [c for c in trials.columns if c not in ("trial", "loo_rmse_ppb")]
    fig = NotebookFigure(figsize=(3.6 * max(len(params), 1), 3.4), layout="constrained")
    axes = fig.subplots(1, max(len(params), 1), squeeze=False)[0]
    best = trials["loo_rmse_ppb"].idxmin()
    for ax, name in zip(axes, params, strict=False):
        ax.scatter(trials[name], trials["loo_rmse_ppb"], s=22, color="#2a7fb8", alpha=0.7)
        ax.scatter(
            trials.loc[[best], name],
            trials.loc[[best], "loo_rmse_ppb"],
            s=70,
            facecolors="none",
            edgecolors="#c0392b",
        )
        values = trials[name]
        if values.min() > 0 and values.max() / values.min() > 20:
            ax.set_xscale("log")
        ax.set(xlabel=name, ylabel="RMSE (ppb)" if ax is axes[0] else "")
    if title:
        fig.suptitle(title)
    return fig


def tuning_sentences(summary: pd.DataFrame) -> list[str]:
    """One Spanish sentence per search of `nox_ml.validation.report.tuning_summary`."""
    out = []
    for row in summary.itertuples():
        text = (
            f"{row.run}: {row.n_trials} pruebas; el mejor error con estación oculta es "
            f"{row.best_rmse_ppb:.2f} ppb (prueba {row.best_trial})"
        )
        if row.untuned_rmse_ppb is not None and pd.notna(row.untuned_rmse_ppb):
            text += f", {row.untuned_rmse_ppb:.2f} sin ajustar ({row.gain_ppb:+.2f} ppb de ganancia)"
        out.append(text + ".")
    return out


# --- Diagnostics of the baseline (`nox-ml diagnose`) ---------------------------------------------------

DIAGNOSTIC_FILES = ("ablation", "learning_curve", "variance_reduction", "degrees_of_freedom")
ABLATION_METRICS = {
    "loo.rmse.model": "rmse",
    "loo.rmse.hybrid": "rmse_híbrido",
    "in_sample.r_tempo": "r_tempo",
    "day_types.sunday_over_weekday.value": "domingo_hábil",
    "normalized.placebo_half_width": "placebo_normalizado",
}


def diagnostics_for(
    config: Path, runs_dir: Path, seeds: int = 5, echo: Callable[[str], None] = print
) -> dict[str, pd.DataFrame]:
    """The CSV files of ``nox-ml diagnose`` for the experiment `config`, by name. If the run has none in
    `runs_dir` they are computed first (about 8 minutes with 5 seeds) and stay there for the next call."""
    from nox_ml.validation import diagnostics

    cfg = experiment.read_config(config)
    folder = runs_dir / cfg.name / "diagnostics"
    if not all((folder / f"{name}.csv").is_file() for name in DIAGNOSTIC_FILES):
        echo(f"No hay diagnóstico en {folder}; se calcula ahora (nox-ml diagnose, unos minutos).")
        diagnostics.run_diagnostics(cfg, runs_dir, seeds, echo=echo)
    return {name: pd.read_csv(folder / f"{name}.csv") for name in DIAGNOSTIC_FILES}


def case_label(case: str, setting: float | None) -> str:
    """Spanish name of a case of the ablation."""
    if case == "baseline":
        return "línea base"
    if case == "no_tempo":
        return "sin TEMPO"
    if case == "stations":
        return f"{int(setting)} estaciones" if setting is not None else "estaciones"
    return f"viento girado {setting:+.0f}°"


def ablation_summary(ablation: pd.DataFrame) -> pd.DataFrame:
    """The headline metrics of every case of the ablation: mean and standard deviation over the random subsets
    (``_sd`` is 0 for the cases that run once). One row per case, in the order of the file."""
    frame = ablation.assign(
        caso=[
            case_label(c, None if pd.isna(s) else s)
            for c, s in zip(ablation["case"], ablation["setting"], strict=True)
        ]
    )
    columns = {name: short for name, short in ABLATION_METRICS.items() if name in frame}
    grouped = frame.groupby("caso", sort=False)[list(columns)].agg(["mean", "std"])
    out = pd.DataFrame(index=grouped.index)
    for name, short in columns.items():
        out[short] = grouped[(name, "mean")]
        out[f"{short}_sd"] = grouped[(name, "std")].fillna(0.0)
    return out


def plot_ablation(summary: pd.DataFrame) -> NotebookFigure:
    """Error with a held-out station, correlation with TEMPO and Sunday ratio of every case."""
    fig = NotebookFigure(figsize=(13, 4), layout="constrained")
    panels = (
        ("rmse", "RMSE con estación oculta (ppb)"),
        ("r_tempo", "correlación con TEMPO"),
        ("domingo_hábil", "domingo ÷ hábil"),
    )
    y = np.arange(len(summary))[::-1]
    for k, (ax, (column, label)) in enumerate(zip(fig.subplots(1, 3), panels, strict=True)):
        ax.errorbar(summary[column], y, xerr=summary[f"{column}_sd"], fmt="o", color="#2a7fb8", capsize=3)
        ax.axvline(float(summary.loc["línea base", column]), color="#c0392b", linewidth=1, linestyle="--")
        ax.set_yticks(y, list(summary.index) if k == 0 else [])
        ax.set(xlabel=label)
        if column == "domingo_hábil":
            ax.axvspan(*TRAFFIC_BAND, color="#d98f1f", alpha=0.25)
    return fig


def learning_summary(curve: pd.DataFrame) -> pd.DataFrame:
    """Mean RMSE (ppb) of the learning curve by axis and size: in sample, held-out station for the model and
    for IDW, and the gap between the first two."""
    keys = ["axis", "n"]
    out = curve.groupby(keys)[["rmse_in_sample", "rmse_loo_model", "rmse_loo_idw"]].mean()
    out["brecha"] = out["rmse_loo_model"] - out["rmse_in_sample"]
    return out.reset_index()


def plot_learning_curves(curve: pd.DataFrame) -> NotebookFigure:
    """Error in sample and with a held-out station against the number of days and of stations (mean and
    spread over the random subsets)."""
    fig = NotebookFigure(figsize=(11, 4), layout="constrained")
    for ax, (axis, label) in zip(
        fig.subplots(1, 2), (("days", "días de datos"), ("stations", "estaciones")), strict=True
    ):
        part = curve[curve["axis"] == axis]
        for column, name, color in (
            ("rmse_in_sample", "en la muestra", "#4d4d4d"),
            ("rmse_loo_model", "estación oculta (modelo)", "#2a7fb8"),
            ("rmse_loo_idw", "estación oculta (IDW)", "#d98f1f"),
        ):
            grouped = part.groupby("n")[column].agg(["mean", "std"]).fillna(0.0)
            ax.errorbar(
                grouped.index,
                grouped["mean"],
                yerr=grouped["std"],
                marker="o",
                color=color,
                capsize=2,
                label=name,
            )
        ax.set(xlabel=label, ylabel="RMSE (ppb)")
        ax.legend(fontsize=8)
    return fig


# --- Wind against the transport: what moves the error --------------------------------------------------

REPORTED_RMSE = {
    "pinn_plume": 12.49,
    "pinn_puff": 12.08,
}  # ppb, the owner's runs (context/management/frente_c.md)


def plume_to_puff(runs_dir: Path) -> pd.DataFrame:
    """Error with a held-out station of the PINN with a stationary plume and with puffs: from
    ``runs/<name>/metrics.json`` when the run exists, else the value the project reported (``fuente``)."""
    rows = []
    for name, reported in REPORTED_RMSE.items():
        path = runs_dir / name / "metrics.json"
        if path.is_file():
            rows.append((name, json.loads(path.read_text())["summary"]["loo_rmse_ppb"], f"runs/{name}"))
        else:
            rows.append((name, reported, "reportado por el proyecto"))
    return pd.DataFrame(rows, columns=["modelo", "rmse_ppb", "fuente"])


def error_changes(ablation: pd.DataFrame, plume_puff: pd.DataFrame) -> pd.DataFrame:
    """Change (ppb) of the error with a held-out station when the wind is turned, from the ablation, and when
    the plume becomes puffs (negative is better): ``cambio``, with its ``origen``. The ``noise_ppb`` attribute
    of the table is the standard deviation of that error between random subsets of stations (the smallest one
    of the ablation): the scale below which a change cannot be told from the choice of stations."""
    base = ablation[ablation["case"] == "baseline"]["loo.rmse.model"].iloc[0]
    turned = ablation[ablation["case"] == "wind_bias"]
    rows = [
        (f"viento girado {degrees:+.0f}°", rmse - base, "ablación de la línea base")
        for degrees, rmse in zip(turned["setting"], turned["loo.rmse.model"], strict=True)
    ]
    errors = plume_puff.set_index("modelo")["rmse_ppb"]
    rows.append(
        ("pluma → puffs (PINN)", errors["pinn_puff"] - errors["pinn_plume"], "pinn_plume y pinn_puff")
    )
    changes = pd.DataFrame(rows, columns=["cambio de", "cambio_ppb", "origen"])
    subsets = ablation[ablation["case"] == "stations"].groupby("setting")["loo.rmse.model"].std().dropna()
    changes.attrs["noise_ppb"] = float(subsets.min()) if len(subsets) else None
    return changes


def plot_error_changes(changes: pd.DataFrame) -> NotebookFigure:
    """Bars of `error_changes`, over the band of the noise from the choice of stations."""
    fig = NotebookFigure(figsize=(7.5, 3.4), layout="constrained")
    ax = fig.subplots()
    y = np.arange(len(changes))[::-1]
    noise = changes.attrs.get("noise_ppb")
    if noise:
        ax.axvspan(
            -noise, noise, color="gray", alpha=0.2, label=f"ruido por elegir estaciones (±{noise:.1f} ppb)"
        )
        ax.legend(fontsize=8, loc="upper right")
    ax.barh(
        y,
        changes["cambio_ppb"],
        color=["#4d4d4d" if "viento" in c else "#c0392b" for c in changes["cambio de"]],
    )
    ax.axvline(0, color="k", linewidth=1)
    ax.set_yticks(y, list(changes["cambio de"]))
    ax.set(xlabel="cambio del error con estación oculta (ppb; negativo es mejor)", title="Qué mueve el error")
    return fig
