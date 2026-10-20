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

Listed as they arise; each says what is blocked.

*(none yet: this section is filled from the run)*
