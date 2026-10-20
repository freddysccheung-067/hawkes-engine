# Harness notes: where the preregistration was silent

`docs/preregistration.md` is frozen and was not edited. Everything below is a place
where the harness had to complete the design. None of it changes a hypothesis,
threshold, grid point, `R` or a decision rule. Each item says what was
implemented, what the alternatives were, and whether it needs an owner decision.
Items marked **DECISION** should be confirmed or amended before the full run.

## Q1. Quantisation is unmeasurable at c = 1/1000 (DECISION)

Section 5.1 freezes `delta = r / min(beta)`. At `c = 1e-3` that gives
`delta = 10` (r=0.01) or `100` (r=0.1), while `T` is 12 to 3000. Of the 84 cells
with `r > 0`, 11 have fewer than 5 ticks in the window and 21 have fewer than 20.
Thirty of the 40 `c = 1e-3, r > 0` cells hold fewer than 100 ticks. The worst, N=200,
rho=0.95, r=0.1, has `T/delta = 0.12`: every event lands on one or two ticks.

Implemented: round to nearest, then clip into `[0, floor(T/delta) * delta]`, so
every timestamp is still an exact multiple of `delta` and the window `T` is not
widened. Pilot result: at `M2_N50000_rho0.95_r0.1_c0.001`, **20 of 20
replications record `se:none`** (the Hessian could not be inverted). They are
rows and count toward `R`, but H6.4 is a statement about `r = 0.1` against
`r = 0` at the same `(N, rho, c)`, and at `c = 1e-3` that comparison is between a
fit and a degenerate dataset. This is a consequence of the frozen axes, not a
harness defect. Options for the owner: leave it and report these cells as
"estimator undefined" (the section 9 commitment already covers this), or amend
H6.4's region to `c = 1`. Not applied.

## Q2. Burn-in is not specified (implemented, flag for confirmation)

Section 3 says "stationary start" but no section states a burn-in. The simulator
default starts from an empty history. Measured, 300 paths per cell:

| cell | cold start, realised / target N | burn-in 10 relaxations |
|---|---|---|
| N=200, rho=0.95, c=1e-3 | 0.05 | 1.00 |
| N=10000, rho=0.95, c=1e-3 | 0.06 | 1.00 |
| N=50000, rho=0.95, c=1e-3 | 0.12 | 1.00 |
| N=2000, rho=0.95, c=1 | 0.88 | 1.05 |
| N=2000, rho=0.3028, c=1 | 1.00 | 1.00 |

Implemented: `burn_in = 10 / (min(beta) * (1 - rho))`. Two relaxation times is
not enough (first-decile rate z = -25 at N=50000, rho=0.95, c=1e-3). Cost is
about 120 ms of simulation per replication at `c = 1e-3, rho = 0.95` and
negligible elsewhere. Without burn-in those cells would have realised 5 to 12
percent of their target N, which contradicts "N is the target expected count".

## Q3. Which simulator

Not named. `thinning`, matching H3 (PRIOR_EVIDENCE section 2), since H6.1 replicates
that measurement. The two simulators are tested to sample one law.

## Q4. Section 10 seed derivation

Underspecified in three places; the narrowest reading was taken and pinned by
golden values in `tests/test_study_harness.py`.

* `SplitMix64(x)` is one step of `cpp/src/rng.cpp::splitmix64` (add the golden
  gamma, two mix multiplies, final xorshift). A two-step reading is possible.
* `[:16]` is applied to the raw 32-byte digest, as the first 16 **bytes**, read
  big-endian. The text could also mean 16 hex characters (8 bytes). Bytes were
  chosen because it gives a 128-bit integer that SplitMix64 then reduces mod 2^64.
  **DECISION:** if 16 hex characters was intended, every seed changes. This is the
  one item where the design's intent is genuinely ambiguous.
* The message formats `rho`, `r`, `c` with `repr(float)`: `0.3028`, `0.0`, `1.0`,
  `0.001`. `M` and `N` are integers.

`rep_index` is 0-based so that replication 1 maps to index 0, which is what makes
"a change in R does not change earlier seeds" true. Rows record both.

## Q5. Smaller choices

* **Rounding rule**: nearest, not floor. Floor shifts every event earlier by
  `delta/2`, a bias that H6.4 does not name.
* **`n_starts = 1`**, passed explicitly so a changed library default cannot
  change the design.
* **Fit seed** is the replication seed. With `n_starts = 1` it affects nothing,
  but it is recorded.
* **`se is None`** is stored with empty SE columns and `failure = "se:none"`;
  analysis counts it as a miss and in `no_se_rate`, as section 3 requires.
* **Format**: CSV, because `pyproject.toml` has no pandas or pyarrow.
* **Checksum** covers the measured columns, not wall times, so a re-run can
  verify.
* **`.done`** records `reps_requested` and `reps_completed` and is written only
  after the last row is flushed; a `.done` that fails its checksum is treated as
  incomplete, not trusted.

## Q6. Pilot caveats

* The pilot measures fit + simulation per replication on the cells named in the
  brief plus one cell per N. Grid cost is interpolated linearly in N; M=4 is
  carried along the preregistration's own M=4 curve from the single measured
  point. High-rho inflation is only sampled at N=50000.
* Parallel scaling was probed once with 8 cells at 40 replications: 31.7 s, 6.0 s
  (4 workers), 4.9 s (8), 4.7 s (12). Eight cells cannot show scaling beyond 8
  workers. The 12-worker figure is therefore a cap at physical cores (24 logical
  threads / 2) and has **not** been measured on a full 128-cell run. Memory
  allows 56 workers at 97 MB each; it is not the binding constraint, which
  contradicts the preregistration's 5.4 GB argument for 8.
* RSS is the worker's peak working set, measured in-process by
  `K32GetProcessMemoryInfo`. An earlier version returned 0 because ctypes
  truncated the process handle; it now declares its prototypes.
