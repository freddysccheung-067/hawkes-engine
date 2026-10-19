# Project state

Last updated: 2026-10-19

## Gate

**H2 complete**: the C++ likelihood and gradient exist and agree with the frozen
reference. **Next: H3** (fit driver, standard errors, log-space optimizer
coordinates).

| Gate | Status |
|------|--------|
| H0 | Done |
| H1 | Done, tag `H1-oracle-locked-v2` |
| H2 | Done |
| H3 | Next |

## Measured agreement

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

The reference's own complex-step check passes at 1e-9 over 72 cases. The
oracle itself was not modified at any point in H2.

## Other verification

- `pytest -q`: 99 passed.
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

No defect was found in the reference implementation. `oracle/` is unchanged.

## Open issues

- `docs/competitor-analysis.md` has been rewritten from live sources, but
  `hawkes (CRAN)` lists no GitHub repository, so no star count exists for it.
  That is stated rather than filled in.
- Local pip installs are blocked by the sandbox classifier. The extension is
  currently verified by building with CMake into `build-dev/` and copying the
  artifact into `python/hawkes_engine/`. This is a local-environment
  workaround, not a repository defect; CI installs normally.

## Owner actions

- **Enable GitHub Pages.** The repository reports `has_pages: true`, but
  `/repos/.../pages` returns 404 and the site 404s. The Docs workflow builds
  successfully and fails at the deploy step. Settings → Pages → Source:
  GitHub Actions.
- **Delete `cpp/tests/test_main.cpp`** if it is still on disk. It is untracked,
  unreferenced, and the delete action was blocked; it is not in any commit.

## Next step

H3: the fit driver and Hessian. The core already exposes the natural-space
gradient and a log-space variant, so the objective wrapper for
`scipy.optimize.minimize` is a thin one. What H3 must settle is the treatment
of the `alpha`-`beta` ridge and what a fit reports when the Hessian is
near-singular (`mathematics.md` section 7).
