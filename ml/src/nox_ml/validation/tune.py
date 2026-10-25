# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""``nox-ml tune``: grid or random search over the params of a model, scored by leave-one-station-out RMSE.

Only the tuning period (nov-dec 2023) may be used: the test period is reserved for the final model.
"""

import itertools
from datetime import date
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import Field, model_validator

from nox_ml.data.inputs import Inputs
from nox_ml.models import REGISTRY
from nox_ml.validation import loo
from nox_ml.validation.experiment import ExperimentConfig, Strict

TEST_PERIOD = (date(2024, 2, 1), date(2024, 5, 31))  # feb-may 2024, reserved for the final model


class SearchConfig(Strict):
    """A search space next to an experiment config.

    `space` maps a param to a list. Random search treats ``[lo, hi]`` (two numbers) as a continuous range
    (integers if the param is an int) and any other list as choices; grid search always treats the list as the
    values to try.
    """

    model: str
    config: Path  # experiment YAML (period, data), relative to the search file
    search: Literal["grid", "random"] = "random"
    n_trials: int | None = Field(None, ge=1)
    seed: int = 7
    space: dict[str, list[Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self) -> "SearchConfig":
        if self.model not in REGISTRY:
            raise ValueError(f"unknown model {self.model!r}; registered: {sorted(REGISTRY)}")
        unknown = set(self.space) - set(REGISTRY[self.model].Params.model_fields)
        if unknown:
            raise ValueError(f"params not in {self.model}: {sorted(unknown)}")
        if self.search == "random" and self.n_trials is None:
            raise ValueError("random search needs n_trials")
        return self


def read_search(path: Path) -> tuple[SearchConfig, ExperimentConfig]:
    """The search file and the experiment config it points to, checked to be usable for tuning."""
    search = SearchConfig.model_validate(yaml.safe_load(path.read_text()))
    base = ExperimentConfig.model_validate(yaml.safe_load((path.parent / search.config).read_text()))
    if base.model.name != search.model:
        raise ValueError(
            f"{search.config} uses model {base.model.name!r}, the search is for {search.model!r}"
        )
    refuse_test_period(base)
    return search, base


def refuse_test_period(config: ExperimentConfig) -> None:
    if config.period.start <= TEST_PERIOD[1] and config.period.end >= TEST_PERIOD[0]:
        raise ValueError(
            f"period {config.period.start}..{config.period.end} overlaps the test period "
            f"{TEST_PERIOD[0]}..{TEST_PERIOD[1]}, reserved for the final model"
        )


def trials(search: SearchConfig, base: ExperimentConfig) -> list[dict[str, Any]]:
    """The param overrides to try, each already validated against the model's params."""
    names = list(search.space)
    if search.search == "grid":
        combos = [
            dict(zip(names, values, strict=True)) for values in itertools.product(*search.space.values())
        ]
    else:
        rng = np.random.default_rng(search.seed)
        fields = REGISTRY[search.model].Params.model_fields
        combos = []
        for _ in range(search.n_trials or 0):
            trial = {}
            for name, values in search.space.items():
                is_range = len(values) == 2 and all(isinstance(v, int | float) for v in values)
                if not is_range:
                    trial[name] = values[rng.integers(len(values))]
                elif fields[name].annotation is int:
                    trial[name] = int(rng.integers(values[0], values[1] + 1))
                else:
                    trial[name] = float(rng.uniform(*values))
            combos.append(trial)
    params = REGISTRY[search.model].Params
    for combo in combos:
        params.model_validate(base.model.params | combo)
    return combos


def score(inputs: Inputs, base: ExperimentConfig, overrides: dict[str, Any]) -> dict[str, Any]:
    """Leave-one-station-out RMSE of the model with `overrides` (the only metric a trial needs)."""
    model = base.model.model_copy(update={"params": base.model.params | overrides})
    table, _ = loo.leave_one_out(inputs, model.build)
    return overrides | {"loo_rmse_ppb": loo.summarize(table)["rmse"]["model"]}


def tune(search: SearchConfig, base: ExperimentConfig, inputs: Inputs) -> pd.DataFrame:
    """All trials in the order they ran (the trial curve), one row each: ``trial``, the overrides and the
    score."""
    rows = [{"trial": i} | score(inputs, base, overrides) for i, overrides in enumerate(trials(search, base))]
    return pd.DataFrame(rows)
