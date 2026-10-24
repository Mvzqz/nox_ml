# nox_ml

Measurement-based estimation of **NOₓ emission changes** by zone, combining monitoring stations, the TEMPO satellite and a physical transport model to separate the effect of emissions from the effect of weather. Proof of concept for Mexico City, with Los Angeles as a control and Bogotá as a no-satellite case.

## Getting started

```sh
bin/uptodate     # installs uv, libraries, pre-commit hooks and data (DVC)
bin/check        # the same fast checks CI runs
uv run nox-ml --help
```

Details in [`docs/installation.md`](docs/installation.md).

## Layout

| Folder | Contents |
|---|---|
| `ml/` | `nox_ml` package: data, physics, inversion, validation and the `nox-ml` CLI |
| `app/` | `nox_app` package: user interface (Streamlit). Reads exported results only |
| `tests/` | End-to-end tests (ML → exported results → app). Unit tests live in each package |
| `configs/` | Per-city and per-experiment configuration |
| `context/` | Technical knowledge, decisions (ADRs) and project management (in Spanish, except ADRs) |
| `docs/` | How to install, use, test and contribute; model contracts in [`docs/models.md`](docs/models.md) |
| `deliverables/` | Progress notebooks for the advisor and published documents (in Spanish) |
| `data/` | Data, versioned with DVC (DagsHub), never with git |
| `bin/` | `uptodate`, `check` and pipeline scripts |

Research-phase code lives in a separate folder and is migrated here piece by piece, deciding each time what comes in.

## Language

Code, comments, and code documentation (READMEs, ADRs, `docs/`) are in English. Notebooks, reports and `context/` (except ADRs) are in Spanish.

## Values

Simple over complex; expressive tests and readable code; runs the same on Ubuntu, macOS and the cloud; test coverage based on risk; fast feedback loops.
