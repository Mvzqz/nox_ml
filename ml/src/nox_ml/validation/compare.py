# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""``nox-ml compare``: the summaries of several runs in one table sorted by the main metric."""

import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

COLUMNS = [
    "run",
    "period",
    "model",
    "role",
    "loo_rmse_ppb",
    "loo_bias_ppb",
    "loo_hourly_rmse_ppb",
    "r_tempo",
    "sunday_ratio",
    "sunday_ratio_lo",
    "sunday_ratio_hi",
    "sunday_ratio_gap",
    "placebo_center",
    "placebo_halfwidth",
    "eligible",
    "fit_seconds",
    "predict_seconds",
    "n_params",
]


def collect(run_dirs: Iterable[Path]) -> tuple[pd.DataFrame, list[Path]]:
    """One row per run folder with a ``summary`` in its ``metrics.json``, sorted by ``loo_rmse_ppb``; also the
    paths skipped because they are not runs (``runs/*`` includes the comparison files) or predate it."""
    rows, skipped = [], []
    for path in run_dirs:
        metrics = path / "metrics.json"
        summary = json.loads(metrics.read_text()).get("summary") if metrics.is_file() else None
        if summary is None:
            skipped.append(path)
        else:
            evaluation = json.loads(metrics.read_text()).get("evaluation")
            rows.append({"run": path.name, "period": "test" if evaluation else "tuning"} | summary)
    table = pd.DataFrame(rows, columns=COLUMNS).sort_values("loo_rmse_ppb", kind="stable")
    return table.reset_index(drop=True), skipped


def _cell(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "NO"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def markdown(table: pd.DataFrame) -> str:
    """The table as GitHub Markdown; empty emission fields (references) show as ``-``. The Sunday ratio shows
    its interval and `eligible` is the placebo gate (``-`` when it does not apply)."""
    shown = table.assign(
        sunday_ratio=[
            _cell(r.sunday_ratio)
            + ("" if pd.isna(r.sunday_ratio_lo) else f" ({r.sunday_ratio_lo:.2f}-{r.sunday_ratio_hi:.2f})")
            for r in table.itertuples()
        ]
    ).drop(columns=["sunday_ratio_lo", "sunday_ratio_hi"])
    shown = shown.astype(object).where(shown.notna(), None)
    header = "| " + " | ".join(shown.columns) + " |"
    rule = "|" + "|".join("---" for _ in shown.columns) + "|"
    body = ["| " + " | ".join(_cell(v) for v in row) + " |" for row in shown.itertuples(index=False)]
    return "\n".join([header, rule, *body])
