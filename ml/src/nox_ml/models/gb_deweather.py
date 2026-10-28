# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportReturnType=false
# pyright: reportIncompatibleMethodOverride=false
# (the pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Meteorological normalization with gradient boosting: `RfDeweather` with another estimator.

Features, deweathering (rows keep their calendar and take draws of the period's weather), the log scale over
the background, the relative index and the bootstrap over days are those of `rf_deweather`; only the
estimator changes, to a `HistGradientBoostingRegressor`. Boosting fits the residual of the previous trees
instead of averaging independent ones, so it can follow the data more closely (and overfit it more): the
placebo and the attenuation of the Sunday index towards 1 are the things to watch.

Differences that come with the estimator:

* No out-of-bag predictions exist, and the residual of the fit itself understates the error (boosting follows
  the training rows), which would bias `predict_stations` downwards. Duan's smearing factor is learnt instead
  from out-of-sample residuals: `CV_GROUPS` blocks of whole days (a day's rows stay together, as they share
  weather), each predicted by a model trained on the other four. It only rescales `predict_stations`, not the
  index. Cost: `fit` trains the model 1 + `CV_GROUPS` times (the extra ones on 80 % of the rows), about 5
  times the time of a single boosting fit; the bootstrap refits of the index do not pay it.
* `drop_features` removes columns of the matrix, for the ablation of features that carry no information in a
  period (``doy_sin`` and ``doy_cos`` are collinear in two months). The day type cannot be dropped: it is the
  quantity under test.
"""

from typing import ClassVar

import numpy as np
import pandas as pd
from pydantic import Field, field_validator
from sklearn.ensemble import HistGradientBoostingRegressor

from nox_ml.models.base import ModelParams
from nox_ml.models.rf_deweather import DeweatherParams, Estimator, RfDeweather

CV_GROUPS = 5  # blocks of days for the out-of-sample residuals of the smearing factor


class GbDeweatherParams(DeweatherParams):
    learning_rate: float = Field(0.1, gt=0, description="shrinkage of each tree's contribution")
    max_iter: int = Field(200, ge=1, description="boosting iterations (trees); there is no early stopping")
    max_leaf_nodes: int = Field(31, ge=2, description="maximum leaves of a tree")
    min_samples_leaf: int = Field(20, ge=1, description="minimum station rows in a leaf")
    l2_regularization: float = Field(0.0, ge=0, description="L2 penalty on the leaf values")
    drop_features: list[str] = Field(
        default_factory=list, description="feature columns taken out of the model (empty keeps them all)"
    )

    @field_validator("drop_features")
    @classmethod
    def keep_the_day_type(cls, names: list[str]) -> list[str]:
        if any(name.startswith("day_type_") for name in names):
            raise ValueError("the day type is the quantity under test and cannot be dropped")
        return names


class GbDeweather(RfDeweather):
    """Gradient boosting on station NOx; the index is the day-type effect with the weather held fixed."""

    name: ClassVar[str] = "gb_deweather"
    Params: ClassVar[type[ModelParams]] = GbDeweatherParams

    def _new_forest(self, oob_score: bool = False) -> Estimator:
        p = self.params
        assert isinstance(p, GbDeweatherParams)
        return HistGradientBoostingRegressor(
            learning_rate=p.learning_rate,
            max_iter=p.max_iter,
            max_leaf_nodes=p.max_leaf_nodes,
            min_samples_leaf=p.min_samples_leaf,
            l2_regularization=p.l2_regularization,
            early_stopping=False,
            random_state=p.seed,
        )

    def _matrix(self, rows: pd.DataFrame) -> pd.DataFrame:
        design = super()._matrix(rows)
        p = self.params
        assert isinstance(p, GbDeweatherParams)
        unknown = sorted(set(p.drop_features) - set(design.columns))
        if unknown:
            raise ValueError(f"drop_features not in the feature matrix: {unknown}")
        return design.drop(columns=p.drop_features)

    def _log_residual(self, forest: Estimator, design: pd.DataFrame, target: np.ndarray) -> np.ndarray:
        """Residual of the log target out of sample: days are dealt at random (seeded) into `CV_GROUPS` blocks
        and each block is predicted by a model trained on the rest. With fewer than two days there is nothing
        to hold out, and the residual of `forest` itself is returned."""
        assert self._fit_rows is not None
        days, day_index = np.unique(self._fit_rows["day"].to_numpy(), return_inverse=True)
        n_groups = min(CV_GROUPS, len(days))
        if n_groups < 2:
            return target - forest.predict(design)
        order = np.random.default_rng(self.params.seed).permutation(len(days))
        block = np.empty(len(days), dtype=int)
        for k, chunk in enumerate(np.array_split(order, n_groups)):
            block[chunk] = k
        rows_block = block[day_index]
        predicted = np.empty(len(target))
        for k in range(n_groups):
            held = rows_block == k
            predicted[held] = self._new_forest().fit(design[~held], target[~held]).predict(design[held])
        return target - predicted

    @property
    def n_params(self) -> int:
        """Nodes of all the trees."""
        if not isinstance(self._forest, HistGradientBoostingRegressor):
            raise RuntimeError("fit the model first")
        return sum(len(tree.nodes) for stage in self._forest._predictors for tree in stage)
