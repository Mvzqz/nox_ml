"""More confidence in switchback designs: calibration of E7 + satellite, carryover and washout, fewer
measure days, and the correlation of the leftover drift between years.

Extends `simulate.py` (same designs, same per-day sums of `daily_sums.py`). A carryover profile gives each
control day a share of the drop by the calendar days since the last measure day; a washout drops from the
control the days within `wash` days after a measure day.

Usage (from the repo root), one test at a time:
    uv run python notebooks/exploraciones/switchback/confidence.py SUMS OUT calibration|carry|fewer|years
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import simulate as sim

SEED = 23
REPS = 3000
# name: (share by days since last measure day as (upto_days, share) steps, washout days)
SCENARIOS: dict[str, tuple[tuple[tuple[int, float], ...], int]] = {
    "none": ((), 0),
    "carry25": (((7, 0.25),), 0),
    "carry50": (((7, 0.5),), 0),
    "carry75": (((7, 0.75),), 0),
    "wash7_carry50": (((7, 0.5),), 7),
    "wash7_tail25": (((7, 0.5), (14, 0.25)), 7),
    "wash14_tail25": (((7, 0.5), (14, 0.25)), 14),
}


def days_since(days: pd.DatetimeIndex, masks: np.ndarray) -> np.ndarray:
    """Calendar days since the last measure day strictly before each day (large if none)."""
    ordinal = sim.day_numbers(days)
    out = np.empty(masks.shape, np.int64)
    for r, mask in enumerate(masks):
        last = np.maximum.accumulate(np.where(mask, ordinal, -10_000))
        out[r] = ordinal - np.concatenate([[-10_000], last[:-1]])
    return out


def carry_and_use(days: pd.DatetimeIndex, masks: np.ndarray, scenario: str) -> tuple[np.ndarray, np.ndarray]:
    """Share of the drop received by each control day, and the control days that are used (after washout)."""
    steps, wash = SCENARIOS[scenario]
    since = days_since(days, masks)
    share = np.zeros(masks.shape)
    previous = 0
    for upto, value in steps:
        share = np.where((since > previous) & (since <= upto), value, share)
        previous = upto
    share = np.where(masks, 0.0, share)
    use = ~masks & ~(since <= wash) if wash else ~masks
    return share, use


def ratios(
    table: pd.DataFrame, masks: np.ndarray, drop: float, share: np.ndarray, use: np.ndarray, estimator: str
) -> np.ndarray:
    """As `simulate.ratios`, with a carryover share per day and a mask of the control days used."""
    obs, model, point = (table[c].to_numpy(float) for c in ("obs", "model", "point"))
    effect = masks * drop + share * drop
    injected = (1 - effect) * obs - effect * point
    t, c = masks, use
    e7 = ((injected * t).sum(1) / (model * t).sum(1)) / ((injected * c).sum(1) / (model * c).sum(1))
    if estimator == "e7":
        return e7
    sat = table["sat"].to_numpy(float)
    seen = np.isfinite(sat)
    value = np.where(seen, (1 - effect) * np.nan_to_num(sat), 0.0)
    satellite = ((value * t).sum(1) / (seen * t).sum(1)) / ((value * c).sum(1) / (seen * c).sum(1))
    return np.sqrt(e7 * satellite)


def draw(days: pd.DatetimeIndex, design: sim.Design, rng: np.random.Generator, reps: int) -> np.ndarray:
    masks = np.array([design(days, rng) for _ in range(reps)])
    return masks[masks.any(1) & (~masks).any(1)]


def evaluate(
    table: pd.DataFrame,
    design: sim.Design,
    rng: np.random.Generator,
    estimator: str,
    scenario: str,
    reps: int = REPS,
    drops: tuple[float, ...] = (0.0, 0.10, 0.20),
) -> list[dict]:
    """Placebo of the design (with its washout, no injection), then minimum detectable drop, detection and
    coverage of the range with the injection and the carryover of the scenario."""
    days = pd.DatetimeIndex(pd.to_datetime(table["day"]))
    masks = draw(days, design, rng, reps)
    _, use = carry_and_use(days, masks, scenario)
    keep = use.any(1)
    masks, use = masks[keep], use[keep]
    null = ratios(table, masks, 0.0, np.zeros(masks.shape), use, estimator)
    _, lo, hi = sim.bounds(null)
    masks = draw(days, design, rng, reps)
    share, use = carry_and_use(days, masks, scenario)
    keep = use.any(1)
    masks, share, use = masks[keep], share[keep], use[keep]
    power = np.array([(ratios(table, masks, d, share, use, estimator) < lo).mean() for d in sim.GRID])
    reached = np.flatnonzero(power >= sim.POWER)
    row = {
        "mdd": float(sim.GRID[reached[0]]) if reached.size else np.nan,
        "k_mean": float(masks.sum(1).mean()),
        "c_mean": float(use.sum(1).mean()),
        "sd_log": float(np.std(np.log(null), ddof=1)),
    }
    out = []
    for d in drops:
        r = ratios(table, masks, d, share, use, estimator)
        out.append(
            {
                **row,
                "drop": d,
                "detected": float((r < lo).mean()),
                "coverage": float(((r / hi - 1 <= -d) & (-d <= r / lo - 1)).mean()),
            }
        )
    return out


def load(sums: Path) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_csv(p) for p in sorted(sums.glob("*.csv"))}


def pick(*names: str) -> dict[str, sim.Design]:
    return {k: v for k, v in sim.DESIGNS.items() if k in names}


def calibration(sums: Path, out: Path) -> None:
    """E7 and E7 + satellite with their own placebo: coverage and false alarms, with and without carryover."""
    rng = np.random.default_rng(SEED)
    rows = []
    designs = pick("b_alternate_days", "c_alternate_weeks", "d_two_week_blocks", "e_random_days")
    for season, table in load(sums).items():
        for estimator in sim.ESTIMATORS:
            for name, design in designs.items():
                for scenario in ("none", "carry50"):
                    for r in evaluate(table, design, rng, estimator, scenario, drops=sim.DROPS):
                        rows.append(
                            {
                                "season": season,
                                "estimator": estimator,
                                "design": name,
                                "scenario": scenario,
                                **r,
                            }
                        )
        print(season, flush=True)
    pd.DataFrame(rows).to_csv(out / "calibration.csv", index=False)


def triple_weeks(days: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Calendar weeks in triples; one week of each triple, drawn at random, carries the measure. With a
    washout of a week, the week after it is dropped from the control: about one week in three each of
    measure, washout and control."""
    units = sim._calendar_units(days, 7, rng)
    triples = units // 3
    pick_week = rng.integers(0, 3, triples.max() + 1)
    return units % 3 == pick_week[triples]


def carry(sums: Path, out: Path) -> None:
    """Minimum detectable drop under other carryovers and with washout."""
    rng = np.random.default_rng(SEED + 1)
    rows = []
    designs = pick("b_alternate_days", "c_alternate_weeks", "d_two_week_blocks")
    designs["g_triple_weeks"] = triple_weeks
    for season, table in load(sums).items():
        for estimator in sim.ESTIMATORS:
            for name, design in designs.items():
                for scenario in SCENARIOS:
                    if name == "b_alternate_days" and scenario.startswith("wash"):
                        continue  # a week of washout leaves no control days between alternate days
                    if name == "g_triple_weeks" and scenario in ("carry25", "carry75"):
                        continue
                    for r in evaluate(table, design, rng, estimator, scenario, drops=(0.0, 0.20)):
                        rows.append(
                            {
                                "season": season,
                                "estimator": estimator,
                                "design": name,
                                "scenario": scenario,
                                **r,
                            }
                        )
        print(season, flush=True)
    pd.DataFrame(rows).to_csv(out / "carry.csv", index=False)


def fewer(sums: Path, out: Path) -> None:
    """Pilots of N normal business days (about half with the measure), in windows spread over each season."""
    rng = np.random.default_rng(SEED + 2)
    rows = []
    designs = pick("b_alternate_days", "c_alternate_weeks", "e_random_days")
    for season, table in load(sums).items():
        for n in (14, 18, 24, 30, 40):
            if n > len(table):
                continue
            for start in sorted({int(s) for s in np.linspace(0, len(table) - n, 3)}):
                window = table.iloc[start : start + n].reset_index(drop=True)
                for estimator in sim.ESTIMATORS:
                    for name, design in designs.items():
                        for scenario in ("none", "carry50"):
                            r = evaluate(window, design, rng, estimator, scenario, reps=1500, drops=(0.0,))[0]
                            rows.append(
                                {"season": season, "n": n, "start": start, "estimator": estimator,
                                 "design": name, "scenario": scenario, **r}
                            )  # fmt: skip
        print(season, flush=True)
    pd.DataFrame(rows).to_csv(out / "fewer.csv", index=False)


def years(sums: Path, out: Path) -> None:
    """Drift left across years. The same calendar assignment (pairs of calendar units counted from the
    season start) is applied to every season; the log ratios are correlated across seasons of the same
    calendar window, and the combination of the six seasons is compared with its independent-years error."""
    rng = np.random.default_rng(SEED + 3)
    tables = load(sums)
    starts = {"nd": "11-01", "fm": "02-15"}
    lengths = {"alternate_days": 1, "alternate_weeks": 7, "two_week_blocks": 14}
    rows = []
    for estimator in sim.ESTIMATORS:
        for design, length in lengths.items():
            logs: dict[str, list[float]] = {s: [] for s in tables}
            for _ in range(REPS):
                first = rng.integers(0, 2, 200).astype(bool)
                offset = rng.integers(0, length)
                for season, table in tables.items():
                    days = pd.DatetimeIndex(pd.to_datetime(table["day"]))
                    begin = pd.Timestamp(f"{days[0].year}-{starts[season[:2]]}")
                    units = ((days - begin).days.to_numpy() + offset) // length
                    mask = np.where(units % 2 == 0, first[units // 2], ~first[units // 2])[None]
                    if not mask.any() or mask.all():
                        logs[season].append(np.nan)
                        continue
                    ratio = ratios(table, mask, 0.0, np.zeros(mask.shape), ~mask, estimator)[0]
                    logs[season].append(float(np.log(ratio)))
            frame = pd.DataFrame(logs).dropna()
            for a in frame:
                for b in frame:
                    if a < b and a[:2] == b[:2]:
                        rows.append({"estimator": estimator, "design": design, "pair": f"{a}-{b}",
                                     "value": float(frame[a].corr(frame[b]))})  # fmt: skip
            sd = frame.std(ddof=1)
            weight = sd**-2 / (sd**-2).sum()
            rows.append({"estimator": estimator, "design": design, "pair": "sd_independent",
                         "value": float(np.sum(sd**-2) ** -0.5)})  # fmt: skip
            rows.append({"estimator": estimator, "design": design, "pair": "sd_shared_assignment",
                         "value": float((frame * weight).sum(axis=1).std(ddof=1))})  # fmt: skip
        print(estimator, flush=True)
    pd.DataFrame(rows).to_csv(out / "years.csv", index=False)


if __name__ == "__main__":
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    tests = {"calibration": calibration, "carry": carry, "fewer": fewer, "years": years}
    tests[sys.argv[3]](Path(sys.argv[1]), out_dir)
