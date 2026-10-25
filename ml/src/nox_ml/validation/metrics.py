"""The flat summary every run stores in ``metrics.json`` under ``summary`` and ``nox-ml compare`` reads."""

from pydantic import BaseModel, ConfigDict

TRAFFIC_SUNDAY_RATIO = (0.65, 0.73)  # Sunday over weekday from traffic counts
PLACEBO_TOLERANCE = 0.15  # eligibility gate: placebo_center within 1 +- this


def gap_to_range(value: float, bounds: tuple[float, float] = TRAFFIC_SUNDAY_RATIO) -> float:
    """Distance from `value` to the interval `bounds` (0 inside)."""
    return max(bounds[0] - value, value - bounds[1], 0.0)


class RunMetrics(BaseModel):
    """Emission fields are null for references, never invented."""

    model_config = ConfigDict(extra="forbid")

    model: str
    role: str
    loo_rmse_ppb: float
    loo_bias_ppb: float
    loo_hourly_rmse_ppb: float
    r_tempo: float | None
    sunday_ratio: float | None
    sunday_ratio_lo: float | None
    sunday_ratio_hi: float | None
    sunday_ratio_gap: float | None
    placebo_center: float | None
    placebo_halfwidth: float | None
    eligible: bool | None  # placebo gate; null for references
    fit_seconds: float
    predict_seconds: float
    n_params: int
