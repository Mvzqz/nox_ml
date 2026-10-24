"""Descarga datos horarios de la RMCAB (Bogotá) alrededor de cada Día sin carro.

Usa el endpoint público del portal Envista (ver data/raw/bogota/MANIFEST.md). Los canales (monitores) de cada
estación se toman de la muestra de nov–dic 2023 (`rmcab_{id}_2023-11_2023-12.json`). Fechas en hora local (UTC−5).
Uso: python scripts/bogota_download.py [--test]
"""
import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "bogota"
OUT = RAW / "dsc"
URL = "https://rmcab.ambientebogota.gov.co/Report/GetMultiStationsReportNewAsync"
KEEP = ("NO", "NO2", "NOX", "Vel Viento", "Dir Viento", "Vel Viento 10M", "Dir Viento 10M", "CO")

# Ventanas: ±~6 semanas alrededor de cada jornada (ver bogota_dsc.py para las fechas).
WINDOWS = {
    "2015": ("2015-01-05", "2015-03-16"), "2016": ("2016-01-05", "2016-03-16"),
    "2017": ("2017-01-05", "2017-03-16"), "2018": ("2018-01-05", "2018-03-16"),
    "2019": ("2019-01-05", "2019-03-16"), "2020": ("2020-01-05", "2020-03-12"),
    "2022s": ("2022-08-10", "2022-11-01"), "2023": ("2023-01-05", "2023-03-16"),
    "2023s": ("2023-08-10", "2023-11-01"), "2024": ("2024-01-05", "2024-03-16"),
}


def ticks(d):
    return int((dt.datetime.fromisoformat(d) - dt.datetime(1, 1, 1)).total_seconds()) * 10_000_000


def fetch(sid, mons, d0, d1):
    q = {"ListStationId": json.dumps([sid]), "ListMonitorIds": json.dumps(mons), "FDate": ticks(d0),
         "TDate": ticks(d1), "TB": json.dumps(["60"]), "ToTB": 60, "ReportType": "Average", "first": "true",
         "take": 0, "skip": 0, "page": 1, "pageSize": 0}
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "Mozilla/5.0"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print("  reintento", sid, d0, e, flush=True)
            time.sleep(5 * (k + 1))
    return None


def main():
    OUT.mkdir(exist_ok=True)
    stations = []
    for f in sorted(RAW.glob("rmcab_*_2023-11_2023-12.json")):
        j = json.load(open(f))
        can = {k: v for k, v in j["canales"].items() if v in KEEP}
        stations.append((j["id"], j["estacion"], can))
    wins = {"2015": WINDOWS["2015"]} if "--test" in sys.argv else WINDOWS
    for name, (d0, d1) in wins.items():
        for sid, est, can in stations:
            dst = OUT / f"rmcab_{sid}_{name}.json"
            if dst.exists():
                continue
            # bloques de ~30 días para no saturar el portal
            rows, a = [], dt.date.fromisoformat(d0)
            end = dt.date.fromisoformat(d1)
            while a < end:
                b = min(a + dt.timedelta(days=30), end)
                r = fetch(sid, list(can), a.isoformat(), b.isoformat())
                if r is not None:
                    rows += [x for x in r.get("Data", r.get("data", [])) if "datetime" in x]
                a = b
            json.dump({"estacion": est, "id": sid, "canales": can, "ventana": [d0, d1], "datos": rows},
                      open(dst, "w"))
            print(name, sid, est, len(rows), flush=True)


if __name__ == "__main__":
    main()
