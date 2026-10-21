# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is pre-alpha
and has no released version.

## [Unreleased]

### Added

- User guide: quickstart, concepts, fitting, the trust map, limits, performance and
  an API reference, built with `sphinx-build -W`.
- `examples/`: five seeded scripts, run in CI by `tests/test_examples.py`.
- `tests/test_docs_claims.py`, which pins figures quoted in the README and pages to
  the committed outputs they come from, and `tests/test_docs_code.py`, which runs the
  code blocks in them.
- `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`.
- Calibration map from the H6 study, `hawkes_engine.trust_lookup` and `MapAnswer`.
- Capability table: wall clock, memory and bootstrap cost on one machine.

### Changed

- Public docstrings now state parameters, return values and the constraint that
  matters, and no longer refer to calibration as future work.
- The README and the documentation front page lead with what was measured and what
  was not established.
