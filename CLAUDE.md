# Working in this repository

## Commands

```bash
pip install -e ".[dev]"      # build the C++ core and install
pytest                       # run the full suite
ruff check . && ruff format --check .
mypy python/hawkes_engine
pre-commit install           # enable the hooks
```

The package has a compiled core. After editing `cpp/` or `CMakeLists.txt` you
must re-run `pip install -e .`; editing only Python files does not require it.

## Rules

- `oracle/hawkes_oracle.py` is frozen. The pre-commit hook rejects edits to it.
  If it is genuinely wrong, follow `docs/verification-rule.md` — amend the spec
  first, then the reference, then re-tag.
- `docs/spec/mathematics.md` is upstream of the code. If an implementation
  disagrees with it, find out which is wrong before changing either.
- Never loosen a test to make it pass. A failing gradient check is information.
- No emoji in source, tests, docs or CI output.
- Commit messages are imperative and under 72 characters, with a body saying
  why. No trailers.

## Layout

| Path | Contents |
|------|----------|
| `cpp/` | C++20 core, built by CMake |
| `python/hawkes_engine/` | Python package |
| `oracle/` | Frozen reference implementation and its tests |
| `docs/adr/` | Architecture decisions, numbered |
| `docs/spec/` | Specification, normative |
| `tests/` | Tests for the Python package |

## Current gate

H1 is complete. H2 (C++ likelihood) is next; see `docs/ROADMAP.md`.
