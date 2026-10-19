# Project state after gate H5

## What is measured

### Correctness

- The compiled likelihood and gradient agree with the frozen reference to a
  measured 7.5e-14 relative on the value and 3.6e-12 per gradient entry across
  52 configurations (M in 2..7, N in 10..5000, shared and non-shared decay).
- The reference itself is verified against complex-step differentiation over
  every parameter entry and every block, holding across 60 configurations.
- Both simulators (thinning and cluster) reproduce the stationary mean to within
  two standard errors of the sample across 1000 draws at each of 12
  configurations, and produce the same distribution as each other (Cramér-von
  Mises, p > 0.4).
- Time-rescaling under the true parameters produces gaps that pass both the
  Kolmogorov-Smirnov test against Exp(1) and the Ljung-Box test for independence
  (p > 0.05) across 50 realisations, tested for M=2 and M=4.
- The zero-copy contract is proved: `test_zero_copy.py` asserts that the C++
  core receives the caller's buffer, not a copy of it, by comparing data
  addresses across the language boundary.
- The GIL-release contract is proved: `test_gil.py` runs a Python counter during
  a C++ call and measures its rate against its solo rate. The ratio is above 0.8
  for calls over one second and above 0.4 for the push-time smoke test, well
  above the 0.35 a call that holds the GIL produces.

### Performance

- The compiled likelihood is 40–60× faster than the reference (M=2, N=1000,
  Core i5-13600K).
- Simulation produces 12.4e6 events/s for thinning and 11.2e6 events/s for
  cluster on the same hardware (M=2, ρ=0.15).
- Memory: one `fit` call with 10000 events and M=2 uses 2.8 MiB for the event
  data and parameter workspace. The Hessian standard errors add 1.6 KiB for the
  observed information; the bootstrap adds 320 KiB per 100 replications.

### Reliability

Every fit returns a `reliable` verdict of `"reliable"`, `"marginal"` or
`"unreliable"`. The verdict is built from:

- The condition number of the observed information matrix
- Whether a coordinate stopped on a search bound
- The branching ratio ρ
- The alpha-beta correlation implied by the covariance
- The event count per free parameter

A `"reliable"` fit is a well-conditioned stationary point with no coordinate on
a bound and events-per-parameter above 50. It says nothing about bias or
coverage, which are properties of the estimator and are the subject of H6.

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
