# 0004. PINN plume as a model of the registry

- **Date:** 2026-10-25
- **Status:** accepted

## Context

The research prototype (`reports/pinn_prototipo.md`, research-archive) trains a network on the 2D advection-diffusion equation and uses it as the source-receptor matrix of the same Bayesian inversion as the baseline. It reproduces the linear inversion where it matters (Sunday/weekday 0.43 against 0.42, leave-one-station-out RMSE 12.5 against 13.4 ppb) and shows that the absolute level depends on the physics (+42 % road emission) while the ratios between day types do not. The prototype also trained the network jointly with the emissions; that did not improve the fit and distorted the network, so it is not migrated.

## Decision

- **`pinn_plume` is a `Model` of `nox_ml.models.REGISTRY`** (ADR 0003). `PinnPlume` subclasses `InversionPlume` and overrides one hook, `transport()`, which returns the source-receptor matrix of one hour; fit, prediction, the emission estimate with its bootstrap interval and the TEMPO correlation are shared. `PinnParams` (layers, width, learning rate, physics weight, Adam steps, L-BFGS rounds, seed, NOx lifetime, wind floor, bootstrap) is its pydantic `Params`; experiments select it with `model: {name: pinn_plume, params: ...}` (`configs/experiments/pinn_plume.yaml`).
- **The transport is injectable.** `jacobian_hour_steady` assembles the matrix of one hour from any stationary response; `jacobian_hour_plume` and `jacobian_hour_pinn` are two responses. `hour_systems` takes an optional `jacobian` whose default is the plume with `sigma_theta` and `u_min` (before, those two arguments were ignored and the module constants used).
- **The network learns physics only and is trained once.** It does not see data, so it cannot leak a held-out station. `obtain_kernel` finds it in memory (one per process: the leave-one-out refits and placebo fits share it), in the network bundled with the package for the default parameters, in a disk cache (`kernel_dir`, keyed by `PinnParams.training_key()`: the training fields plus the equation constants), or trains it. This is a deliberate exception to "no file I/O inside `fit`": the cache is a memo of a deterministic function of the parameters, never of the data. `tau_h` and `u_min` change how the network is evaluated, not the network.
- **Contract tests judge a model on data from its own physics.** `test_a_model_recovers_the_synthetic_emissions` and the placebo test simulate the fixture with the model's `transport()`. Data from the plume inverted with the PINN moves the absolute level by tens of percent (the cross twin of the report), which says nothing about the estimator.
- **torch stays an optional extra (`pinn`)**: the model registers only if torch imports, but CI and `bin/uptodate` install it so type checks and the network tests run.

## Consequences

- The default `pinn_plume` needs no training. Other parameters train in about 3 minutes on 4 CPU cores (the research reported 18 minutes on a shared machine) once per process, or once per machine with `kernel_dir`.
- The absolute emission of the PINN is not comparable to the plume's to better than 25-40 %; compare ratios and use the normalized estimator for changes.
- Limits inherited from the prototype: one uniform wind per hour (what makes the Green function valid), stationary state, about 1.5 km resolution, chemistry only as a lifetime. A variable wind field needs a PINN of the full field, a different and much more expensive model.
- The bundled network must be trained again (and copied to `nox_ml/models/pinn/bundled/`) when the equation constants change; a test fails if the bundled key is stale.
