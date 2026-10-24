"""NOx loss by OH + NO2 -> HNO3, dependent on month and hour.

Migrated from `scripts/vida_quimica.py` (research-archive); only the pure part. Reading SIMAT, caching and
the evaluation modes stay out. Standard variant `oh_24h`: OH_REF = 6e6 cm-3 at local noon of April,
OH proportional to the primary production of OH (b = 1), no extra loss, 24 h puffs.

    k_NOx(t) = K_OH_NO2 * [OH](t) * F_NO2
    [OH](t)  = OH_REF * (P(t) / P_ref) ** b,   P = j(O1D) * O3 * H2O

At night OH is ~0: the nocturnal loss (N2O5) is ignored.
"""

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from nox_ml.time import utc_to_local

Array = NDArray[np.float64]

LAT0, LON0 = 19.43, -99.13  # city centre
K_OH_NO2 = 9.3e-12  # cm3/s (JPL at ~780 hPa)
F_NO2 = 0.85  # NO2/NOx in the afternoon
OH_REF = 6e6  # cm-3 at noon of April (MCMA-2003, MILAGRO 2006)
REF_YEAR, REF_MONTH, REF_HOUR = 2024, 4, 12  # local noon of April 2024 defines P_ref
SECONDS_PER_HOUR = 3600.0


def cos_zenith(t_utc: pd.DatetimeIndex, lat: float = LAT0, lon: float = LON0) -> Array:
    """Cosine of the solar zenith angle at hourly timestamps (middle of the hour), Spencer approximation."""
    doy = t_utc.day_of_year.to_numpy()
    hour = t_utc.hour.to_numpy()
    g = 2 * np.pi / 365 * (doy - 1 + (hour + 0.5 - 12) / 24)
    decl = (
        0.006918
        - 0.399912 * np.cos(g)
        + 0.070257 * np.sin(g)
        - 0.006758 * np.cos(2 * g)
        + 0.000907 * np.sin(2 * g)
        - 0.002697 * np.cos(3 * g)
        + 0.00148 * np.sin(3 * g)
    )
    eqt = 229.18 * (
        0.000075
        + 0.001868 * np.cos(g)
        - 0.032077 * np.sin(g)
        - 0.014615 * np.cos(2 * g)
        - 0.040849 * np.sin(2 * g)
    )
    tst = (hour + 0.5) * 60 + eqt + 4 * lon
    ha = np.deg2rad(tst / 4 - 180)
    phi = np.deg2rad(lat)
    return np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(ha)


def j_o1d(cz: ArrayLike) -> Array:
    """MCM J1 (O3 -> O1D): 6.073e-5 * cos^1.743 * exp(-0.474 / cos); 0 at night."""
    cz = np.asarray(cz, dtype=float)
    out = np.zeros_like(cz)
    day = cz > 0.02
    out[day] = 6.073e-5 * cz[day] ** 1.743 * np.exp(-0.474 / cz[day])
    return out


def oh_production(jo1d: ArrayLike, o3: ArrayLike, tmp_c: ArrayLike, rh: ArrayLike) -> Array:
    """Primary production of OH, P = j(O1D) * O3 * H2O (vapour pressure in hPa, from T in C and RH in %)."""
    tmp_c = np.asarray(tmp_c, dtype=float)
    es = 6.112 * np.exp(17.67 * tmp_c / (tmp_c + 243.5))
    h2o = np.asarray(rh, dtype=float) / 100 * es
    return np.asarray(jo1d) * np.clip(o3, 1, None) * h2o


def reference_production(
    p: pd.Series,
    year: int = REF_YEAR,
    month: int = REF_MONTH,
    hour: int = REF_HOUR,
) -> float:
    """P_ref: mean of the hourly series `p` (UTC index) at local `hour` of `month`/`year`."""
    local = utc_to_local(pd.DatetimeIndex(p.index))
    return float(p[(local.year == year) & (local.month == month) & (local.hour == hour)].mean())


def nox_loss_rate(
    p: ArrayLike, p_ref: float, oh_ref: float = OH_REF, b: float = 1.0, k_extra: float = 0.0
) -> Array:
    """NOx loss rate (1/s). `k_extra` is a constant additional loss (PAN, organic nitrates, deposition)."""
    oh = oh_ref * np.clip(np.asarray(p) / p_ref, 0, None) ** b
    return K_OH_NO2 * oh * F_NO2 + k_extra


def lifetime_h(k_loss: ArrayLike) -> Array:
    """NOx lifetime (h) from the loss rate (1/s); NaN where there is no loss."""
    k = np.asarray(k_loss, dtype=float)
    return 1 / np.where(k == 0, np.nan, k) / SECONDS_PER_HOUR
