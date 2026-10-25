import json
from pathlib import Path

NOTEBOOK = Path(__file__).parents[2] / "deliverables" / "Avance4.39.ipynb"


def run_code_cells(monkeypatch, folder):
    monkeypatch.chdir(folder)
    scope: dict = {}
    for cell in json.loads(NOTEBOOK.read_text())["cells"]:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), scope)
    return scope


def test_the_notebook_runs_without_any_run_and_says_which_models_are_missing(tmp_path, monkeypatch):
    scope = run_code_cells(monkeypatch, tmp_path)

    assert scope["table"].empty
    assert len(scope["pending"]) == len(scope["report"].PLANNED)


def test_the_notebook_has_the_sections_of_the_plan_and_ends_with_the_ai_declaration():
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    headings = [
        line for c in cells if c["cell_type"] == "markdown" for line in c["source"] if line[:3] == "## "
    ]

    assert [h.split(". ", 1)[1].strip() for h in headings] == [
        "Objetivo",
        "Los modelos y las referencias",
        "Tabla comparativa",
        "Los dos mejores",
        "Ajuste fino",
        "Modelo final",
        "Declaración del uso de herramientas de IA",
    ]
    assert cells[-1]["cell_type"] == "markdown"


def test_the_notebook_code_only_calls_nox_ml():
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    imports = [line for c in cells if c["cell_type"] == "code" for line in c["source"] if "import" in line]

    assert imports == ["from nox_ml.validation import compare, report\n"]
