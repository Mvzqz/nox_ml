# Testing strategy

Minimum coverage depends on risk: a bug in the physics or the estimator changes the conclusions; a bug in the app is visible right away.

| Level | What it tests | Minimum coverage | When it runs |
|---|---|---|---|
| `nox_ml.physics`, `nox_ml.inversion` | Physical properties (hypothesis): mass conservation, linearity in emissions, wind floor, puffs without wind do not move | 90 % | Every commit |
| `nox_ml.validation` | Small synthetic data with known answers: the twin recovers the emission, the placebo is centered on 1 | 85 % | Every commit |
| `nox_ml.data` | Units (wind in mph), time zones, gaps, formats | 70 % | Every commit |
| Scientific regression (`-m regression`) | A fixed sample reproduces key figures (Sunday ratio, placebo) within a tolerance | — | Pull request |
| `nox_app` | Smoke test with `streamlit.testing.AppTest`; the app does not import `nox_ml` | 50 % | Pull request |
| Full validation (`-m slow`) | Placebos and validations on real data (DVC) | — | Weekly or manual |
| Notebooks | Execute on test data (nbmake) | — | Pull request |

Fast tests (not `slow`) must run in under a minute. Per-package thresholds are enforced in CI as each module is migrated.
