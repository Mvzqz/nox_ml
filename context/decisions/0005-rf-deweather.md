# 0005. Random forest deweathering as a relative model

- **Date:** 2026-10-25
- **Status:** accepted

## Context

The meteorological normalization of the air quality literature (rmweather) fits a random forest of concentration on meteorology and calendar, and reads the effect of a calendar variable with the weather held fixed. The project needs one such model next to the inversions: it gives only changes (no tonnes), but it does not depend on a transport model.

## Decision

- **`rf_deweather` is a `Model` of the registry** (ADR 0003) with a `relative` `EmissionEstimate`: the index of each day type over the weekday, pooled over zones (`zone` null). Zones are not resolved because a station responds to the emissions upwind of it, from several zones at once.
- **Deweathering as in rmweather.** Each fitted row keeps its calendar (hour, day of year, day type, station) and takes the weather of 20 rows drawn from the whole period (the five weather features together, so their correlations hold); the forest's prediction averaged over the draws is the row's deweathered NOx. The index of a day type is the weighted mean of those over its rows, relative to the weekday. Changing only the day-type column of every row was tried first and discarded: with few rows the trees rarely split on it and the index fell towards 1.
- **Log scale.** The forest learns the log of the NOx above a 5 ppb background (the baseline's prior; floored at 1 ppb) and the index is a ratio of geometric means. On raw ppb the stagnant hours dominate the splits and the effect of the day type on the rest is attenuated towards 1 (a Sunday emitting half came out at 0.65 to 0.8). Predictions in ppb are back-transformed with Duan's smearing factor from the out-of-bag residuals.
- **Features** are listed with their reason in the docstring of `nox_ml.models.rf_deweather`: hour and day of year as sin/cos, ventilation (speed times boundary layer height) and its sum over the previous 3 and 6 hours, wind direction as sin/cos, day type and station as one-hot.
- **Intervals** come from refitting on days drawn with replacement (`sample_weight`), the same unit of resampling as the inversion's bootstrap.
- **Contract tests use their own synthetic stations.** The fixture of the other models has two Sundays and wind directions that decide the plume: the forest fingerprints those 12 hours by their wind instead of separating the day type from it. `test_contract` gives the models that learn from the weather (`LEARN_FROM_WEATHER`) eight weeks of stations whose NOx is emission over ventilation (`ventilation_synthetic`), with a known Sunday ratio.

## Consequences

- The index of a forest is still attenuated a little towards 1 when data are few (a Sunday emitting 0.46 comes out at about 0.5 on 8 weeks of three stations). Report it with its interval and its placebo.
- A day type and a weather regime that never overlap cannot be separated by any model; the forest then returns an index near 1 (no overlap, no information).
- A fit costs seconds and every `estimate_emissions` refits `bootstrap_n` forests; the placebo (8 refits) dominates a run.
