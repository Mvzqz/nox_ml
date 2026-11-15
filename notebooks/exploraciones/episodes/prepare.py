"""Daily tables of every season for the episode validation (F3), cached in runs/episode_validation/.

For each window: the daily table of `nox-ml episode` (observed NOx and NOx modeled with the prior emission,
`normalized_days`), the TEMPO parts (`tempo_parts`: regional background and urban part) and the afternoon
ventilation of each day (boundary layer and wind speed of the fitted hours), which is what the weather
episodes are chosen by, without looking at NOx.

Usage: uv run python notebooks/exploraciones/episodes/prepare.py [window ...]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from nox_ml.data.inputs import DEFAULT_SOURCES, LOCKDOWN_SOURCES, load_inputs, openaq_sources
from nox_ml.inversion.jacobian import plume_transport
from nox_ml.inversion.linear import SIGMA_THETA, U_MIN
from nox_ml.time import local_day
from nox_ml.validation.episodes import tempo_parts
from nox_ml.validation.experiment import normalized_days

DATA = Path("data")
CACHE = Path("runs/episode_validation")

# window: (start, end, sources); the seasons of configs/seasons/ plus nov-dec 2023 (where the tool was built),
# feb-may 2024 (only measured, nothing chosen with it) and the lockdown years 2019-2020 (no TEMPO)
WINDOWS = {
    "nd2023": ("2023-11-01", "2023-12-31", DEFAULT_SOURCES),
    "fm2024": ("2024-02-15", "2024-05-31", DEFAULT_SOURCES),
    "nd2024": ("2024-11-01", "2024-12-31", DEFAULT_SOURCES),
    "fm2025": ("2025-02-15", "2025-05-31", openaq_sources("2025-02-15", "2025-06-01")),
    "nd2025": ("2025-11-01", "2025-12-31", openaq_sources("2025-11-01", "2026-01-01")),
    "fm2026": ("2026-02-15", "2026-05-31", openaq_sources("2026-02-15", "2026-06-01")),
    "fm2019": ("2019-02-15", "2019-05-31", LOCKDOWN_SOURCES),
    "fm2020": ("2020-02-15", "2020-05-31", LOCKDOWN_SOURCES),
}


def ventilation(inputs) -> pd.DataFrame:
    """Afternoon boundary layer (m), wind speed (m/s) and ventilation coefficient (m2/s) by local day."""
    rows = [(local_day(h.hour), h.pbl, float(np.hypot(*h.wind))) for h in inputs.hours]
    table = pd.DataFrame(rows, columns=["day", "pbl", "wind"]).assign(vc=lambda x: x.pbl * x.wind)
    return table.groupby("day")[["pbl", "wind", "vc"]].mean()


def prepare(name: str) -> None:
    start, end, sources = WINDOWS[name]
    inputs = load_inputs(DATA, start, end, (12, 17), sources)
    daily = normalized_days(inputs, inputs.jacobians(*plume_transport(SIGMA_THETA, U_MIN)))
    tempo = (
        tempo_parts(inputs) if sources.tempo else pd.DataFrame(columns=["background", "urban"], dtype=float)
    )
    out = daily.join(ventilation(inputs)).join(tempo)
    CACHE.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE / f"days_{name}.parquet")
    print(f"{name}: {len(out)} days, {out['background'].notna().sum()} with TEMPO")


if __name__ == "__main__":
    for window in sys.argv[1:] or list(WINDOWS):
        prepare(window)
