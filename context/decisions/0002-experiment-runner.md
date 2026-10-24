# 0002. Experiment runner and baseline

- **Date:** 2026-10-24
- **Status:** accepted

## Context

The baseline inversion exists (`nox_ml.inversion.linear`), but its quality was only visible in research reports. Every improvement we plan (puffs, more regions, TEMPO weight, extra stations...) needs to be measured against the same numbers, computed the same way.

## Decision

- An experiment is one validated YAML (`configs/experiments/*.yaml`, pydantic, unknown fields rejected). `nox-ml run <config>` assembles the inputs, calls `invert` and writes `runs/<name>/`: the resolved `config.yaml`, `metrics.json` and `code_version.json` (git hash, dirty flag). `runs/` is not versioned: a run is reproducible from config plus hash.
- `configs/experiments/baseline.yaml` is the reference. Its numbers on Nov-Dec 2023 reproduce the "Dominio, sin industria" 15 degree row of `reports/base_sigma30.md` (research-archive) and are guarded by a `slow` test (r 0.77 / 0.74, LOO 13.6 / 11.6 / 11.7 ppb, Sunday 0.42 (0.35-0.54)).
- **Every method change enters as a config field whose default is the baseline behavior**, never as a code edit that moves the baseline. An improvement is then `baseline.yaml` plus one changed field, and `metrics.json` of both runs are compared. If the baseline test must change, that is a decision to record here.
- Leave-one-station-out removes the held-out rows *before* the system is built (the hourly background is integrated out analytically, so subtracting them afterwards is not equivalent). The bootstrap over days re-solves the posterior from per-hour systems (`hour_systems` + `solve`), so it does not recompute Jacobians.

## Consequences

- A run of the baseline takes about 4 minutes (24 leave-one-out refits dominate).
- The hours kept are those with station NOx rows and wind (as in the research), so TEMPO pixels of hours without stations are not used. Including them is a candidate improvement to compare through a config field.
