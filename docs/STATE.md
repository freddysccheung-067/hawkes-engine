# Project state after gate H10

## What is measured

### Correctness

- The compiled likelihood and gradient agree with the frozen reference to a
  measured 7.5e-14 relative on the value and 3.6e-12 per gradient entry. The
  measurement grid is M in {1,2,3,4,6} x N in {1,2,10,50,200,1000}, 30
  configurations, every entry of every gradient block compared; the assertions
  add N in {0,1,2} and the shared-decay variants.
- The reference itself is verified against complex-step differentiation over
  every parameter entry and every block, across 20 configurations
  (M in {1,2,3,4} x N in {1,2,10,50,200}), at 1e-9.
- Both simulators reproduce the stationary mean within two between-path
  standard errors across 400 paths at each of 9 (M, rho) configurations, 18
  checks in all. They agree with each other on counts (Mann-Whitney U plus
  two-sample Kolmogorov-Smirnov per dimension) and on pooled gaps
  (two-sample KS, Bonferroni over pairs).
- Time-rescaling under the true parameters passes both the Kolmogorov-Smirnov
  test against Exp(1) and the Ljung-Box test for independence (p > 0.05) on 10
  checks (5 (M, rho) cases x 2 methods), each with a negative control that must
  reject.
- The zero-copy contract is proved: `test_zero_copy.py` asserts that the C++
  core receives the caller's buffer, not a copy of it, by comparing data
  addresses across the language boundary.
- The GIL-release contract is proved: `test_gil.py` runs a Python counter during
  a C++ call and measures its rate against its solo rate. The ratio is above 0.8
  for calls over one second and above 0.4 for the push-time smoke test, well
  above the 0.35 a call that holds the GIL produces.

### Performance

All figures below are from `benchmarks/results/*_2026-10-19.csv`, one machine:
Windows 11, MSVC 19.44, Python 3.12.10, Intel Family 6 Model 198 (Alder Lake
class). They are not claims about other hardware.

- At M=2 the reference takes 0.453 s for N=1000 (0.453 us/event, measured). The
  core takes 41.9 ns/event at N=100000, so about 42 us for N=1000 if the
  per-event cost holds, which is roughly four orders of magnitude. The core
  figure is extrapolated: the benchmark file measures N in {1e5, 1e6} only, and
  the ratio grows with N because the reference is O(N^2) and the core is O(N).
- Simulation throughput spans 3.7e6 to 22.3e6 events/s for thinning and 3.6e6
  to 7.9e6 for cluster over M in {2,4,8} x rho in {0.5,0.9}.
- `fit` cost at M=2: 49 ms per iteration at N=1e5, 217 ms at N=1e6. At M=4,
  39 ms and 368 ms. A Hessian pass adds `2 n_params` gradient evaluations.
- Peak memory was not measured at H5. `tests/test_zero_copy.py` asserts no RSS
  growth across 20 repeated simulate calls, which catches the leak class but
  is not a memory budget for a fit. H7 measured it; see the H7 section below.

### Reliability

Every fit returns a `reliable` verdict of `"reliable"`, `"marginal"` or
`"unreliable"`. The verdict is built from:

- The condition number of the observed information matrix
- Whether a coordinate stopped on a search bound
- The branching ratio ρ
- The alpha-beta correlation implied by the covariance
- The event count per free parameter

A `"reliable"` fit is a well-conditioned stationary point, with no coordinate on
a bound, whose condition number is below 1e6 and whose events-per-parameter is
above 10 (the thresholds in `trust.THRESHOLDS`). It says nothing about bias or
coverage, which are properties of the estimator. H6 measured the verdict against
coverage but did not recalibrate it: the thresholds are still engineering
judgement, and 3211 fits whose beta estimate was more than ten times the truth
were labelled `reliable` (H6 section below).

## What is open

### Gaps in coverage

- The verdict is a conditioning report, not a trust guarantee. The H6 map reports
  measured coverage for a regime; it does not change the verdict.
- 0.1.0 is published on PyPI with the full wheel matrix. PyPI publication is
  triggered by a trusted-publishing workflow; see `RELEASING.md` for the steps a
  later release has to follow.

### Known limitations

- Python 3.13 and 3.14 are not built. The wheel matrix is cp310-cp312.
- musllinux is not built. The core has no libc-sensitive dependency.
- No 32-bit or ARM Windows wheels.
- `se_method="bootstrap"` refits the model `n_bootstrap` times and is slow. The
  default is `"hessian"`.
- The estimator does not accept inequality constraints on α or β beyond
  positivity. Constraints like "α_ii = 0 for all i" (no self-excitation) are
  expressible through `zero_diagonal`, but arbitrary linear inequalities are not.
- The likelihood assumes all events are observed. Partial observation, missing
  data and censoring are not modelled.

### Design decisions that constrain the public API

- ADR-002: rows are targets, columns are sources. This is the transpose of some
  references but the convention of others (Liniger, Bacry). It is frozen.
- ADR-006: no `-march=native` wheels are published. A wheel that crashes on an
  older CPU rather than running slower is a support nightmare.
- The reference implementation is frozen. A defect in it is a defect in the
  specification, not a bug to patch.

## What is next

H6 (trust calibration) has begun. **The design is frozen and tagged
`H6-preregistration`** at commit `7bb8fae`, before any H6 measurement. The
preregistration is [`preregistration.md`](preregistration.md) and the prior
evidence it builds on is [`studies/PRIOR_EVIDENCE.md`](../studies/PRIOR_EVIDENCE.md).

Frozen so far:

- **Question, estimands, six hypotheses, grid, R, correction and stopping rule**
  in the preregistration. 128 cells: 120 at M=2 over N, rho, beta·delta and a
  decay scale, plus an 8-cell M=4 satellite.
- **`R = 2000`** replications per cell, derived from the Monte Carlo standard
  error of an estimated coverage and of a relative bias, not chosen for
  roundness. Cost projection is 13.0 h single-core at 8 workers.
- **The grid itself**, frozen in `studies/theta0.json` with canonical digest
  `f735ae41…`. Generation is `studies/make_theta0.py`; the run must match the
  digest or refuse to start.
- **Confirmatory status is partial and disclosed.** H3 measured a 4.63-sigma
  excess at 2000 events before H6 was designed, so H6.1 and H6.2 are labelled
  exploratory in the preregistration and cannot carry the paper's headline.
  H6.5 (reported SE versus empirical SD) and H6.6 (does the verdict separate
  coverage) are the confirmatory results.

**The full grid has run.** 128 cells, 2000 replications each, 256 000 rows,
12 workers, 6763 s (1.88 h) against the pilot's 0.8 h estimate at 12 workers,
because the five most expensive M=4 and N=50000 cells ran serially at the tail.
Every cell was produced at commit `58b6b0b`, which appended Amendment 3, so the
run followed the final design freeze. `python -m studies.collect` reports 128 of
128 complete with every checksum verified; `studies/results/manifest.json`
records the per-cell hashes. The raw rows (185 MB) are gitignored and exist only
on the machine that ran the study.

What the raw rows show, before any estimand, is in
[`studies/RUN_REPORT.md`](../studies/RUN_REPORT.md). Two findings were recorded
before `analyze.py`, and Amendments 4 and 5 responded to them:

- **The `c = 1e-3` half of the grid is estimator-undefined.** `beta_min * T` is
  below 3 in 15 of 20 `r = 0` cells there; 75 percent of those fits return no
  standard error and the fitted beta runs to its upper bound, with or without
  quantisation. Amendment 3.3's "resolved" rule will likely leave H6.4 inconclusive.
- **At `c = 1` and small N, a share of converged fits return an implausible beta
  and are labelled `reliable`.** 5454 fits across the 20 `M = 2`, `r = 0` cells,
  3211 of them `reliable`. A count, not a test; H6.6 is still decided by its
  pre-committed rule.

**The pre-registered analysis has run** (`studies/analyze.py`, all 128 cells, 1000
bootstrap resamples per cell). Status: **H6 is complete.** All six hypotheses have
a final label, the four owner decisions are resolved (`studies/ANALYSIS_NOTES.md`
D1-D4), and the map ships in the wheel.

Headline: the inverse-Hessian standard errors understate sampling spread, pooled
`q = mean SE / SD = 0.779 +/- 0.011` over the 12 `M = 2`, `N >= 2000`,
`c = 1`, `r = 0` cells, confirmed after Holm; the `M = 4` satellite agrees in direction
(`0.336 +/- 0.023`).

| Hypothesis | Status | `T` | `tau` | `SE` | `z` | `p` | Holm | Final label |
|---|---|---|---|---|---|---|---|---|
| H6.1 | exploratory | 0.2325 | 0.05 | 0.0367 | 4.98 | 3.25e-07 | outside family | **confirmed (exploratory)** |
| H6.2 | exploratory | 0.171 | 0.9 | 0.00842 | 86.59 | <1e-300 | outside family | **confirmed (exploratory)** |
| H6.3 | confirmatory | 0.01672 | 0.0 | 0.00589 | 2.84 | 0.00224 | step 3, 0.025 met | **not confirmed** |
| H6.4 | confirmatory | -1.696e+07 | 0.01 | 3.5e+06 | -4.85 | 1 | step 4, 0.05 missed | **not confirmed** |
| H6.5 | confirmatory | 0.7791 | 1.0 | 0.0114 | 19.35 | 1.08e-83 | step 2, 0.01667 met | **confirmed** |
| H6.6 | confirmatory | 0.7751 | 0.02 | 0.0112 | 67.24 | <1e-300 | step 1, 0.0125 met | **confirmed** |

Generated from `studies/results/analysis/hypotheses.json`. Where the admissible
forms of an SE or population combination disagree, the label is the least
favourable one any of them produces (Amendment 6.3), so a disagreement can only
weaken a claim.

- **H6.6 is confirmed but mostly mechanical.** 96 percent of `unreliable`
  replications carry no standard error, which E3.5 scores as a miss. Among those that
  carry one, a post hoc check gives a separation of about +0.07 +/- 0.04. The paper
  does not lead with it (D2).
- **H6.3 is not confirmed** because coverage rises from `rho = 0.3028` to `0.60`,
  failing the monotonicity clause, although the threshold clause holds.
- **H6.4 is not confirmed**, and the direction is the result: at `N >= 10 000`
  quantisation biases `beta` **downward** by 37 to 62 percent, the opposite of the
  hypothesis. The large negative mean over all 22 cells is an artefact of the heavy
  tail in the small-`N` cells' `r = 0` arm.

Owner decisions, all resolved on 2026-10-21 (`studies/ANALYSIS_NOTES.md`):

1. **D1, H6.4:** Amendment 6 keeps all 22 cells, adopts the independent-cell SE,
   and takes the weakest label when forms disagree.
2. **D2, H6.6:** the paper does not lead with it; H6.5 is the headline.
3. **D3:** the 0.5 `no_se_rate` threshold for the map's `estimator_undefined` flag
   is confirmed.
4. **API and packaging:** `trust_lookup` and `MapAnswer` are in `__all__` with a
   pinned-surface test, and CMake installs the map to `hawkes_engine/data/` so an
   installed wheel answers from it.

Shipped: `data/trust/v1_excitation_only.csv` (128 rows, study `h6-v1`),
`hawkes_engine.trust_lookup`, `paper/draft.md` (generated by
`studies/make_paper.py`, not submitted), and four figures in `studies/figures/`.

**H7 is complete.** Performance is characterised on one machine in
[`benchmarks/results/capability_2026-10-21.md`](../benchmarks/results/capability_2026-10-21.md),
generated by `benchmarks/capability_report.py` from the CSVs beside it. The H6
outputs are untouched.

- **Wall clock.** Pair decay, `se_method="hessian"`, N about 1e6: M=2 takes 7 to
  10 s, M=4 42 to 55 s, M=6 4.9 min, M=8 12 to 14 min. The one-hour wall was not
  reached; nothing above N = 1e6 was timed.
- **Memory.** About 33 bytes per event, near-independent of M and unchanged by the
  Hessian pass. N = 1e7 peaks at 316 MiB above the import baseline; memory does not
  bind before time does.
- **Hessian.** A fixed 4P gradient evaluations, 29 to 50 percent of a fit at
  N = 1e6. At M >= 6 and N about 1e4 the iteration count dominates instead (up to
  2765 iterations), and those fits are mostly labelled `marginal` or `unreliable`.
- **Bootstrap.** B = 200 at M=4, N=1e5 costs 8.5 min on one worker, 2.3 min on four
  and 86 s on the default 24-process pool. Larger bootstrap configurations were not
  timed.
- **Hot loop.** Profiled with cProfile and a timing decomposition (no native
  profiler was available). Nothing cheap and safe to fix; no code changed.

Single-run cells at N = 1e6 carry no spread, and everything is one machine.
Owner actions: run `capability_wall.py` and `capability_memory.py` on a Linux machine
to exercise the `VmHWM` path and a second CPU; optionally time the bootstrap at
M=4, N=1e6 and at M >= 6, which would take hours.

**H8 is complete.** Documentation and runnable examples, organised around the
places where the library can mislead rather than around its features.

- **Pages** (`docs/`, built with `sphinx-build -W --keep-going`): `quickstart`,
  `concepts`, `fitting`, `trust`, `limits`, `performance`, `reference`, with
  `install`, `ROADMAP` and `verification-rule` as before. `spec/`, `adr/`,
  `preregistration.md`, `competitor-analysis.md` and this file stay in the
  repository and out of the toctree. The hypothesis table, the wall-clock,
  bootstrap and pair-against-shared tables are extracted from the committed
  outputs by `docs/_gen.py` at build time (`docs/_generated/` is gitignored).
- **Examples** (`examples/01` to `05`, each under 60 lines, seeded, run by
  `tests/test_examples.py`): simulate and fit; the time-rescaling check under the
  truth, a wrong baseline and a fitted model; the three `trust_lookup` outcomes;
  a 50-replicate look at the standard-error ratio; pair against shared decay.
- **Claims test** (`tests/test_docs_claims.py`) pins these figures to their
  sources: q = 0.779 +/- 0.011, the beta block 0.61 (and the mu and alpha blocks
  and the satellite), 128 cells, 2000 replications, 67 undefined cells, 96.4
  percent of `unreliable` fits with no SE, +0.0726, 5454 and 3211 heavy-tail fits,
  the 13.8 min and 828.62 s wall figures, the bootstrap costs in the fitting
  guide, and the labels of H6.3 to H6.6 and H6.1/H6.2. It also checks that every
  repository link resolves, that no published page uses an unmeasured adjective,
  and that the toctree matches the pages. `tests/test_docs_code.py` runs every
  code block in them.
- **What the examples revealed.** The README's old example (T = 2000, seed 1)
  returned beta of about 452 against a truth of 1.7, converged and labelled
  `reliable`, and the time-rescaling check also passed it; both are now on the
  Limits page. Separately, example 04's 50 replicates at the anchor cell did not
  reproduce q < 1 for the alpha block (it came out at 1.118), which its header
  says; the pooled result over 12 cells is what supports the finding.
- **Stale text corrected.** `paper/draft.md` (regenerated from
  `studies/make_paper.py`) still said H6.4 awaited a decision and counted five
  amendments; ROADMAP called the map "validated"; this file's heading was H5.

Remaining for H9: the PyPI release itself (trusted publishing, a version bump
from `0.1.0.dev0`, the first `CHANGELOG` entry); GitHub private vulnerability
reporting, if SECURITY.md is to point at it; and the decision below.

**Owner decision.** `ljung_box` and `ReliabilityReport` are used in the docs but
are not in `__all__` (the surface is pinned by `tests/test_api.py`). The docs
import `ljung_box` from `hawkes_engine.diagnostics`. **Resolved 2026-10-25: both
are exported.** The reason is that each was a completeness gap rather than a
design choice — `ljung_box` is the third of three diagnostics of which `ks_test`
and `qq_data` already shipped, and `ReliabilityReport` is the documented return
type of `report`, which shipped, so a user could call `report()` and receive an
object they could not name. Exporting a docstring also exposed that
`ljung_box`'s had no Parameters section; it has one now, because the pinned
surface test checks it.

**Next: H9 (v0.1.0 release).**

**H9 is complete.** `v0.1.0` is tagged and published: wheels for CPython 3.10 to
3.12 on Linux x86-64, macOS (x86-64 and arm64) and Windows AMD64, plus an sdist,
uploaded by trusted publishing. `CITATION.cff` carries the Zenodo version DOI
`10.5281/zenodo.23613789` and the concept DOI `10.5281/zenodo.23613788`.

**H10 is complete: the calibration-driven interval, and the submission paper.**
0.2.0 is the release in which the calibration study drives the estimator.

- **`se_method="auto"`.** The fit looks its own regime up in the shipped map and
  acts on what was measured: bootstrap where an estimated block's 2-SE interval
  around `q` excludes 1, the Hessian (labelled uncalibrated) outside the map,
  and no interval where the map reports the estimator undefined. The rule, the
  threshold and the cost limit are in [`se_policy.md`](se_policy.md), written
  before the code.
- **The cost limit.** `auto_max_seconds` defaults to 120. The projection is a power
  law fitted to the four measured serial rows of the capability table and
  reproduces each within 3 percent; a projection above the limit keeps the Hessian
  interval, records why, and warns. Measured during the build: a bootstrap at
  M=2, N~2000 costs about 0.2 s of work per replication, against 0.4 s of
  process start-up when a pool is used for a single worker.
- **`FitResult.se_source`, `se_note` and `auto`.** Schema 2; schema-1 documents
  still load.
- **`workers=1` in the bootstrap now runs in-process**, which removed 200 process
  spawns per fit and cut the auto study's replication cost from 3.6 s to 1.8 s.
- **The auto-v1 study** is pre-registered in
  [`preregistration_auto.md`](preregistration_auto.md) with three cells at 2000
  events, both arms on the same event streams, and is reported in
  `studies/results/auto/analysis/report.txt`.
- **The paper.** `paper/main.tex` is generated by `studies/make_paper_tex.py`; every
  number and table is emitted from a committed output. `studies/check_paper.py`
  verifies the structure that does not need a TeX installation, because none was
  available to this session: every macro defined once, every `\input` present,
  every table's cell count matching its column spec, every citation resolving to a
  bibliography entry with a year and a DOI or arXiv id. Six of the seven
  bibliography entries were checked against the publisher record during the build;
  the Chen & Hall DOI was corrected from `...0095` to `...0096` by that check, and
  the Laub identifier is left marked `[VERIFY]` because the sources disagreed.
- **Blocker resolved.** The paper now compiles. A `Paper` workflow installs TeX
  Live, typesets the committed tree, fails on an overfull box or an unresolved
  citation, test-compiles the arXiv archive in isolation, and uploads both. The
  first real compile found twenty macros whose names contained digits
  (`\Hsix61Label`), which TeX read as `\Hsix` followed by literal text and which
  `check_paper.py` could not see because its own pattern stopped at the letter.
  Both are fixed, and the check now rejects a non-letter macro name.
- **The paper is deposited on HAL**, identifier `hal-05838093` reserved on
  2026-10-25, and is **in moderation**: the record is not public until a moderator
  accepts it, and until then both the public URL and the depositor-side `docid`
  view return nothing to anyone else. HAL needs no endorsement, which is why it
  was chosen. arXiv is still pending an endorsement for `stat.ME`. Every
  bibliography entry has been checked; the Laub identifier resolved to
  `1507.02822` and is no longer marked `[VERIFY]`.

## What is next

Written 2026-10-25, after the round of work recorded above. Each line says what is
known and what would settle it; none of these is a target.

### Shipped, but not yet on PyPI

- **cp313 and cp314 wheels build; they have not been released.** `CIBW_BUILD`
  covers cp310 to cp314 and the test matrix runs 3.13 and 3.14, so the source is
  known good on those interpreters — a cp313 wheel was built locally and passed
  `CIBW_TEST_COMMAND`. They reach a user only with the next release, which needs
  a version bump and a tag; neither is part of the change that added them.
- **The `Development Status` classifier moved to `3 - Alpha`**, with
  `docs/index.md`, `CONTRIBUTING.md`, `SECURITY.md` and `CHANGELOG.md` moved with
  it. ADR-009 is unchanged: 0.x minors may still break the surface.

### Open defects and gaps

- **`se_source` is wrong for an explicit bootstrap.** `fit(...,
  se_method="bootstrap")` returns `se_source="hessian"`, which contradicts what
  `FitResult.se_source` documents and what `auto` reports for the same method.
  The initialiser in `fit.py` never sets it for that branch, and
  `test_se_source_and_se_never_contradict` passes only because it asserts
  membership in a set rather than the value. Not fixed, because it was found
  while working on the bootstrap pool and is a separate defect.
- **The bootstrap pool is unreliable at the default worker count.** Measured 2
  failures in 25 runs of the README's `auto` block, and a death after 12 of 200
  replications. A dead pool now falls back to computing the replications in the
  caller, which gives the same draws at a wall time that is not the same (36.69 s
  serial against 5.47 s pooled at 24 workers). The pool itself is still not
  trustworthy, which is worth a native diagnosis; lowering the worker count was
  rejected as hiding it.
- **The serial fallback cannot be distinguished from a missing guard by outcome**
  in one case: both are `BrokenProcessPool`. It is told apart by how many
  replications completed first, which is 0 unguarded and was 12 under load at this
  size. A race that kills the pool before its first completion would still be
  reported as a guard failure.
- **The calibration map covers pair decay only.** `shared_decay=True` is M decay
  rates rather than M², sits outside the map, and `se_method="auto"` therefore
  falls back to the Hessian and labels the interval uncalibrated. For a user with
  more types than events that is the model they would fit, so it is the largest
  known gap in what `auto` can do.
- **The paper states a measurement it did not run.** Its theory section derives
  the sandwich covariance `I^-1 J I^-1` and names a correctly evaluated `J` as the
  natural candidate for closing the measured gap, and then says the study stored
  no per-replication Hessian, so it could not be tested. That is accurate, and it
  is the one place the paper says "cannot test" where a rerun could say "tested".

### Awaiting the world, not this repository

- **HAL** `hal-05838093` is in moderation. The API indexes public records only and
  does not answer for it; nothing on this side changes that. When it is accepted,
  `CITATION.cff`, the HAL paragraph above and the release notes should name the
  URL.
- **arXiv** `stat.ME` needs an endorsement. There is no preprint identifier, and
  `CITATION.cff` therefore carries no `preferred-citation` rather than an
  unpublished one.
