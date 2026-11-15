"""Health scenarios: deaths and child asthma cases avoided if road NOx emission fell by X %.

Chain: emission cut -> NO2 drop (empirical Sunday elasticity) -> avoided deaths / asthma cases
(log-linear risk functions) with Monte Carlo over every uncertain input.

Run: ``nice -n 10 uv run python notebooks/exploraciones/health/health_scenarios.py``
"""

import gzip
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data.calendar import atypical_days
from nox_ml.data.simat import read_zip_member
from nox_ml.inversion.linear import HOLIDAYS

RAW = Path("data/raw/simat")
OUT = Path(__file__).parent / "results"
YEARS = (2019, 2023, 2024)  # complete years with 24 h NO2
ZOCALO = (19.4326, -99.1332)
MAX_KM = 45.0
MIN_HOURS = 18
MIN_COVERAGE = 0.75
SCENARIOS = (5, 10, 20, 30)
N_DRAWS = 20000
RNG = np.random.default_rng(20260115)

# Population and baseline rates (see the note for sources and what is assumed).
POP_ZMVM = 21_804_515  # Census 2020, ZMVM (DataMexico / INEGI)
DEATHS_ALL_AGES = 143_000  # ~CDMX 78.6k + 73 % of Edomex 87.6k (INEGI EDR 2023, approximate)
ADULT_SHARE = 0.97  # deaths at ages >= 25
POP_UNDER18_SHARE = 0.27
ASTHMA_INCIDENCE = (0.0015, 0.003, 0.005)  # per child-year: low, mode, high (assumed, IHME-order)

# Risk functions: log-linear RR; (RR, lo95, hi95, unit increment)
HUANGFU = (1.02, 1.01, 1.04, 10.0)  # per 10 ug/m3, all-cause, long term (Huangfu & Atkinson, 2020)
STIEB = (1.047, 1.023, 1.072, 10.0)  # per 10 ppb, all/natural cause (Stieb et al., 2021)
ASTHMA = (1.05, 1.02, 1.07, 4.0)  # per 4 ppb, child asthma incidence (Khreis 2017; NOT verified)
ASTHMA_GBD = (1.05, 1.02, 1.08, 5.0)  # per 5 ppb, GBD 2023 (Burkart 2025; CI assumed)


def read_year(year: int) -> pd.DataFrame:
    """A SIMAT year with its local `day`; the file is a gzip or a ZIP and the header length differs.

    Stamps are hour-ending and the older years write the last hour as 24:00, so the day is built
    from the date and the hour separately (hour h in 1..24 ends at h:00 of its own day).
    """
    path = RAW / f"contaminantes_{year}.csv.gz"
    data = read_zip_member(path) if zipfile.is_zipfile(path) else gzip.decompress(path.read_bytes())
    lines = data.decode("latin1").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip('"').startswith("date"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype={"value": "float64"})
    stamp = df["date"].astype(str)
    df = df[stamp.str.contains(r"\d:\d{2}")].copy()
    stamp = df["date"].astype(str)
    hour = stamp.str.extract(r"(\d{1,2}):\d{2}")[0].astype(int)
    date = pd.to_datetime(stamp.str.extract(r"^(\S+)")[0], format="mixed")
    df["day"] = date.where(hour != 0, date - pd.Timedelta(days=1))  # 00:00 closes the previous day
    return df


def daily_no2() -> pd.DataFrame:
    """Daily mean NO2 (ppb) per station, only days with enough hours."""
    cat = pd.read_csv(RAW / "cat_estacion.csv", skiprows=1, encoding="latin1")
    dlat = (cat["latitud"] - ZOCALO[0]) * 111.0
    dlon = (cat["longitud"] - ZOCALO[1]) * 111.0 * np.cos(np.radians(ZOCALO[0]))
    near = set(cat.loc[np.hypot(dlat, dlon) <= MAX_KM, "cve_estac"])
    frames = []
    for year in YEARS:
        raw = read_year(year)
        raw = raw[(raw["id_parameter"] == "NO2") & raw["id_station"].isin(near)]
        raw = raw.dropna(subset=["value"])
        g = raw.groupby(["id_station", "day"])["value"].agg(["mean", "count"])
        frames.append(g[g["count"] >= MIN_HOURS]["mean"].rename("no2").reset_index())
    return pd.concat(frames, ignore_index=True)


def annual_means(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (st, yr), g in daily.groupby(["id_station", daily["day"].dt.year]):
        n_days = 366 if yr % 4 == 0 else 365
        if len(g) / n_days >= MIN_COVERAGE:
            rows.append((st, yr, g["no2"].mean(), len(g) / n_days))
    return pd.DataFrame(rows, columns=["station", "year", "no2_ppb", "coverage"])


def sunday_ratio(daily: pd.DataFrame, n_boot: int = 1000) -> tuple[float, float, float]:
    """Sunday / weekday (Mon-Fri) NO2 24 h ratio: pooled, bootstrap by week, atypical days out."""
    d = daily[~daily["day"].isin(pd.to_datetime(list(HOLIDAYS)))].copy()
    bad = atypical_days(d["day"].min(), d["day"].max())
    d = d[~d["day"].isin(bad) & (d["day"].dt.year != 2020)]
    # normalise each station-year so stations with high NO2 do not dominate the ratio
    d["rel"] = d["no2"] / d.groupby(["id_station", d["day"].dt.year])["no2"].transform("mean")
    d["dow"] = d["day"].dt.dayofweek
    d["week"] = (d["day"] + pd.Timedelta(days=1)).dt.to_period("W-SAT")  # Sunday starts the week
    wk = d[d["dow"].isin([0, 1, 2, 3, 4, 6])]
    sun = wk[wk["dow"] == 6].groupby("week")["rel"].mean()
    hab = wk[wk["dow"] != 6].groupby("week")["rel"].mean()
    weeks = sun.index.intersection(hab.index)
    s, h = sun[weeks].to_numpy(), hab[weeks].to_numpy()
    point = s.mean() / h.mean()
    idx = RNG.integers(0, len(weeks), (n_boot, len(weeks)))
    boot = s[idx].mean(1) / h[idx].mean(1)
    lo, hi = np.percentile(boot, [5, 95])
    return point, lo, hi


def draw_log_beta(rr: tuple[float, float, float, float], n: int) -> np.ndarray:
    """Per-unit log-risk draws from a normal fitted to the reported 95 % CI."""
    point, lo, hi, step = rr
    sd = (np.log(hi) - np.log(lo)) / (2 * 1.96)
    return RNG.normal(np.log(point), sd, n) / step


def simulate(base_ppb: float, ratio: tuple[float, float, float]) -> pd.DataFrame:
    n = N_DRAWS
    # Sunday NO2 ratio -> NO2 drop; emission drop on Sunday ~ 50 % (30-60 %)
    r = RNG.normal(ratio[0], (ratio[2] - ratio[1]) / (2 * 1.645), n)
    sunday_emis_drop = RNG.triangular(0.30, 0.50, 0.60, n)
    elasticity = np.clip((1 - r) / sunday_emis_drop, 0.05, 1.0)  # dNO2/NO2 per dE/E
    base = base_ppb * RNG.uniform(0.80, 1.0, n)  # stations over-represent roads vs. residents
    ppb_to_ug = RNG.uniform(1.47, 1.88, n)  # altitude/temperature (ZMVM) vs. 25 C, 1 atm
    deaths_base = DEATHS_ALL_AGES * ADULT_SHARE * RNG.uniform(0.9, 1.1, n)
    children = POP_ZMVM * POP_UNDER18_SHARE
    incidence = RNG.triangular(*ASTHMA_INCIDENCE, n)
    use_stieb = RNG.random(n) < 0.5
    b_h = draw_log_beta(HUANGFU, n) * ppb_to_ug  # per ppb
    b_s = draw_log_beta(STIEB, n)  # per ppb
    beta_mort = np.where(use_stieb, b_s, b_h)
    use_gbd = RNG.random(n) < 0.5
    beta_asth = np.where(use_gbd, draw_log_beta(ASTHMA_GBD, n), draw_log_beta(ASTHMA, n))
    rows = []
    for pct in SCENARIOS:
        d_no2 = base * elasticity * pct / 100.0
        deaths = deaths_base * (1 - np.exp(-beta_mort * d_no2))
        cases = children * incidence * (1 - np.exp(-beta_asth * d_no2))
        for name, x in (("dNO2_ppb", d_no2), ("deaths", deaths), ("asthma_cases", cases)):
            rows.append((pct, name, *np.percentile(x, [5, 50, 95])))
        for name, mask in (("deaths_Huangfu", ~use_stieb), ("deaths_Stieb", use_stieb)):
            rows.append((pct, name, *np.percentile(deaths[mask], [5, 50, 95])))
    rows.append((0, "elasticity", *np.percentile(elasticity, [5, 50, 95])))
    return pd.DataFrame(rows, columns=["scenario_pct", "metric", "p05", "p50", "p95"])


def attributable_burden(base_ppb: float) -> pd.DataFrame:
    """Control: deaths and asthma cases attributable to ALL NO2 above 0 (and above 10 ug/m3)."""
    n = N_DRAWS
    ppb_to_ug = RNG.uniform(1.47, 1.88, n)
    base = base_ppb * RNG.uniform(0.80, 1.0, n)
    deaths_base = DEATHS_ALL_AGES * ADULT_SHARE * RNG.uniform(0.9, 1.1, n)
    use_stieb = RNG.random(n) < 0.5
    beta = np.where(use_stieb, draw_log_beta(STIEB, n), draw_log_beta(HUANGFU, n) * ppb_to_ug)
    who = 10.0 / ppb_to_ug  # annual WHO 2021 guideline, ppb
    out = {}
    for label, cf in (("sin_umbral", 0.0), ("guia_OMS_10", who)):
        conc = np.clip(base - cf, 0, None)
        out[f"muertes_{label}"] = np.percentile(deaths_base * (1 - np.exp(-beta * conc)), [5, 50, 95])
    rate = RNG.triangular(*ASTHMA_INCIDENCE, n)
    beta_a = np.where(RNG.random(n) < 0.5, draw_log_beta(ASTHMA_GBD, n), draw_log_beta(ASTHMA, n))
    paf = 1 - np.exp(-beta_a * np.clip(base - 2.0, 0, None))  # counterfactual 2 ppb
    out["asma_paf_pct"] = np.percentile(100 * paf, [5, 50, 95])
    out["asma_casos"] = np.percentile(POP_ZMVM * POP_UNDER18_SHARE * rate * paf, [5, 50, 95])
    return pd.DataFrame(out, index=["p05", "p50", "p95"]).T


def main() -> None:
    OUT.mkdir(exist_ok=True)
    daily = daily_no2()
    ann = annual_means(daily)
    ann.to_csv(OUT / "annual_no2_by_station.csv", index=False, float_format="%.2f")
    print(ann.groupby("year")["no2_ppb"].agg(["mean", "median", "count"]).round(2))
    base = float(ann[ann["year"].isin((2023, 2024))]["no2_ppb"].mean())
    ratio = sunday_ratio(daily)
    print(f"base NO2 (ppb, 2023-24 mean of stations): {base:.2f}")
    print(f"Sunday/weekday NO2 24 h: {ratio[0]:.3f} (90 %: {ratio[1]:.3f}-{ratio[2]:.3f})")
    res = simulate(base, ratio)
    res.to_csv(OUT / "scenarios.csv", index=False, float_format="%.2f")
    print(res.round(2).to_string())
    burden = attributable_burden(base)
    burden.to_csv(OUT / "attributable_burden.csv", float_format="%.2f")
    print(burden.round(1))


if __name__ == "__main__":
    main()
