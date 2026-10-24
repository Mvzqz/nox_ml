"""LA: reintenta los escaneos de TEMPO que fallaron (curl 6/56, 12–16 dic 2023) y agrega las 19 UTC del
1 al 4 de noviembre, cuando regía el horario de verano (PDT = UTC−7: tarde 12–17 h = 19–00 UTC).

Uso: .venv/bin/python scripts/la_tempo_retry.py
"""
import sys

import tempo_download as td
from la_common import BBOX, RAW

td.BBOX = BBOX
td.OUT = RAW / "tempo"
td.MANIFEST = td.OUT / "manifest.csv"

if __name__ == "__main__":
    td.UTC_HOURS = [19]
    sys.argv = [sys.argv[0], "2023-11-01", "2023-11-04", "--workers", "4"]
    td.main()
    td.UTC_HOURS = [20, 21, 22, 23, 0, 1]
    sys.argv = [sys.argv[0], "2023-12-12", "2023-12-17", "--workers", "4"]
    td.main()
