# hawkes-engine 0.1.0

Released 2026-10-24. This is the first release. It is a pre-alpha
research release: the library works, the study behind it is finished, and what the
study found is less flattering than what a first release usually advertises. That
finding is the first section, because it is the reason to read the rest.

The API may change between 0.x minor versions. See
[ADR-009](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/adr/ADR-009-versioning.md)
for what 0.1.0 promises and what a 0.2.0 may break.

## What this is

Multivariate Hawkes processes with exponential kernels for Python: a compiled
likelihood and gradient, a maximum-likelihood fit with standard errors, two
independent exact simulators, time-rescaling diagnostics, and a lookup of what a
pre-registered simulation study measured about the fit's standard errors in a
given regime.

Rows are targets and columns are sources: `alpha[i, j]` is the excitation a type-`j`
event applies to type `i` (ADR-002).

## What was measured

Over 128 simulation cells with 2000 replications each (256 000 fits), the standard
errors the fit reports are **smaller than the sampling spread of its estimates**.

- Pooled over the 12 two-type cells with at least 2000 events, the ratio of mean
  reported standard error to empirical standard deviation is **0.779 +/- 0.011**.
  Hypothesis H6.5, confirmed after Holm correction.
- By parameter block over the same cells: **0.936** for the baselines, **0.869**
  for the excitation weights, and **0.61** for the decay rates. The decay estimate
  is where the shortfall is.
- The four-type satellite agrees in direction, **0.336 +/- 0.023**.
- A median-based companion that is insensitive to the heavy tail gives
  **0.983 +/- 0.003**. The shortfall is concentrated in the tail, not spread evenly.
- Nominal-95% intervals built from these standard errors covered between **0.918**
  and **0.953** of the time at 10 000 events and above, and as little as **0.171**
  at 200 events with a branching ratio of 0.95.

A user should read a reported standard error from this release as a lower bound on
the uncertainty, not as the uncertainty.

## What was not confirmed

Two of the six pre-registered hypotheses were not confirmed, and one confirmed
result is mostly mechanical. All three are stated in the release rather than in a
limitations appendix.

- **H6.3, not confirmed.** Coverage was expected to fall toward criticality. The
  threshold clause held (a difference of 0.0167 +/- 0.0059 between branching
  ratios 0.3028 and 0.95) but coverage rose from 0.3028 to 0.60, failing the
  pre-registered monotonicity clause.
- **H6.4, not confirmed.** Timestamp quantisation was expected to bias the decay
  estimate up. At 10 000 events and above it biased it **down**, by 37 to 62
  percent. The direction is the result.
- **H6.6 was confirmed but is 96.4 percent mechanical.** The `reliable` verdict
  separates coverage, but 96.4 percent of `unreliable` replications carry no
  standard error at all, and a replication without one counts as a miss. Among
  replications that do carry one, the separation is +0.0726 +/- 0.0394. The
  verdict marks fits that produced an interval; it does not detect an interval
  that is wrong.

The labels of all six hypotheses, with their statistics, are on the
[Trust page](https://freddysccheung-067.github.io/hawkes-engine/trust.html). The
design, with six dated amendments, is
[`docs/preregistration.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/preregistration.md).

## What the estimator cannot do

These are measured limits, not cautions.

- **It is undefined where the observation window holds a fraction of one decay
  time.** In the study this happened in **67 of the 128 cells**: all 60 at decay
  scale `c = 1e-3` and 7 at `c = 1`. In the `c = 1e-3`, exact-timestamp cells 75
  percent of fits returned no standard error and the fitted decay ran to its upper
  search bound. Nothing on the way into `fit` stops you fitting such data; check
  `beta_min * T` yourself.
- **At small `N` the decay estimate has a heavy tail the verdict does not see.**
  5454 converged fits returned a decay estimate more than ten times the truth, and
  the library labelled **3211 of them `reliable`**. At the anchor cell the decay
  estimate has median 1.305 and maximum 43914 against a true 1.2.
- **Large `M` at small `N` is slow and unreliable.** At `M >= 6` with about 10 000
  events, the optimiser needed 942 to 2765 iterations and every fit measured was
  labelled `marginal` or `unreliable`. Time is not the limit there; identifiability is.

The [Limits page](https://freddysccheung-067.github.io/hawkes-engine/limits.html)
has each of these with its evidence.

## Supported platforms and Python versions

| Platform | Architecture | Python |
|---|---|---|
| Linux | x86-64 (manylinux) | 3.10, 3.11, 3.12 |
| macOS | x86-64 and arm64 | 3.10, 3.11, 3.12 |
| Windows | AMD64 | 3.10, 3.11, 3.12 |

Not built: musllinux, 32-bit, ARM Windows, and Python 3.13 or 3.14. The wheels
target generic x86-64: no `-march=native` and no `-ffast-math`, so a wheel runs on
any machine its platform tag claims rather than crashing on an older CPU (ADR-006).

## Install

```bash
python -m pip install hawkes-engine==0.1.0
```

Building from source needs a C++20 compiler, CMake 3.24 and Python 3.10 to 3.12;
[the install guide](https://freddysccheung-067.github.io/hawkes-engine/install.html)
has the commands for each operating system.

## How to verify the preregistration

Every claim above comes from a design frozen before the data existed. A stranger
can check that it was.

- The design is at the annotated tag **`H6-preregistration`** (commit `7bb8fae`),
  an ancestor of this release.
- `git diff H6-preregistration -- docs/preregistration.md` shows **zero removed
  lines**: the six later amendments are appended, and no frozen text was edited.
- The six amendments are dated and each states what had been seen when it was
  written. Two of them (4 and 6) disclose that a decision was taken with
  knowledge of the data, and say why that is disclosed rather than hidden.
- The grid is frozen in `studies/theta0.json`, and `studies/verify_grid.py` checks
  its digest and refuses to run against a changed grid.
- The study's per-cell hashes are in `studies/results/manifest.json`, manifest
  digest `fd4b73b31c10d87f6af9f69759b6429aecc4231e3dde9dab5fa3c02d7b9f10e4`.
- The numbers in these notes are pinned to the committed outputs they come from by
  `tests/test_docs_claims.py`, so a figure that drifts from its source fails CI.

## Known limitations

- `FitResult.reliable` is a conditioning report, not a statement about bias or
  coverage.
- The calibration map covers two types (with a four-type satellite of 8 cells),
  pair decay and exponential kernels. `shared_decay=True` is a different model and
  is outside the map.
- `trust_lookup` answers from the nearest of 128 cells and gives that answer
  however far the cell is.
- Nothing above 10^6 events was timed. Every timing is from one machine.
- All events must be observed; censoring and missing data are not modelled.
- No comparison with any other library has been made, and none is implied.

## The paper

`paper/draft.md` is a draft. It has not been submitted or published, and the
citation metadata does not claim otherwise.

The archived release is at DOI [`10.5281/zenodo.23613789`](https://doi.org/10.5281/zenodo.23613789),
which pins version 0.1.0. All versions share the concept DOI
[`10.5281/zenodo.23613788`](https://doi.org/10.5281/zenodo.23613788), and cite that
one when the exact version does not matter.
