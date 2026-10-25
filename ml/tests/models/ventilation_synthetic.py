# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Synthetic stations for the models that learn concentration from the weather (random forest): NOx is a
background plus the emission of the day type over the ventilation, with lognormal noise. The emission of the
Sunday is a chosen fraction of the weekday's (the Saturday sits halfway to it), so the answer is known, and
the weather can be made to depend on the day type (`stagnant_on_sunday`)."""

import numpy as np
import pandas as pd
from synthetic import TRUTH, Synthetic

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.jacobian import Receptors
from nox_ml.inversion.linear import BACKGROUND_STATION, HOLIDAYS, HourData
from nox_ml.inversion.normalized import day_type

BACKGROUND_PPB = BACKGROUND_STATION[0]
PBL_M = 800.0
LEVELS = (0.8, 1.0, 1.2)  # station sitings: relative level of each station


def ventilation_inputs(
    n_days: int = 56,
    sunday: float = TRUTH["sunday_holiday"] / TRUTH["weekday"],
    stagnant_on_sunday: float = 0.5,
    noise: float = 0.15,
    seed: int = 0,
) -> Inputs:
    """`n_days` from 2023-11-06, local 12-17 h, at three stations. Every day is stagnant (wind 0.7-2 m/s) or
    windy (2-5 m/s); a Sunday or holiday is stagnant with probability `stagnant_on_sunday`, any other day
    with 0.5, so a value other than 0.5 ties the weather to the day type. NOx above the background is
    ``20 * emission * level / (speed * pbl / 2000)`` ppb, with the emission 1 on weekdays, `sunday` on
    Sundays and holidays and their midpoint on Saturdays."""
    rng = np.random.default_rng(seed)
    xy = pd.DataFrame({"x": [0.0, 1000.0, 2000.0], "y": 0.0}, index=["AAA", "BBB", "CCC"])
    receptors = Receptors(xy["x"].to_numpy(), xy["y"].to_numpy())
    days = pd.date_range("2023-11-06", periods=n_days)
    emission = np.array([1.0, (1.0 + sunday) / 2, sunday])
    hours, ids = [], []
    for day, kind in zip(days, day_type(days, HOLIDAYS), strict=True):
        stagnant = rng.random() < (stagnant_on_sunday if kind == 2 else 0.5)
        for utc_hour in range(18, 24):
            speed = rng.uniform(0.7, 2.0) if stagnant else rng.uniform(2.0, 5.0)
            angle = rng.uniform(0, 2 * np.pi)
            above = 20 * emission[kind] * np.array(LEVELS) * 2000 / (speed * PBL_M)
            hours.append(
                HourData(
                    hour=day + pd.Timedelta(hours=utc_hour),
                    wind=(speed * np.cos(angle), speed * np.sin(angle)),
                    pbl=PBL_M,
                    stations=receptors,
                    nox=BACKGROUND_PPB + above * rng.lognormal(0, noise, len(xy)),
                    pixels=Receptors(np.array([]), np.array([])),
                    no2=np.array([]),
                )
            )
            ids.append(np.array(xy.index))
    zones = pd.DataFrame({"x": [0.0], "y": [0.0], "weight": [1.0], "region": [0]})
    points = pd.DataFrame({"name": ["P0"], "x": [0.0], "y": [0.0], "prior": [1.0], "sd": [1.0]})
    return Inputs(hours, ids, xy, zones, points, 0.7, n_regions=1)


def ventilation_synthetic(**kwargs) -> Synthetic:
    """The contract's `Synthetic` for these data: only the Sunday ratio is known (no tonnes)."""
    return Synthetic(ventilation_inputs(**kwargs), {})
