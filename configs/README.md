# Configuration

- `cities/`: domain, data sources and time zone per city (`cdmx.yaml`, `la.yaml`, `bogota.yaml`).
- `experiments/`: one YAML per experiment, validated by `nox_ml.validation.experiment.ExperimentConfig`. `nox-ml run <config>` writes `runs/<name>/` with the configuration, metrics and code version (see `docs/experiments.md`). `baseline.yaml` is the reference every improvement is compared against.
