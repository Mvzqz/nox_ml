# Deliverables

Progress notebooks for the advisor and published documents, written in Spanish. Notebooks **only reuse functions** from `nox_ml` (no logic of their own), are stored without outputs (nbstripout), and CI checks that they execute.

Naming: `YYYY-MM-DD_topic.ipynb`.

`experimentos/` holds the experiment notebooks (`01_transporte`, `02_emision_vs_clima`, `03_ajuste_pinn_puff`, `04_ablacion`, `05_viento_y_objetivo`), numbered instead of dated because they are read in order. They call `nox_ml.validation.report_experiments` and need the data (`dvc pull`); 03 reads `runs/` and says what is missing when a run does not exist on the machine; 04 and 05 run `nox-ml diagnose` the first time if `runs/baseline/diagnostics/` is not there (about 8 minutes). Executing all five takes about 10 minutes (`pytest -m slow ml/tests/test_notebooks_experimentos.py`).
