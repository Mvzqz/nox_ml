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

## Metrics

| Block | What it is |
|---|---|
| `in_sample` | Correlation of the fitted model with station NOx (`r_stations`, `rmse_stations`) and TEMPO NO2 (`r_tempo`) |
| `loo` | Leave-one-station-out RMSE (ppb) of the model, IDW and the hybrid (model + IDW of the residuals), pooled by number of rows. `bias` is the part that repeats at each station and `hourly` the part that changes hour to hour. `hybrid_beats_idw` counts stations. `stations` has the per-station table |
| `day_types` | Road emission by day type and the Saturday and Sunday over weekday ratios, with a percentile interval from a bootstrap over whole days |
| `normalized` | Meteorology-normalized estimator (observed over modeled NOx with the prior emission): `placebo_half_width` is half the central interval of the ratio of fake Sundays among weekdays, the smallest change it could detect |

## Comparing an improvement with the baseline

1. Copy `baseline.yaml`, change `name` and the field of the improvement, run it.
2. Compare the two `metrics.json` (`diff`, or load both in pandas). Read the whole picture: a lower LOO RMSE with a wider placebo is not an improvement.

Every method change must be a config field whose default is the baseline behavior (ADR 0002), so that `baseline.yaml` keeps giving the same numbers. The `slow` test `ml/tests/test_baseline_run.py` checks it.

## Inputs of the baseline

- Station NOx rows (SIMAT hour labels 12-17 local) and the hourly wind of the stations; only hours with both are used, as in the research.
- Domain wind: plain hourly mean of the station u, v. Boundary layer height: ERA5 filled with MERRA-2, averaged with the next hour, at least 200 m.
- NO2/NOx ratio: rows with both values. TEMPO: valid pixels at the hour of their scan.
- 9 road regions (3x3), 4 point sources, plume with 15 degrees of wind-direction uncertainty and TEMPO at its nominal weight (`nox_ml.inversion.linear`).

## Diagnostics of the baseline

```sh
uv run nox-ml diagnose configs/experiments/baseline.yaml                  # about an hour
uv run nox-ml diagnose configs/experiments/baseline.yaml --only information   # seconds
```

It writes CSV files to `runs/<name>/diagnostics/` (`nox_ml.validation.diagnostics`; the functions return DataFrames, the plots are made in the notebooks). `--seeds` sets the random subsets per case (5); `--only` (repeatable) picks `information`, `ablation` or `learning`.

| File | Contents |
|---|---|
| `variance_reduction.csv` | Per unknown (point source, or road region × day type): prior and posterior standard deviation and the fraction of the prior variance removed, with the stations only, TEMPO only and both. Computed from the prior and `J^T R^-1 J`, so it does not depend on the observed values |
| `degrees_of_freedom.csv` | Degrees of freedom for signal (trace of the averaging kernel, the sum of the reductions above) per source, in total and by group (points, weekday, Saturday, Sunday or holiday) |
| `ablation.csv` | All the metrics of `metrics.json` (as `block.name` columns, without the per-station table) for the `baseline`, `no_tempo`, `stations` (24, 15 and 9; random subsets that spread out over the domain, 5 seeds; all 24 is the baseline) and `wind_bias` (the wind of every hour turned +15 and +30 degrees clockwise) |
| `learning_curve.csv` | In-sample RMSE at the stations and leave-one-station-out RMSE (model, IDW, hybrid) with 15, 30, 45 and 61 days (blocks of consecutive days, 5 seeds) and with 6, 12, 18 and 24 stations (5 seeds) |

Notes for reading them:

- Station subsets start from a random station and add the others with probability proportional to the squared distance to the ones chosen (k-means++ seeding). Hours left without station rows are dropped, as in the input assembly; the wind and boundary layer height of an hour are not recomputed from the stations that remain.
- The wind-direction case is a systematic rotation of the inputs; the 15 degrees of wind-direction uncertainty of the inversion are unchanged.
- The variance reduction treats TEMPO pixels as independent, as the baseline does; it is an upper bound of what they can give.
