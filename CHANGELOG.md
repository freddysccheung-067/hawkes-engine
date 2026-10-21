# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is pre-alpha.

## [0.1.0] - <!-- RELEASE_DATE -->

The first release. It is a pre-alpha research release, and the notes lead with what
the study found rather than with what was added:
[`docs/release_notes_0.1.0.md`](docs/release_notes_0.1.0.md).

### Measured

- The reported standard errors understate sampling spread. Pooled over the 12
  two-type cells with at least 2000 events, the ratio of mean reported standard
  error to empirical standard deviation is 0.779 +/- 0.011; the decay block is 0.61.
- Two pre-registered hypotheses, H6.3 and H6.4, were not confirmed. H6.6 was
  confirmed but is 96.4 percent mechanical.
- The estimator is undefined where the observation window holds a fraction of one
  decay time: 67 of the 128 cells.

### Added

- The calibration map from the H6 study: `hawkes_engine.trust_lookup` and
  `MapAnswer`, shipped inside the wheel so an installed package can answer without
  the repository.
- A user guide: quickstart, concepts, fitting, trust, limits, performance and an API
  reference, built with `sphinx-build -W`.
- `examples/`: five seeded scripts, run in CI.
- `tests/test_docs_claims.py`, which pins quoted figures to the committed outputs
  they come from, and `tests/test_docs_code.py`, which runs the code blocks.
- `tests/test_version.py`, which holds every copy of the version string equal.
- `CITATION.cff`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/RELEASING.md`.
- Wheels for CPython 3.10 to 3.12 on Linux x86-64, macOS (x86-64 and arm64) and
  Windows AMD64, plus an sdist, built by CI and published by trusted publishing.

### Changed

- Public docstrings state parameters, return values and the constraint that
  matters, and no longer refer to calibration as future work.
- The README and the documentation front page lead with what was measured and what
  was not established.
- The version is read from `hawkes_engine._version`; `docs/conf.py` no longer
  repeats it, and the compiled core reports the version it was built as.

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
