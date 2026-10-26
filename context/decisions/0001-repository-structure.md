# 0001. Repository structure and tooling

- **Date:** 2026-10-24
- **Status:** accepted

## Context

The research phase is over (see `reports/PENDIENTES.md` in the research folder). The code is a collection of scripts; we need a collaborative repository that is reproducible across machines and has quality gates.

## Decision

- One repository (public GitHub `Mvzqz/nox_ml`, connected to DagsHub) with a **uv** workspace of two packages: `nox_ml` (ML and physics) and `nox_app` (interface). The app depends only on exported results.
- **DVC** on DagsHub (private) for data from the start; the DVC pipeline is added once modules are migrated.
- **ruff** (lint and format), **pyright** (types), **pytest + hypothesis** (tests), **pre-commit**, and **GitHub Actions** on Ubuntu only (cheapest runner; amended 2026-10-24: macOS is checked locally by teammates who use it).
- **Streamlit** for the interface for now; hosting (possibly GCP) is decided later.
- **Jupyter** notebooks in `notebooks/` that only reuse package functions.
- Risk-based test coverage (`docs/testing.md`).
- Code, comments and code documentation in English; notebooks, reports and `context/` (except ADRs) in Spanish.
- Gradual migration from the research folder (`~/code/contaminacion`: `scripts/`, `reports/`, `data/`), deciding each time what comes in, starting with the highest-risk parts (physics, estimator, inversion).

## Consequences

- A new machine is ready with `bin/uptodate`.
- Changing the interface (e.g. FastAPI + web) does not touch the ML code.
- Research code stays out of the repository until migrated; everything that enters passes lint, type checks and tests.
