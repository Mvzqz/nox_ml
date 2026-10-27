# 0007. Ensemble contract, nested stacking and test-period evaluation

- **Date:** 2026-10-27
- **Status:** accepted

## Context

Advance 5 compares ensembles (bagging, wind ensembles, deep ensembles, boosting, stacking, Bayesian model averaging) with the same evaluation bench as single models, and must keep estimating emissions. It also evaluates the final model once on the test period (feb–may 2024), which `tune` must never see.

## Decision

- **An ensemble is a `Model`** (`role: model`) that wraps base models declared in its `params` as experiment configs (`members: [{name, params}]`, defaults filled in). `convex_ensemble` is the registered one; its default, equal weights over two inversions, is the simple average and the example that `test_contract` runs. Later ensembles subclass `ConvexEnsemble`. Members must be base models: no references (no emissions) and no nested ensembles (the weights would multiply and the config become unreadable).
- **Convex weights** (>= 0, sum 1), validated in the params, apply to predictions and to emissions. Concentration is linear in emission, so the combination of predictions is the same combination of emissions.
- **Emission rule.** Absolute (t/yr) only if every member is absolute and shares `transport_key()`: weighted mean, sd of the mixture. Otherwise relative: each member's index over the weekday, pooled over zones, weighted. Different transports differ by 25–40 % in level, and averaging tonnes would hide that; the index is what they share. Intervals are weighted means of the members' bounds (a member without one gets a normal 90 % interval from its sd).
- **Nested stacking** (`nox_ml.validation.stacking`) learns weights from the `oof.parquet` of the base runs; the weights for station *s* come from the other stations. Rules: least squares on the simplex (X5) and Gaussian likelihood (X6). No base model is refitted for the nov–dec 2023 table.
- **`nox-ml evaluate <config> --period test`** runs a frozen config on the test period with the same metrics as `run`, in `runs/<name>.test/`, and records `evaluation: {period, start, end, frozen_on}` in `metrics.json`. `compare` shows it as a `period` column. `tune` keeps rejecting the test period and has no option to ask for it; a search pointing to a `.test` config is refused.

## Consequences

- **Residual leak in nested stacking.** The out-of-fold prediction of station *t* came from a model fitted with *s*, so the weights for *s* depend on the observations of *s* through how well the base models predicted *t*. This does not let the weights favor *s*, but strict nesting would refit the base models without each *s*. It is accepted for the nov–dec 2023 table; the test period uses the frozen weights, so it has no such leak.
- An ensemble fit costs the sum of its members; a leave-one-station-out run and the placebo refit every member.
- Relative ensembles lose the zone breakdown even when some members have it.
- `evaluate` can be run many times; each run is a look at the test data. The protocol is to freeze the configuration first. The `evaluation` record and `code_version.json` make the looks auditable.
