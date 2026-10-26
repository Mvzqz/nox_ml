# nox_ml

Measurement-based estimation of **NOₓ emission changes** by zone, combining monitoring stations, the TEMPO satellite and a physical transport model to separate the effect of emissions from the effect of weather. Proof of concept for Mexico City, with Los Angeles as a control and Bogotá as a no-satellite case.

## Objective

Estimate how much the NOₓ emissions of each zone of a city change (for example, between weekdays and Sundays, or under traffic restrictions) from measurements alone, separating the effect of emissions from the effect of weather. The models must estimate emissions, not just interpolate concentrations; they are compared with the same validation scheme (leave one station out, placebo tests) so the final model can be justified beyond a single metric.

## Team 39

| Member | ID |
|---|---|
| Isabella Arango Restrepo | A01796305 |
| Isaí Ambrocio | A01625101 |
| Manuel Alejandro Vázquez Meza | A01796404 |

## Course requirements

| Course element | Where it lives |
|---|---|
| README (description, objective, members, structure) | This file |
| Data | [`data/`](data/) (versioned with DVC) and its catalog [`data/README.md`](data/README.md): origin, license and access of every source |
| Notebooks | [`notebooks/`](notebooks/); executed HTML exports in [`docs/entregables/html/`](docs/entregables/html/) |
| Documentation (including the deliverables of weeks 1, 2, 8 and 9) | [`docs/`](docs/) and [`docs/entregables/`](docs/entregables/README.md) |

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
| `ml/` | `nox_ml` package: data, physics, inversion, models, validation and the `nox-ml` CLI |
| `app/` | `nox_app` package: user interface (Streamlit). Reads exported results only |
| `tests/` | End-to-end tests (ML → exported results → app). Unit tests live in each package |
| `configs/` | Per-city and per-experiment configuration |
| `context/` | Technical knowledge, decisions (ADRs) and project management (in Spanish, except ADRs) |
| `docs/` | How to install, use, test and contribute; model contracts in [`docs/models.md`](docs/models.md); course deliverables in [`docs/entregables/`](docs/entregables/README.md) |
| `notebooks/` | Progress notebooks for the advisor and published documents (in Spanish) |
| `data/` | Data, versioned with DVC (DagsHub), never with git; catalog in [`data/README.md`](data/README.md) |
| `bin/` | `uptodate`, `check`, `export-notebooks` and pipeline scripts |

Research-phase code lives in a separate folder and is migrated here piece by piece, deciding each time what comes in.

## Language

Code, comments, and code documentation (READMEs, ADRs, `docs/`) are in English. Notebooks, reports and `context/` (except ADRs) are in Spanish.

## Values

Simple over complex; expressive tests and readable code; runs the same on Ubuntu, macOS and the cloud; test coverage based on risk; fast feedback loops.
