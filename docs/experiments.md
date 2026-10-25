# Experiments

An experiment is a YAML in `configs/experiments/`. Run it from the repository root (needs `dvc pull`):

```sh
uv run nox-ml run configs/experiments/baseline.yaml     # about 4 minutes
```

It writes `runs/<name>/` (not versioned in git):

| File | Contents |
|---|---|
| `config.yaml` | The config as validated, with every default filled in |
| `metrics.json` | The metrics below |
| `code_version.json` | `git_hash` of the code and whether the tree had uncommitted changes |
| `oof.parquet` | Leave-one-station-out predictions (`station`, `utc`, `nox_ppb_pred`), each from a model that never saw that station |
| `emissions.parquet` | The emission estimate of the model fitted on all stations (models only, not references) |

## Metrics

| Block | What it is |
|---|---|
| `in_sample` | Correlation of the fitted model with station NOx (`r_stations`, `rmse_stations`) and TEMPO NO2 (`r_tempo`) |
| `loo` | Leave-one-station-out RMSE (ppb) of the model, IDW and the hybrid (model + IDW of the residuals), pooled by number of rows. `bias` is the part that repeats at each station and `hourly` the part that changes hour to hour. `hybrid_beats_idw` counts stations. `stations` has the per-station table |
| `day_types` | Road emission by day type and the Saturday and Sunday over weekday ratios, with a percentile interval from a bootstrap over whole days |
| `summary` | The flat row `nox-ml compare` reads: `loo_rmse_ppb`, emission metrics, `placebo_center` / `placebo_halfwidth` and the gate `eligible` (center within 1 ± 0.15), `fit_seconds`, `predict_seconds`, `n_params`. Emission fields are null for references |
| `normalized` | Meteorology-normalized estimator (observed over modeled NOx with the prior emission): `placebo_half_width` is half the central interval of the ratio of fake Sundays among weekdays, the smallest change it could detect |

The method is the `model: {name, params}` field (`nox_ml.models.REGISTRY`; see `docs/models.md`). `nox-ml compare runs/*` puts runs side by side and `nox-ml tune <search.yaml>` searches params on nov-dec 2023 (`docs/models.md`, section 7; the search file also names the experiment config with `config:`).

## Comparing an improvement with the baseline

1. Copy `baseline.yaml`, change `name` and the field of the improvement, run it.
2. Compare the two `metrics.json` (`diff`, or load both in pandas). Read the whole picture: a lower LOO RMSE with a wider placebo is not an improvement.

Every method change must be a config field whose default is the baseline behavior (ADR 0002), so that `baseline.yaml` keeps giving the same numbers. The `slow` test `ml/tests/test_baseline_run.py` checks it.

## Inputs of the baseline

- Station NOx rows (SIMAT hour labels 12-17 local) and the hourly wind of the stations; only hours with both are used, as in the research.
- Domain wind: plain hourly mean of the station u, v. Boundary layer height: ERA5 filled with MERRA-2, averaged with the next hour, at least 200 m.
- NO2/NOx ratio: rows with both values. TEMPO: valid pixels at the hour of their scan.
- 9 road regions (3x3), 4 point sources, plume with 15 degrees of wind-direction uncertainty and TEMPO at its nominal weight (`nox_ml.inversion.linear`).
