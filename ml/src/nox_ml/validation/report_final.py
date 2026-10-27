# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas and matplotlib typing infer unions; behavior is covered by the tests instead)
"""Tables and figures of the Avance 5 notebook (ensembles and final model).

Everything reads the stored runs (``results/runs/``) and tolerates the ones that do not exist yet, so the
notebook runs while the ensembles are being built. The figures of the final model also need the observed
station NOx of the run's period, read from the data with `observed`. Labels are in Spanish because the
audience of the notebooks is.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from matplotlib.figure import Figure
from matplotlib.ticker import NullFormatter

from nox_ml.data.inputs import load_inputs
from nox_ml.data.roads import N_SPLIT
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.inversion.normalized import day_type
from nox_ml.time import local_day, local_hour
from nox_ml.validation import compare, stacking
from nox_ml.validation.experiment import ExperimentConfig, read_config
from nox_ml.validation.metrics import PLACEBO_TOLERANCE, TRAFFIC_SUNDAY_RATIO
from nox_ml.validation.report import NotebookFigure
from nox_ml.validation.report_baseline import BLUE, DAY_LABELS, GREEN, GREY, ORANGE, RED

# (id, experiment config = run name, kind) of every model the comparison expects (avance5_arranque.md)
INDIVIDUAL = [
    ("E5b", "pinn_puff", "individual"),
    ("E2", "inversion_puff", "individual"),
    ("E5a", "pinn_plume", "individual"),
    ("E6", "rf_deweather", "individual"),
]
ENSEMBLES = [
    ("X1", "bagged_inversion", "homogéneo"),
    ("X2", "wind_ensemble", "homogéneo"),
    ("X3", "pinn_seeds", "homogéneo"),
    ("X4", "gb_deweather", "homogéneo"),
    ("X5", "stacking", "heterogéneo"),
    ("X6", "bayes_average", "heterogéneo"),
]
PLANNED = INDIVIDUAL + ENSEMBLES
TEST_SUFFIX = ".test"  # `nox-ml evaluate` writes runs/<name>.test/
DAY_ORDER = ("weekday", "saturday", "sunday_holiday")
REGION_NAMES = ("SO", "S", "SE", "O", "Centro", "E", "NO", "N", "NE")  # 0 = SW ... 8 = NE (data.roads)


def _figure(nrows: int = 1, ncols: int = 1, figsize: tuple[float, float] = (8, 4), **kwargs: Any):
    """A figure that draws itself in the notebook without pyplot, and its axes."""
    fig = NotebookFigure(figsize=figsize)
    return fig, fig.subplots(nrows, ncols, **kwargs)


# --- Comparison -------------------------------------------------------------------------------------------


def comparison(runs_dir: Path, observed: pd.DataFrame | None = None) -> pd.DataFrame:
    """The planned individual models and ensembles that have a run in `runs_dir` (tuning period), with their
    id and kind, sorted by ``loo_rmse_ppb``. When a run stores the nested evaluation of its weights
    (``nested_oof.parquet``, stacking) and `observed` is given, its error is the nested one, the honest one:
    ``loo_source`` says which was used."""
    runs = [runs_dir / name for _, name, _ in PLANNED if (runs_dir / name / "metrics.json").is_file()]
    table, _ = compare.collect(runs)
    if table.empty:
        return table.assign(
            id=pd.Series(dtype=str), kind=pd.Series(dtype=str), loo_source=pd.Series(dtype=str)
        )
    ids = {name: (i, kind) for i, name, kind in PLANNED}
    table = table.assign(
        id=table["run"].map(lambda r: ids[r][0]),
        kind=table["run"].map(lambda r: ids[r][1]),
        loo_source="run",
    )
    if observed is not None:
        for k, run in table["run"].items():
            nested = runs_dir / run / "nested_oof.parquet"
            if nested.is_file():
                table.loc[k, "loo_rmse_ppb"] = stacking.loo_rmse(observed, pd.read_parquet(nested))
                table.loc[k, "loo_source"] = "anidado"
    first = ["id", "run", "kind", "loo_source"]
    table = table[first + [c for c in table.columns if c not in first]]
    return table.sort_values("loo_rmse_ppb", kind="stable").reset_index(drop=True)


def missing(table: pd.DataFrame) -> pd.DataFrame:
    """The planned models and ensembles without a run yet."""
    done = set(table["run"]) if not table.empty else set()
    rows = [{"id": i, "run": name, "kind": kind} for i, name, kind in PLANNED if name not in done]
    return pd.DataFrame(rows, columns=["id", "run", "kind"])


def kinds_covered(table: pd.DataFrame) -> pd.Series:
    """How many ensembles of each kind have a run (the rubric asks for at least four, of both kinds)."""
    ensembles = table[table["kind"] != "individual"] if not table.empty else table
    counts = ensembles["kind"].value_counts() if not ensembles.empty else pd.Series(dtype=int)
    return counts.reindex(["homogéneo", "heterogéneo"], fill_value=0)


def test_period(runs_dir: Path) -> pd.DataFrame:
    """The runs of `nox-ml evaluate` (``runs/<name>.test/``), sorted by ``loo_rmse_ppb``."""
    runs = sorted(p for p in runs_dir.glob(f"*{TEST_SUFFIX}") if (p / "metrics.json").is_file())
    table, _ = compare.collect(runs)
    return table


def ensemble_weights(run: Path) -> pd.DataFrame | None:
    """The weights a stacking run learned for each held-out station (``nested_weights.csv``), or None."""
    path = run / "nested_weights.csv"
    return pd.read_csv(path, index_col="station") if path.is_file() else None


# --- Observations of a run --------------------------------------------------------------------------------


def run_config(run: Path, root: Path) -> ExperimentConfig:
    """The stored config of a run, with the data folder of the repository."""
    config = read_config(run / "config.yaml")
    return config.model_copy(update={"data_dir": root / "data"})


def observed(config: ExperimentConfig) -> pd.DataFrame:
    """The observed station NOx of the config's period, one row per station and hour as the harness uses it:
    ``station``, ``utc`` (start of the hour), ``obs`` (ppb), plus the local day and hour (as SIMAT labels it,
    the end of the hour), the day type and
    the ventilation of the hour (wind speed × boundary layer height, m²/s)."""
    from nox_ml.validation import loo  # here: at import time loo -> models -> loo is circular

    inputs = load_inputs(
        config.data_dir, config.period.start.isoformat(), config.period.end.isoformat(), config.simat_hours
    )
    rows = loo.station_rows(inputs).rename(columns={"h": "utc"})
    hours = pd.DataFrame(
        {
            "utc": [h.hour for h in inputs.hours],
            "ventilation": [float(np.hypot(*h.wind) * h.pbl) for h in inputs.hours],
        }
    )
    rows = rows.merge(hours, on="utc", how="left")
    days = pd.DatetimeIndex(local_day(rows["utc"]))
    kinds = np.asarray(day_type(days, HOLIDAYS))
    return rows.assign(
        day=days,
        hour=np.asarray(local_hour(rows["utc"])) + 1,  # SIMAT labels the end of the hour (12-17 h)
        day_type=pd.Series(kinds).map(dict(enumerate(DAY_ORDER))).to_numpy(),
    )


def held_out(run: Path, observed: pd.DataFrame) -> pd.DataFrame:
    """The run's out-of-fold predictions next to the observations: each station predicted by the model fitted
    without it. Adds ``pred`` and ``residual`` (observed - predicted, ppb)."""
    oof = pd.read_parquet(run / "oof.parquet").rename(columns={"nox_ppb_pred": "pred"})
    table = observed.merge(oof[["station", "utc", "pred"]], on=["station", "utc"], how="inner")
    return table.assign(residual=table["obs"] - table["pred"])


def error_summary(table: pd.DataFrame) -> dict[str, float]:
    """Pooled RMSE, bias and correlation of held-out predictions, and the number of rows."""
    residual = table["residual"].to_numpy(float)
    return {
        "rmse_ppb": float(np.sqrt(np.mean(residual**2))),
        "bias_ppb": float(residual.mean()),
        "r": float(np.corrcoef(table["obs"], table["pred"])[0, 1]),
        "n": float(len(table)),
    }


# --- Figures of the final model ---------------------------------------------------------------------------


def plot_observed_vs_predicted(table: pd.DataFrame, title: str = "") -> Figure:
    """Observed against predicted NOx at held-out stations (hexagonal density), with the 1:1 line."""
    fig, ax = _figure(figsize=(5.5, 5))
    top = float(np.nanpercentile(np.r_[table["obs"], table["pred"]], 99.5))
    hb = ax.hexbin(table["pred"], table["obs"], gridsize=40, extent=(0, top, 0, top), mincnt=1, cmap="Blues")
    fig.colorbar(hb, ax=ax, label="horas")
    ax.plot([0, top], [0, top], color=RED, lw=1, label="1:1")
    s = error_summary(table)
    ax.text(
        0.03,
        0.97,
        f"RMSE {s['rmse_ppb']:.1f} ppb\nsesgo {s['bias_ppb']:+.1f} ppb\nr {s['r']:.2f}\nn {int(s['n'])}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
    )
    ax.set(
        xlabel="NOₓ predicho en la estación oculta (ppb)",
        ylabel="NOₓ observado (ppb)",
        xlim=(0, top),
        ylim=(0, top),
        title=title or "Observado frente a predicho en estaciones ocultas",
    )
    ax.legend(loc="lower right", fontsize=8)
    return fig


def plot_residuals(table: pd.DataFrame) -> Figure:
    """Residuals (observed - predicted) by station, by local hour and against the ventilation of the hour."""
    fig, axes = _figure(1, 3, figsize=(14, 4))
    by_station = table.groupby("station")["residual"].agg(["mean", lambda r: np.sqrt(np.mean(r**2))])
    by_station.columns = ["bias", "rmse"]
    by_station = by_station.sort_values("bias")
    y = np.arange(len(by_station))
    axes[0].barh(y, by_station["rmse"], color=GREY, alpha=0.5, label="RMSE")
    axes[0].barh(y, by_station["bias"], color=BLUE, height=0.5, label="sesgo")
    axes[0].set_yticks(y, by_station.index, fontsize=7)
    axes[0].axvline(0, color="black", lw=0.8)
    axes[0].set(xlabel="ppb", title="Por estación")
    axes[0].legend(fontsize=8)

    hours = sorted(table["hour"].unique())
    axes[1].boxplot(
        [table.loc[table["hour"] == h, "residual"] for h in hours], tick_labels=hours, showfliers=False
    )
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set(xlabel="hora local", ylabel="residuo (ppb)", title="Por hora del día")

    vent = table.dropna(subset=["ventilation"])
    bins = np.quantile(vent["ventilation"], np.linspace(0, 1, 11))
    groups = vent.groupby(pd.cut(vent["ventilation"], np.unique(bins), include_lowest=True), observed=True)
    centers = groups["ventilation"].median()
    axes[2].scatter(vent["ventilation"], vent["residual"], s=3, color=GREY, alpha=0.2)
    axes[2].plot(centers, groups["residual"].median(), "o-", color=ORANGE, label="mediana por decil")
    axes[2].axhline(0, color="black", lw=0.8)
    axes[2].set_xscale("log")
    axes[2].xaxis.set_minor_formatter(NullFormatter())
    axes[2].set(xlabel="ventilación (m²/s)", ylabel="residuo (ppb)", title="Frente a la ventilación")
    axes[2].legend(fontsize=8)
    fig.suptitle("Residuos en estaciones ocultas (observado − predicho)")
    fig.tight_layout()
    return fig


def plot_series(table: pd.DataFrame, stations: Sequence[str]) -> Figure:
    """Afternoon mean NOx of each day, observed and predicted, at a few held-out stations."""
    fig, axes = _figure(len(stations), 1, figsize=(11, 2.6 * len(stations)), sharex=True, squeeze=False)
    for ax, station in zip(axes[:, 0], stations, strict=True):
        daily = table[table["station"] == station].groupby("day")[["obs", "pred"]].mean()
        days = pd.date_range(table["day"].min(), table["day"].max(), freq="D")
        daily = daily.reindex(days)  # days without data break the line instead of joining across them
        ax.plot(daily.index, daily["obs"], color="black", lw=1.2, label="observado")
        ax.plot(daily.index, daily["pred"], color=BLUE, lw=1.2, label="predicho (estación oculta)")
        sundays = daily.index[pd.DatetimeIndex(daily.index).day_of_week == 6]
        for day in sundays:
            ax.axvspan(day, day + pd.Timedelta(days=1), color=GREEN, alpha=0.15, lw=0)
        ax.set(ylabel="NOₓ (ppb)", title=station)
    axes[0, 0].legend(fontsize=8, loc="upper right")
    fig.suptitle("Promedio de la tarde (12–17 h) por día; domingos sombreados")
    fig.tight_layout()
    return fig


def emissions(run: Path) -> pd.DataFrame:
    """The ``emissions.parquet`` of a run."""
    return pd.read_parquet(run / "emissions.parquet")


def plot_emission_map(run: Path) -> Figure:
    """Absolute estimate: the 3×3 regions with the weekday road emission (t/yr) and its sd, and the
    Sunday/weekday ratio of each region. Relative estimate (no zones): the index of each day type."""
    table = emissions(run)
    if (table["kind"] == "relative").all() if "kind" in table else table["zone"].isna().all():
        return _plot_relative_index(table)
    fig, axes = _figure(1, 2, figsize=(11, 4.8))
    pivot = table.pivot(index="zone", columns="day_type", values="mean")
    sd = table.pivot(index="zone", columns="day_type", values="sd")
    grid = np.full((N_SPLIT, N_SPLIT), np.nan)
    ratio = np.full((N_SPLIT, N_SPLIT), np.nan)
    for zone in pivot.index:
        row, col = divmod(int(zone), N_SPLIT)
        grid[row, col] = pivot.loc[zone, "weekday"]
        if pivot.loc[zone, "weekday"] > 0:
            ratio[row, col] = pivot.loc[zone, "sunday_holiday"] / pivot.loc[zone, "weekday"]
    image = axes[0].imshow(grid, origin="lower", cmap="YlOrRd")
    fig.colorbar(image, ax=axes[0], label="t/año (día hábil)")
    image2 = axes[1].imshow(ratio, origin="lower", cmap="RdBu", vmin=0, vmax=2)
    fig.colorbar(image2, ax=axes[1], label="domingo / hábil")
    for zone in pivot.index:
        row, col = divmod(int(zone), N_SPLIT)
        name = REGION_NAMES[int(zone)]
        axes[0].text(
            col,
            row,
            f"{name}\n{grid[row, col]:,.0f}\n± {sd.loc[zone, 'weekday']:,.0f}",
            ha="center",
            va="center",
            fontsize=8,
        )
        label = "—" if np.isnan(ratio[row, col]) else f"{ratio[row, col]:.2f}"
        axes[1].text(col, row, f"{name}\n{label}", ha="center", va="center", fontsize=8)
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].set_title("Emisión vial por región (norte arriba)")
    axes[1].set_title("Cociente domingo / hábil por región")
    fig.tight_layout()
    return fig


def _plot_relative_index(table: pd.DataFrame) -> Figure:
    pooled = table[table["zone"].isna()].set_index("day_type").reindex(list(DAY_ORDER)).dropna(how="all")
    fig, ax = _figure(figsize=(6, 3.5))
    y = np.arange(len(pooled))
    ax.errorbar(
        pooled["mean"],
        y,
        xerr=[pooled["mean"] - pooled["lo"], pooled["hi"] - pooled["mean"]],
        fmt="o",
        capsize=5,
    )
    ax.set_yticks(y, [DAY_LABELS[d] for d in pooled.index])
    ax.axvline(1, color=GREY, lw=0.8)
    ax.set(
        xlabel="índice de emisión sobre el día hábil", title="Emisión relativa por tipo de día (sin zonas)"
    )
    return fig


def _metrics(run: Path) -> dict[str, Any]:
    return json.loads((run / "metrics.json").read_text())


def plot_day_types(runs: dict[str, Path]) -> Figure:
    """Saturday and Sunday over weekday with their intervals and the placebo, for each labelled run (for
    example the final model on the tuning and on the test period), against the traffic counts and the
    placebo gate."""
    fig, ax = _figure(figsize=(8.5, 1.2 + 1.1 * len(runs) * 1.5))
    lo, hi = TRAFFIC_SUNDAY_RATIO
    ax.axvspan(lo, hi, color=GREEN, alpha=0.2, label=f"domingo según el tráfico ({lo}–{hi})")
    ax.axvspan(
        1 - PLACEBO_TOLERANCE, 1 + PLACEBO_TOLERANCE, color=GREY, alpha=0.15, label="compuerta del placebo"
    )
    labels, y = [], 0
    colors = [BLUE, ORANGE, GREEN, RED]
    for k, (label, run) in enumerate(runs.items()):
        m = _metrics(run)
        s, days = m["summary"], m.get("day_types", {})
        rows = []
        sat = days.get("saturday_over_weekday")
        if sat:
            rows.append(("sábado / hábil", sat["value"], sat["lo"], sat["hi"]))
        rows.append(("domingo / hábil", s["sunday_ratio"], s["sunday_ratio_lo"], s["sunday_ratio_hi"]))
        if s.get("placebo_center") is not None:
            c, w = s["placebo_center"], s["placebo_halfwidth"]
            rows.append(("placebo", c, c - w, c + w))
        for name, value, low, high in rows:
            if value is None:
                continue
            low = value if low is None else low
            high = value if high is None else high
            ax.errorbar(
                value, y, xerr=[[value - low], [high - value]], fmt="o", capsize=4, color=colors[k % 4]
            )
            ax.text(high + 0.02, y, f"{value:.2f}", va="center", fontsize=8)
            labels.append(f"{label}: {name}")
            y += 1
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.invert_yaxis()
    ax.set(xlabel="cociente de emisión (intervalo del 90 %)", xlim=(0.2, 1.6))
    ax.legend(fontsize=7, loc="lower left")
    ax.set_title("Cambios de emisión que el modelo ve, y el que no debe ver (placebo)")
    return fig


def plot_weights(weights: pd.DataFrame) -> Figure:
    """The weights of a stacking ensemble learned without each station: their spread says how stable the
    combination is."""
    fig, ax = _figure(figsize=(7, 3.5))
    ax.boxplot(
        [weights[c] for c in weights.columns], tick_labels=list(weights.columns), orientation="horizontal"
    )
    for k, column in enumerate(weights.columns, start=1):
        ax.text(weights[column].median(), k + 0.3, f"{weights[column].median():.2f}", ha="center", fontsize=8)
    ax.set(xlabel="peso (aprendido sin la estación evaluada)", xlim=(-0.05, 1.05))
    ax.set_title("Pesos del ensamble en cada estación oculta")
    return fig


def config_model(run: Path) -> str | None:
    """The registered model of a stored run."""
    path = run / "config.yaml"
    return yaml.safe_load(path.read_text())["model"]["name"] if path.is_file() else None


def observed_or_none(run: Path, root: Path) -> pd.DataFrame | None:
    """`observed` for the period of a stored run, or None with the reason printed when the run or the data
    are not there (the notebook still runs: its tables do not need them)."""
    if not (run / "config.yaml").is_file():
        print(f"Sin corrida {run.name}: las figuras que la usan se omiten.")
        return None
    try:
        return observed(run_config(run, root))
    except FileNotFoundError as error:
        print(f"Sin datos para {run.name} ({error.filename}): corre `uv run dvc pull`.")
        return None
