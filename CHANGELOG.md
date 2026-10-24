# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is pre-alpha.

## [0.2.0] - 2026-10-24

The release in which the calibration study drives the estimator. Full notes, with
the study result and the paper status: [`docs/release_notes_0.2.0.md`](docs/release_notes_0.2.0.md).

### Changed

- **`fit(..., se_method="auto")` is new, and it can choose a different method than
  the default.** The fit looks its own regime up in the shipped calibration map and
  acts on what was measured there: where an estimated block's two-standard-error
  interval around the measured `q` excludes 1, it reports a parametric-bootstrap
  interval instead of the Hessian one; where the map does not cover the regime it
  keeps the Hessian interval and says it is uncalibrated; where the map reports the
  estimator undefined it reports no interval at all. `"hessian"` remains the
  default; `"auto"` is opt-in.
- **A fit can now take longer than it used to.** With `se_method="auto"`, a
  bootstrap may run. The projected cost is checked against `auto_max_seconds`
  (default 120) before it does, and a projection above the limit keeps the Hessian
  interval, records why, and warns rather than spending the time.
- `FitResult` gains `se_source`, `se_note` and `auto`. `se_source` is `"hessian"`,
  `"bootstrap"` or `"none"`; the serialisation schema is now 2, and schema-1
  documents still load (with `se_source` reading as `"hessian"` and no record).
- `fit` accepts `bootstrap_workers`, so a study that parallelises over fits can run
  each bootstrap serially instead of starting a pool per fit.
- `fit` raises on `n_bootstrap` below 10 for `"bootstrap"` and `"auto"`, because the
  bootstrap never reports an interval below that count.

### Added

- `docs/se_policy.md`: the decision rule, written before the feature, with the
  threshold justified from the map's own Monte Carlo error and the cost limit
  justified from the capability table.
- `docs/preregistration_auto.md`: the pre-registered study of the switch, with its
  result in `studies/results/auto/`.
- `paper/main.tex`, generated with every number emitted from a committed output by
  `studies/make_paper_tex.py`; `paper/refs.bib`; `paper/SUBMISSION.md`.
- A figure for the interval study, `studies/figures/auto_coverage.pdf`.

### Unchanged

- The likelihood, the gradient, the observed-information standard errors, the
  bootstrap itself and both simulators. This release adds a decision above the
  estimator, not new mathematics inside it.

## [0.1.0] - 2026-10-24

The first release. It is a pre-alpha research release, and the notes lead with what
the study found rather than with what was added:
[`docs/release_notes_0.1.0.md`](docs/release_notes_0.1.0.md).
