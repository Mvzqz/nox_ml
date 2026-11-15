"""Validation of `nox-ml episode` (`nox_ml.validation.episodes`) on episodes of known cause (F3).

Reads the daily tables of `prepare.py`, chooses the episodes without looking at NOx (`choose`), writes them
with their criterion to ``episodios.csv``, runs `diagnose_episode` on each one (the same null intervals and
verdict as the command) and adds a prudent verdict that never claims emission (`prudent`). Writes
``resultados.csv`` (one row per episode) and ``aciertos.csv`` (rates by type) next to this file.

Usage: uv run python notebooks/exploraciones/episodes/validate.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data import calendar, contingencies
from nox_ml.inversion.linear import HOLIDAYS
from nox_ml.validation.episodes import diagnose_episode

DATA = Path("data")
CACHE = Path("runs/episode_validation")
HERE = Path(__file__).parent
SEED = 0

TEMPO_SEASONS = ("nd2023", "fm2024", "nd2024", "fm2025", "nd2025", "fm2026")
# weather weeks per extreme: nov-dec has ~5 eligible weeks before the year-end, feb-may ~12
N_WEATHER = {
    "nd2023": 1,
    "nd2024": 1,
    "nd2025": 1,
    "fm2024": 2,
    "fm2025": 2,
    "fm2026": 2,
    "fm2019": 2,
    "fm2020": 0,
}
LOCKDOWN = pd.date_range("2020-03-23", "2020-05-31")  # schools closed on 23 March (Hernandez-Paniagua 2021)
HOLIDAY_DAYS = pd.DatetimeIndex(HOLIDAYS)
MIN_NULL = 100  # fake episodes a null interval needs to be read

# expected cause of each type: what a right diagnosis says
EXPECTED = {
    "estancada": "weather_up",
    "ventilada": "weather_down",
    "festivo": "emission_down",
    "semana_santa": "emission_down",
    "confinamiento": "emission_down",
    "placebo_2019": "none",
    "fin_de_anio": "accumulation",
    "fondo_alto": "accumulation",
    "contingencia": "unknown",
}


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(CACHE / f"days_{name}.parquet")


def contingency_episodes() -> pd.DataFrame:
    return contingencies.read_episodes(DATA / "raw" / contingencies.EPISODES_FILE)


def unusual_days(d: pd.DataFrame) -> pd.DatetimeIndex:
    """Days that are no normal reference: atypical periods, contingencies, holidays and the 2020 lockdown."""
    days = pd.DatetimeIndex(d.index)
    bad = calendar.atypical_days(days.min(), days.max())
    return bad.union(contingencies.active_days(contingency_episodes())).union(HOLIDAY_DAYS).union(LOCKDOWN)


def business_weeks(d: pd.DataFrame) -> list[pd.DatetimeIndex]:
    """Monday-to-Friday weeks with no unusual day and at least four days with data."""
    bad = unusual_days(d)
    days = pd.DatetimeIndex(d.index)
    weeks = []
    for monday in days[days.dayofweek == 0]:
        week = pd.date_range(monday, periods=5)
        if not week.isin(bad).any() and week.isin(days).sum() >= 4:
            weeks.append(week[week.isin(days)])
    return weeks


def week_rows(season: str, d: pd.DataFrame) -> list[dict]:
    """The most stagnant and most ventilated weeks by the afternoon ventilation coefficient (boundary layer
    times wind speed) and, with TEMPO, the week with the highest regional background not chosen already."""
    weeks = business_weeks(d)
    vc = pd.Series([d.loc[w, "vc"].mean() for w in weeks])
    n = N_WEATHER[season]
    rows, used = [], set()
    for kind, order in (("estancada", vc.sort_values().index), ("ventilada", vc.sort_values()[::-1].index)):
        for rank, i in enumerate(order[:n]):
            used.add(i)
            rows.append(
                {
                    "type": kind,
                    "days": weeks[i],
                    "criterion": f"rank {rank + 1} of {len(weeks)} weeks by ventilation "
                    f"(PBL x wind, {vc[i]:.0f} m2/s; season median {vc.median():.0f})",
                }
            )
    if d["background"].notna().any():
        bg = pd.Series([d.loc[w, "background"].mean() for w in weeks]).drop(list(used))
        i = bg.idxmax()
        rows.append(
            {
                "type": "fondo_alto",
                "days": weeks[i],
                "criterion": f"highest TEMPO regional background of {len(weeks)} weeks "
                f"({bg[i]:.2e} vs median {bg.median():.2e}), not a weather week",
            }
        )
    return rows


def calendar_rows(season: str, d: pd.DataFrame) -> list[dict]:
    days = pd.DatetimeIndex(d.index)
    first, last = days.min(), days.max()
    rows = []
    atypical = calendar.atypical_days(first, last)
    for day in HOLIDAY_DAYS[(first <= HOLIDAY_DAYS) & (last >= HOLIDAY_DAYS)]:
        if day.dayofweek < 5 and day not in atypical and day not in LOCKDOWN and day in days:
            rows.append({"type": "festivo", "days": pd.DatetimeIndex([day]), "criterion": "official holiday"})
    easter = calendar.easter_holidays(first.year)
    if season != "fm2020" and easter.min() >= first:
        business = easter[(easter.dayofweek < 5) & ~easter.isin(HOLIDAY_DAYS) & easter.isin(days)]
        rows.append(
            {
                "type": "semana_santa",
                "days": business,
                "criterion": "business days of Holy Week and the week after (school holidays)",
            }
        )
    for year in (first.year - 1, first.year):
        for lo, hi, what in ((16, 23, "before Christmas"), (24, 31, "Christmas to New Year")):
            span = pd.date_range(f"{year}-12-{lo}", f"{year}-12-{hi}")
            span = span[(span.dayofweek < 5) & ~span.isin(HOLIDAY_DAYS) & span.isin(days)]
            if len(span):
                rows.append({"type": "fin_de_anio", "days": span, "criterion": f"business days {what}"})
    if season in ("fm2019", "fm2020"):
        # the 2019 placebo: the same weeks, 52 weeks earlier (same weekdays)
        shift = pd.Timedelta(days=0 if season == "fm2020" else 364)
        kind = "confinamiento" if season == "fm2020" else "placebo_2019"
        for lo in ("2020-03-23", "2020-03-30"):
            span = pd.date_range(pd.Timestamp(lo) - shift, periods=5)
            rows.append({"type": kind, "days": span, "criterion": "first lockdown weeks (2019: same weeks)"})
    if season in TEMPO_SEASONS:
        for row in contingency_episodes().itertuples():
            span = pd.date_range(row.activation, row.suspension)
            if span.isin(days).any():
                rows.append(
                    {"type": "contingencia", "days": span, "criterion": f"ozone contingency {row.episode}"}
                )
    return rows


def choose() -> dict[str, list[dict]]:
    return {
        s: week_rows(s, load(s)) + calendar_rows(s, load(s)) for s in (*TEMPO_SEASONS, "fm2019", "fm2020")
    }


def as_weekday(d: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """A copy of `d` where the episode `days` keep their own weekday (a holiday is otherwise a Sunday), so a
    holiday is compared with normal days of its weekday."""
    out = d.copy()
    out.loc[days, "weekday"] = days.dayofweek
    return out


def prudent(ratios: dict, null: dict) -> tuple[str, bool]:
    """``explica``, ``en_parte``, ``no_explica`` or ``normal`` (the concentration is usual), and whether the
    regional background rose; never a claim about the emission. Fixed before running the validation.

    The weather explains the episode when its ratio is unusual in the direction of the concentration; in part
    when the emission ratio is unusual in that direction too; it does not explain it otherwise."""

    def side(name: str) -> int:
        value, lo, hi = ratios[name], null[name]["lo"], null[name]["hi"]
        if not np.isfinite(value) or lo <= value <= hi:
            return 0
        return 1 if value > hi else -1

    background_up = side("background") > 0
    c = side("concentration")
    if c == 0:
        return "normal", background_up
    if side("weather") == c:
        return ("en_parte" if side("emission") == c else "explica"), background_up
    return "no_explica", background_up


def diagnose(season: str, row: dict) -> dict:
    d = load(season)
    days = row["days"]
    excluded = unusual_days(d).difference(days)
    if row["type"] == "festivo":
        d = as_weekday(d, days)
    tempo = d[["background", "urban"]]
    out = {"season": season, "type": row["type"], "start": days.min().date(), "end": days.max().date()}
    out |= {"n_days": len(days), "criterion": row["criterion"]}
    try:
        result = diagnose_episode(d, tempo, days, excluded, seed=SEED)
    except ValueError as error:
        return out | {"verdict": "no_evaluable", "notes": str(error)}
    for name, value in result["ratios"].items():
        null = result["null"][name]
        out |= {name: value, f"{name}_lo": null["lo"], f"{name}_hi": null["hi"]}
    n_null = min(result["null"][k]["n"] for k in ("concentration", "weather", "emission"))
    label = result["detail"]["verdict"] if n_null >= MIN_NULL else "no_evaluable"
    careful, background_up = prudent(result["ratios"], result["null"])
    return out | {
        "verdict": label,
        "notes": ";".join(result["detail"]["notes"]),
        "prudent": careful if label != "no_evaluable" else "no_evaluable",
        "background_up": background_up,
        "n_null": n_null,
    }


def score(r: pd.Series) -> pd.Series:
    """Whether the weather part is right, whether the emission is falsely claimed (original verdict) and the
    same two with the prudent verdict, for the expected cause of the episode type."""
    expected, v, p = EXPECTED[r.type], r.verdict, r.prudent
    if v == "no_evaluable" or expected in ("unknown",):
        return pd.Series({"weather_ok": np.nan, "fp": np.nan, "weather_ok_p": np.nan, "fp_p": np.nan})
    e_claim = v in ("emission", "both", "emission_or_accumulation")
    up = r.emission > 1
    if expected.startswith("weather"):
        direction = 1 if expected == "weather_up" else -1
        w_ok = v in ("weather", "both") and np.sign(np.log(r.weather)) == direction
        fp = e_claim
        w_ok_p = p in ("explica", "en_parte") and np.sign(np.log(r.weather)) == direction
        fp_p = p == "no_explica"
    elif expected == "emission_down":
        # the weather must not take the credit; a claimed emission rise is the false positive
        w_ok = v != "weather"
        fp = e_claim and up
        w_ok_p = p != "explica"
        fp_p = False
    elif expected == "accumulation":
        w_ok = v != "weather"
        fp = e_claim
        w_ok_p = p != "explica"
        fp_p = p == "no_explica" and not r.background_up
    else:  # placebo: nothing happened
        w_ok = v == "normal" or v == "weather"
        fp = e_claim
        w_ok_p = True
        fp_p = p == "no_explica"
    return pd.Series({"weather_ok": w_ok, "fp": fp, "weather_ok_p": w_ok_p, "fp_p": fp_p}, dtype=object)


def main() -> None:
    chosen = choose()
    episodes = pd.DataFrame(
        [
            {"season": s, "type": r["type"], "start": r["days"].min().date(), "end": r["days"].max().date()}
            | {"days": " ".join(x.strftime("%Y-%m-%d") for x in r["days"]), "criterion": r["criterion"]}
            for s, rows in chosen.items()
            for r in rows
        ]
    )
    episodes.to_csv(HERE / "episodios.csv", index=False)
    results = pd.DataFrame([diagnose(s, r) for s, rows in chosen.items() for r in rows])
    results = results.join(results.apply(score, axis=1))
    results.round(3).to_csv(HERE / "resultados.csv", index=False)
    rates = results.groupby("type").agg(
        n=("verdict", "size"),
        no_evaluable=("verdict", lambda x: int((x == "no_evaluable").sum())),
        weather_ok=("weather_ok", "mean"),
        fp=("fp", "mean"),
        weather_ok_p=("weather_ok_p", "mean"),
        fp_p=("fp_p", "mean"),
    )
    rates.round(2).to_csv(HERE / "aciertos.csv")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(rates.round(2))
        cols = ["season", "type", "start", "concentration", "weather", "emission", "background", "urban"]
        print(results[[*cols, "verdict", "notes", "prudent", "background_up"]].round(2).to_string())


if __name__ == "__main__":
    main()
