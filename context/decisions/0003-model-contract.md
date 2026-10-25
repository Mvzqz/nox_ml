# 0003. Model contract and registry

- **Date:** 2026-10-24
- **Status:** accepted

## Context

`docs/models.md` defines how models and references plug into the evaluation harness. The harness (ADR 0002) only knew the baseline inversion.

## Decision

- `nox_ml.models` holds the `Model` protocol, `EmissionEstimate`, the pydantic `ModelParams` and `REGISTRY`. The experiment config has `model: {name, params}`; its default is the baseline (`inversion_plume`), and the stored `config.yaml` has every param filled in. `baseline.yaml` gives the numbers of ADR 0002.
- **`Dataset` is `nox_ml.data.inputs.Inputs`**, not the table layout of `docs/models.md` section 1. It already carries what the baseline needs; a model that needs other tables extends `Inputs`.
- Leave-one-station-out refits a fresh model with `exclude_stations=[station]`. The hourly background of a prediction is estimated from the stations the model was fitted with, so the held-out station never enters it (same numbers as before). The IDW and hybrid columns of `metrics.json` are still computed by the harness from the model's predictions.
- The bootstrap over days moved from the experiment config to the params of `inversion_plume` (`bootstrap_n`, `bootstrap_level`, `seed`), because it re-solves that model. `sigma_theta_deg` and `u_min_ms` are params too (defaults = the old constants).
- The placebo gate is measured on the model itself: it is fitted again on weekdays only with a random subset relabeled as Sundays (`placebo.refits` times, each a full fit). The older `normalized` block stays as a model-independent reference.
- `metrics.json` keeps its blocks and adds `summary` (`validation.metrics.RunMetrics`), the flat row that `nox-ml compare` reads. Runs before this change have no `summary` and are skipped by `compare`.

## Consequences

- A baseline run takes longer: `placebo.refits` extra fits, plus a station-only Jacobian per leave-one-out fold.
- `nox-ml tune` scores trials with plain leave-one-station-out RMSE on the config period; the nested split and day-block folds of `docs/models.md` section 3 are not implemented yet, so a tuned model's RMSE is optimistic.
