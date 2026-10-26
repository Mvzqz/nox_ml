# Installation

Requirements: Linux or macOS with `curl` and `git`. `bin/uptodate` installs the rest (uv and Python 3.12).

```sh
git clone https://github.com/Mvzqz/nox_ml.git
cd nox_ml
bin/uptodate
```

`bin/uptodate` also installs the `pinn` extra (torch, CPU build on Linux), needed by `nox_ml.models.pinn`. Without it everything else works, but `pinn_plume` is not registered and `bin/check` cannot type-check or test it.

## Data (DVC + DagsHub)

Data lives in the (private) DVC storage on DagsHub. With access to the DagsHub repository:

```sh
uv run dvc remote modify origin --local auth basic
uv run dvc remote modify origin --local user <dagshub-user>
uv run dvc remote modify origin --local password <dagshub-token>
uv run dvc pull
```

Credentials stay in `.dvc/config.local`, which git ignores.

## Optional credentials

- **NASA Earthdata** (`~/.netrc`, machine `urs.earthdata.nasa.gov`): only to re-download TEMPO from the source.

## Notebooks

```sh
uv run jupyter lab notebooks/
```
