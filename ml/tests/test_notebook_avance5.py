import json
from pathlib import Path

NOTEBOOK = Path(__file__).parents[2] / "notebooks" / "Avance5.39.ipynb"


def test_the_notebook_runs_without_any_run_and_says_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scope: dict = {}
    for cell in json.loads(NOTEBOOK.read_text())["cells"]:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), scope)

    assert scope["table"].empty
    assert len(scope["pending"]) == len(scope["report_final"].PLANNED)
    assert scope["held_out"] is None


def test_the_notebook_has_the_sections_of_the_rubric_and_ends_with_the_ai_declaration():
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    headings = [
        line for c in cells if c["cell_type"] == "markdown" for line in c["source"] if line[:3] == "## "
    ]

    assert [h.split(". ", 1)[1].strip() for h in headings] == [
        "Objetivo",
        "Los ensambles",
        "Ajuste de hiperparámetros",
        "Tabla comparativa",
        "Modelo final",
        "Evaluación en datos no vistos",
        "Gráficos del modelo final",
        "Limitaciones",
        "Declaración del uso de herramientas de IA",
    ]
    assert cells[-1]["cell_type"] == "markdown"


def test_the_notebook_code_only_calls_nox_ml():
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    imports = [line for c in cells if c["cell_type"] == "code" for line in c["source"] if "import" in line]

    assert imports == ["from nox_ml.validation import report, report_final\n"]


def test_the_final_model_has_at_least_four_figures():
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    figures = [c for c in cells if c["cell_type"] == "code" and "report_final.plot_" in "".join(c["source"])]

    assert len(figures) >= 4
