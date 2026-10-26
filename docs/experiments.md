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

## The PINN plume

`configs/experiments/pinn_plume.yaml` is the baseline with `model: {name: pinn_plume}` (ADR 0004): the same inversion, data, priors and metrics, with the source-receptor matrix given by a physics-informed network instead of the Gaussian plume. It needs the `pinn` extra (`bin/uptodate` installs it); without torch the model is not registered.

The network of the default parameters is bundled, so the run does not train. Other parameters train one the first time (about 3 minutes on 4 cores) and keep it in `kernel_dir` for the next run:

```sh
uv run nox-ml train-pinn configs/experiments/pinn_plume.yaml   # network + validation against the exact solution
uv run nox-ml run configs/experiments/pinn_plume.yaml
```

Hyperparameters (`layers`, `width`, `learning_rate`, `physics_weight`, `adam_steps`, `lbfgs_rounds`, `seed`, `tau_h`, `u_min`, bootstrap) are the fields of `nox_ml.models.pinn.params.PinnParams`; `tau_h` and `u_min` do not retrain.

## Random forest deweathering

`configs/experiments/rf_deweather.yaml` (ADR 0006) fits a random forest of station NOx on meteorology and calendar and reports a **relative** emission index per day type (pooled over zones, weekday = 1) with its bootstrap interval; it gives no tonnes. Hyperparameters are the fields of `nox_ml.models.rf_deweather.RfDeweatherParams`. A run takes a few minutes, mostly the placebo refits.

## The PINN puffs

`configs/experiments/pinn_puff.yaml` is `pinn_plume.yaml` with `model: {name: pinn_puff}` (ADR 0005): the kernel of the network is applied to the plume of the last hour and to the puffs of the previous `max_age_h` hours (24 by default). It uses the same bundled network, so it does not train. Building its matrices takes about 11 minutes on one core, once per run:

```sh
uv run nox-ml run configs/experiments/pinn_puff.yaml
uv run nox-ml compare runs/*
```

## Comparing an improvement with the baseline

1. Copy `baseline.yaml`, change `name` and the field of the improvement, run it.
2. Compare the two `metrics.json` (`diff`, or load both in pandas). Read the whole picture: a lower LOO RMSE with a wider placebo is not an improvement.

Every method change must be a config field whose default is the baseline behavior (ADR 0002), so that `baseline.yaml` keeps giving the same numbers. The `slow` test `ml/tests/test_baseline_run.py` checks it.


### E7: Meteorology-normalized emission ratios

The `normalized_ratio` model estimates relative changes in NOx emissions using meteorological normalization. Unlike the baseline, it does not estimate absolute emission tonnages.

The experiment uses the same evaluation period (November–December 2023) and SIMAT hours (12 and 17) as `inversion_plume`.

**Reproduction commands:**

```sh
uv run --no-sync nox-ml run configs/experiments/baseline.yaml
uv run --no-sync nox-ml run configs/experiments/normalized_ratio.yaml
uv run --no-sync nox-ml compare runs/baseline runs/normalized_ratio
```

**Real-data comparison:**

| Metric | Baseline | E7 |
|---|---:|---:|
| LOO RMSE (ppb) | 13.59 | 16.75 |
| LOO bias (ppb) | 6.83 | 7.30 |
| Hourly LOO RMSE (ppb) | 11.75 | 15.08 |
| Sunday/weekday ratio | 0.42 | 0.56 |
| Sunday ratio reference gap | 0.23 | 0.09 |
| Placebo center | 1.08 | 0.88 |
| Placebo half-width | 0.35 | 0.22 |
| Fit time (s) | 23.17 | 0.00 |
| Prediction time (s) | 0.21 | 23.21 |
| Number of parameters | 31 | 2 |

Both models are eligible under the experiment's placebo criterion.

The baseline achieves better predictive accuracy, while E7 uses fewer parameters, produces a narrower placebo interval, and estimates a Sunday/weekday emission ratio closer to the reference value.

E7's fitting time is negligible at the displayed precision, but its prediction time is considerably longer. Therefore, it should not be described as faster overall.

**Conclusion:** E7 provides an interpretable alternative for estimating relative emission changes, but it does not outperform the baseline in predictive accuracy.



## Inputs of the baseline

- Station NOx rows (SIMAT hour labels 12-17 local) and the hourly wind of the stations; only hours with both are used, as in the research.
- Domain wind: plain hourly mean of the station u, v. Boundary layer height: ERA5 filled with MERRA-2, averaged with the next hour, at least 200 m.
- NO2/NOx ratio: rows with both values. TEMPO: valid pixels at the hour of their scan.
- 9 road regions (3x3), 4 point sources, plume with 15 degrees of wind-direction uncertainty and TEMPO at its nominal weight (`nox_ml.inversion.linear`).

## Diagnostics of the baseline

```sh
uv run nox-ml diagnose configs/experiments/baseline.yaml                  # about 8 minutes
uv run nox-ml diagnose configs/experiments/baseline.yaml --only information   # about 25 seconds
```

It writes CSV files to `runs/<name>/diagnostics/` (`nox_ml.validation.diagnostics`; the functions return DataFrames, the plots are made in the notebooks). `--seeds` sets the random subsets per case (5); `--only` (repeatable) picks `information`, `ablation` or `learning`.

| File | Contents |
|---|---|
| `variance_reduction.csv` | Per unknown (point source, or road region × day type): prior and posterior standard deviation and the fraction of the prior variance removed, with the stations only, TEMPO only and both. Computed from the prior and `J^T R^-1 J`, so it does not depend on the observed values |
| `degrees_of_freedom.csv` | Degrees of freedom for signal (trace of the averaging kernel, the sum of the reductions above) per source, in total and by group (points, weekday, Saturday, Sunday or holiday) |
| `ablation.csv` | All the metrics of `metrics.json` (`evaluate`, the same code as `nox-ml run`, with the model of the config) (as `block.name` columns, without the per-station table) for the `baseline`, `no_tempo`, `stations` (24, 15 and 9; random subsets that spread out over the domain, 5 seeds; all 24 is the baseline) and `wind_bias` (the wind of every hour turned +15 and +30 degrees clockwise) |
| `learning_curve.csv` | In-sample RMSE at the stations and leave-one-station-out RMSE (model, IDW, hybrid) with 15, 30, 45 and 61 days (blocks of consecutive days, 5 seeds) and with 6, 12, 18 and 24 stations (5 seeds) |

Notes for reading them:

- The Jacobians are built once (by the baseline fit) and sliced for every variant that keeps the wind: subsets of stations, days, and no TEMPO. Only the wind-rotation cases build their own. The placebo refits inside `evaluate` still rebuild the Jacobians of the weekday hours once per case (`Inputs.on_days` starts an empty cache).
- Station subsets start from a random station and add the others with probability proportional to the squared distance to the ones chosen (k-means++ seeding). Hours left without station rows are dropped, as in the input assembly; the wind and boundary layer height of an hour are not recomputed from the stations that remain.
- The wind-direction case is a systematic rotation of the inputs; the 15 degrees of wind-direction uncertainty of the inversion are unchanged.
- The variance reduction treats TEMPO pixels as independent, as the baseline does; it is an upper bound of what they can give.
