# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas and matplotlib typing infer unions; behavior is covered by the tests instead)
"""Tables and figures of the progress notebooks (``notebooks/``).

The notebooks only call functions of ``nox_ml``; whatever they show that is not a metric of the harness is
computed here. Every figure function takes the data it draws (a run's ``metrics.json``, the inputs, the
diagnostics tables) and returns a matplotlib `Figure`. Labels are in Spanish because the audience of the
notebooks is.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from nox_ml.data.inputs import Inputs
from nox_ml.data.roads import N_SPLIT, domain_bounds_utm
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.inversion.normalized import SUNDAY_HOLIDAY, day_type
from nox_ml.time import local_day
from nox_ml.validation import diagnostics, loo
from nox_ml.validation.experiment import ExperimentConfig, read_config
from nox_ml.validation.metrics import PLACEBO_TOLERANCE, TRAFFIC_SUNDAY_RATIO

IDW_TOLERANCE = 0.25  # the model may be this much worse than IDW (RMSE ratio - 1) and still "close"

BLUE, ORANGE, GREEN, GREY, RED = "#2a6fbb", "#d9822b", "#3a9a5b", "#8c8c8c", "#c0392b"
LABELS = {"model": "Modelo (inversión)", "idw": "IDW", "hybrid": "Híbrido (modelo + IDW de residuos)"}
COLORS = {"model": BLUE, "idw": ORANGE, "hybrid": GREEN}
DAY_LABELS = {"weekday": "día hábil", "saturday": "sábado", "sunday_holiday": "domingo / festivo"}
SOURCE_LABELS = {"stations": "solo estaciones", "tempo": "solo TEMPO", "both": "estaciones + TEMPO"}
SOURCE_COLORS = {"stations": BLUE, "tempo": ORANGE, "both": GREEN}

matplotlib.rcParams.update(
    {
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "figure.dpi": 100,
    }
)


def _figure(nrows: int = 1, ncols: int = 1, figsize: tuple[float, float] = (8, 4), **kwargs: Any):
    """A figure outside pyplot (no global state, nothing shown twice in a notebook) and its axes."""
    fig = Figure(figsize=figsize)
    return fig, fig.subplots(nrows, ncols, **kwargs)


# --- Setup ------------------------------------------------------------------------------------------------


def find_root(start: Path | None = None) -> Path:
    """The repository root (the folder with ``pyproject.toml`` and ``configs/``) above `start` (default: the
    current folder), so a notebook runs from wherever it is opened."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file() and (folder / "configs").is_dir():
            return folder
    raise FileNotFoundError(f"no repository root above {here}")


def load_config(name: str = "baseline", root: Path | None = None) -> ExperimentConfig:
    """``configs/experiments/<name>.yaml`` with the data folder of the repository."""
    root = root or find_root()
    config = read_config(root / "configs" / "experiments" / f"{name}.yaml")
    return config.model_copy(update={"data_dir": root / "data"})


def load_metrics(run: Path) -> dict[str, Any]:
    """The ``metrics.json`` of a run folder."""
    return json.loads((run / "metrics.json").read_text())


def load_diagnostics(run: Path) -> dict[str, pd.DataFrame]:
    """The tables of ``nox-ml diagnose`` in a run folder: ``reduction``, ``dofs``, ``ablation``, ``curve``."""
    folder = run / "diagnostics"
    files = {
        "reduction": "variance_reduction",
        "dofs": "degrees_of_freedom",
        "ablation": "ablation",
        "curve": "learning_curve",
    }
    return {key: pd.read_csv(folder / f"{name}.csv") for key, name in files.items()}


# --- Tables -----------------------------------------------------------------------------------------------


def data_overview(inputs: Inputs, config: ExperimentConfig) -> pd.DataFrame:
    """What the baseline uses: one row per data source with its amount (columns ``dato``, ``contenido``)."""
    days = {local_day(h.hour) for h in inputs.hours}
    first, last = config.simat_hours
    stations = diagnostics.station_ids(inputs)
    rows = [
        (
            "SIMAT: NOx",
            f"{len(stations)} estaciones, {inputs.n_station_rows:,} observaciones horarias "
            f"({first}-{last} h locales)",
        ),
        (
            "SIMAT + ERA5/MERRA-2: meteorología",
            f"viento horario del dominio y capa de mezcla, {len(inputs.hours)} horas",
        ),
        ("TEMPO: NO₂ troposférico", f"{inputs.n_pixels:,} píxeles válidos en las mismas horas"),
        (
            "OpenStreetMap: calles",
            f"{len(inputs.zones):,} celdas de 1 km con calles, en {inputs.n_regions} zonas 3×3",
        ),
        ("Fuentes puntuales", f"{len(inputs.points)} (centrales eléctricas y aeropuertos)"),
        ("Periodo", f"{min(days):%d-%m-%Y} a {max(days):%d-%m-%Y}, {len(days)} días con datos"),
    ]
    return pd.DataFrame(rows, columns=["dato", "contenido"])


def capacity_table(metrics: Mapping[str, Any]) -> pd.DataFrame:
    """Parameters of the model against the data it is fitted to (columns ``concepto``, ``valor``)."""
    inputs, run = metrics["inputs"], metrics["summary"]
    rows = [
        ("Parámetros del modelo", f"{run['n_params']}"),
        ("Observaciones de estaciones", f"{inputs['n_station_rows']:,}"),
        ("Píxeles de TEMPO", f"{inputs['n_pixels']:,}"),
        ("Píxeles de TEMPO por parámetro", f"{inputs['n_pixels'] / run['n_params']:,.0f}"),
    ]
    return pd.DataFrame(rows, columns=["concepto", "valor"])


def minimum_performance(metrics: Mapping[str, Any]) -> pd.DataFrame:
    """The three minimum criteria of the baseline, each with its value, its requirement and whether it passes
    (columns ``criterio``, ``valor``, ``requisito``, ``cumple``)."""
    run, pooled = metrics["summary"], metrics["loo"]["rmse"]
    lo_gate, hi_gate = 1 - PLACEBO_TOLERANCE, 1 + PLACEBO_TOLERANCE
    over_idw = pooled["model"] / pooled["idw"] - 1
    traffic = TRAFFIC_SUNDAY_RATIO
    rows = [
        (
            "Placebo centrado en 1",
            f"{run['placebo_center']:.2f} ± {run['placebo_halfwidth']:.2f}",
            f"centro en {lo_gate:.2f}-{hi_gate:.2f}",
            lo_gate <= run["placebo_center"] <= hi_gate,
        ),
        (
            "Dirección del domingo",
            f"{run['sunday_ratio']:.2f} ({run['sunday_ratio_lo']:.2f}-{run['sunday_ratio_hi']:.2f})",
            "intervalo completo por debajo de 1",
            run["sunday_ratio_hi"] < 1,
        ),
        (
            "Magnitud del domingo (referencia)",
            f"{run['sunday_ratio']:.2f}",
            f"dentro de {traffic[0]}-{traffic[1]} (tráfico contado)",
            traffic[0] <= run["sunday_ratio"] <= traffic[1],
        ),
        (
            "Cercanía a IDW",
            f"{pooled['model']:.1f} vs {pooled['idw']:.1f} ppb ({over_idw:+.0%})",
            f"hasta {IDW_TOLERANCE:.0%} peor que IDW",
            over_idw <= IDW_TOLERANCE,
        ),
    ]
    return pd.DataFrame(rows, columns=["criterio", "valor", "requisito", "cumple"])


def in_sample_vs_held_out(
    inputs: Inputs, config: ExperimentConfig, metrics: Mapping[str, Any]
) -> pd.DataFrame:
    """RMSE (ppb) by station of the model fitted on all the stations (``rmse_en_muestra``) and with the
    station held out (``rmse_oculta``, from the run), with the rows of the station (``n``)."""
    rows = loo.station_rows(inputs)
    stations = sorted(rows["station"].unique())
    fitted = config.model.build().fit(inputs).predict_stations(inputs, stations)
    fitted = rows.merge(fitted, left_on=["station", "h"], right_on=["station", "utc"], how="left")
    error = (fitted["nox_ppb_pred"] - fitted["obs"]).to_numpy(float)
    in_sample = pd.Series(error**2, index=fitted["station"]).groupby(level=0).mean() ** 0.5
    held = pd.DataFrame(metrics["loo"]["stations"]).T
    return pd.DataFrame(
        {
            "n": held["n"].astype(int),
            "rmse_en_muestra": in_sample.reindex(held.index),
            "rmse_oculta": held["rmse_model"].astype(float),
        }
    ).rename_axis("estacion")


# --- Figures: the problem and the data --------------------------------------------------------------------


def plot_domain(inputs: Inputs) -> Figure:
    """Map of the domain in km: road cells (by prior emission), TEMPO pixels, stations, point sources and the
    3×3 zones of the inversion."""
    x0, y0, x1, y1 = domain_bounds_utm()
    km = 1000
    fig, ax = _figure(figsize=(7.5, 7))
    zones = inputs.zones
    ax.scatter(
        (zones["x"] - x0) / km,
        (zones["y"] - y0) / km,
        c=np.log10(zones["weight"]),
        s=4,
        marker="s",
        cmap="Greys",
        alpha=0.5,
        label="celdas con calles (OSM)",
    )
    px = np.concatenate([h.pixels.x for h in inputs.hours])
    py = np.concatenate([h.pixels.y for h in inputs.hours])
    pick = np.random.default_rng(0).choice(len(px), min(len(px), 4000), replace=False)
    ax.scatter(
        (px[pick] - x0) / km,
        (py[pick] - y0) / km,
        s=3,
        color=BLUE,
        alpha=0.25,
        label="píxeles TEMPO (muestra)",
    )
    st = inputs.station_xy
    ax.scatter((st["x"] - x0) / km, (st["y"] - y0) / km, s=45, color=RED, zorder=3, label="estaciones SIMAT")
    for name, row in st.iterrows():
        ax.annotate(
            str(name),
            ((row["x"] - x0) / km, (row["y"] - y0) / km),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    pts = inputs.points
    ax.scatter(
        (pts["x"] - x0) / km,
        (pts["y"] - y0) / km,
        s=90,
        marker="*",
        color=ORANGE,
        zorder=3,
        label="fuentes puntuales",
    )
    for i in range(1, N_SPLIT):
        ax.axvline(i * (x1 - x0) / N_SPLIT / km, color=GREY, lw=0.8, ls="--")
        ax.axhline(i * (y1 - y0) / N_SPLIT / km, color=GREY, lw=0.8, ls="--")
    ax.set(xlim=(0, (x1 - x0) / km), ylim=(0, (y1 - y0) / km), xlabel="este (km)", ylabel="norte (km)")
    ax.set_aspect("equal")
    ax.set_title("Dominio: estaciones, TEMPO, calles y zonas de la inversión")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=2, fontsize=8, markerscale=1.5)
    return fig


def plot_daily_context(inputs: Inputs) -> Figure:
    """Daily mean afternoon NOx of the stations, wind speed and boundary layer height; the Sundays and
    holidays are marked: the emission signal is inside the first panel, the other two are weather."""
    days = [local_day(h.hour) for h in inputs.hours]
    table = pd.DataFrame(
        {
            "day": days,
            "nox": [h.nox.mean() for h in inputs.hours],
            "wind": [np.hypot(*h.wind) for h in inputs.hours],
            "pbl": [h.pbl for h in inputs.hours],
        }
    )
    daily = table.groupby("day").mean()
    sunday = np.asarray(day_type(pd.DatetimeIndex(daily.index), HOLIDAYS)) == SUNDAY_HOLIDAY
    fig, axes = _figure(3, 1, figsize=(9, 6.5), sharex=True)
    panels = (
        ("nox", "NOx medio de las estaciones (ppb)"),
        ("wind", "Viento del dominio (m/s)"),
        ("pbl", "Capa de mezcla (m)"),
    )
    for ax, (column, label) in zip(axes, panels, strict=True):
        ax.bar(daily.index, daily[column], color=np.where(sunday, ORANGE, BLUE), width=0.85)
        ax.set_ylabel(label, fontsize=8)
    axes[0].set_title("Tardes de nov-dic 2023 (naranja: domingos y festivos)")
    fig.tight_layout()
    return fig


# --- Figures: the algorithm and the metrics ---------------------------------------------------------------


def plot_loo_by_station(metrics: Mapping[str, Any]) -> Figure:
    """RMSE of the held-out station for the model, IDW and the hybrid, one group of bars per station."""
    table = pd.DataFrame(metrics["loo"]["stations"]).T.astype(float).sort_values("rmse_idw")
    fig, ax = _figure(figsize=(10, 4.2))
    x = np.arange(len(table))
    for k, name in enumerate(loo.PREDICTORS):
        ax.bar(x + (k - 1) * 0.27, table[f"rmse_{name}"], width=0.27, color=COLORS[name], label=LABELS[name])
    ax.set_xticks(x, table.index, rotation=60, fontsize=8)
    ax.set(
        ylabel="RMSE en la estación oculta (ppb)", title="Predecir donde no hay sensor: modelo frente a IDW"
    )
    ax.legend(fontsize=8)
    return fig


def plot_level_and_rhythm(metrics: Mapping[str, Any]) -> Figure:
    """The held-out RMSE of each predictor next to its two parts: the bias that repeats at each station (the
    level) and the error that changes from hour to hour (the rhythm). RMSE² = bias² + rhythm²."""
    pooled = metrics["loo"]
    fig, ax = _figure(figsize=(7.5, 3.8))
    parts = (
        ("rmse", "RMSE", BLUE),
        ("bias", "sesgo (nivel)", GREY),
        ("hourly", "de hora en hora (ritmo)", ORANGE),
    )
    for k, (key, label, color) in enumerate(parts):
        values = [pooled[key][name] for name in loo.PREDICTORS]
        ax.barh(np.arange(3) + (k - 1) * 0.27, values, height=0.27, color=color, label=label)
        for y, value in enumerate(values):
            ax.text(value + 0.2, y + (k - 1) * 0.27, f"{value:.1f}", va="center", fontsize=8)
    ax.set_yticks(range(3), [LABELS[n] for n in loo.PREDICTORS])
    ax.invert_yaxis()
    ax.set(xlabel="ppb", xlim=(0, 16), title="Nivel y ritmo del error en estación oculta")
    ax.legend(fontsize=8, loc="lower right")
    return fig


def plot_emission_metrics(metrics: Mapping[str, Any]) -> Figure:
    """Sunday over weekday with its interval, against the traffic-count range, and the placebo (the same
    ratio when there is no change) with the gate of the minimum performance."""
    run = metrics["summary"]
    fig, ax = _figure(figsize=(7.5, 3.4))
    lo, hi = TRAFFIC_SUNDAY_RATIO
    ax.axvspan(lo, hi, color=GREEN, alpha=0.25, label=f"tráfico contado ({lo}-{hi})")
    ax.axvspan(
        1 - PLACEBO_TOLERANCE,
        1 + PLACEBO_TOLERANCE,
        color=GREY,
        alpha=0.2,
        label="compuerta del placebo (1 ± 0.15)",
    )
    rows = (
        ("domingo / hábil", run["sunday_ratio"], run["sunday_ratio_lo"], run["sunday_ratio_hi"], BLUE),
        (
            "placebo (sin cambio)",
            run["placebo_center"],
            run["placebo_center"] - run["placebo_halfwidth"],
            run["placebo_center"] + run["placebo_halfwidth"],
            ORANGE,
        ),
    )
    for y, (_, value, low, high, color) in enumerate(rows):
        ax.errorbar(value, y, xerr=[[value - low], [high - value]], fmt="o", color=color, capsize=5, lw=2)
        ax.text(high + 0.03, y, f"{value:.2f}", va="center", fontsize=9)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set(xlim=(0.2, 1.6), ylim=(-0.6, len(rows) - 0.4), xlabel="cociente de emisión (intervalo del 90 %)")
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Qué tan bien ve el modelo un cambio de emisión conocido")
    return fig


# --- Figures: diagnostics ---------------------------------------------------------------------------------


def plot_information(reduction: pd.DataFrame, dofs: pd.DataFrame) -> Figure:
    """Information of each kind of observation: the variance removed from every unknown (left) and the degrees
    of freedom for signal by group of unknowns (right)."""
    fig, (left, right) = _figure(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    x = np.arange(len(reduction))
    for k, source in enumerate(diagnostics.SOURCES):
        left.bar(
            x + (k - 1) * 0.27,
            reduction[f"reduction_{source}"],
            width=0.27,
            color=SOURCE_COLORS[source],
            label=SOURCE_LABELS[source],
        )
    short = {"weekday": "háb", "saturday": "sáb", "sunday_holiday": "dom"}
    labels = [
        label.split()[0] if group == "points" else f"{short[group]} {int(zone)}"
        for group, zone, label in zip(reduction["group"], reduction["zone"], reduction["label"], strict=True)
    ]
    left.set_xticks(x, labels, rotation=90, fontsize=6)
    left.set(ylabel="fracción de la varianza a priori eliminada", ylim=(0, 1.25))
    left.set_yticks([0, 0.25, 0.5, 0.75, 1])
    left.set_title("Información sobre cada incógnita (fuentes puntuales y zonas 0-8 por tipo de día)")
    left.legend(fontsize=8, ncols=3, loc="upper center")
    groups = [c for c in dofs.columns if c not in ("source", "dofs")]
    bottom = np.zeros(len(dofs))
    palette = [ORANGE, BLUE, "#6aa3d9", "#a9c8e8"]
    for color, group in zip(palette, groups, strict=False):
        values = dofs[group].to_numpy(float)
        right.bar(
            [SOURCE_LABELS[s] for s in dofs["source"]],
            values,
            bottom=bottom,
            color=color,
            label=DAY_LABELS.get(group, "fuentes puntuales"),
        )
        bottom += values
    for i, total in enumerate(dofs["dofs"]):
        right.text(i, total + 0.15, f"{total:.1f}", ha="center", fontsize=9)
    right.set(ylabel="grados de libertad para la señal", ylim=(0, len(reduction) * 1.3))
    right.set_title(f"De {len(reduction)} incógnitas")
    right.tick_params(axis="x", labelsize=8)
    right.legend(fontsize=8, ncols=2, loc="upper center")
    fig.tight_layout()
    return fig


def _summarize_cases(ablation: pd.DataFrame, column: str) -> pd.DataFrame:
    """Mean and range over seeds of `column` for every case/setting of the ablation, in plotting order."""

    def label(case: str, setting: float) -> str:
        if case == "baseline":
            return "base"
        if case == "no_tempo":
            return "sin TEMPO"
        return f"{int(setting)} estaciones" if case == "stations" else f"viento +{int(setting)}°"

    grouped = (
        ablation.groupby(["case", "setting"], dropna=False)[column].agg(["mean", "min", "max"]).reset_index()
    )
    grouped["label"] = [label(c, s) for c, s in zip(grouped["case"], grouped["setting"], strict=True)]
    order = {"baseline": 0, "no_tempo": 1, "stations": 2, "wind_bias": 3}
    grouped["rank"] = grouped["case"].map(order)
    return grouped.sort_values(["rank", "setting"], ascending=[True, False]).reset_index(drop=True)


def plot_ablation(ablation: pd.DataFrame) -> Figure:
    """The ablation (an input taken away or degraded) on four metrics: error in a held-out station, Sunday
    over weekday, agreement with TEMPO and the width of the placebo."""
    panels = (
        ("summary.loo_rmse_ppb", "RMSE estación oculta (ppb)", None, (0, 20)),
        ("summary.sunday_ratio", "domingo / hábil", TRAFFIC_SUNDAY_RATIO, (0, 1.1)),
        ("summary.r_tempo", "r con TEMPO (en muestra)", None, (0, 1)),
        ("summary.placebo_halfwidth", "semiancho del placebo", None, (0, 0.6)),
    )
    fig, axes = _figure(1, 4, figsize=(15, 4.6), sharey=True)
    for ax, (column, title, band, limits) in zip(axes, panels, strict=True):
        table = _summarize_cases(ablation, column)
        y = np.arange(len(table))
        if column in ablation:
            ax.errorbar(
                table["mean"],
                y,
                xerr=[(table["mean"] - table["min"]).fillna(0), (table["max"] - table["mean"]).fillna(0)],
                fmt="o",
                color=BLUE,
                capsize=3,
            )
        if band:
            ax.axvspan(*band, color=GREEN, alpha=0.25)
        ax.set_yticks(y, table["label"])
        ax.set_xlim(*limits)
        ax.set_title(title, fontsize=10)
    axes[0].invert_yaxis()
    fig.suptitle(
        "Ablación: línea = media de las repeticiones, barras = rango; banda verde = tráfico contado",
        fontsize=10,
    )
    fig.tight_layout()
    return fig


def plot_learning_curves(curve: pd.DataFrame) -> Figure:
    """In-sample and held-out-station RMSE as the model sees fewer days (left) or fewer stations (right);
    lines are the mean over the random subsets and the bands their range. IDW is drawn for reference."""
    fig, axes = _figure(1, 2, figsize=(11, 4), sharey=True)
    series = (
        ("rmse_in_sample", "dentro de muestra", BLUE, "--"),
        ("rmse_loo_model", "estación oculta (modelo)", BLUE, "-"),
        ("rmse_loo_idw", "estación oculta (IDW)", ORANGE, "-"),
    )
    for ax, axis, title in zip(
        axes, ("days", "stations"), ("Menos días de datos", "Menos estaciones"), strict=True
    ):
        part = curve[curve["axis"] == axis]
        for column, label, color, style in series:
            stats = part.groupby("n")[column].agg(["mean", "min", "max"])
            ax.plot(stats.index, stats["mean"], style, color=color, marker="o", label=label)
            ax.fill_between(stats.index, stats["min"], stats["max"], color=color, alpha=0.12)
        ax.set(xlabel="días" if axis == "days" else "estaciones", title=title)
    axes[0].set_ylabel("RMSE (ppb)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_in_sample_vs_held_out(table: pd.DataFrame) -> Figure:
    """RMSE by station inside the sample against the station held out: points above the diagonal are
    stations the model predicts worse when it has not seen them."""
    fig, ax = _figure(figsize=(5.8, 5.2))
    top = float(max(table["rmse_en_muestra"].max(), table["rmse_oculta"].max())) * 1.08
    ax.plot([0, top], [0, top], color=GREY, lw=1)
    ax.scatter(table["rmse_en_muestra"], table["rmse_oculta"], s=table["n"] / 4, color=BLUE, alpha=0.7)
    for name, row in table.iterrows():
        ax.annotate(
            str(name),
            (row["rmse_en_muestra"], row["rmse_oculta"]),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax.set(
        xlim=(0, top),
        ylim=(0, top),
        xlabel="RMSE dentro de muestra (ppb)",
        ylabel="RMSE con la estación oculta (ppb)",
        title="Dentro de muestra frente a estación oculta",
    )
    ax.set_aspect("equal")
    return fig
