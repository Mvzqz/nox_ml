"""Hourly profile of road traffic emission.

Migrated from `scripts/puffs_cdmx.py` (research-archive): only reading the profile that the research derived
from the Infovial vehicle counts of January 2017 (`data/interim/puffs_cdmx/perfil_infovial.json`). Deriving it
from the raw counts is not migrated.
"""

import json
from pathlib import Path

# Day type (0 weekday, 1 Saturday, 2 Sunday or holiday) -> local hour -> emission factor (daily mean 1).
Infovial = dict[int, dict[int, float]]


def read_infovial_profile(path: Path) -> Infovial:
    """Read the profile JSON, whose keys are strings, into integer day types and hours."""
    raw = json.loads(path.read_text())
    return {
        int(day_type): {int(hour): float(v) for hour, v in hours.items()} for day_type, hours in raw.items()
    }
