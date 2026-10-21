# Contributing

The project is pre-alpha and its gates are sequential (see
[docs/ROADMAP.md](docs/ROADMAP.md)). The most useful contribution is a defect report
against the specification, the reference implementation, or a figure in the
documentation that a committed output does not support.

## Build and test

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"     # .venv\Scripts\ on Windows
.venv/bin/python -m pytest -q -m "not slow"
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy python/hawkes_engine
.venv/bin/python -m sphinx -W --keep-going -b html docs docs/_build/html
```

A C++20 compiler and CMake 3.24 are required. After editing `cpp/` or
`CMakeLists.txt`, re-run `pip install -e .`; editing only Python does not need it.
[docs/install.md](docs/install.md) has the details per operating system.

## Rules the code is held to

- `oracle/hawkes_oracle.py` is frozen. A pre-commit hook rejects edits to it. If it
  is wrong, follow [docs/verification-rule.md](docs/verification-rule.md): amend the
  specification first, then the reference, then re-tag.
- `docs/spec/mathematics.md` is upstream of the code. If the two disagree, find out
  which is wrong before changing either.
- A test is never loosened to make it pass. A failing gradient check is information.
- `docs/preregistration.md`, `studies/theta0.json`, `studies/results/cells/` and
  `studies/results/analysis/` record a finished study and are not edited. A change
  to the design would be a new study with its own pre-registration.
- A number in the README or a published page must come from a committed output.
  `tests/test_docs_claims.py` pins the headline ones to their sources; add a figure
  there when you add it to a page. If a page and a measurement disagree, the page
  changes.
- No emoji in source, tests, documentation or CI output.
- Commit messages are imperative and under 72 characters, with a body saying why.

## Examples

`examples/` holds short, seeded scripts that print their result. Each runs under
`tests/test_examples.py`; a new one needs an entry there with a line it must print.
