# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Convex weights of an ensemble learned from the out-of-fold predictions of its base models, nested by
station (``docs/models.md``, section 10).

The weights used to evaluate station ``s`` are learned on the out-of-fold rows of the *other* stations, so
the held-out station never sets its own weights. The base models are not refitted: the inputs are the
``oof.parquet`` of their runs and the observed station NOx (`nox_ml.validation.loo.station_rows`).

Two rules, both returning weights >= 0 that sum to 1:

- ``stack``: least squares on the simplex (stacking, X5);
- ``likelihood``: weights proportional to the Gaussian likelihood of the held-out rows, each model with the
  error sd it showed (Bayesian model averaging, X6).

One leak stays: the out-of-fold prediction of a station ``t != s`` came from a model fitted *with* ``s``.
The weights therefore depend on the observations of ``s`` only through how well the base models predicted
the others, which is not the information that would let them favor ``s`` (ADR 0007).
"""

from collections.abc import Callable, Mapping

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import minimize

Array = NDArray[np.float64]
Rule = Callable[[Array, Array], Array]  # (predictions n x k, observed n) -> weights k

MIN_SD = 1e-6  # ppb; floor of the error sd in the likelihood rule


def stack_weights(predictions: Array, observed: Array) -> Array:
    """Weights >= 0 summing to 1 that minimize the squared error of the weighted predictions."""
    k = predictions.shape[1]
    gram = predictions.T @ predictions / len(observed)
    moment = predictions.T @ observed / len(observed)
    start = np.full(k, 1 / k)
    result = minimize(
        lambda w: 0.5 * w @ gram @ w - moment @ w,
        start,
        jac=lambda w: gram @ w - moment,
        bounds=[(0, 1)] * k,
        constraints={"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(k)},
        method="SLSQP",
    )
    return normalized(result.x)


def likelihood_weights(predictions: Array, observed: Array) -> Array:
    """Weights proportional to the Gaussian likelihood of the rows under each model (sd = its own RMSE)."""
    sd = np.maximum(np.sqrt(np.mean((predictions - observed[:, None]) ** 2, axis=0)), MIN_SD)
    log_likelihood = -len(observed) * (np.log(sd) + 0.5)  # sum of log N(obs; pred, sd) at sd = RMSE
    return normalized(np.exp(log_likelihood - log_likelihood.max()))


def normalized(weights: Array) -> Array:
    """Clip numerical noise below zero and rescale to sum 1."""
    clipped = np.clip(weights, 0, None)
    return clipped / clipped.sum()


RULES: dict[str, Rule] = {"stack": stack_weights, "likelihood": likelihood_weights}


def aligned(observed: pd.DataFrame, oof: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Rows observed and predicted by every model: ``station``, ``utc``, ``obs`` and one column per model."""
    table = observed.rename(columns={"h": "utc"})[["station", "utc", "obs"]]
    for name, frame in oof.items():
        table = table.merge(
            frame.rename(columns={"nox_ppb_pred": name})[["station", "utc", name]],
            on=["station", "utc"],
            how="inner",
        )
    if table.empty:
        raise ValueError("the base models have no out-of-fold row in common")
    return table


def fit_weights(observed: pd.DataFrame, oof: Mapping[str, pd.DataFrame], rule: str = "stack") -> pd.Series:
    """Weights of the models learned on all stations (the ones frozen in the config of the final ensemble)."""
    table = aligned(observed, oof)
    names = list(oof)
    weights = RULES[rule](table[names].to_numpy(float), table["obs"].to_numpy(float))
    return pd.Series(weights, index=names, name="weight")


def nested_weights(
    observed: pd.DataFrame, oof: Mapping[str, pd.DataFrame], rule: str = "stack"
) -> pd.DataFrame:
    """For every station ``s``, the weights learned without ``s``: rows ``station`` and columns = models."""
    table = aligned(observed, oof)
    names = list(oof)
    stations = sorted(table["station"].unique())
    if len(stations) < 2:
        raise ValueError("nested stacking needs at least two stations")
    out = {}
    for station in stations:
        rest = table[table["station"] != station]
        out[station] = RULES[rule](rest[names].to_numpy(float), rest["obs"].to_numpy(float))
    return pd.DataFrame(out, index=names).T.rename_axis("station")


def nested_oof(
    observed: pd.DataFrame, oof: Mapping[str, pd.DataFrame], rule: str = "stack"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Out-of-fold predictions of the ensemble without refitting any base model, with the weights used.

    Returns ``(oof, weights)``: `oof` has ``station``, ``utc``, ``nox_ppb_pred`` (each station predicted
    with the weights learned without it) and `weights` is `nested_weights`.
    """
    weights = nested_weights(observed, oof, rule)
    table = aligned(observed, oof)
    names = list(oof)
    w = weights.loc[table["station"]].to_numpy()
    combined = (table[names].to_numpy(float) * w).sum(axis=1)
    return table.assign(nox_ppb_pred=combined)[["station", "utc", "nox_ppb_pred"]], weights


def loo_rmse(observed: pd.DataFrame, oof: pd.DataFrame) -> float:
    """Pooled RMSE (ppb) of out-of-fold predictions against the observed rows (the `loo_rmse_ppb` metric)."""
    table = aligned(observed, {"pred": oof})
    return float(np.sqrt(np.mean((table["pred"] - table["obs"]) ** 2)))
