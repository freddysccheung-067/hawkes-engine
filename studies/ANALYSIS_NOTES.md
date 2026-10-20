# Analysis notes: readings, combinations and owner decisions

Study `h6-v1`. This file is written **before `studies/analyze.py` has been run on the
raw rows**. Its first commit precedes the first estimand on real data, so each
reading below was fixed without knowledge of which side of any bar it puts a
hypothesis on. Anything added after the run is in the dated section at the end and
says so.

Two kinds of item are recorded here, and they are treated differently:

- **A reading** is a place where section 3 or 4 admits more than one definition
  of an estimand. The reading implemented is stated; the other is computed and
  reported as a **sensitivity value**, never as a result.
- **A combination** is a place where Amendment 5 (or section 4) names a standard
  error or a rule but does not say how to compute it. Both forms are computed. If
  they put a hypothesis on different sides of a bar, the verdict is reported as
  **pending owner decision**, with both, and H6 is not marked complete.

Nothing here changes a threshold, region, direction, `R`, the bootstrap seed or
the resample count.

## Readings (implemented reading first; the other is a sensitivity value)

**R1. Population for E3.1 to E3.4 and E3.6.** Section 3 defines them over
"replication `r = 1..R`". Every one of the 256 000 rows carries a `theta_hat`,
including non-converged fits. **Implemented: all `R` replications.** Sensitivity:
converged replications only.

**R2. Divisor in E3.3.** Section 3 writes `mean_r`, so the variance uses divisor
`R`, not `R - 1`. **Implemented as written.** At `R = 2000` the difference is
2.5e-4 relative.

**R3. E3.4 is over replications that have a standard error.** A replication with
`se = None` has no `se_r^j` to average. This is the only reading under which E3.4
is defined; it is recorded because it means E3.6 divides a mean over the
`se`-carrying replications by a spread over all of them. Sensitivity: `q_matched`,
with `sd` over the same `se`-carrying replications.

**R4. Coverage population in a hypothesis.** E3.5 is reported twice (over all
replications, and conditioned on convergence) and section 4 does not say which
one H6.2, H6.3 and H6.6 are decided on. **Implemented: over all replications**,
with `se = None` a miss, because that is the coverage a user of the library
experiences, and it is the version E3.5 states first in its own definition of a
miss. Sensitivity: conditioned on convergence.

**R5. Block in H6.3 and H6.6.** H6.2 names `cov_B` for a block; H6.3 and H6.6 say
"coverage" with no block. **Implemented: coverage over all coordinates of the
cell** (the per-replication share of the cell's `n_params` intervals that cover).
Sensitivity: each block separately.

**R6. H6.6's region and how a pooled `Delta` is formed.** E3.7 defines
`cov_reliable`, `cov_unreliable` and `Delta` **per cell**, and the pre-committed
limitation ("fewer than two cells contain both verdict classes") only makes sense
for a within-cell comparison. **Implemented: `Delta` is computed in each cell
that contains at least one replication of each class, and the region's `Delta` is
the unweighted mean of those cell values.** The region "all cells at `c = 1`,
`r = 0`" is read literally and includes the four `M = 4` satellite cells
(Amendment 4.4 clarified H6.5 only). Sensitivities: `M = 2` cells only; and a
replication-pooled `Delta` over the whole region, which mixes cells and is
therefore confounded with `N`.

**R7. H6.5's pooled `q`.** Section 4 says "weighted by coordinate count".
**Implemented: the coordinate-weighted mean of the per-block `q_B` over the 12
`M = 2` cells (Amendment 4.4), with weights 2, 4, 4 for mu, alpha, beta.** Since
every cell has 10 coordinates, this is also the plain mean of the cells'
coordinate-weighted `q`. Sensitivity: the ratio form
`sum(w mse_B) / sum(w sd_B)`.

**R8. H6.5's decision.** Section 4's threshold line reads `q - 2 SE(q) < 1`, which
`q = 1.00 +/- 0.02` would satisfy. Section 4's general clause makes a result
within two standard errors of its threshold inconclusive, and Amendment 5 states
the rule as `z = (1 - q) / SE(q) > 2`. **Implemented: Amendment 5's `z`**, so
confirmation needs `q + 2 SE(q) < 1`. This is not a reading I chose; Amendment 5
already fixes it, and it is recorded so that nobody reads section 4's line alone.

**R9. H6.1 and H6.2 statistics.** Both are "at least one cell" rules. Reported
`T` and `SE` are those of the cell with the largest `z`; `p` is `1 - Phi(z_max)`,
uncorrected for the maximum, and labelled exploratory.

**R10. H6.4's per-cell difference.** `D_c = rel_beta(r = 0.1) - rel_beta(r = 0)`,
both E3.2 over all `R` replications, with
`SE(D_c) = sqrt(SE(rel)_0.1^2 + SE(rel)_0^2)` and `SE(rel) = sd_beta / (sqrt(R)
mean|beta_0|)` as section 4 states.

**R11. E4.3 uses one set of replications for numerator and denominator.** Both
`median_r(se_r^j)` and `mad_j` are taken over the replications that have a
standard error, since Amendment 4.2's "over replications that have a standard
error" qualifies the whole ratio.

**R12. Bootstrap generator.** Amendment 4.2 fixes the seed, `SplitMix64` of the
first 16 bytes of `sha256("h6-v1-boot|<cell key>")` (section 10 with Amendment
3.1), and 1000 resamples. It does not name the generator. **Implemented: numpy's
`PCG64` seeded with that integer**, which is the generator family ADR-005 uses
for the simulator. Indices are drawn as one `(1000, R)` array per cell.

**R13. Monte Carlo SE of a coverage.** Section 3's `sqrt(cov (1 - cov) / R)` treats
each replication's coverage as one Bernoulli draw. For a block of several
coordinates the replication's coverage is a share, whose variance is at most
`cov (1 - cov)`, so this is the formula as written and errs large. Used as written.

## Combinations (both computed; a split puts the verdict on hold)

**C1. H6.3, SE of a coverage pooled over `N in {2000, 10000}`.** Amendment 5 gives
`sqrt(SE(cov_0.3028)^2 + SE(cov_0.95)^2)` but each term is now a pooled coverage.
Form A: section 3's binomial formula with the pooled count `2R`. Form B: the SE of
the mean of two cell coverages, `sqrt(SE_2000^2 + SE_10000^2) / 2`.

**C2. H6.3, the monotonicity step.** "Each step allowed to rise by at most `2 SE`"
does not say which SE. Form A: the SE of the step, `sqrt(SE_k^2 + SE_k+1^2)`.
Form B: the SE of the later value alone.

**C3. H6.4, the SE of the mean over cells.** Amendment 5: "root sum of squares of
the two cell-level SEs, combined across cells as the SE of their mean". Form A:
cells independent, `sqrt(sum SE(D_c)^2) / K`. Form B: the between-cell standard
deviation of `D_c` over `sqrt(K)`, which also carries heterogeneity between cells.

**C4. H6.4, which resolved cells enter.** Amendment 5.5 sets the population at the
22 resolved `r = 0.1` cells and says the 2 at `c = 1e-3` "are expected to carry no
standard error ... and are counted out by the floor's own wording". The floor
counts cells "with both a converged fit and a standard error"; a cell qualifies
here if at least one of its replications is converged and has a standard error.
Form A: every one of the 22 that qualifies. Form B: the 20 at `c = 1` only, which
is what the amendment expected the floor to leave. If the two `c = 1e-3` cells do
carry converged fits with standard errors, the amendment's premise is false and
the two forms differ in population.

**C5. H6.6, the SE of the mean `Delta` over cells.** As C3: Form A independent
cells, Form B between-cell spread.

Every combination of the forms above (2 x 2 for H6.3, 2 x 2 for H6.4, 2 for H6.6)
is run through the section 4 rule and the Holm procedure. A hypothesis's label is
final only if it is the same in every combination. Holm can propagate a split:
if a pending hypothesis moves another's step, the other is pending too.

## Map construction (not a hypothesis; flagged for the owner)

**M1. `estimator_undefined`.** Amendment 3.3 labels unresolved `r > 0` cells
"estimator undefined at this tick resolution". The shipped map also flags any cell
in which **more than half the replications return no standard error**, because
its coverage is then a count of refusals rather than of intervals. The 0.5 is a
choice for the map's lookup and decides no hypothesis. **Owner decision:**
confirm the 0.5, or set another rule.

## Owner decisions

Listed as they arise; each says what is blocked. Everything in this section was
written **after** `analyze.py` had run on the raw rows (2026-10-21, analysis commit
`a6427a9`), and says so.

**D1. H6.4 lands on two sides of its bar (C3 x C4). BLOCKS the H6.4 label and
therefore H6 completion.** The two `c = 1e-3` cells in the population,
`M2_N50000_rho0.3028_r0.1_c0.001` and `M2_N50000_rho0.6_r0.1_c0.001`, do carry
converged fits with a standard error (22 and 2 of 2000 replications). Amendment
5.5 expected them to carry none and to be "counted out by the floor's own
wording"; that premise is false against the data, so the floor counts 22 cells,
not 20. Their matched `r = 0` cells have `rel_beta` of 1.1e8 and 2.6e8 (the
`c = 1e-3` estimator runs to its bound), so they dominate any mean over cells.

| form | cells | `T` | `SE` | `z` | section 4 |
|---|---|---|---|---|---|
| C3A-C4A (independent cells, all 22) | 22 | -1.70e7 | 3.50e6 | -4.85 | refuted, negative |
| C3B-C4A (between-cell, all 22) | 22 | -1.70e7 | 1.27e7 | -1.34 | inconclusive |
| C3A-C4B (independent, `c = 1` only) | 20 | -815 | 497 | -1.64 | inconclusive |
| C3B-C4B (between-cell, `c = 1` only) | 20 | -815 | 710 | -1.15 | inconclusive |

The final label is "not confirmed" in one form and "inconclusive" in three; it is
**not "confirmed" in any**. The owner must decide (a) whether the two `c = 1e-3`
cells enter (C4) and (b) how cell SEs combine (C3). Either answer is an amendment.

A fact the owner should have in view, and which is **not** a verdict: at
`N >= 10 000`, `c = 1`, every one of the eight `r = 0.1` cells has
`rel_beta(0.1) - rel_beta(0)` between -0.37 and -0.62 with cell-level SE below
0.008, i.e. quantisation biases beta **downward** by roughly 40 to 60 percent,
the opposite of H6.4's direction. The mean over cells is dominated by the
small-`N` cells, whose `r = 0` `rel_beta` is inflated by the heavy tail (+8 at
`N = 2000`, +260 at `N = 200`). Section 4 already names a significantly negative
difference as a refutation "with its direction"; whether the mean over cells is
the right aggregate when the `r = 0` arm is tail-dominated is the owner's call.

**D2. H6.6 is confirmed, and is substantially mechanical.** (Post hoc; recorded
as a finding, not as a change.) In the H6.6 region, 3661 of the 3799
`unreliable` replications (96.4 percent) have no standard error, and E3.5 counts
those as coverage 0 by definition, while `trust.report` returns `unreliable`
whenever the information matrix cannot be inverted. Among replications that
**do** carry a standard error, the mean over the 11 cells holding both classes is
`Delta = +0.073 +/- 0.039` (independent cells) or `+/- 0.034` (between-cell
spread): above 0.02 but within two SE of it under the first form. The
pre-registered verdict stands as computed. The owner should decide whether the
paper leads with it, given that the separation mostly reflects the verdict
flagging fits that returned no interval at all. This diagnostic was not named
before the run and is reported as post hoc.

**D3. `estimator_undefined` rule for the map (M1).** Confirm the 0.5 `no_se_rate`
threshold or set another. Blocks nothing in the hypotheses.

**D4. H6.3's monotonicity clause fails on a rise, not a fall.** Coverage rises
from `rho = 0.3028` (0.9334 +/- 0.0039) to `0.60` (0.9450 +/- 0.0036), a step of
+0.0116 against an allowance of 0.0107 (form C2A) or 0.0072 (C2B). The threshold
clause passes (`z = 2.84`), so section 4 gives "refuted" in all four forms and the
label is "not confirmed" in every form. Nothing is pending; it is recorded because
the failing step is the anchor end of the sequence, where the heavy tail of
`beta[0,1]` lowers coverage at `N = 2000`.

## Phase 3 findings (after the run)

- **Independent recomputation.** `studies/sanity_independent.py`, pure Python,
  three cells, five statistics, four blocks: worst relative difference 2.4e-16.
- **Row counts.** 128 cells x 6 estimand populations: zero mismatches against rows
  minus the exclusions recounted from the raw `failure` strings.
- **Extremes.** 223 of 384 cell-blocks have coverage exactly 0 or 1 or `q` outside
  [0.2, 5]: 176 are estimator-undefined cells, 32 are `sd` inflated by the heavy
  `beta_hat` tail (`sd > 10 x` mean SE), 2 have more than 20 percent no-SE
  replications, and 13 are `r = 0.1, c = 1` cells at `N >= 1000` where alpha and
  beta are biased by 40 to 56 percent, 8 to 12 times the mean SE, so every interval
  misses while `q` stays near 1 (the SE is honest about spread, not about bias).
  The likelihood's tie rule (`cpp/src/workspace.cpp`: simultaneous events do not
  excite each other) is a plausible mechanism for the downward bias; it was not
  tested here.
