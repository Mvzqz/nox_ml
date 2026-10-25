# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Meteorological normalization with a random forest (deweathering, as in the rmweather literature).

A `RandomForestRegressor` learns the log of station NOx above the background from meteorology and calendar
(on a log scale a change of emission is the same shift under every weather, so the trees can find it also
where concentrations are low; on raw ppb the few stagnant hours dominate the splits and the effect of the
day type is attenuated towards 1). As in rmweather, the weather of
each observed row is replaced by draws from the weather of the whole period (all the weather features
together, so their correlations hold) while its calendar (hour, day of year, day type, station) stays as
observed; the prediction averaged over the draws is that row's deweathered log NOx. The emission index of a
day type is the ratio of the geometric means of its rows' deweathered NOx above the background to the
weekday's. Every day type is
evaluated on the same weather, so the weather that happened to fall on Sundays does not enter the index. The
index is relative: it has no units and says nothing about tonnes.

Features, and why each one is there:

=====================  =======================================================================================
``hour_sin/cos``       Local hour of the day as a circle: 23 h and 0 h are neighbours, and trees need no
                       arbitrary cut at midnight. Absorbs the diurnal cycle of traffic and mixing.
``doy_sin/cos``        Local day of the year as a circle (period 365.25 d): seasonal drift in emissions and
                       background without a monotone trend that cannot be extrapolated.
``ventilation``        Wind speed (m/s) times boundary layer height (m): the dilution rate of a box over the
                       city. Concentration is roughly emission over ventilation, so this one feature carries
                       most of the weather signal in one dimension a tree can split on.
``ventilation_3h/6h``  Sum of the ventilation of the previous 3 and 6 hours: pollution that accumulated
                       under stagnation (or was flushed out) is still there. Hours missing from the data
                       (the afternoon window leaves gaps) are filled with the mean of the available ones,
                       and with the current hour when there are none, so a gap does not look like stagnation.
``wind_sin/cos``       Wind direction as a circle (360 deg = 0 deg); it tells which side of the city the air
                       comes from, a source of difference between stations the speed alone cannot give.
``day_type_*``         One-hot weekday / Saturday / Sunday-or-holiday, the quantity under test; it is kept
                       as observed. Honors `Inputs.day_kinds` (placebo relabeling).
``station_*``          One-hot station id: the level of each site (distance to roads, siting). A station
                       not seen in the fit (leave-one-out) is all zeros, a mix of the others.
=====================  =======================================================================================

Zones: the index is pooled (``zone`` null). A station responds to the emissions upwind of it, from several
zones at once, so a forest on station data cannot attribute a change to a zone.
"""

from collections.abc import Sequence
from typing import ClassVar, Literal, Self

import numpy as np
import pandas as pd
from pydantic import Field
from sklearn.ensemble import RandomForestRegressor

from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import BACKGROUND_STATION, DAY_TYPE_NAMES, HOLIDAYS
from nox_ml.inversion.normalized import WEEKDAY, day_type, interval
from nox_ml.models.base import PREDICTION_COLUMNS, EmissionEstimate, ModelParams
from nox_ml.time import local_day, utc_to_local

PREVIOUS_WINDOWS_H = (3, 6)
WEATHER = [
    "wind_sin",
    "wind_cos",
    "ventilation",
    "ventilation_3h",
    "ventilation_6h",
]  # resampled to deweather
FLOOR_ABOVE_BACKGROUND_PPB = 1.0  # NOx above the background is floored here before the log (noise, clean air)


class RfDeweatherParams(ModelParams):
    n_estimators: int = Field(200, ge=1, description="trees of the forest")
    max_depth: int | None = Field(
        None, ge=1, description="maximum depth of a tree; null grows until the leaves are pure"
    )
    min_samples_leaf: int = Field(3, ge=1, description="minimum station rows in a leaf")
    max_features: float = Field(1.0, gt=0, le=1, description="fraction of the features tried at each split")
    background_ppb: float = Field(
        BACKGROUND_STATION[0],
        ge=0,
        description="NOx not emitted by the city (ppb), taken off before the ratio",
    )
    weather_samples: int = Field(
        20, ge=1, description="weather draws of the period per row when deweathering"
    )
    bootstrap_n: int = Field(10, ge=1, description="refits on days drawn with replacement, for the intervals")
    bootstrap_level: float = Field(0.90, gt=0, lt=1, description="central level of the intervals")


def ventilation_features(hours: pd.DataFrame) -> pd.DataFrame:
    """Ventilation and its sums over the previous 3 and 6 hours, indexed like `hours`.

    `hours` has one row per hour with ``utc``, ``u``, ``v`` (m/s) and ``pbl`` (m). The sum over the previous
    `n` hours is `n` times the mean of those present in `hours`; with none present, `n` times the current
    hour.
    """
    series = pd.Series(np.hypot(hours["u"], hours["v"]).to_numpy() * hours["pbl"].to_numpy(), hours["utc"])
    out = {"ventilation": series.to_numpy()}
    for n in PREVIOUS_WINDOWS_H:
        lagged = pd.concat(
            [series.shift(freq=pd.Timedelta(hours=k)) for k in range(1, n + 1)], axis=1, sort=False
        )
        mean = lagged.reindex(series.index).mean(axis=1)  # NaN when no previous hour is present
        out[f"ventilation_{n}h"] = n * mean.fillna(series).to_numpy()
    return pd.DataFrame(out, index=hours.index)


def hour_table(data: Inputs, holidays: Sequence[str] = HOLIDAYS) -> pd.DataFrame:
    """Meteorology and calendar features of every hour of `data` (one row per hour, in order)."""
    utc = pd.DatetimeIndex([h.hour for h in data.hours])
    hours = pd.DataFrame(
        {
            "utc": utc,
            "u": [h.wind[0] for h in data.hours],
            "v": [h.wind[1] for h in data.hours],
            "pbl": [h.pbl for h in data.hours],
        }
    )
    local = utc_to_local(utc)
    hour_angle = 2 * np.pi * (local.hour + local.minute / 60) / 24
    doy_angle = 2 * np.pi * (local.day_of_year - 1) / 365.25
    speed = np.hypot(hours["u"], hours["v"]).to_numpy()
    towards = np.arctan2(hours["v"], hours["u"]).to_numpy()
    days = local_day(utc)
    kinds = day_type(days, holidays)
    kinds = np.array([(data.day_kinds or {}).get(d, int(k)) for d, k in zip(days, kinds, strict=True)])
    features = pd.DataFrame(
        {
            "hour_sin": np.sin(hour_angle),
            "hour_cos": np.cos(hour_angle),
            "doy_sin": np.sin(doy_angle),
            "doy_cos": np.cos(doy_angle),
            "wind_sin": np.where(speed > 0, np.sin(towards), 0.0),
            "wind_cos": np.where(speed > 0, np.cos(towards), 0.0),
        },
        index=hours.index,
    )
    return pd.concat([features, ventilation_features(hours)], axis=1).assign(day_type=kinds)


class RfDeweather:
    """Random forest on station NOx; the emission index is the day-type effect with the weather held fixed."""

    name: ClassVar[str] = "rf_deweather"
    role: ClassVar[Literal["model", "reference"]] = "model"
    Params: ClassVar[type[ModelParams]] = RfDeweatherParams

    def __init__(self, params: RfDeweatherParams | None = None) -> None:
        self.params: ModelParams = params or self.Params()
        self._forest: RandomForestRegressor | None = None
        self._stations: list[str] = []
        self._fit_rows: pd.DataFrame | None = None
        self._smearing = 1.0  # Duan's factor: back-transforms the mean of the log to a mean

    def _forest_params(self) -> RfDeweatherParams:
        assert isinstance(self.params, RfDeweatherParams)
        return self.params

    def _target(self, rows: pd.DataFrame) -> np.ndarray:
        """Log of the NOx above the background (floored)."""
        above = rows["nox"].to_numpy() - self._forest_params().background_ppb
        return np.log(np.maximum(above, FLOOR_ABOVE_BACKGROUND_PPB))

    def _new_forest(self, oob_score: bool = False) -> RandomForestRegressor:
        p = self._forest_params()
        return RandomForestRegressor(
            n_estimators=p.n_estimators,
            max_depth=p.max_depth,
            min_samples_leaf=p.min_samples_leaf,
            max_features=p.max_features,
            random_state=p.seed,
            oob_score=oob_score,
            n_jobs=-1,
        )

    @property
    def n_params(self) -> int:
        """Nodes of all the trees."""
        if self._forest is None:
            raise RuntimeError("fit the model first")
        return int(sum(tree.tree_.node_count for tree in self._forest.estimators_))

    def _rows(self, data: Inputs, stations: Sequence[str] | None) -> pd.DataFrame:
        """One row per station row of `data` (of `stations`, or all), with ``station``, ``utc``, ``nox``, the
        local ``day`` and the hour features."""
        table = hour_table(data)
        counts = [len(ids) for ids in data.station_ids]
        rows = table.loc[table.index.repeat(counts)].reset_index(drop=True)
        rows["station"] = np.concatenate(data.station_ids) if counts else []
        rows["utc"] = np.repeat([h.hour for h in data.hours], counts)
        rows["nox"] = np.concatenate([h.nox for h in data.hours]) if counts else []
        rows["day"] = local_day(pd.DatetimeIndex(rows["utc"]))
        return rows if stations is None else rows[rows["station"].isin(list(stations))].reset_index(drop=True)

    def _matrix(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Feature matrix of `rows` in the column order of the fit."""
        kinds = rows["day_type"].to_numpy()
        features = rows.drop(columns=["station", "utc", "nox", "day", "day_type"])
        types = pd.DataFrame(
            {f"day_type_{name}": (kinds == k).astype(float) for k, name in enumerate(DAY_TYPE_NAMES)}
        )
        sites = pd.DataFrame({f"station_{s}": (rows["station"] == s).astype(float) for s in self._stations})
        return pd.concat([features.reset_index(drop=True), types, sites], axis=1)

    def fit(self, data: Inputs, *, exclude_stations: Sequence[str] = ()) -> Self:
        rows = self._rows(data, None)
        rows = rows[~rows["station"].isin(list(exclude_stations))].reset_index(drop=True)
        self._stations = sorted(set(rows["station"]))
        self._fit_rows = rows
        target = self._target(rows)
        forest = self._new_forest(oob_score=True).fit(self._matrix(rows), target)
        self._forest = forest
        residual = target - forest.oob_prediction_
        self._smearing = float(np.nanmean(np.exp(residual))) if np.isfinite(residual).any() else 1.0
        return self

    def predict_stations(self, data: Inputs, stations: Sequence[str]) -> pd.DataFrame:
        if self._forest is None:
            raise RuntimeError("fit the model first")
        rows = self._rows(data, stations)
        above = self._smearing * np.exp(self._forest.predict(self._matrix(rows))) if len(rows) else []
        pred = self._forest_params().background_ppb + above
        return pd.DataFrame({"station": rows["station"], "utc": rows["utc"], "nox_ppb_pred": pred})[
            PREDICTION_COLUMNS
        ]

    def _indices(
        self, forest: RandomForestRegressor, design: pd.DataFrame, weights: np.ndarray
    ) -> np.ndarray:
        """Emission index of each day type over the weekday (geometric means). Each row of the fit gets the
        weather of `weather_samples` rows drawn from the period, and the forest's predictions are averaged per
        row; the `weights` (1 per row, or the counts of a bootstrap over days) average them by day type."""
        assert self._fit_rows is not None
        p = self._forest_params()
        rng = np.random.default_rng(p.seed)
        draws = design[WEATHER].to_numpy()[rng.choice(len(design), p.weather_samples)]
        stacked = pd.concat([design] * p.weather_samples, ignore_index=True)
        stacked[WEATHER] = np.repeat(draws, len(design), axis=0)
        deweathered = forest.predict(stacked).reshape(p.weather_samples, len(design)).mean(axis=0)
        kinds = self._fit_rows["day_type"].to_numpy()
        level = np.array(
            [
                np.average(deweathered[kinds == k], weights=weights[kinds == k])
                if weights[kinds == k].sum() > 0
                else np.nan
                for k in range(len(DAY_TYPE_NAMES))
            ]
        )
        return np.exp(level - level[WEEKDAY])

    def estimate_emissions(self) -> EmissionEstimate:
        """Index of each day type over the weekday (pooled over zones) with a bootstrap over whole days. A
        day type without rows in the fit gets NaN."""
        if self._forest is None or self._fit_rows is None:
            raise RuntimeError("fit the model first")
        p, rows = self._forest_params(), self._fit_rows
        design, target = self._matrix(rows), self._target(rows)
        index = self._indices(self._forest, design, np.ones(len(rows)))
        days, day_index = np.unique(rows["day"].to_numpy(), return_inverse=True)
        rng = np.random.default_rng(p.seed)
        boot = []
        for _ in range(p.bootstrap_n):
            weights = np.bincount(rng.choice(len(days), len(days)), minlength=len(days))[day_index]
            replicate = self._new_forest().fit(design, target, sample_weight=weights)
            boot.append(self._indices(replicate, design, weights))
        replicates = np.array(boot)
        bounds = np.array(
            [
                interval(replicates[:, k], p.bootstrap_level)
                if np.isfinite(replicates[:, k]).any()
                else (np.nan,) * 2
                for k in range(len(index))
            ]
        )
        table = pd.DataFrame(
            {
                "zone": np.full(len(index), np.nan),
                "day_type": DAY_TYPE_NAMES,
                "mean": index,
                "lo": np.minimum(bounds[:, 0], index),
                "hi": np.maximum(bounds[:, 1], index),
            }
        )
        return EmissionEstimate("relative", table)
