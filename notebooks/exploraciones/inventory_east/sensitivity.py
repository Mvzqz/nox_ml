"""Test 3: sensitivity of the east share of E5b>=0 (`pinn_puff_nonneg`) to the east stations and the wind.

One fit per call (about 10 min), no leave-one-out, bootstrap or placebo: only what the zone shares need
(`estimate_emissions` over the fitted model). Outputs go to `out/` here, never to `results/runs/`.

  sensitivity.py list    CONFIG            stations with their region
  sensitivity.py base    CONFIG            the fit as frozen (checks that this script reproduces the run)
  sensitivity.py drop    CONFIG STATION    the fit without a station
  sensitivity.py rotate  CONFIG DEGREES    the fit with the wind turned by DEGREES (counterclockwise)
"""

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import calendar, roads
from nox_ml.data.inputs import Inputs
from nox_ml.time import local_day
from nox_ml.validation import experiment
from nox_ml.validation.experiment import load_inputs
from nox_ml.validation.report_final import ZONES

OUT = Path(__file__).parent / "out"


def read_inputs(config: experiment.ExperimentConfig) -> Inputs:
    """The inputs of `experiment.run_experiment`, built the same way."""
    inputs = load_inputs(
        config.data_dir,
        config.period.start.isoformat(),
        config.period.end.isoformat(),
        config.simat_hours,
        config.sources(),
    )
    if config.exclude_atypical:
        days = pd.DatetimeIndex(sorted({local_day(h.hour) for h in inputs.hours}))
        inputs = inputs.on_days(days.difference(calendar.atypical_days(days.min(), days.max())))
    return inputs


def station_regions(inputs: Inputs) -> pd.Series:
    """Region (0-8, as `roads.road_emission_cells`) of each station."""
    x0, y0, x1, y1 = roads.domain_bounds_utm()
    nx, ny = int((x1 - x0) // roads.CELL_M) + 1, int((y1 - y0) // roads.CELL_M) + 1
    ix = ((inputs.station_xy["x"] - x0) // roads.CELL_M).astype(int).clip(0, nx - 1)
    iy = ((inputs.station_xy["y"] - y0) // roads.CELL_M).astype(int).clip(0, ny - 1)
    return ix * roads.N_SPLIT // nx + roads.N_SPLIT * (iy * roads.N_SPLIT // ny)


def used_stations(inputs: Inputs) -> list[str]:
    return sorted({str(s) for ids in inputs.station_ids for s in ids})


def drop_station(inputs: Inputs, station: str) -> Inputs:
    """The inputs without a station's rows (its Jacobian rows are rebuilt, the cache starts empty)."""
    return replace(
        inputs,
        hours=inputs.without_station(station),
        station_ids=[ids[ids != station] for ids in inputs.station_ids],
        jacobian_cache={},
    )


def rotate_wind(inputs: Inputs, degrees: float) -> Inputs:
    """Every wind vector (hours, domain history, station winds) turned by `degrees`."""
    c, s = np.cos(np.radians(degrees)), np.sin(np.radians(degrees))

    def turn(u, v):
        return c * u - s * v, s * u + c * v

    hours = [replace(h, wind=turn(*h.wind)) for h in inputs.hours]
    wind = None
    if inputs.wind is not None:
        wind = inputs.wind.copy()
        wind["u"], wind["v"] = turn(inputs.wind["u"], inputs.wind["v"])
    station_wind = None
    if inputs.station_wind is not None:
        station_wind = inputs.station_wind.copy()
        for station in {col[1] for col in station_wind.columns}:
            station_wind[("u", station)], station_wind[("v", station)] = turn(
                inputs.station_wind[("u", station)], inputs.station_wind[("v", station)]
            )
    return replace(inputs, hours=hours, wind=wind, station_wind=station_wind, jacobian_cache={})


def shares(table: pd.DataFrame) -> dict[str, float]:
    weekday = table[(table["day_type"] == "weekday") & table["zone"].notna()]
    region = weekday.set_index(weekday["zone"].astype(int))["mean"].clip(lower=0)
    return {zone: float(region.reindex(members).sum() / region.sum()) for zone, members in ZONES.items()}


def main(argv: list[str]) -> None:
    mode, config = argv[0], experiment.read_config(Path(argv[1]))
    inputs = read_inputs(config)
    if mode == "list":
        print(pd.DataFrame({"region": station_regions(inputs)}).loc[used_stations(inputs)])
        return
    label = mode
    if mode == "drop":
        inputs, label = drop_station(inputs, argv[2]), f"drop_{argv[2]}"
    elif mode == "rotate":
        inputs, label = rotate_wind(inputs, float(argv[2])), f"rotate_{argv[2]}"
    model = config.model.build().fit(inputs)
    table = model.estimate_emissions().validate().to_frame()
    result = {"config": config.name, "mode": label, "n_stations": len(used_stations(inputs))} | shares(table)
    OUT.mkdir(exist_ok=True)
    (OUT / f"{config.name}.{label}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result)


if __name__ == "__main__":
    main(sys.argv[1:])
