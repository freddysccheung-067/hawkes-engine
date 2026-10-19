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

- At M=2, N=1000 the core runs at about 37 ns/event against the reference's
  about 453 ns/event, roughly 12x. The ratio grows with N because the
  reference is O(N^2) and the core is O(N); the largest comparison the
  benchmark file carries is N=1000, so no larger figure is claimed.
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

H6 (trust calibration) is the next gate. It will run a pre-registered study
across the (M, N, ρ, events-per-parameter, decay structure) grid and report
measured bias and coverage for every region, so that a user reading `reliable`
knows what that means in their configuration.

H7 (performance characterisation) will measure wall-clock time and memory across
the same grid and document what scale of problem the library handles before
bootstrap standard errors or a large M make a fit unacceptably slow.

H9 is the first PyPI release.
