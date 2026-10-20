# H6 run report: what the raw rows show, before any estimand

Study `h6-v1`. Written 2026-10-20 after the full grid finished and **before
`analyze.py` exists**. It reports counts and plausibility checks on the raw rows.
It computes no hypothesis test, and it does not change the preregistration.

## 1. What ran

- 128 cells, 2000 replications each, 256 000 rows, 12 workers, 6763 s wall clock.
- Every cell was produced at commit `58b6b0b`, the commit that appended
  Amendment 3. No cell ran against an earlier design. `.done` markers and CSV
  hashes are in `studies/results/manifest.json`, manifest digest
  `fd4b73b31c10d87f6af9f69759b6429aecc4231e3dde9dab5fa3c02d7b9f10e4`.
- `python -m studies.collect`: 128 of 128 cells complete, every checksum
  re-verifies. Realised mean event counts are within 10 percent of `N_target` in
  every cell.
- The raw cell files (185 MB) are gitignored. They exist on the machine that ran
  the study. The manifest is what lets a later reader confirm a regenerated cell
  matches; any cell can be re-run alone, bit for bit, from its seed.

## 2. The estimator is undefined over most of the `c = 1e-3` half of the grid

This is a property of the frozen design, not of the harness, and it was visible in
the pilot before the run.

At `c = 1e-3`, `beta_min * T` is between 0.012 and 43 for `r = 0` cells, below 1 for
12 of those 20 cells and below 3 for 15. The window holds a fraction of one decay
time, so beta cannot be identified. At `c = 1` the same quantity is between 11.9
and 43 066, and is 36 or above for 19 of the 20 cells.

| regime (M = 2) | cells | converged | no standard error | stopped on a bound |
|---|---|---|---|---|
| `c = 1`, `r = 0` | 20 | 0.991 | 0.067 | 0.052 |
| `c = 1`, `r = 0.01` | 20 | 0.988 | 0.092 | 0.085 |
| `c = 1`, `r = 0.1` | 20 | 0.970 | 0.165 | 0.158 |
| `c = 1e-3`, `r = 0` | 20 | 0.943 | **0.754** | 0.411 |
| `c = 1e-3`, `r = 0.01` | 20 | 0.848 | **0.999** | 0.983 |
| `c = 1e-3`, `r = 0.1` | 20 | 0.943 | **0.998** | 0.998 |

At `c = 1e-3` the median fitted beta is 10^4 to 10^6 times the true value: the
optimiser runs to its upper bound. Quantisation is not the cause, since the
unquantised `r = 0` cells fail the same way. The one cell below 0.50 convergence,
`M2_N50000_rho0.85_r0.01_c0.001` (0.476), is in this regime.

**Consequence for Amendment 3.3.** That amendment treated `c = 1e-3` as a
quantisation problem and counted 10 resolved cells there. The data show those 10
cells are estimator-undefined for a reason that has nothing to do with `delta`.
The pre-committed rule already covers this: if fewer than 10 resolved cells have
both a converged fit and a standard error, H6.4 is **inconclusive** and the count
is stated. It will very likely be inconclusive on the `c = 1e-3` half and decided,
if at all, on the 40 `c = 1` cells. That is reported as found. Nothing is added,
dropped, or re-pointed.

H6.3, H6.5 and H6.6 are defined on `c = 1` only and are unaffected.

## 3. At `c = 1`, the estimator misbehaves at small N, and the verdict does not say so

At `c = 1` the fit usually converges and usually reports standard errors. But a
fraction of converged fits return a beta far outside any plausible range, and the
library calls most of them `reliable`.

Counting converged `c = 1`, `r = 0` fits where some `beta_hat` exceeds ten times the
largest true beta, over the 20 `M = 2` cells:

| N | rho = 0.3028 | 0.6 | 0.85 | 0.95 |
|---|---|---|---|---|
| 200 | 48.2 % | 31.1 % | 55.8 % | 94.5 % |
| 1000 | 13.5 % | 3.1 % | 3.6 % | 26.0 % |
| 2000 | 4.7 % | 0.4 % | 0.4 % | 4.6 % |
| 10 000 | 0.1 % | 0 | 0 | 0 |
| 50 000 | 0 | 0 | 0 | 0 |

In total 5454 such fits, **of which 3211 carry the verdict `reliable`**. The
condition number, bound-hit flag and events-per-parameter rule in
`trust.THRESHOLDS` do not catch a beta estimate that has drifted into the flat
region of the likelihood without hitting its bound.

This is a count, not a test. It bears on H6.6 (does the verdict separate coverage?)
but H6.6 is decided by `analyze.py` against its pre-committed rule, not by this
table. It is recorded here so that the pattern is on file before any estimand
exists.

## 4. The H3 anchor: consistent in direction, but H3 did not look at the tail

Cell `M2_N2000_rho0.3028_r0.0_c1.0` is the H3 configuration to within 8e-5
(Amendment 2). 1999 of 2000 fits converged.

| parameter | truth | mean estimate | relative bias | bias / sd |
|---|---|---|---|---|
| `alpha[0,1]` | 0.1000 | 0.1527 | +0.527 | +0.138 |
| `beta[0,1]` | 1.2000 | 37.99 | +30.7 | +0.036 |
| other excitation entries | | | +0.03 to +0.06 | +0.11 to +0.17 |
| `beta` diagonal and `beta[1,0]` | | | +0.08 to +0.13 | +0.19 to +0.21 |

The mean of `beta[0,1]` is dominated by a heavy right tail: median 1.305, 95th
percentile 11.5, 99th percentile 142, maximum 43 914. Over the first 100
replications (H3's sample size) the same entry has mean 57 and sd 517, median
1.26. The excitation entries are biased upward throughout, in the direction H3
found, and `alpha[0,1]` is the worst, as H3 found. A mean and a standard deviation
are the wrong summaries for a quantity with that tail. This is a **plausibility
observation and not a result**: the pre-registered estimands, and their decision
rules, are defined in section 3 of the preregistration and will be computed by
`analyze.py` exactly as written there. Whether the estimands should be robust to
this tail is a question for the owner, and an amendment if the answer is yes. It
is not decided here.

## 5. What this run does not yet tell us

No coverage, no bias estimand, no `q = mean(SE) / sd`, and no hypothesis verdict
has been computed. Everything above is a count over raw rows. The decision rules
in section 4 of the preregistration are untouched.

## 6. Decisions needed before `analyze.py`

1. **Robust estimands.** Section 3 defines bias as a mean. With a tail like the
   one above, the mean of `beta_hat` is not a stable summary and its Monte Carlo
   standard error is not `sd / sqrt(R)` in any useful sense. Options: keep the
   estimands as frozen and report the tail prominently; or append an amendment
   adding a median-based companion estimand, reported alongside and never in place
   of the frozen one. Neither is applied.
2. **What the paper says about `c = 1e-3`.** Recommended: report it as a region
   where the estimator is undefined at the window lengths the design allows,
   with `beta_min * T` as the stated cause.
