"""LA: descarga recortes de TEMPO NO₂ L2 V04 reutilizando tempo_download.py con el dominio de LA.

Tarde local PST (UTC−8): 12–17 h = 20–01 UTC. Salida en data/raw/la/tempo/ con su manifest.csv.
Uso: .venv/bin/python scripts/la_tempo_download.py 2023-11-01 2023-12-31
"""
import sys

import tempo_download as td
from la_common import BBOX, RAW

td.BBOX = BBOX
td.OUT = RAW / "tempo"
td.MANIFEST = td.OUT / "manifest.csv"
td.UTC_HOURS = [20, 21, 22, 23, 0, 1]

if __name__ == "__main__":
    sys.argv = [sys.argv[0], *sys.argv[1:3], "--workers", "6"]
    sys.exit(td.main())
