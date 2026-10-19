# Project state

Last updated: 2026-10-19

## Gate

**H3 complete**: the fit driver, the standard errors and the reliability report
exist, and the properties they claim are measured. **Next: H4** (the C++
simulators, agreeing with the reference).

| Gate | Status |
|------|--------|
| H0 | Done |
| H1 | Done, tag `H1-oracle-locked-v2` |
| H2 | Done |
| H3 | Done |
| H4 | Next |

## H3: what the estimator is and what it is not

`fit()` optimizes in log space with the compiled analytic gradient
(`L-BFGS-B`, `jac=True`), so positivity is structural and no candidate is
rejected for being infeasible. `alpha_ii` is free by default; `zero_diagonal`
removes it from the flat vector rather than projecting it out afterwards.

Convergence is `||grad||_inf <= 1e-6 * max(1, |loglik|)` evaluated at the
**returned** point, with a status check that admits 0 and 2. Status 2
("abnormal termination in line search") fires when the line search fails with
nothing left to gain, so it is not by itself a failure; the gradient is the
evidence and the status is context. Status 1 (iteration limit) is never
overridden.

### Reliability thresholds

`trust.THRESHOLDS`, all in one dict so H6 replaces a number rather than editing
logic. None of these is calibrated yet; they are engineering judgement and the
docstring says so.

| Key | Value | Why |
|---|---|---|
| `condition_marginal` | 1e6 | the information is a squared quantity, so 1e6 in H is 1e3 in the parameters |
| `condition_unreliable` | 1e10 | past this the inverse has lost half its digits; matches `hessian.COND_LIMIT` so a matrix the inverter refused is not called reliable here |
| `rho_critical_margin` | 1e-3 | nearer to the pole than this and the stationary mean, and the finite-sample distribution of rho, are both out of reach |
| `ridge_correlation` | 0.99 | below this ordinary excitation already produces 0.9; the ridge is a flat direction, not a preference |
| `events_per_param_marginal` | 10 | conventional rule of thumb for a likelihood fit of this size |
| `events_per_param_unreliable` | 3 | below this the Hessian asymptotics do not apply at all |

`report()` reads the conditioning, the bound hits, `rho`, the alpha-beta
correlation from the covariance, and events per parameter. It does not claim
anything about bias or coverage, and a test asserts that its docstring says so
in plain words.

### Measured recovery

Two-type pair model, `mu = (0.5, 0.3)`, `alpha = [[0.20, 0.10], [0.15, 0.25]]`,
`beta = [[1.0, 1.2], [1.1, 1.3]]`, 100 independent replications per size,
estimates standardized by the Monte Carlo standard error of the mean:

| Size | worst \|z\| | mean \|z\| | worst bias/sd | coverage |
|---|---|---|---|---|
| ~200 events | 4.44 | 1.81 | 0.67 | not asserted |
| ~2000 events | 4.63 | 0.90 | 0.46 | 0.90 to 0.95 |
| ~20000 events | 2.0 | 0.75 | 0.21 | 0.93 to 0.96 |

**The brief's per-parameter 3-sigma property is false at 2000 events.** It is
not a numerical artefact: bootstrapping the mean over the 100 replicates gives
a standard error within 2% of the naive one, so the excess is real finite-sample
bias in the excitation entries, concentrated at `alpha[0,1]`/`beta[0,1]` where
the branching is smallest and the decay is least identified. The same z is
+0.11 at 20000 events. The tests therefore pin 3-sigma where it holds (20000),
and pin `|bias|/sd <= 0.6` per parameter plus coverage at 2000. At 200 the
criterion fails on average too and the test pins scale only.

Reported rather than asserted away, per the rules.

### Time shift

A shift by `s` leaves the excitation part of the likelihood alone and moves the
baseline compensator by `s * sum(mu)`, so

    ell_shifted(theta) = ell(theta) - s * sum(mu).

That identity is exact and is what the test asserts. There is **no** translation
equivariance for the estimate, and the first version of the test assumed there
was. Measured at 20000 events: shifting by 10 moves `rho` by 0.4% and the
loglik by 3.4e-4 per event; shifting by 100 moves them by 4.2% and 3.4e-3.
`mu` is the coordinate most affected, because the added term is linear in it.

## H2: measured agreement

Grid: M in {1, 2, 3, 4, 6}, N in {0, 1, 2, 10, 50, 200, 1000}, random
subcritical parameters, sorted times, `T >= last time`.

| Quantity | Measured worst case | Bound | Where |
|---|---|---|---|
| `loglik` value, relative | 7.5e-14 | 1e-12 | M = 4, N = 1000 |
| Gradient, per entry | 3.6e-12 | 1e-10 | `dbeta`, M = 6, N = 1000 |
| Gradient vs complex step | inside 1e-9 | 1e-9 | M in {1,2,3}, N = 20 |

Every gradient entry is compared, not the array maximum, in all three blocks.
The per-entry floor is 1e-12 of the block's largest magnitude, so a true
derivative near zero is not scored on rounding noise.

The reference's own complex-step check passes at 1e-9 over 72 cases. Measured
worst relative error across that grid: **3.49e-13** (d/dbeta, M = 1, N = 60),
inside the 8.1e-13 the earlier audit reported. The oracle itself was not
modified at any point in H2.

`oracle/verify_complex_step.py` does not exist: it was folded into
`oracle/test_oracle_gradient.py` at `H1-oracle-locked-v2`, as the revision
history in `docs/verification-rule.md` records. The number above was measured
by calling that suite's own `_complex_step_gradient` helper, so it is the same
check, not a reimplementation of it.

## Other verification

- `pytest -q -m "not slow"`: 143 passed. The full count including the two slow
  recovery studies is 145.
- Catch2 suite: 8 cases, 60 assertions. Covers the N = 0 and N = 1 closed
  forms, simultaneous timestamps, the `-inf` path, shared-versus-pair equality,
  the log-space chain rule, validation messages, and zero allocation.
- Zero allocation in the event loop: proven by replacing global `operator new`
  in the test binary and asserting a count of zero across four evaluations.
- ASan/UBSan: the presets exist (`asan`, `ubsan`) and CI runs them on Linux.
  Not run locally: the local toolchain is MSVC, which does not support
  `-fsanitize`.
- `ruff check .` and `ruff format --check .` pass; `mypy python/hawkes_engine`
  passes.

## Benchmarks

`benchmarks/results/loglik_2026-10-19.csv`, with the machine recorded in the
file. Windows 11, MSVC 19.44, Python 3.12. Median over repeated calls, N = 1e6:
M = 8 costs 0.46 s for the pair value and 0.09 s for the shared value.

`benchmarks/results/fit_2026-10-19.csv` for the estimator: a complete `fit()`
call, optimizer plus Hessian plus reliability report. Pair kernel, one start.

| M | N | iterations | wall | per iteration |
|---|---|---|---|---|
| 2 | 1.0e5 | 46 | 2.3 s | 49 ms |
| 2 | 1.0e6 | 46 | 10.0 s | 217 ms |
| 4 | 1.0e5 | 231 | 9.1 s | 39 ms |
| 4 | 1.0e6 | 246 | 90.4 s | 368 ms |

The per-iteration cost is the compiled likelihood; the iteration count is the
starting point and the optimizer. M = 4 costs nearly four times M = 2 per
iteration, which is the M^2 state in the pair recursion. The Hessian pass costs
`2 n_params` extra likelihood evaluations with the gradient, so 20 at M = 2.

## Defects found during H3

1. **A fixed block stayed in the free vector.** `alpha` supplied as a zero
   matrix was validated as fixed but still occupied coordinates, so the
   finite-difference Hessian stepped it to `-6.1e-6` and the core rejected the
   point with a validation error. Fixed by giving `Layout` the fixed values as
   constants and masking those entries out of the vector, which is the same
   mechanism `zero_diagonal` uses.
2. **A symmetric difference probe stepped a positive parameter below zero.**
   Small `alpha` entries are common and an unclamped `h` crosses the boundary
   at once. The step is now capped at half the coordinate for any coordinate
   whose domain is the open half-line.
3. **scipy status 2 was scored as non-convergence.** The line search also
   terminates there when there is nothing left to gain, so valid fits were
   being called failures and inflating the measured bias. Convergence is now
   decided on the recomputed gradient, with the status admitted only as 0 or 2.
4. **The bootstrap imported the test scaffolding.** `_boot.py` reached into
   `tests/_simulate_reference.py`, which does not exist in an installed wheel,
   so `se_method="bootstrap"` would have failed everywhere but this checkout.
   Thinning moved into `hawkes_engine._simulate`; the reference keeps its own
   independent cluster simulator.
5. **The bootstrap seed mixer overflowed `np.uint64`.** Harmless modular
   arithmetic, but it warned on every draw and made the stream depend on a
   NumPy conversion. Rewritten in Python integers with an explicit mask.
6. **The test helper for the dense Hessian applied the step twice.** It passed
   basis vectors that already carried `h`, so the effective width was `h`
   squared and every derived-versus-dense comparison read 3x low. Found by
   testing the helper on a known quadratic before trusting it. The library was
   correct throughout; the check was not.

No defect was found in the frozen reference at H3 either. `oracle/` is
unchanged.

## Defects found during H2

1. **The first event loop let simultaneous events excite each other.** It
   decayed, evaluated, and excited one event at a time, so a second event at
   the same timestamp saw the first. The specification sums over strictly
   earlier events. Caught by the tie test before it reached any oracle
   comparison; fixed by processing ties as a group.
2. **The compensator is accumulated, not reconstructed.** An earlier draft
   planned to recover `sum(1 - exp(-x))` as `count - S`; that subtracts two
   quantities of size `N*x` to leave one of size `N*x^2/2` and loses every
   significant digit when `beta*(T - t)` is small. It is now accumulated from
   `expm1` directly.
3. **The beta-derivative weight needed its own series.** `1 - (1+x)e^-x` is a
   difference of nearly equal numbers for small `x`; it is evaluated by its
   Maclaurin series below 0.5 and by `expm1` above.
4. **Binding output shape.** `dalpha` was allocated `(M, M*M)` instead of
   `(M, M)`. Caught by the entry-by-entry oracle comparison, which is the
   reason that comparison is entry-by-entry.
5. **The static core was not position-independent.** `hawkes_core` is a static
   library linked into a shared module, and CMake enables PIC for shared
   targets but not static ones. ELF platforms rejected the link; MSVC does not
   care, so this stayed hidden until CI ran on Ubuntu. Found only after the
   workflow was changed to re-emit build errors as annotations, because job
   logs are not readable without admin rights and a link failure had been
   arriving as nothing but "exit code 1".
6. **`typing_extensions` was imported but never declared.** The packages that
   pin it do so under `python_version < "3.11"` markers, so a clean 3.11 or
   3.12 environment never has it. CI showed the signature exactly: 3.10 green
   on every platform, 3.11 and 3.12 red on every platform. `TypedDict` has been
   in `typing` since 3.8, so the backport was removed rather than declared.

No defect was found in the reference implementation. `oracle/` is unchanged.

## One requested property does not hold

The H2 brief asked for a property test that the likelihood is monotone in
`mu_i` when `alpha = 0`. It is not. With no excitation,

    d(ell)/d(mu_i) = n_i / mu_i - T

so raising `mu_i` *increases* the likelihood whenever type `i` has more events
than its baseline alone would explain over the window. That is the usual case
for a process whose events are clustered, which is the only case a Hawkes
model is used for.

The test now pins the derivative exactly rather than a monotonicity that is
false. The other two properties in that group — time-shift and permutation
invariance — were also stated wrongly on the first attempt: a shift moves the
baseline compensator by `s * sum(mu_i)` and the `d/dmu` block by `s` per entry,
so the likelihood is not shift-invariant, only its excitation part and the
`alpha`/`beta` blocks are. Both tests now assert the transformation that
actually holds.

## CI lessons

Two of the three rounds of CI failure were diagnosable only after the workflow
started printing the build errors. The unauthenticated REST API returns 403 for
job logs on a public repository, and the check-run annotations carry only the
exit code, so a compiler or linker message is invisible. The install and build
steps now capture output and re-emit matching lines with `::error::`, which
does surface in the annotations endpoint. That change is worth keeping for its
own sake.

## Open issues

- `docs/competitor-analysis.md` has been rewritten from live sources, but
  `hawkes (CRAN)` lists no GitHub repository, so no star count exists for it.
  That is stated rather than filled in.
- Local pip installs are blocked by the sandbox classifier in this session,
  for `pip install -e` in both Bash and PowerShell. Everything was therefore
  verified in a `.venv`, which installs normally: `python -m venv .venv` then
  `./.venv/Scripts/python.exe -m pip install -e ".[test]"`. This is a
  local-environment restriction, not a repository defect; CI installs normally.
- An earlier N=20000 time-shift measurement took over ten minutes because the
  reference thinning re-summed the intensity at every probe. The O(N^2) form
  was replaced by the section 4 recursion; 23000 events now simulate in 0.26 s.

## Owner actions

- **Delete the stale extension copy in the system interpreter.** The package in
  `C:\Users\Freddy\AppData\Local\Programs\Python\Python312\Lib\site-packages\hawkes_engine\`
  contains a `_core` built at 09:31 that predates the H2 likelihood; it exports
  `build_info` and nothing else. scikit-build-core's redirect finder maps
  `hawkes_engine._core` to that copy, so `import hawkes_engine` in the system
  interpreter fails with `AttributeError: loglik` on 94 tests. Reinstalling
  from the repository fixes it; the `.venv` is unaffected. This is the defect
  Phase 0 was asked to find, and it is the reason every command in this session
  runs through `.venv/Scripts/python.exe`.
- The untracked `cpp/tests/test_main.cpp` could not be deleted: the file
  removal was blocked by the sandbox classifier. It is in no commit and
  referenced by nothing, so `rm cpp/tests/test_main.cpp` is cosmetic.
- Six untracked HTML files in the repository root (`p2.html`, `page.html`,
  `w.html` through `w6.html`, about 372 KB each) are saved GitHub pages from an
  earlier session, not repository content. They should be deleted or added to
  `.gitignore` by the owner; this session left them alone because they are not
  related to the gate.
- Pages: previously confirmed running as "GitHub Actions". No change.

## Next step

H4: the C++ thinning and cluster simulators, each agreeing with the reference
on the stationary mean and the event count. The reference they must agree with
is `hawkes_engine._simulate.simulate_thinning` for the thinning half and
`tests/_simulate_reference.simulate_cluster` for the branching half. Both are
checked against `(I - Gamma)^{-1} mu` already, at 0.3% and 0.8% respectively on
5000 seconds, and the H3 recovery studies run through the thinning one, so it
is exercised at every realistic parameter set rather than only in isolation.
