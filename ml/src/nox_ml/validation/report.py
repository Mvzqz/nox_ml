# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""What the comparison notebook shows from ``runs/``: the planned models that have not run yet, the two best
eligible ones, and the trials of the searches. Everything tolerates missing runs."""

import io
from pathlib import Path

import pandas as pd
import yaml
from matplotlib.figure import Figure

from nox_ml.validation import compare

# (id, registered model, experiment config) of every model the comparison expects (docs/models.md)
PLANNED = [
    ("E1", "inversion_plume", "baseline"),
    ("E2", "inversion_puff", "inversion_puff"),
    ("E3", "regularized_ls", "regularized_ls"),
    ("E4", "lognormal_map", "lognormal_map"),
    ("E5a", "pinn_plume", "pinn_plume"),
    ("E5b", "pinn_puff", "pinn_puff"),
    ("E5c", "pinn_joint", "pinn_joint"),
    ("E6", "rf_deweather", "rf_deweather"),
    ("E7", "normalized_ratio", "normalized_ratio"),
    ("R1", "idw", "idw"),
    ("R2", "kriging", "kriging"),
]


class NotebookFigure(Figure):
    """A figure that draws itself in a notebook: Jupyter only shows the figures made with pyplot, and these
    are made without it so that they do not pile up in memory."""

    def _repr_png_(self) -> bytes:
        buffer = io.BytesIO()
        self.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
        return buffer.getvalue()


def find_runs() -> Path:
    """``runs/`` of the repository containing the working directory (``./runs`` outside a repository)."""
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if (folder / "pyproject.toml").is_file():
            return folder / "runs"
    return Path("runs")


def run_dirs(runs_dir: Path, *, tuned: bool = False) -> list[Path]:
    """The run folders of `runs_dir`: those of ``nox-ml run`` or, with `tuned`, those of ``nox-ml tune`` (the
    ones with a ``trials.csv``). A missing folder has no runs."""
    folders = sorted(p for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.is_dir() else []
    return [p for p in folders if (p / "trials.csv").is_file() == tuned]


def missing(table: pd.DataFrame) -> pd.DataFrame:
    """The planned models with no run in `table`, with the config that would run them."""
    done = set(table["model"])
    rows = [
        {"id": i, "model": model, "run": f"nox-ml run configs/experiments/{config}.yaml"}
        for i, model, config in PLANNED
        if model not in done
    ]
    return pd.DataFrame(rows, columns=["id", "model", "run"])


def selection(table: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    """The `n` best (lowest ``loo_rmse_ppb``) models that pass the placebo gate; references do not compete."""
    ok = table[(table["role"] == "model") & table["eligible"].eq(True)]
    return ok.sort_values("loo_rmse_ppb", kind="stable").head(n).reset_index(drop=True)


def read_trials(runs_dir: Path) -> dict[str, pd.DataFrame]:
    """``runs/*/trials.csv`` by run name, in the order the trials ran."""
    return {p.name: pd.read_csv(p / "trials.csv") for p in run_dirs(runs_dir, tuned=True)}


def _model_of(run: Path) -> str | None:
    config = run / "config.yaml"
    return yaml.safe_load(config.read_text())["model"]["name"] if config.is_file() else None


def search_space(trials: pd.DataFrame) -> pd.DataFrame:
    """What each searched param took across the trials (the space actually explored)."""
    params = [c for c in trials.columns if c not in ("trial", "loo_rmse_ppb")]
    rows = [
        {"param": c, "min": trials[c].min(), "max": trials[c].max(), "values": trials[c].nunique()}
        for c in params
    ]
    return pd.DataFrame(rows, columns=["param", "min", "max", "values"])


def best_trial(trials: pd.DataFrame) -> pd.Series:
    """The row of the lowest ``loo_rmse_ppb`` (the first one on a tie)."""
    return trials.loc[trials["loo_rmse_ppb"].idxmin()]


def tuning_summary(runs_dir: Path, table: pd.DataFrame) -> pd.DataFrame:
    """One row per search: number of trials, best and worst RMSE, the untuned run of the same model and the
    gain over it, and the refit of the best trial (RMSE, Sunday ratio, placebo gate).

    The search scores with a simple split, not a nested one, so the tuned error is a little optimistic."""
    refits, _ = compare.collect(run_dirs(runs_dir, tuned=True))
    refits = refits.set_index("run")
    untuned = table.drop_duplicates("model").set_index("model")["loo_rmse_ppb"]
    rows = []
    for run, trials in read_trials(runs_dir).items():
        model = _model_of(runs_dir / run)
        best = trials["loo_rmse_ppb"].min()
        base = untuned.get(model)
        refit = refits.loc[run] if run in refits.index else None
        rows.append(
            {
                "run": run,
                "model": model,
                "n_trials": len(trials),
                "best_trial": int(best_trial(trials)["trial"]),
                "best_rmse_ppb": best,
                "worst_rmse_ppb": trials["loo_rmse_ppb"].max(),
                "untuned_rmse_ppb": base,
                "gain_ppb": None if base is None else base - best,
                "refit_rmse_ppb": None if refit is None else refit["loo_rmse_ppb"],
                "refit_sunday_ratio": None if refit is None else refit["sunday_ratio"],
                "refit_eligible": None if refit is None else refit["eligible"],
            }
        )
    return pd.DataFrame(rows)


def plot_trials(runs_dir: Path, table: pd.DataFrame) -> NotebookFigure | None:
    """The trial curve of every search (RMSE of each trial and the best so far, against the untuned run);
    ``None`` when there is no ``trials.csv``."""
    trials = read_trials(runs_dir)
    if not trials:
        return None
    untuned = table.drop_duplicates("model").set_index("model")["loo_rmse_ppb"]
    fig = NotebookFigure(figsize=(5.5 * len(trials), 3.8), layout="constrained")
    for ax, (run, frame) in zip(fig.subplots(1, len(trials), squeeze=False)[0], trials.items(), strict=True):
        ax.plot(frame["trial"], frame["loo_rmse_ppb"], "o", alpha=0.6, label="prueba")
        ax.step(frame["trial"], frame["loo_rmse_ppb"].cummin(), where="post", label="mejor hasta ahora")
        base = untuned.get(_model_of(runs_dir / run))
        if base is not None:
            ax.axhline(base, color="gray", linestyle="--", label="sin ajustar")
        ax.set(title=run, xlabel="prueba", ylabel="RMSE con estación oculta (ppb)")
        ax.legend()
    return fig
