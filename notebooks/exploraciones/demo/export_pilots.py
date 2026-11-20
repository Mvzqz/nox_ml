# ruff: noqa: E501  (user-facing Spanish strings read better unwrapped)
"""Export the pilots the app (app/src/nox_app/pilots.py) starts from: results/runs/demo/pilots.json.

- **Retrospective** pilots with real results: the 2020 lockdown phases and the 2024 contingencies with
  measures (results/runs/normalized_ratio.*), with the station coverage of their months
  (notebooks/exploraciones/network_qc/completeness_by_month.csv).
- **Planned** pilots with simulated numbers (``mock``), one per stage of the life cycle, until the app has a
  backend where real pilots are registered.

Run from the repository root: ``uv run python notebooks/exploraciones/demo/export_pilots.py``.
"""

import json
from pathlib import Path

import pandas as pd

RUNS = Path("results/runs")
COMPLETENESS = Path("notebooks/exploraciones/network_qc/completeness_by_month.csv")


def coverage(start: str, end: str) -> float | None:
    c = pd.read_csv(COMPLETENESS)
    c = c[
        ((c["source"] == "SIMAT") & (c["month"] <= "2024-12"))
        | ((c["source"] == "OpenAQ") & (c["month"] > "2024-12"))
    ]
    found = (
        c.set_index("month")["completeness"]
        .reindex(pd.period_range(start, end, freq="M").astype(str))
        .dropna()
    )
    return round(float(found.mean()), 3) if len(found) else None


def change(r: dict) -> dict:
    return {k: round(r[name] - 1, 4) for k, name in (("change", "ratio"), ("lo", "lo"), ("hi", "hi"))}


def retrospective() -> list[dict]:
    lockdown = json.loads((RUNS / "normalized_ratio.lockdown/lockdown.json").read_text())
    pilots = []
    for i, (phase, label) in enumerate((("phase2", "fase 2"), ("phase3", "fase 3")), start=1):
        a, b = (f"2020-{d}" for d in lockdown["phases"][phase])
        pilots.append({
            "id": f"r{i:02d}", "name": f"Confinamiento por COVID-19, {label}", "origin": "Retrospectivo", "created": "2026-03-01",
            "start": a, "end": b, "design": "Continuo", "target": None, "result": change(lockdown["effect"][phase]["did"]),
            "coverage": coverage(a, b),
            "description": "Cierre de actividades no esenciales. Se compara con las mismas semanas de 2019 para descontar la temporada.",
            "operations": "No replicable como política: sirve de referencia de cuánto puede bajar la emisión con una caída fuerte del tráfico.",
            "notes": [{"date": "2026-03-01", "text": "Registrado como referencia retrospectiva."}],
        })  # fmt: skip
    cont = json.loads((RUNS / "normalized_ratio.contingencies/contingencies.json").read_text())["scenarios"][
        "measures"
    ]
    days = cont["days"]["event"]
    pilots.append({
        "id": "r03", "name": "Contingencias por ozono con restricción vehicular, 2024", "origin": "Retrospectivo", "created": "2026-03-01",
        "start": days[0], "end": days[-1], "design": f"{len(days)} días de contingencia", "target": None, "result": change(cont),
        "coverage": coverage(days[0], days[-1]),
        "description": "Días con la Fase I activada (doble Hoy No Circula y restricciones a la industria), frente a días normales de la misma temporada.",
        "operations": "Se activa con poca anticipación y dura 1 a 3 días: demasiado corto para que la medida se note en la emisión.",
        "notes": [{"date": "2026-03-01", "text": "Registrado como referencia retrospectiva."}],
    })  # fmt: skip
    return pilots


# One planned pilot per stage of the life cycle, with simulated numbers.
MOCKS = [
    {
        "id": "m01", "name": "Hoy No Circula sabatino ampliado", "created": "2026-04-10", "start": "2026-06-01", "end": "2026-07-24",
        "design": "Semanas alternas", "target": -0.10, "result": {"change": -0.12, "lo": -0.19, "hi": -0.05}, "coverage": 0.86,
        "description": "Restricción sabatina a vehículos con holograma 1, en semanas alternas durante 8 semanas.",
        "operations": "Lo opera la Secretaría con la infraestructura actual de fotomultas; extenderlo requiere coordinar con el Estado de México.",
        "notes": [{"date": "2026-04-10", "text": "Diseño aprobado: semanas alternas, meta −10 %."},
                  {"date": "2026-06-01", "text": "Arranca el piloto."}, {"date": "2026-09-10", "text": "Evaluación consolidada."}],
    },
    {
        "id": "m02", "name": "Carril confinado de carga en Eje 8 Sur", "created": "2026-07-20", "start": "2026-09-07", "end": "2026-10-16",
        "design": "Semanas alternas", "target": -0.08, "result": {"change": -0.04, "lo": -0.14, "hi": 0.06},
        "result_with_atypical": {"change": -0.07, "lo": -0.16, "hi": 0.03}, "coverage": 0.81,
        "description": "Carril exclusivo para carga en horario nocturno, en semanas alternas durante 6 semanas.",
        "operations": "Requiere señalización móvil y dos patrullas por turno; los transportistas pidieron avisos con una semana de anticipación.",
        "notes": [{"date": "2026-07-20", "text": "Diseño aprobado."}, {"date": "2026-09-16", "text": "Feriado del 16 de septiembre dentro del periodo."}],
    },
    {
        "id": "m03", "name": "Verificación vehicular reforzada en Iztapalapa", "created": "2026-06-15", "start": "2026-08-03", "end": "2026-08-28",
        "design": "Continuo", "target": -0.05, "result": {"change": -0.02, "lo": -0.15, "hi": 0.11}, "coverage": 0.42,
        "description": "Operativo de verificación en vía pública durante 4 semanas.",
        "operations": "Operativo intensivo en personal; dos estaciones de la zona estuvieron fuera de servicio buena parte del periodo.",
        "notes": [{"date": "2026-08-12", "text": "Dos estaciones de la zona sin datos desde el 10 de agosto."}],
    },
    {
        "id": "m04", "name": "Reparto nocturno de mercancías en el Centro", "created": "2026-09-01", "start": "2026-10-12", "end": "2026-11-13",
        "design": "Continuo", "target": -0.06,
        "description": "Las entregas a comercios del Centro se mueven de 7–11 h a 22–6 h.",
        "operations": "Depende de la adhesión voluntaria de distribuidores; 60 % se inscribió.",
        "notes": [{"date": "2026-10-12", "text": "Arranca el piloto."}, {"date": "2026-11-13", "text": "Termina el piloto; esperando datos."}],
    },
    {
        "id": "m05", "name": "Ciclovía recreativa entre semana en Reforma", "created": "2026-10-01", "start": "2026-11-09", "end": "2026-12-18",
        "design": "Días alternos", "target": -0.05,
        "description": "Cierre de un carril de Reforma a autos los martes y jueves de 6 a 10 h.",
        "operations": "Lo opera el programa Muévete en Bici con el personal actual.",
        "notes": [{"date": "2026-11-09", "text": "Arranca el piloto."}],
    },
    {
        "id": "m06", "name": "Restricción de carga pesada en horas pico", "created": "2026-11-02", "start": "2027-02-15", "end": "2027-04-30",
        "design": "Semanas alternas", "target": -0.12,
        "description": "Prohibición de circular a vehículos de más de 3.5 t de 7 a 10 h en vías primarias.",
        "operations": "Requiere acuerdo con la Cámara de Autotransporte; pendiente la publicación en la Gaceta.",
        "notes": [{"date": "2026-11-02", "text": "Programado para la temporada feb–may 2027."}],
    },
    {
        "id": "m07", "name": "Zona de bajas emisiones en el Centro Histórico", "created": "2026-11-15", "start": None, "end": None, "draft": True,
        "design": "Bloques de dos semanas", "target": -0.15,
        "description": "Acceso solo a vehículos con holograma 0 y 00 al perímetro A.",
        "operations": "Por definir con la Alcaldía Cuauhtémoc.",
        "notes": [{"date": "2026-11-15", "text": "Borrador: falta fijar fechas."}],
    },
]  # fmt: skip


if __name__ == "__main__":
    mocks = [{**m, "origin": "Planificado", "mock": True} for m in MOCKS]
    pilots = mocks + retrospective()
    Path("results/runs/demo/pilots.json").write_text(json.dumps(pilots, indent=1, ensure_ascii=False) + "\n")
    for p in pilots:
        print(p["id"], p["origin"], p["start"], p["end"], p.get("result"), p.get("coverage"))
