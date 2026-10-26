import json
from pathlib import Path

import pandas as pd
import yaml

NOTEBOOK = Path(__file__).parents[2] / "notebooks" / "Avance4.39.ipynb"


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


def test_the_front_c_cells_read_the_searches_and_the_kappa_grid_when_they_exist(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("")
    runs = tmp_path / "results" / "runs"
    config = {"model": {"name": "pinn_puff", "params": {"kappa": 1500.0}}}
    summary = {"model": "pinn_puff", "role": "model", "loo_rmse_ppb": 12.08, "eligible": True}

    def write_run(name, kappa=None, trials=None):
        folder = runs / name
        folder.mkdir(parents=True)
        (folder / "metrics.json").write_text(json.dumps({"summary": summary}))
        params = config["model"]["params"] | ({} if kappa is None else {"kappa": kappa})
        (folder / "config.yaml").write_text(yaml.safe_dump({"model": config["model"] | {"params": params}}))
        if trials is not None:
            pd.DataFrame(trials).to_csv(folder / "trials.csv", index=False)

    write_run("pinn_puff")
    write_run("pinn_puff_k500", kappa=500.0)
    write_run(
        "pinn_puff.transport",
        trials={"trial": [0, 1, 2], "u_min": [1.0, 1.5, 2.0], "loo_rmse_ppb": [12.08, 12.0, 11.9]},
    )
    write_run(
        "pinn_puff.kernel",
        trials={"trial": [0, 1, 2], "width": [32, 64, 96], "loo_rmse_ppb": [12.08, 12.1, 12.09]},
    )

    scope = run_code_cells(monkeypatch, tmp_path)

    assert list(scope["table"]["run"]) == ["pinn_puff"]  # the kappa run is not a competitor
    assert list(scope["ranked"]["id"]) == ["E5b"]
    assert list(scope["grid"]["kappa_m"]) == [500.0, 1500.0]
    assert set(scope["trials"]) == {"pinn_puff.transport", "pinn_puff.kernel"}
