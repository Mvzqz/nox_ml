import json
import re
from pathlib import Path

import pytest

from nox_ml.validation import report_eda

DELIVERABLES = Path(__file__).parents[2] / "notebooks"
DATA = Path(__file__).parents[2] / "data"
SECTIONS = {
    "Avance1.39.ipynb": [
        "Objetivo y reglas del ejercicio",
        "Estructura y tipos de datos",
        "Estadísticos descriptivos",
        "Datos faltantes y sus patrones",
        "Valores atípicos",
        "Gráficas univariadas",
        "Análisis bivariado y multivariado",
        "Tendencias temporales",
        "Decisiones de preprocesamiento y su justificación",
        "Conclusiones",
    ],
    "Avance2.39.ipynb": [
        "Objetivo y reglas del ejercicio",
        "Construcción de características con justificación de dominio",
        "Resumen de las características",
        "Escalamiento y transformaciones",
        "Selección y extracción de características",
        "Conclusiones de la preparación de datos (CRISP-ML(Q))",
    ],
}
notebooks = pytest.mark.parametrize("name", SECTIONS)


def cells(name: str) -> list[dict]:
    return json.loads((DELIVERABLES / name).read_text())["cells"]


def code_lines(name: str) -> list[str]:
    return [
        line for c in cells(name) if c["cell_type"] == "code" for line in "".join(c["source"]).splitlines()
    ]


@notebooks
def test_the_notebook_has_the_sections_of_the_course_in_order(name):
    headings = [
        line
        for c in cells(name)
        if c["cell_type"] == "markdown"
        for line in "".join(c["source"]).splitlines()
        if line.startswith("## ")
    ]

    assert [h.split(". ", 1)[1] for h in headings] == SECTIONS[name]


@notebooks
def test_the_notebook_code_only_calls_nox_ml_and_defines_nothing(name):
    lines = code_lines(name)

    assert all(line.startswith("from nox_ml") for line in lines if "import" in line)
    assert not [line for line in lines if re.match(r"\s*(def|class|for|while|lambda)\b", line)]


@notebooks
def test_every_helper_the_notebook_calls_exists_in_the_report_module(name):
    called = set(re.findall(r"\beda\.(\w+)", "\n".join(code_lines(name))))

    assert called
    assert {f for f in called if not hasattr(report_eda, f)} == set()


@notebooks
def test_the_notebook_is_stored_without_outputs(name):
    code = [c for c in cells(name) if c["cell_type"] == "code"]

    assert all(c["outputs"] == [] and c["execution_count"] is None for c in code)


@notebooks
def test_the_notebook_keeps_the_test_period_out_of_the_decisions(name):
    text = "\n".join("".join(c["source"]) for c in cells(name) if c["cell_type"] == "code")

    assert "TEST_PERIOD" not in text or name == "Avance1.39.ipynb"
    assert "pixels_test" not in text or name == "Avance1.39.ipynb"


@pytest.mark.slow
@pytest.mark.skipif(not (DATA / "raw" / "simat").exists(), reason="data not pulled")
@notebooks
def test_the_notebook_runs_on_the_real_data(name, monkeypatch):
    monkeypatch.chdir(DELIVERABLES.parent)
    scope: dict = {}
    for cell in cells(name):
        if cell["cell_type"] == "code":
            source = "\n".join(
                line for line in "".join(cell["source"]).splitlines() if not line.startswith("%")
            )
            exec(source, scope)

    assert len(scope["rows"]) > 7000
