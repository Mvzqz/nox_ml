"""Switchback designs for E7: minimum detectable drop, false alarms and range coverage.

Reads the per-day sums of `daily_sums.py` and, for each season and design, draws many random realizations
of which normal business days carry the measure (about half of them). The ratio of E7 for a realization is
(sum obs / sum model) of the measure days over the rest. A drop d is injected as in `events.inject_drop`:
obs -> (1 - d) obs - d point on the measure days, and on the control days with carryover (half the effect in
the week after a measure day).

The uncertainty is the placebo of the same design: the spread of the ratio over random realizations of the
design without injection (no bootstrap). A drop is detected when the ratio falls below the lower bound of
that spread, widened as in the sheets (`products.RANGE_WIDENING`). The range of a realization is
(ratio / hi - 1, ratio / lo - 1): the ratio is the true one times a placebo draw. (`products.measure_result`
writes ratio * center / hi; the same when the placebo is centered on 1, as with random days, but not for
days in a row, whose placebo center moves with the drift of the season.)

Usage (from the repo root):
    uv run python notebooks/exploraciones/switchback/simulate.py SUMS_DIR OUT_DIR [--verify]
"""

import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 11
REPS = 4000  # realizations per design (null and injected draws are independent)
BOOT = 200  # day bootstrap resamples, for the comparison with the placebo
LEVEL = 0.90
POWER = 0.80
WIDENING = 1.05  # products.RANGE_WIDENING
DROPS = (0.0, 0.05, 0.10, 0.15, 0.20)
GRID = np.round(np.arange(0.0, 0.71, 0.01), 2)  # drops searched for the minimum detectable
CARRY_SHARE = 0.5
CARRY_DAYS = 7

Design = Callable[[pd.DatetimeIndex, np.random.Generator], np.ndarray]


def day_numbers(days: pd.DatetimeIndex) -> np.ndarray:
    """Calendar days since the first day."""
    ordinal = days.to_numpy().astype("datetime64[D]").astype(np.int64)
    return ordinal - ordinal[0]


def contiguous(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Half the normal days in a row (before and after are the control), at a random start."""
    n, k = len(days), len(days) // 2
    start = rng.integers(0, n - k + 1)
    mask = np.zeros(n, bool)
    mask[start : start + k] = True
    return mask


def _paired_units(units: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One unit of each consecutive pair of units (0-1, 2-3, ...) carries the measure, at random. A lone
    last unit is drawn with probability one half."""
    pairs = units // 2
    first = rng.integers(0, 2, pairs.max() + 1).astype(bool)
    return np.where(units % 2 == 0, first[pairs], ~first[pairs])


def alternate_days(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Consecutive normal days in pairs; one of each pair, drawn at random."""
    return _paired_units(np.arange(len(days)), rng)


def _calendar_units(days: pd.DatetimeIndex, length: int, rng: np.random.Generator) -> np.ndarray:
    """Index of the `length`-day calendar unit of each day, with the boundary at a random offset."""
    offset = rng.integers(0, length)
    elapsed = day_numbers(days) + offset
    return elapsed // length


def alternate_weeks(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Calendar weeks in pairs; one week of each pair, drawn at random."""
    return _paired_units(_calendar_units(days, 7, rng), rng)


def two_week_blocks(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Blocks of two calendar weeks in pairs; one block of each pair, drawn at random."""
    return _paired_units(_calendar_units(days, 14, rng), rng)


def random_days(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Half the normal days, drawn at random (the placebo of the sheets)."""
    mask = np.zeros(len(days), bool)
    mask[rng.choice(len(days), len(days) // 2, replace=False)] = True
    return mask


def random_weeks(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Half the calendar weeks, drawn at random."""
    units = _calendar_units(days, 7, rng)
    weeks = np.unique(units)
    chosen = rng.choice(weeks, len(weeks) // 2, replace=False)
    return np.isin(units, chosen)


DESIGNS: dict[str, Design] = {
    "a_contiguous": contiguous,
    "b_alternate_days": alternate_days,
    "c_alternate_weeks": alternate_weeks,
    "d_two_week_blocks": two_week_blocks,
    "e_random_days": random_days,
    "f_random_weeks": random_weeks,
}


def carryover(days: pd.DatetimeIndex, masks: np.ndarray) -> np.ndarray:
    """Control days whose last measure day is at most `CARRY_DAYS` calendar days before them."""
    ordinal = day_numbers(days)
    out = np.zeros_like(masks)
    for r, mask in enumerate(masks):
        last = np.maximum.accumulate(np.where(mask, ordinal, -10_000))
        before = np.concatenate([[-10_000], last[:-1]])
        out[r] = ~mask & (ordinal - before <= CARRY_DAYS)
    return out


def ratios(table: pd.DataFrame, masks: np.ndarray, drop: float, carry: np.ndarray | None) -> np.ndarray:
    """E7 ratio (measure over control) of each realization, with `drop` injected."""
    obs, model, point = (table[c].to_numpy(float) for c in ("obs", "model", "point"))
    effect = masks * drop
    if carry is not None:
        effect = effect + carry * drop * CARRY_SHARE
    injected = (1 - effect) * obs - effect * point
    t, c = masks, ~masks
    num = (injected * t).sum(1) / (model * t).sum(1)
    den = (injected * c).sum(1) / (model * c).sum(1)
    return num / den


def draw(days: pd.DatetimeIndex, design: Design, rng: np.random.Generator) -> np.ndarray:
    masks = np.array([design(days, rng) for _ in range(REPS)])
    keep = masks.any(1) & (~masks).any(1)
    return masks[keep]


def bounds(null: np.ndarray) -> tuple[float, float, float]:
    """Center and widened lower and upper bound of the placebo of a design."""
    center = float(np.median(null))
    lo, hi = np.quantile(null, [(1 - LEVEL) / 2, (1 + LEVEL) / 2])
    return center, center * (lo / center) ** WIDENING, center * (hi / center) ** WIDENING


def bootstrap_coverage(table: pd.DataFrame, masks: np.ndarray, rng: np.random.Generator) -> float:
    """Share of realizations without injection whose 90 % day bootstrap (E7's own interval: days resampled
    with replacement within each group) contains 1. Uses the first 500 realizations."""
    obs, model = table["obs"].to_numpy(float), table["model"].to_numpy(float)
    hits = []
    for mask in masks[:500]:
        t, c = np.flatnonzero(mask), np.flatnonzero(~mask)
        bt = rng.choice(t, (BOOT, len(t)))
        bc = rng.choice(c, (BOOT, len(c)))
        r = (obs[bt].sum(1) / model[bt].sum(1)) / (obs[bc].sum(1) / model[bc].sum(1))
        lo, hi = np.quantile(r, [(1 - LEVEL) / 2, (1 + LEVEL) / 2])
        hits.append(lo <= 1 <= hi)
    return float(np.mean(hits))


def evaluate(table: pd.DataFrame, design: Design, rng: np.random.Generator) -> list[dict]:
    days = pd.DatetimeIndex(pd.to_datetime(table["day"]))
    null_masks = draw(days, design, rng)
    center, lo, hi = bounds(ratios(table, null_masks, 0.0, None))
    sd_log = float(np.std(np.log(ratios(table, null_masks, 0.0, None)), ddof=1))
    masks = draw(days, design, rng)
    carry = carryover(days, masks)
    k = float(masks.sum(1).mean())
    rows = []
    for name, c in (("none", None), ("carry50", carry)):
        power = np.array([(ratios(table, masks, d, c) < lo).mean() for d in GRID])
        reached = np.flatnonzero(power >= POWER)
        mdd = float(GRID[reached[0]]) if reached.size else np.nan
        for d in DROPS:
            r = ratios(table, masks, d, c)
            low, high = r / hi - 1, r / lo - 1  # true ratio = r / placebo draw
            rows.append(
                {
                    "carryover": name,
                    "drop": d,
                    "k_mean": k,
                    "n_days": len(days),
                    "sd_log": sd_log,
                    "placebo_center": center,
                    "placebo_lo": lo,
                    "placebo_hi": hi,
                    "detected": float((r < lo).mean()),
                    "increase": float((r > hi).mean()),
                    "coverage": float(((low <= -d) & (-d <= high)).mean()),
                    "mean_recovered": float(1 - np.median(r) / center),
                    "mdd": mdd,
                }
            )
    rows[0]["boot_coverage0"] = bootstrap_coverage(table, null_masks, rng)
    return rows


def verify(sums: Path) -> None:
    """The per-day shortcut against E7 itself on one realization with an injected drop."""
    from daily_sums import DATA, SEASONS

    from nox_ml.validation import events, products

    table = pd.read_csv(sums / "nd2024.csv", parse_dates=["day"])
    days = pd.DatetimeIndex(table["day"])
    mask = alternate_weeks(days, np.random.default_rng(0))
    start, end = SEASONS["nd2024"]
    inputs = products.season_inputs(DATA, start, end, products.sources_for(start, end))
    injected = events.inject_drop(inputs, days[mask], 0.15).on_days(days)
    full, _ = events._fit_ratio(injected, products.estimator("change"), days[mask])
    fast = ratios(table, mask[None], 0.15, None)[0]
    print(f"E7 {full:.6f}  per-day sums {fast:.6f}")


def main(sums: Path, out: Path) -> None:
    rng = np.random.default_rng(SEED)
    rows = []
    for path in sorted(sums.glob("*.csv")):
        table = pd.read_csv(path)
        for name, design in DESIGNS.items():
            for row in evaluate(table, design, rng):
                rows.append({"season": path.stem, "design": name, **row})
            print(path.stem, name, flush=True)
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out / "switchback.csv", index=False)
    summary = frame[frame["drop"] == 0.0].pivot_table(
        index="design", columns=["carryover", "season"], values="mdd"
    )
    print(summary.round(2).to_string())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    if "--verify" in sys.argv:
        verify(Path(sys.argv[1]))
    else:
        main(Path(sys.argv[1]), Path(sys.argv[2]))
