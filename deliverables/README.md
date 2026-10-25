# Deliverables

Progress notebooks for the advisor and published documents, written in Spanish. Notebooks **only reuse functions** from `nox_ml` (no logic of their own; tables and figures live in `nox_ml.validation.report_baseline`), are stored without outputs (nbstripout), and CI checks that they execute.

Naming: `YYYY-MM-DD_topic.ipynb`.

`experimentos/` holds the experiment notebooks (`01_transporte`, `02_emision_vs_clima`, `03_ajuste_pinn_puff`, `04_ablacion`, `05_viento_y_objetivo`), numbered instead of dated because they are read in order. They call `nox_ml.validation.report_experiments` and need the data (`dvc pull`); 03 reads `runs/` and says what is missing when a run does not exist on the machine; 04 and 05 run `nox-ml diagnose` the first time if `runs/baseline/diagnostics/` is not there (about 8 minutes). Executing all five takes about 10 minutes (`pytest -m slow ml/tests/test_notebooks_experimentos.py`).
Naming: `Avance<N>.39.ipynb` for the progress reports (see `context/management/plan_avances.md`), `YYYY-MM-DD_topic.ipynb` for the rest.

Run one top to bottom on the real data (`uv run dvc pull` first):

```sh
uv run jupyter nbconvert --to notebook --execute --inplace deliverables/Avance3.39.ipynb   # keeps outputs for reading
uv run pytest --nbmake deliverables/Avance3.39.ipynb                                       # execution check (about 6 min)
```

`Avance3.39.ipynb` runs the baseline and its diagnostics (`nox-ml diagnose`) itself, so it needs the data and takes several minutes; the notebook declares a 30 min cell timeout for nbmake.

## HTML exports

`bin/export-notebooks` executes every notebook in this folder (recursively) and writes the HTML to `docs/entregables/html/`, keeping the relative names (`deliverables/a/b.ipynb` → `docs/entregables/html/a/b.html`). It needs the data (`dvc pull`) and works on Linux and macOS.

```sh
bin/export-notebooks                          # all notebooks
bin/export-notebooks deliverables/<name>.ipynb  # only some
NOTEBOOK_TIMEOUT=7200 bin/export-notebooks    # seconds per cell (default 3600)
```

The HTML keeps the outputs (the notebooks themselves stay without them). Export on the owner's machine, where all the runs exist (cloud exports are incomplete), and commit the files in `docs/entregables/html/`; the large-file hook skips that folder. List the new notebook in [`docs/entregables/README.md`](../docs/entregables/README.md).
