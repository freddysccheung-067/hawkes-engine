# Project state after gate H5

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
- Peak memory has not been measured. `tests/test_zero_copy.py` asserts no RSS
  growth across 20 repeated simulate calls, which catches the leak class but
  is not a memory budget for a fit.

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
coverage, which are properties of the estimator and are the subject of H6. None
of the thresholds is calibrated; they are engineering judgement until H6
replaces them with measured values.

## What is open

### Gaps in coverage

- The calibration map that converts a `"reliable"` verdict into a measured bias
  and coverage statement is H6. Until that gate, the verdict is a conditioning
  report, not a trust guarantee.
- The performance characterisation (H7) will measure wall-clock time and memory
  across the full parameter space (M, N, ρ, decay structure) rather than report
  one machine's figure for a single configuration.
- No PyPI wheels. The first release is H9. Until then, install from source or
  from a CI wheel downloaded manually from the Actions tab.

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

Not yet done at this commit: the harness (`studies/grid.py`, `run_cell.py`,
`collect.py`), the pilot that measures real per-replication cost, the run itself,
the shipped parquet, the `trust.py` lookup, the paper and the figures.

H7 (performance characterisation) will measure wall-clock time and memory across
the same grid and document what scale of problem the library handles before
bootstrap standard errors or a large M make a fit unacceptably slow.

H9 is the first PyPI release.
