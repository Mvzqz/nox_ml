# Models: contracts and how to add one

The project goal is to **estimate emissions** (and their changes) by zone and day type. Estimating emissions is therefore a requirement for every model. Concentration-only methods (IDW, kriging) are kept as **references**: the floor a model must match or beat when predicting unseen stations, never candidates.

Every model and reference plugs into the same pipeline:

```
Dataset ──► Model.fit ──► Model.predict_stations ──► evaluate ──► runs/<name>/metrics.json ──► compare
                    └──► Model.estimate_emissions (required for models)
```

The evaluation harness (`nox-ml run`) owns data loading, splits and metrics. A model only fits and predicts. This keeps models comparable and makes adding one a local change.

## 1. Dataset contract

Built once per period by the harness (`nox_ml.validation` / input assembly). Models must treat it as read-only.

| Field | Content |
|---|---|
| `stations` | Hourly NOx at monitoring stations: `station`, `utc`, `local`, `nox_ppb`, `x`, `y` (UTM 14N m) |
| `tempo` | TEMPO NO₂ pixels: `utc`, `x`, `y`, `no2_column` (molec/cm²), `sigma` |
| `meteo` | Hourly domain meteorology: `utc`, `u`, `v` (m/s), `pbl_m` |
| `cells` | Emission grid: `x`, `y`, `weight` (t/yr prior), `zone` |
| `point_sources` | `name`, `x`, `y`, `prior_t_yr`, `prior_sd` |
| `day_type` | `utc` → `weekday` / `saturday` / `sunday_holiday` |

Hours are already filtered as in research (hours with station rows and wind, local 12–17).

## 2. Model contract

```python
class Model(Protocol):
    name: str  # registry key, e.g. "inversion_plume"
    role: Literal["model", "reference"]  # references (IDW, kriging) only predict concentrations
    params: BaseModel  # pydantic hyperparameters (validated, serializable)

    def fit(self, data: Dataset, *, exclude_stations: Sequence[str] = ()) -> Self: ...
    def predict_stations(self, data: Dataset, stations: Sequence[str]) -> pd.DataFrame:
        ...
        # columns: station, utc, nox_ppb_pred

    def estimate_emissions(self) -> EmissionEstimate:
        ...
        # required when role == "model". kind="absolute": mean and sd (t/yr) per zone × day type;
        # kind="relative": emission index per day type (and zone if available), mean and CI,
        # for methods that only resolve changes (e.g. meteorological normalization).
```

Rules:

- `fit` must never read rows of `exclude_stations` (leave-one-station-out). The harness passes the held-out station here; models must not filter it themselves later.
- Deterministic given `params.seed`.
- No file or network I/O inside `fit`/`predict`; everything comes from `Dataset`.
- Hyperparameters live only in `params`, with defaults, units in the field description, and ranges in the search space (section 5).

Register the class in `nox_ml.models.REGISTRY` and give it a config in `configs/experiments/<name>.yaml`.

## 3. Evaluation protocol

| Item | Choice | Why |
|---|---|---|
| Split | Leave-one-station-out over all stations | Measures what matters: predicting where there is no sensor |
| Tuning split | Inside the training stations only (nested), plus day-block folds | No leakage of the held-out station or of neighbouring hours |
| Main metric | `loo_rmse_ppb` (lower is better) | Spatial generalization in the units people read |
| Emission metrics (required for models) | `sunday_ratio` + CI and its gap to traffic counts (0.65–0.73), `placebo_center` and `placebo_halfwidth` | Accuracy of an emission change with a known answer; the model must not invent changes; minimum detectable change |
| Other metrics | `loo_bias_ppb`, `loo_hourly_rmse_ppb`, `r_tempo` | Error split into level and timing; agreement with an independent instrument |
| Eligibility gate | `placebo_center` within 1 ± 0.15 | A model that invents emission changes is not eligible, whatever its RMSE |
| Cost | `fit_seconds`, `predict_seconds`, `n_params` | Required for model comparison |
| References | IDW and kriging (`role: reference`) | Concentration floor a model must match or beat; they have no emission metrics |

`metrics.json` follows `nox_ml.validation.metrics.RunMetrics` (pydantic). References have `null` emission metrics, never invented ones.

## 4. Run artifacts (needed for ensembles)

Every run also writes, under `runs/<name>/`:

- `oof.parquet`: out-of-fold station predictions from the leave-one-station-out loop (`station`, `utc`, `nox_ppb_pred`). Stacking and blending are trained on these, never on in-sample predictions.
- `emissions.parquet`: the `EmissionEstimate` of the model fitted on all training stations.

## 5. Data reserved for testing

- **Spatial:** leave-one-station-out (every run).
- **Temporal:** feb–may 2024 is the **test period**. Tuning and model selection use nov–dec 2023 only; `nox-ml tune` refuses a config whose period overlaps the test period. The test period is reached only with `nox-ml evaluate` (section 6).
- **Events with a known answer:** 2020 lockdown (against 2019) and the 2024 contingencies. Used only to evaluate the final model.

## 6. Comparison

```sh
uv run nox-ml run configs/experiments/<name>.yaml      # one run → runs/<name>/
uv run nox-ml compare runs/*                           # table sorted by the main metric
```

`compare` writes `runs/comparison.csv` and a Markdown table that notebooks display as is. Its `period` column says whether a run is `tuning` (nov–dec 2023) or `test`.

### Test period

```sh
uv run nox-ml evaluate runs/<name>/config.yaml --period test   # frozen config → runs/<name>.test/
```

`evaluate` takes a finished config, changes only its period (15 feb–31 may 2024: the test period from the first day with TEMPO pixels) and name (`<name>.test`), and runs it like `run`: same metrics, same artifacts. `metrics.json` records the look under `evaluation` (`period: test`, its dates and the period the config was frozen on). `--period test` is the only value and it is required. `tune` has no such option and rejects any config on the test period, including a `runs/<name>.test/config.yaml`, so the test period cannot guide a search. Each evaluation is a look at the test data: decide the final configuration before running it.

## 7. Tuning

A search space is a YAML file next to the experiment config:

```yaml
model: inversion_puff
search: random          # grid | random
n_trials: 40
seed: 7
space:
  sigma_theta_deg: [10, 45]          # continuous range
  u_min_ms: [0.5, 1.0, 1.5, 2.0]     # categorical
  tempo_sigma_mult: [1, 2, 3, 5, 10]
```

`nox-ml tune <search.yaml>` scores every trial with the nested split, saves all trials in `runs/<name>/trials.csv`, and refits the best one. The search must be deep enough to show where the optimum is (report the trial curve, not only the winner).

## 8. Tests every model must pass

`ml/tests/models/test_contract.py` is parametrized over `REGISTRY`; a new model is tested automatically once registered:

1. Fits and predicts on the tiny synthetic `Dataset` fixture in under 30 s.
2. Prediction frame has the contract columns and no NaN for stations with data.
3. Same seed → identical predictions.
4. Leakage guard: changing every value of an excluded station does not change the fitted model.
5. `params` round-trips through YAML.
6. Models (`role: model`): `estimate_emissions` follows the schema for its `kind`, has finite means and positive uncertainty, and recovers the synthetic truth (absolute emissions, or the Sunday/weekday ratio for relative models) within the fixture tolerance. Models that learn from the weather instead of simulating it (`LEARN_FROM_WEATHER` in the test) are given eight weeks of synthetic stations (`ventilation_synthetic`), because two Sundays cannot be told apart from their wind.
7. Models: a placebo on the fixture (no emission change) is centered on 1 within the tolerance.
8. The run writes `oof.parquet` without any in-sample row of the held-out station.

Model-specific tests (physics properties, reproduction of research numbers) go in the model's own test file.

## 9. Adding a model, step by step

1. Branch `models/<name>` from `main`.
2. `ml/src/nox_ml/models/<name>.py`: params class + model class; reuse `physics/`, `inversion/` and `data/`, do not copy them.
3. Register it; add `configs/experiments/<name>.yaml` and, if tuned, `<name>.search.yaml`.
4. `bin/check` (contract tests run automatically).
5. `nox-ml run` on nov–dec 2023 and paste the `compare` row in the PR description.

## 10. Ensembles

An ensemble is a `Model` of the registry (`role: model`) that wraps its base models, so it runs, tunes and compares like any other and must pass section 8. It is registered as `convex_ensemble` (ADR 0007). The base models are declared in its `params` as experiment configs:

```yaml
model:
  name: convex_ensemble
  params:
    members:                      # two or more base models (role "model", not ensembles)
      - {name: inversion_plume, params: {bootstrap_n: 200}}
      - {name: regularized_ls}
    weights: [0.5, 0.5]           # convex (>= 0, sum 1) or null: equal weights, the simple average
```

Each member's `params` is stored with every default filled in, so `config.yaml` records exactly what was combined. `fit(exclude_stations=...)` passes the exclusion to every member.

**Predictions** are the weighted mean of the members' predictions. Concentration is linear in emission, so this is the same combination of their emissions.

**Emissions** follow one rule (`nox_ml.models.ensemble`):

| Members | Estimate | How |
|---|---|---|
| All absolute and the same `transport_key()` | `absolute` (t/yr) | weighted mean of the means; sd of the mixture (disagreement between members adds to the sd) |
| Anything else: another transport, or a relative member | `relative`, pooled over zones | each member reduced to its index over the weekday, then weighted mean of index, `lo` and `hi` |

Members with different transports differ by 25–40 % in absolute level, and that difference is not an error of one of them, so averaging their tonnes would invent a level. The index over the weekday is what they share. Zones are not resolved in the relative case (ADR 0006).

### Learning the weights without refitting

`nox_ml.validation.stacking` learns the weights from the `oof.parquet` of the base runs and the observed station NOx (`loo.station_rows`). The weights used to evaluate station *s* are learned on the other stations only, and are >= 0 and sum to 1:

```python
from nox_ml.validation import stacking

oof = {name: pd.read_parquet(f"runs/{name}/oof.parquet") for name in ("inversion_puff", "rf_deweather")}
combined, weights = stacking.nested_oof(
    observed, oof, rule="stack"
)  # out-of-fold ensemble, one weight row per station
frozen = stacking.fit_weights(observed, oof, rule="stack")  # weights on all stations, for the final config
```

- `rule="stack"`: least squares on the simplex (stacking, X5).
- `rule="likelihood"`: weights proportional to the Gaussian likelihood of the held-out rows (Bayesian model averaging, X6). Hours of one station are correlated, so it concentrates on the best model faster than the data justify.

`nested_oof` gives the ensemble's out-of-fold RMSE (`stacking.loo_rmse`) for the nov–dec 2023 table without refitting any base model. The weights of the final ensemble (`frozen`) go into the `weights` of its config before `evaluate`. One leak remains and is documented in ADR 0007.

### `pinn_seeds` (X3)

A subclass of `ConvexEnsemble` (`nox_ml.models.pinn.seeds`): E5b (`base`, an experiment config; default: `configs/experiments/pinn_puff.yaml`) once per network seed in `seeds` (default `[0, 1, 2, 3]`; 0 is the bundled network), equal weights. Its aim is the uncertainty of the network, not a lower error.

- **Emissions are absolute.** The members' `transport_key()` differ (the key holds the network), but they are the same physics, so `shares_absolute_level` is true when the members differ only in `seed`. The sd is that of the mixture: the variance between networks adds to the one within each.
- **Cache.** `seeds` is validated against `MAX_CACHED_TRANSPORTS` (16, `nox_ml.data.inputs`): with more members than slots every fold would evict and rebuild the Jacobians (~11 min per member). New networks are trained once (~3 min) and stored in `kernel_dir`.
- **Cost.** The sum of its members: ~1.5-2 h in nov–dec 2023 with 4 seeds.

### Tests

`convex_ensemble` is in `REGISTRY`, so `test_contract` runs on it. `tests/models/test_ensemble.py` covers members, convex weights and the emission rule; `tests/test_stacking.py` covers convex weights and that a station never sets its own; `tests/test_evaluate.py` covers the test-period mode. `tests/models/test_pinn_seeds.py` covers `pinn_seeds`; `test_contract` runs it with tiny networks (same class, small defaults) so that it trains in seconds.
