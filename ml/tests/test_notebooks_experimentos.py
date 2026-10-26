import json
import re
from pathlib import Path

import pytest

FOLDER = Path(__file__).parents[2] / "notebooks" / "experimentos"
NOTEBOOKS = sorted(FOLDER.glob("*.ipynb"))
DATA = Path(__file__).parents[2] / "data" / "interim" / "simat_nox.parquet"


def cells(path):
    return json.loads(path.read_text())["cells"]


def run_code_cells(path, folder, monkeypatch):
    monkeypatch.chdir(folder)
    scope: dict = {}
    for cell in cells(path):
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), scope)
    return scope


def test_the_five_experiment_notebooks_are_there():
    assert [p.name for p in NOTEBOOKS] == [
        "01_transporte.ipynb",
        "02_emision_vs_clima.ipynb",
        "03_ajuste_pinn_puff.ipynb",
        "04_ablacion.ipynb",
        "05_viento_y_objetivo.ipynb",
    ]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_a_notebook_is_stored_without_outputs(path):
    code = [c for c in cells(path) if c["cell_type"] == "code"]

    assert code
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in code)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_the_code_of_a_notebook_only_calls_nox_ml(path):
    imports = [
        line.strip()
        for c in cells(path)
        if c["cell_type"] == "code"
        for line in "".join(c["source"]).splitlines()
        if re.match(r"\s*(import|from) ", line)
    ]

    assert imports
    assert all(re.match(r"(from|import) nox_ml\b", line) for line in imports), imports


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_a_notebook_starts_with_its_title_and_has_an_interpretation_after_the_results(path):
    markdown = ["".join(c["source"]) for c in cells(path) if c["cell_type"] == "markdown"]

    assert markdown[0].startswith(f"# Experimento {int(path.name[:2])}. ")
    if path.name != "03_ajuste_pinn_puff.ipynb":  # the readings of 3 depend on runs that only exist locally
        assert sum("**Lectura" in m for m in markdown) >= 2


def test_the_wind_notebook_says_what_is_cited_and_what_is_reproduced():
    headings = [
        line
        for c in cells(FOLDER / "05_viento_y_objetivo.ipynb")
        if c["cell_type"] == "markdown"
        for line in "".join(c["source"]).splitlines()
        if line.startswith("## ")
    ]

    assert [h.split(". ", 1)[1] for h in headings[:5]] == [
        "El objetivo original *(citado)*",
        "Gemelo sintético: ¿qué se pierde con el error del viento? *(reproducido)*",
        "El error real del viento *(reproducido)*",
        "La decisión *(citado)*",
        "El giro posterior: el viento ya no es lo que limita",
    ]
    text = "".join("".join(c["source"]) for c in cells(FOLDER / "05_viento_y_objetivo.ipynb"))
    assert "### Los Ángeles *(citado" in text
    assert "### En este repositorio *(reproducido)*" in text


def test_the_pinn_puff_notebook_runs_without_any_run_and_says_what_is_missing(tmp_path, monkeypatch):
    scope = run_code_cells(FOLDER / "03_ajuste_pinn_puff.ipynb", tmp_path, monkeypatch)

    assert not scope["rx"].runs_status(scope["RUNS"])["exists"].any()
    assert scope["pinn"].empty and scope["kappas"].empty and scope["summary"].empty
    assert scope["transport"] is None and scope["kernel"] is None
    assert scope["rx"].plot_kappa(scope["kappas"]) is None


@pytest.mark.slow
@pytest.mark.skipif(not DATA.exists(), reason="needs the data (dvc pull)")
@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_every_notebook_executes_on_the_real_data(path, monkeypatch):
    scope = run_code_cells(path, FOLDER, monkeypatch)

    assert scope["rx"]
