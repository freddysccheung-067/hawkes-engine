# Pre-registration: the `auto` interval study

- **Study ID:** `auto-v1`
- **Frozen:** 2026-10-24, before any `auto-v1` measurement. The commit hash of the
  freeze is recorded in `studies/results/auto/provenance.json` when the study runs.
  See Amendment 1: the date here originally read 2026-10-26, which was wrong.
- **Supersedes:** nothing. It is a separate study from `h6-v1`, not an amendment to it.
- **Amendment rule:** if a hypothesis, threshold, cell or replication count changes
  after the freeze commit, the change is a **dated amendment section appended to
  this file**, stating what changed and why. Nothing above an amendment is edited.

This study tests the feature `se_method="auto"` adds, whose policy is fixed in
[`se_policy.md`](se_policy.md). The calibration map it reads is the output of
[`preregistration.md`](preregistration.md) at the tag `H6-preregistration`.

---

## 1. Why a second pre-registration is needed

H6 measured the Hessian interval and mapped where it is too narrow. It did not
measure any alternative, because none existed when it was designed. `auto` is a
new decision, and the claim it makes — that switching to the bootstrap moves the
interval toward nominal coverage without overshooting — is a claim about a
quantity H6 never measured. Reusing H6's document would mean testing a hypothesis
the document does not contain, and appending an amendment to H6 would mean
changing the design of a finished study to cover work it did not do.

A fresh file is the only honest option, and it costs nothing: the design below is
small, concrete, and fixed before the code that runs it exists.

## 2. The question

> For a two-type Hawkes process with 2000 events, does the interval `auto` reports
> cover the truth closer to the nominal 0.95 than the Hessian interval does, and
> does it ever widen the interval past 1.05 times nominal?

A stranger can answer both parts yes or no from the outputs.

## 3. Estimands

Per cell, over `R` replications:

- `cov_method(block)`: the share of nominal-95% intervals that cover the truth,
  for `block` in `{mu, alpha, beta, all}`, where a replication whose interval is
  absent counts as a miss. This is H6's own definition (section 3, E3.5), reused
  unchanged so the two studies are comparable.
- `q_method(block)`: mean reported SE over empirical SD, as in H6.
- `delta(block) = |cov_auto - 0.95| - |cov_hessian - 0.95|`: the paired distance
  from nominal. **Negative means `auto` is closer.**
- `over(block) = cov_auto - 0.95`: positive means `auto` overshoots nominal.

Every estimate carries a Monte Carlo standard error. For a coverage over `R`
independent replications, `SE = sqrt(p(1-p)/R)`; for a difference of two
coverages measured on the same replications, the paired SE from the per-replication
difference is used, because the two arms share the same simulated event streams
and are therefore not independent.

## 4. Hypotheses

**H-A1 (confirmatory). `auto` lands closer to nominal coverage than the Hessian
does.** At each of the three cells in section 5, `delta(block) < 0` for the `beta`
block by more than two paired standard errors, and the same sign holds for the
pooled `all` block.

**H-A2 (confirmatory). `auto` does not overshoot nominal.** At every cell and
every block, `cov_auto <= 0.95 * 1.05 = 0.9975`. The interval is allowed to be
conservative by up to five percent of the nominal level, which is the width at
which a user would still call the interval an interval rather than a
non-statement, and no more.

**H-A3 (exploratory, reported either way). The refinement narrows the gap at high
branching ratio.** The improvement in `delta` is larger at `rho = 0.95` than at
`rho = 0.3028`. This is exploratory because the map's own pattern (the shortfall
is worst at low `N` and high `rho`) suggests it, so the direction is not
independent of the design that suggested it.

H-A1 and H-A2 are confirmatory: the first is the claim the feature exists to make
and the second is the failure mode that would make the feature worse than the
default. Both are decided by their scripts, no multiplicity correction is applied
(one test each, stated), and a failure is reported as a failure.

**A null result is a result.** If the bootstrap does not move coverage toward
nominal, that is what the release reports, on the Limits page and in the release
notes, and the default stays as it was documented.

## 5. The cells

Three cells, all `M = 2`, `c = 1` (exact timestamps), `r = 0`, `N = 2000`, taken
from the frozen grid `studies/theta0.json` with the parameters H6 used:

| Cell | `rho` | Why it is in the study |
|---|---|---|
| `M2_N2000_rho0.3028_r0.0_c1.0` | 0.3028 | The anchor. Lowest shortfall in the map's `N = 2000` band. |
| `M2_N2000_rho0.85_r0.0_c1.0` | 0.85 | Mid-range branching ratio, all blocks firing in the map. |
| `M2_N2000_rho0.95_r0.0_c1.0` | 0.95 | The worst cell in the map; where an interval most needs to be wider. |

The cells are fixed by the H6 grid, not chosen after looking at an `auto-v1`
result. No other cell is run, and no cell is dropped.

## 6. Replications

`R = 2000` per cell, the same as H6, for two reasons: comparability of the Monte
Carlo standard error with H6's, and a coverage SE of at most
`sqrt(0.25/2000) = 0.0112`, which resolves the differences the map shows (the
`N = 2000` cells differ from nominal by 0.05 to 0.9).

Seeding: replication `i` of a cell draws its event stream from
`_core.seed_stream(cell_seed, i)`, exactly as H6's section 10 defines it, with the
study's own cell seed from `sha256("auto-v1|<M>|<N>|<rho>|<r>|<c>")`. The bootstrap
inside replication `i` uses `_child_seed(seed=i, index=j)` for replication `j`,
which is the shipped bootstrap's own derivation; no new seed scheme is introduced.

**Both arms share the event stream.** Each replication is simulated once, fitted
once with `se_method="hessian"`, and refitted from the same data with
`se_method="auto"`. Sharing the data is what makes the comparison paired, and it
is legitimate because the two arms differ only in how the interval is computed,
never in the data or the point estimate. The `auto` arm's own map lookup is made
from that fit's parameters exactly as `fit` makes it in production.

## 7. The bootstrap inside the study

`B = 200`, `workers = 1` inside each replication, because the study parallelises
over replications and a nested process pool is the failure mode `tests/test_bootstrap_guard.py`
exists to catch. `auto_max_seconds = None` inside the study so the arm is not
silently turned back into a Hessian interval: the projection that would refuse it
is a property of the default configuration, and this study needs the bootstrap to
run.

## 8. Cost, and the cancellation rule

At the measured rate of one bootstrap at `M = 2`, `N ~ 2000` (0.07 s per
replication at `B = 20`, measured during the design), `B = 200` costs about 14 s
per study replication, so the study's `auto` arm costs about `3 * 2000 * 14 s =
23` worker-hours before parallelisation, and about 1 hour on a 24-worker pool.
The Hessian arm adds about 0.6 s per replication.

The study stops and reports what it has if the projected wall clock exceeds
**6 hours**, which is the point at which the run stops fitting inside the work it
is meant to inform. A stop is recorded in `studies/results/auto/RUN_REPORT.md`
with the cells complete at the time, and no partial cell is used.

## 9. What is reported either way

- Every cell, both arms, every block: coverage, `q`, `delta`, `over`, with SEs.
- The labels of H-A1, H-A2 and H-A3, and the specific numbers that decided each.
- The map decision `auto` made in each replication, counted: how many chose the
  bootstrap, how many were refused by the limit, how many were undefined.
- The per-replication wall times, so the cost projection in `se_policy.md` can be
  checked against a second measurement.
- A null result, reported as a null result, on the Limits page and in the release
  notes.

## Amendment 1 — 2026-10-24, correcting the frozen date in the header

**What had been seen.** The study has run: `studies/results/auto/analysis/` holds
its outputs and `studies/results/auto/analysis/report.txt` its result, which is
reported in the release notes and in the paper.

The header says this document was frozen on **2026-10-26**. That date is wrong. The
commit that froze it is `7d35a53`, dated 2026-10-24T17:49:43+08:00, and the harness
that ran the study was committed at `93cd39f` the same evening. No measurement
existed on either date before the freeze, so the freeze itself is sound; the date
written in it is not, and a date two days in the future on a document whose only
value is that its dates can be believed is a defect worth naming rather than
quietly editing.

**What is corrected.** The header now reads 2026-10-24. This is the one edit to text
above an amendment in this file, it is disclosed here, and it changes a date to the
date its own commit records. No hypothesis, threshold, cell, replication count or
estimand was touched.

**What is added.** Section 1 said the freeze commit "is recorded in
`studies/results/auto/provenance.json` when the study runs". Nothing wrote that
file. `studies/run_auto.py` now writes it at the end of a run, carrying the
pre-registration's commit, the run's commit, the cells covered and their checksums.
That file does not exist for the run that produced the current results, because the
harness that ran it predates this amendment; the freeze commit for those results is
`7d35a53` as recorded above, and the per-cell `.done` markers carry their checksums.
