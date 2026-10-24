# Contributing

1. Run `bin/uptodate` once per machine and whenever `uv.lock` changes.
2. Work on a branch and open a pull request to `main`.
3. Before each commit, pre-commit runs formatting, lint, type checks and fast tests. To run everything: `bin/check`.
4. New code comes with tests according to its risk ([`docs/testing.md`](docs/testing.md)).
5. Decisions that change the method or the architecture are recorded in `context/decisions/` (one short ADR).
6. Data is added with `uv run dvc add <path>` and uploaded with `uv run dvc push`, never with git.
7. Credentials (`~/.netrc`, DagsHub tokens) never enter the repository.

## Style

- Code, comments and docstrings in English; notebooks and reports in Spanish.
- Small, pure functions in `physics/` and `inversion/`; side effects (files, network) in `data/` and the CLI.
- A test describes one behavior: `test_<what>_<when>`, with a single reason to fail.
