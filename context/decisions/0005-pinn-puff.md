# 0005. PINN puffs: the kernel applied to every segment of every puff

- **Date:** 2026-10-25
- **Status:** accepted

## Context

E5a (`pinn_plume`, ADR 0004) replaces the Gaussian plume of the stationary baseline with the plume of a network. The best physical model of the research is not stationary: it follows the emission hour by hour in puffs (`jacobian_hour_puff`). E5b combines the two.

## Decision

- **`pinn_puff` is a `Model` of the registry** that subclasses `InversionPlume` (through `PinnInversion`, which it shares with `PinnPlume`: kernel and parameter count) and changes `transport()` and `transport_key()`. `PinnPuffParams` adds `max_age_h` to `PinnParams`; it does not enter the training key, so both models share the bundled network.
- **Assembly as in `jacobian_hour_puff`**: the plume of the last hour (cut at what the wind carried in one hour) plus sub-puffs every 15 minutes up to `max_age_h`, with the trajectories, speed floor and road profile of `nox_ml.physics.puff`. The shape of every piece comes from the kernel:
  - the last hour is the kernel column, so with no older puffs the matrix is that of `pinn_plume` wherever the receptor is within reach;
  - a puff that travelled `d` metres has unit mass spread isotropically around its centre with the profile `P(r) = F(d, r) / (2 pi int r F dr)` of the kernel's cross-wind section at `d` (exactly the Gaussian if `F` is one). Beyond the 50 km of the table the section widens as `sqrt(d)`. The decay is the survival fraction of the lifetime `tau_h`; the kernel's own decay is divided out by the normalisation, so nothing is counted twice.
- **A transport with memory needs the hours around it**, so `HourJacobianFn` is not enough. `HistoryTransport` (`nox_ml.inversion.linear`) binds to the fitted hours and gets a `History`: the hourly wind of the whole period and the Infovial profile, which `Inputs` now carries (`wind`, `infovial`; the wind stops one day after the period, so a period never reads another one). `hour_jacobians` calls `for_hours` when the transport has it; plain functions work as before. Without a history (the contract fixture) the transport uses the winds of the hours themselves and the typical traffic profile.
- **`transport_key()`** is `("pinn_puff", kernel training hash, tau_h, u_min, max_age_h)`: it never equals the plume's, `pinn_plume`'s or a future Gaussian puff model's.

## Consequences

- Building the matrices of nov-dec 2023 takes about 11 minutes on one core (the PINN plume: under 1 minute), once per run thanks to the Jacobian cache; each puff evaluates a profile table and interpolates it.
- The kernel's cross-wind width grows as `sqrt(d)` and the Gaussian's as `d`, so far from the source (more than about 20 km) the puffs of the PINN are wider and lower; between 5 and 20 km they agree within a factor 1.7.
- The survival is a constant lifetime `tau_h`. When the OH-based loss of E2 reaches `Inputs`, `PinnPuffTransport` can use its `variable_lifetime` instead.
