# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Export the pilots the app (app/src/nox_app/pilots.py) starts from: results/runs/demo/pilots.json.

Pilots with simulated numbers (``mock``), one per stage of the life cycle, until the app has a backend where
real pilots are registered. Only pilots planned with the app exist: a measure applied before did not follow
its design rules, so it is not a pilot.

Run from the repository root: ``uv run python notebooks/exploraciones/demo/export_pilots.py``.
"""

import json
from pathlib import Path

# One planned pilot per stage of the life cycle, with simulated numbers.
MOCKS = [
    {
        "id": "m01", "name": "Hoy No Circula sabatino ampliado", "created": "2026-04-10", "start": "2026-06-01", "end": "2026-07-24",
        "design": "Semanas alternas", "target": -0.10, "result": {"change": -0.12, "lo": -0.19, "hi": -0.05}, "coverage": 0.86,
        "description": "Restricción sabatina a vehículos con holograma 1, en semanas alternas durante 8 semanas.",
    },
    {
        "id": "m02", "name": "Carril confinado de carga en Eje 8 Sur", "created": "2026-07-20", "start": "2026-09-07", "end": "2026-10-16",
        "design": "Semanas alternas", "target": -0.08, "result": {"change": -0.04, "lo": -0.14, "hi": 0.06},
        "result_with_atypical": {"change": -0.07, "lo": -0.16, "hi": 0.03}, "coverage": 0.81,
        "description": "Carril exclusivo para carga en horario nocturno, en semanas alternas durante 6 semanas.",
    },
    {
        "id": "m03", "name": "Verificación reforzada en Iztapalapa", "created": "2026-06-15", "start": "2026-08-03", "end": "2026-08-28",
        "design": "Continuo", "target": -0.05, "result": {"change": -0.02, "lo": -0.15, "hi": 0.11}, "coverage": 0.42,
        "description": "Operativo de verificación en vía pública durante 4 semanas.",
    },
    {
        "id": "m04", "name": "Reparto nocturno en el Centro", "created": "2026-09-01", "start": "2026-10-12", "end": "2026-11-13",
        "design": "Continuo", "target": -0.06,
        "description": "Las entregas a comercios del Centro se mueven de 7–11 h a 22–6 h.",
    },
    {
        "id": "m05", "name": "Ciclovía entre semana en Reforma", "created": "2026-10-01", "start": "2026-11-09", "end": "2026-12-18",
        "design": "Días alternos", "target": -0.05,
        "description": "Cierre de un carril de Reforma a autos los martes y jueves de 6 a 10 h.",
    },
    {
        "id": "m06", "name": "Restricción de carga pesada en horas pico", "created": "2026-11-02", "start": "2027-02-15", "end": "2027-04-30",
        "design": "Semanas alternas", "target": -0.12,
        "description": "Prohibición de circular a vehículos de más de 3.5 t de 7 a 10 h en vías primarias.",
    },
    {
        "id": "m07", "name": "Bajas emisiones, Centro Histórico", "created": "2026-11-15", "start": None, "end": None, "draft": True,
        "design": "Bloques de dos semanas", "target": -0.15,
        "description": "Acceso solo a vehículos con holograma 0 y 00 al perímetro A.",
    },
]  # fmt: skip


if __name__ == "__main__":
    pilots = [{**m, "mock": True} for m in MOCKS]
    Path("results/runs/demo/pilots.json").write_text(json.dumps(pilots, indent=1, ensure_ascii=False) + "\n")
    for p in pilots:
        print(p["id"], p["start"], p["end"], p.get("result"), p.get("coverage"))
