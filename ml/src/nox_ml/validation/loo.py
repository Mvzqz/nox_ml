# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Fit of the inversion at the stations and leave-one-station-out validation.

Migrated from `real_check_linear.py` (sections 1 and 4, research-archive). For every station, the model is
refit without its rows (they are removed *before* the system is built; the background of each hour is
integrated out, so subtracting them afterwards would not be the same) and compared with three predictions of
the held-out NOx:

- model: the Jacobian with the refit sources, plus the background of the hour from the other stations;
- IDW: the average of the other stations of the hour, weighted by ``1 / distance^2``;
- hybrid: the model plus the IDW of the residuals of the model at the other stations (same hour).
"""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import (
    BACKGROUND_PIXEL,
    BACKGROUND_STATION,
    SIGMA_PIXEL,
    SIGMA_STATION,
    HourSystem,
    Posterior,
    background_mean,
    invert,
)

Array = NDArray[np.float64]

MIN_DISTANCE_KM = 0.5  # floor of the distance in the IDW weights
PREDICTORS = ("model", "idw", "hybrid")


def station_rows(inputs: Inputs) -> pd.DataFrame:
    """One row per station observation, in hour order: ``h`` (UTC), ``station`` and ``obs`` (ppb)."""
    return pd.DataFrame(
        {
            "h": np.repeat([h.hour for h in inputs.hours], [len(i) for i in inputs.station_ids]),
            "station": np.concatenate(inputs.station_ids),
            "obs": np.concatenate([h.nox for h in inputs.hours]),
        }
    )


def predict_stations(
    inputs: Inputs, systems: Sequence[HourSystem], post: Posterior, exclude: str | None = None
) -> Array:
    """Model NOx (ppb) of every station row: the Jacobian with the sources of `post` plus the background of
    its hour, estimated from the rows of that hour (not those of the station `exclude`, if given)."""
    out = []
    for hour, ids, system in zip(inputs.hours, inputs.station_ids, systems, strict=True):
        base = system.jacobian.stations @ post.state(system.kind)
        use = np.ones(len(ids), bool) if exclude is None else ids != exclude
        background = background_mean((hour.nox - base)[use], SIGMA_STATION, BACKGROUND_STATION)
        out.append(base + background)
    return np.concatenate(out)


def predict_pixels(inputs: Inputs, systems: Sequence[HourSystem], post: Posterior) -> tuple[Array, Array]:
    """Model NO2 column and observed one (molecules/cm2) of every TEMPO pixel, in the order of the hours."""
    model, observed = [], []
    for hour, system in zip(inputs.hours, systems, strict=True):
        base = system.jacobian.pixels @ post.state(system.kind)
        model.append(base + background_mean(hour.no2 - base, SIGMA_PIXEL, BACKGROUND_PIXEL))
        observed.append(hour.no2)
    return np.concatenate(model), np.concatenate(observed)


def idw_and_hybrid(rows: pd.DataFrame, model: Array, station: str, station_xy: pd.DataFrame) -> pd.DataFrame:
    """Predictions of the rows of `station` from the other stations of the same hour.

    `model` is the model NOx of all `rows`. Returns columns ``obs``, ``model``, ``idw`` and ``hybrid`` for
    the held-out rows that have at least one other station in their hour.
    """
    is_held = (rows["station"] == station).to_numpy()
    others = rows[~is_held].assign(residual=(rows["obs"] - model)[~is_held])
    dx = station_xy["x"] - station_xy.loc[station, "x"]
    dy = station_xy["y"] - station_xy.loc[station, "y"]
    km = np.maximum(np.hypot(dx, dy) / 1000, MIN_DISTANCE_KM)
    w = 1 / others["station"].map(km) ** 2
    hourly = (
        pd.DataFrame({"w": w, "wo": w * others["obs"], "wr": w * others["residual"], "h": others["h"]})
        .groupby("h")
        .sum()
    )
    held = rows[is_held].assign(model=model[is_held])
    held = held[held["h"].isin(hourly.index)]
    near = hourly.loc[held["h"]]
    return pd.DataFrame(
        {
            "obs": held["obs"].to_numpy(),
            "model": held["model"].to_numpy(),
            "idw": (near["wo"] / near["w"]).to_numpy(),
            "hybrid": held["model"].to_numpy() + (near["wr"] / near["w"]).to_numpy(),
        }
    )


def leave_one_out(inputs: Inputs, systems: Sequence[HourSystem]) -> pd.DataFrame:
    """Leave-one-station-out: one row per station with ``n`` and, for each predictor, its ``rmse_*``,
    ``bias_*`` (mean prediction minus observation) and ``r_*`` on the held-out rows.

    `systems` are the hour systems of the fit with all stations; they give the Jacobian rows of the held-out
    station. Each refit runs `invert` on the inputs without that station.
    """
    rows = station_rows(inputs)
    stations = sorted(rows["station"].unique())
    table = []
    for station in stations:
        post = invert(
            inputs.without_station(station),
            inputs.zones,
            inputs.points,
            inputs.no2_nox_ratio,
            inputs.n_regions,
        )
        model = predict_stations(inputs, systems, post, exclude=station)
        held = idw_and_hybrid(rows, model, station, inputs.station_xy)
        entry: dict[str, float | str] = {"station": station, "n": len(held)}
        for name in PREDICTORS:
            error = held[name] - held["obs"]
            entry[f"rmse_{name}"] = float(np.sqrt(np.mean(error**2)))
            entry[f"bias_{name}"] = float(np.mean(error))
            entry[f"r_{name}"] = float(np.corrcoef(held[name], held["obs"])[0, 1])
        table.append(entry)
    return pd.DataFrame(table).set_index("station")


def summarize(loo: pd.DataFrame) -> dict:
    """Pooled RMSE of the leave-one-out table (weighted by the number of rows of each station), split into
    the part that repeats at each station (its bias, RMS over stations) and the part that varies from hour to
    hour (RMSE without the bias), and the number of stations where the hybrid beats IDW."""

    def pooled(values: pd.Series) -> float:
        return float(np.sqrt((loo["n"] * values**2).sum() / loo["n"].sum()))

    out: dict = {"n_stations": len(loo), "rmse": {}, "bias": {}, "hourly": {}}
    for name in PREDICTORS:
        rmse, bias = loo[f"rmse_{name}"], loo[f"bias_{name}"]
        out["rmse"][name] = pooled(rmse)
        out["bias"][name] = pooled(bias)
        out["hourly"][name] = pooled(np.sqrt(np.maximum(rmse**2 - bias**2, 0)))
    out["hybrid_beats_idw"] = int((loo["rmse_hybrid"] < loo["rmse_idw"]).sum())
    out["model_beats_idw"] = int((loo["rmse_model"] < loo["rmse_idw"]).sum())
    return out
