# Pre-registration: H6 trust calibration study

- **Study ID:** `h6-v1`
- **Tag:** `H6-preregistration`
- **Frozen:** 2026-10-20, before any H6 measurement.
- **Supersedes:** nothing. This is the first pre-registration in this project.
- **Amendment rule:** if a hypothesis, threshold, grid point or replication count
  changes after this commit, the change is a **dated amendment section appended to
  this file**, stating what changed and why. The text above the amendment stays
  readable and unedited. Nothing is deleted, and no number is revised silently.

The prior evidence is in [`studies/PRIOR_EVIDENCE.md`](../studies/PRIOR_EVIDENCE.md).
That file is binding context for section 2.

---

## 1. The open question

> **For which sample sizes, branching ratios, decay-window regimes and timestamp
> resolutions does this estimator's maximum-likelihood estimate, together with the
> standard error it reports, behave the way a user of the library is entitled to
> assume — and can the library's `reliable` verdict distinguish the regions where
> it does from the regions where it does not?**

A stranger can answer that yes or no. If the answer is no, the deliverable is a
map of where it fails and how badly, not a fix.

The question matters because `fit.trust()` currently returns `reliable` on the
strength of conditioning numbers that were never calibrated, and because
`FitResult.reliable` is the only thing standing between a user and a confidently
wrong interval.

---

## 2. Confirmatory versus exploratory: what H3 already knew

This study is **not cleanly confirmatory**. Before any hypothesis below was
written, the repository recorded (`studies/PRIOR_EVIDENCE.md` §2):

- at ~2000 events, rho = 0.3028, M = 2, a worst |z| of **4.63** and a worst
  `bias/sd` of **0.46**, concentrated in the excitation entries;
- that the excess is **real finite-sample bias**, not a numerical artefact
  (bootstrap of the mean agrees to 2%);
- coverage in the range **0.90–0.95** at that same cell, against a nominal 0.95.

Therefore:

| Hypothesis | Status | Why |
|---|---|---|
| **H6.1** excitation bias at N ≤ 2000 | **Exploratory** | H3 already saw 4.63 at N=2000, rho=0.3028. H6.1 tests whether it persists into the unmeasured high-rho region; the *existence* claim is a replication. |
| **H6.2** coverage below 0.90 at N ≤ 1000 | **Exploratory, partially** | H3's measured minimum at N=2000 was 0.90, i.e. exactly at the proposed threshold, at rho=0.3028 only. The direction is suggested by H3; the magnitude at N≤1000 and at high rho is not. |
| **H6.3** coverage degrades as rho → 1 | **Confirmatory** | No measurement at any rho other than 0.3028 exists. |
| **H6.4** timestamp quantisation biases beta upward | **Confirmatory** | Never measured. The library has no resolution parameter; this axis has never been exercised. |
| **H6.5** Hessian SEs understate sampling spread | **Confirmatory** | H3 compared bias to MC error and coverage to intervals. It never formed the ratio `mean reported SE / empirical SD`. That comparison has never been made. |
| **H6.6** the verdict separates measured coverage | **Confirmatory** | The thresholds are documented as uncalibrated engineering judgement and have never been tested against a measured quantity. |

The distinction has teeth: an exploratory result is reported with its
exploratory label attached and **cannot** carry the paper's headline. H6.5 and
H6.6 are the confirmatory results, which is why they are the ones the abstract
leads with.

---

## 3. Estimands

All defined over one population: **theta_0 fixed, data random, independent
replications.** Nothing in this study conditions on an observed dataset.

Let `theta_0` be a grid configuration, `theta_hat_r` the estimate from
replication `r = 1..R`, `se_r` the reported natural-space standard error, and
`theta_0^j` the `j`-th coordinate. Let `B ∈ {mu, alpha, beta}` be a parameter
block and `J(B)` its coordinate set.

**E3.1 Mean bias.** `bias_B = mean_r mean_{j∈J(B)} (theta_hat_r^j − theta_0^j)`.

**E3.2 Relative bias.** `rel_B = bias_B / mean_{j∈J(B)} |theta_0^j|`. Reported
per block and per coordinate. This is the estimand H6.1 is stated in, because a
5% threshold must be scale-free to be comparable across `mu`, `alpha` and `beta`.

**E3.3 Sampling spread.** `sd_B = sqrt(mean_r mean_{j∈J(B)} (theta_hat_r^j −
mean_r theta_hat_r^j)^2)` — the empirical standard deviation across
replications, not the average of the reported standard errors.

**E3.4 Mean reported SE.** `mse_B = mean_r mean_{j∈J(B)} se_r^j`.

**E3.5 Interval coverage at nominal 0.95.** `cov_B = mean_r mean_{j∈J(B)}
1{|theta_hat_r^j − theta_0^j| ≤ 1.959964 · se_r^j}`. A replication whose `se` is
`None` (the library declined to invert the information matrix) counts as a
**miss** and is counted separately as `no_se_rate`. Coverage is reported twice:
conditioned on convergence, and over all replications.

**E3.6 SE honesty ratio.** `q_B = mse_B / sd_B`. `q < 1` means the library
understates uncertainty; `q > 1` means it overstates. This is the single number
the study exists to produce, and section 4's comparison is the paper's centre.

**E3.7 Verdict accuracy.** For each cell, `cov_reliable` and `cov_unreliable` are
the mean of E3.5 over replications whose verdict was `"reliable"` and
`"unreliable"` respectively. The estimand of H6.6 is
`Δ = cov_reliable − cov_unreliable`. `marginal` is excluded from `Δ` and
reported separately, because a three-level verdict with no measured value for the
middle level would be a gap in the map.

**Monte Carlo uncertainty.** Every estimand above is reported with its Monte
Carlo standard error: `SE(bias_B) = sd_B / sqrt(R)` for E3.1,
`SE(cov_B) = sqrt(cov_B(1−cov_B)/R)` for E3.5, and by the delta method for
E3.6 and E3.7. A number in the paper is reported as `estimate ± MC SE`, never
bare.

---

## 4. Hypotheses

Each states a direction, a grid region, a threshold, a decision rule and a
falsifier. **A hypothesis whose falsifier cannot be stated is not a hypothesis**,
and none of the six below has that defect.

Decision rules use the pre-specified Monte Carlo standard error, so a result that
sits within two MC standard errors of its threshold is reported as
**inconclusive** rather than claimed in either direction.

### H6.1 — excitation entry bias (EXPLORATORY)

- **Region:** `N ∈ {200, 2000}`, `rho ∈ {0.85, 0.95}`, `c = 1`, `r = 0`.
- **Direction:** `rel_alpha > 0` (upward).
- **Threshold:** `rel_alpha > 0.05` (5% relative bias).
- **Decision:** confirmed if, in at least one cell of the region,
  `rel_alpha − 2·SE(rel_alpha) > 0.05`. Inconclusive if the 2-SE interval
  straddles 0.05. Refuted otherwise.
- **Falsifier:** every cell in the region has `rel_alpha + 2·SE ≤ 0.05`.
- **Note:** exploratory, because H3 measured 4.63 at `N=2000, rho=0.3028`. This
  hypothesis extends it to `rho ≥ 0.85`, which H3 never touched.

### H6.2 — coverage collapse at small N (EXPLORATORY)

- **Region:** `N ∈ {200, 1000}`, all `rho`, `c = 1`, `r = 0`.
- **Direction:** `cov < 0.95`, specifically below the engineering floor 0.90.
- **Threshold:** `cov_B < 0.90` for at least one block `B`.
- **Decision:** confirmed if any cell in the region has `cov_B + 2·SE(cov_B) <
  0.90`.
- **Falsifier:** every `cov_B − 2·SE ≥ 0.90`.
- **Why exploratory:** H3's measured minimum at N=2000 was 0.90 exactly.

### H6.3 — coverage degrades toward criticality (CONFIRMATORY)

- **Region:** fixed `N ∈ {2000, 10000}`, `c = 1`, `r = 0`, across
  `rho ∈ {0.3028, 0.60, 0.85, 0.95}`.
- **Direction:** `cov(rho=0.95) < cov(rho=0.3028)`.
- **Threshold:** a drop of more than two combined standard errors, i.e.
  `cov(0.3028) − cov(0.95) > 2·sqrt(SE(0.3028)^2 + SE(0.95)^2)`.
- **Monotonicity clause:** additionally, the four values must be non-increasing
  in rho up to MC error — each step allowed to rise by at most `2·SE`. Both
  clauses must hold for confirmation.
- **Falsifier:** coverage does not fall from 0.3028 to 0.95 by the stated margin,
  or the sequence rises by more than 2 SE at any step.

### H6.4 — timestamp quantisation biases beta upward (CONFIRMATORY)

- **Region:** all cells with `r = 0.1`, compared against the matching `r = 0`
  cell (same `N`, `rho`, `c`).
- **Direction:** `rel_beta(r=0.1) − rel_beta(r=0) > 0`.
- **Threshold:** the difference exceeds 2 combined standard errors **and** exceeds
  0.01 absolute on the relative scale.
- **Falsifier:** the difference is below either bar; or it is significantly
  **negative**, in which case the sign is the finding and is reported as a
  refutation with its direction.
- **Unpaired by construction:** `r = 0` and `r = 0.1` are different cells and
  therefore have different seeds (section 10). The comparison is a difference of
  means, not a paired difference, so its standard error is the root sum of
  squares of the two cell-level SEs (≈0.016 on the relative scale at `c = 1`).
  With that SE, a 2-SE rule alone would tolerate 0.032; the absolute 0.01 bound is
  the binding constraint, and it is stated so it cannot be relaxed after the
  fact.
- **Grid note:** `beta·delta` is the axis variable by construction (section 5),
  so quantisation is applied on the decay time-scale, not the absolute
  time-scale. A tick coarsened in absolute seconds but fine against the decay
  time is not a coarse-timestamp regime.

### H6.5 — reported SEs understate sampling spread (CONFIRMATORY)

- **Region:** pooled over all cells with `N ≥ 2000`, `c = 1`, `r = 0`, weighted
  by coordinate count; also reported per block.
- **Direction:** `q_B < 1`.
- **Threshold:** pooled `q − 2·SE(q) < 1`.
- **Falsifier:** pooled `q − 2·SE(q) ≥ 1`, i.e. the intervals are honest or
  conservative.
- **Primary status:** this is the study's **primary confirmatory estimand**. If
  `q < 1` robustly, that is the headline, and it is titled as such.

### H6.6 — the verdict separates measured coverage (CONFIRMATORY)

- **Region:** all cells at `c = 1`, `r = 0`.
- **Direction:** `Δ = cov_reliable − cov_unreliable > 0`.
- **Threshold:** `Δ > 2·SE(Δ)` **and** `Δ > 0.02` absolute.
- **Falsifier:** `Δ` is below either bar.
- **Pre-committed limitation:** if fewer than two cells contain both verdict
  classes at `R` replications each, H6.6 is **inconclusive by design** and is
  reported as such. The pilot and the 200-event cell suggest `unreliable`
  verdicts may be rare (one observation at N≈205 in
  `PRIOR_EVIDENCE.md` §6), so this hypothesis may simply lack the data. Saying
  so in advance is the point.

---

## 5. The grid

### 5.1 Axes

The configuration is `theta_0 = (mu, alpha_0, beta_0)` with

```
mu  = (0.5, 0.3)
b_a = [[1.0, 1.2], [1.1, 1.3]]      (the H3 decay)
G_H3 = ([[0.20, 0.10], [0.15, 0.25]] / b_a)     spectral radius 0.3028236...
G_0  = G_H3 / 0.3028236...                      spectral radius 1 (measured)
```

For a cell with branching ratio `rho` and decay scale `c`:

```
beta_i = c * b_a
alpha_i = rho * G_0 * beta_i
```

Then `alpha_i / beta_i = rho * G_0`, so **`rho` and the stationary rate depend
only on `rho`, not on `c`.** Measured rates: `rho=0.3028 → 1.161`, `0.60 →
2.052`, `0.85 → 5.549`, `0.95 → 16.752` events per unit time. At `rho = 0.3028,
c = 1` this reproduces the H3 configuration exactly, which is the calibration
anchor.

| Axis | Values | Why each value is there |
|---|---|---|
| **N** (target event count) | 200, 1000, 2000, 10000, 50000 | 200: where H3's criterion fails outright. 1000: between, untested. 2000: H3's headline cell, so the map is anchored to a published number. 10000: an order of magnitude up. 50000: the scale at which users actually run fits. |
| **rho** | 0.3028, 0.60, 0.85, 0.95 | 0.3028: H3's exact value (`0.3028235666`), so the anchor reproduces prior evidence rather than approximating it. 0.60: ordinary excitation. 0.85: ADR-002's warning threshold. 0.95: the near-critical regime users fit and where `(I−Γ)` is nearly singular. |
| **r = beta·delta** | 0, 0.01, 0.1 | 0: exact times, the control. 0.01: a tick 1% of the fastest decay. 0.1: a tick a tenth of the fastest decay, the coarse regime. Implemented as `delta = r / min(beta)`, so each entry has `beta_ij·delta ∈ [r, r·max(beta)/min(beta)]` = `[r, 1.3r]`. The axis is invariant to `c` because `delta` scales with `1/c` exactly as `beta` does. |
| **c** (decay scale) | 1, 1/1000 | 1: H3's decay. 1/1000: kernels 1000× slower, so `beta·T` drops from ≈1700–2200 to ≈1.7–2.2 at N=2000 — slow decay, heavily overlapping kernels, the regime where the alpha-beta ridge should bite. |

**`beta·T` is derived, not chosen.** At `rho=0.3028, c=1, N=2000`, `T = 1723` and
`beta·T` spans 1723 to 2239 across the four `beta` entries. At `c=1/1000` it
spans 1.72 to 2.24. `beta·T` is reported per cell in the shipped map; it is not an
independent axis, and this is stated so that no reader thinks the grid holds
window length fixed.

**N is the target expected count.** `T = N_target / rate(rho)`, so the *realised*
count differs per replication by sampling. Both `N_target` and the realised
`n_events` are recorded per row.

### 5.2 Cell count

`5 (N) × 4 (rho) × 3 (r) × 2 (c) = 120 cells` at M = 2.

Plus a satellite at M = 4, `8 cells`: `rho ∈ {0.3028, 0.85} × N ∈ {2000, 20000} ×
r ∈ {0, 0.1} × c = 1`. Its purpose is a single guard against a result that is an
artefact of M = 2; it is not a second full grid.

`theta_0` for every cell is generated by the formulas above from committed
constants by `studies/make_theta0.py`. The output is `studies/theta0.json`, 128
cells, **SHA-256 `f735ae4113563f53ce992d4fc767bdc0439e72731af130f3b57d33720a291887`**,
committed in the same commit as this file.

The digest is **canonical**, not a hash of the file's bytes: it is the SHA-256 of
the parsed payload re-serialised with fixed arguments (`indent=2`,
`sort_keys=False`, `ensure_ascii=False`, one trailing newline). It depends on the
grid and nothing else, so it is the same in a fresh clone on any platform
regardless of line endings. A byte hash would not be: this repository has
`core.autocrlf = true`, which normalises endings on add and on checkout.
`.gitattributes` marks the file `-text` so the working tree keeps LF, but the
verification is the canonical digest, not the file's length. The run recomputes
it before its first cell and refuses to start on a mismatch.

### 5.3 Cells ruled out in advance by compute, and what that costs

- **M > 4** excluded. Fit cost scales with `n_params²` in the Hessian; M=4 at
  N=20000 already costs 998 ms per fit (measured). M ≥ 6 would multiply the
  budget by more than the study can afford.
- **`shared_decay = True`** excluded from the main grid. It changes `n_params`
  and therefore the Hessian conditioning, which is the thing H6.6 tests; folding
  it in would confound two effects.
- **`zero_diagonal = True`** excluded.
- **`rho > 0.95`** excluded: the stationary mean is 16.75× the baseline at 0.95;
  beyond it the mean exceeds what the window can sample before the run leaves
  the range where a finite `T` means anything.
- **`N > 50000`** excluded on cost (≈0.44 s/fit measured).

**Consequence for generalisation, stated plainly:** the map covers M = 2 with one
M = 4 satellite, pair decay only, `rho ≤ 0.95`, `N ≤ 50000`. Any query outside
that box must return `"unknown"`. The paper says the map is about this region and
does not extrapolate.

---

## 6. Replications and the Monte Carlo error budget

`R` is fixed at **2000** per cell, before the run. The derivation:

**(a) Coverage.** At `p = 0.95`, `SE(cov) = sqrt(p(1−p)/R) = sqrt(0.95·0.05/2000)
= 0.00487`. A 95% interval on an estimated coverage is therefore `±0.0095`. The
decision thresholds above sit at 0.90 and at drop-margins of ~0.02, which are
two and four times that half-width. `R = 2000` resolves every coverage threshold
in section 4 to better than half its margin.

**(b) Relative bias.** `SE(rel_B) = sd_B / (sqrt(R)·|theta_0|)`. Excitation
coordinates have relative standard deviation between roughly 0.3 and 0.6. At
0.5, `SE(rel) = 0.5/sqrt(2000) = 0.0112`, i.e. **1.1 percentage points**. The
H6.1 threshold is 5%, which is 4.5 standard errors away from zero. A threshold
that close to the noise floor would have needed `R ≈ 10000`; 2000 is enough here
because the effect size H3 suggests (bias/sd ≈ 0.46 at N=2000, where relative SD
is ≈0.5, giving ≈20% relative bias) is far above it.

**(c) SE honesty ratio.** `SE(q)/q ≈ sqrt(1/(2R)) = 0.0158` from the empirical
SD alone; a conservative combined figure is `≈0.022`. A deviation from
`q = 1` of 4.5% is detectable. The H6.5 threshold is therefore a 4.5% shortcut
in the reported standard errors.

**(d) Why not 1000 or 5000.** `R = 1000` gives `SE(rel) = 0.5/sqrt(1000) = 0.0158`,
which puts the 0.05 threshold at 3.2 standard errors and means a 2-SE decision rule
would require an observed relative bias above 0.082 to call anything — that is
too coarse to detect the effect H6.1 is about. `R = 5000` costs 2.5× the compute
for a 0.4 percentage-point improvement on a threshold already resolved at 2000.
**2000 is chosen against the decision rules, not against roundness.**

**Cost projection** (arithmetic, from the measured fit times in
`PRIOR_EVIDENCE.md` §6, `t_fit(N) ≈ 10 + 0.008N` ms at M=2):

| N | fit ms |
|---|---|
| 200 | 12 |
| 1000 | 18 |
| 2000 | 26 |
| 10000 | 90 |
| 50000 | 410 |
| **sum over the 5 N values** | **556 ms** |

`556 ms × 24 (rho,r,c) combinations = 13.3 s` per replication-equivalent sweep.
`× 2000 replications = 26 700 s ≈ 7.4 h` at M = 2. High-rho fits iterate more
(measured 67 iterations at `rho=0.95, N=50000` against 34 at `rho=0.3028, c=1`); a
1.4× inflation gives **≈10.4 h single-core**.

The M = 4 satellite, 8 cells: per-replication cost is
`(0.188 s at N=2000 + 0.994 s at N=20000) × 2 (rho) × 2 (r) = 4.72 s`, so
`× 2000 = 9 440 s ≈ 2.6 h`.

**Total ≈ 13.0 h single-core**, ≈2 h at 8 workers if the cell mix spreads evenly.

The worker count is **8**, not 24, because 5.4 GB of RAM was free when this was
written and the M=4, N=20000 fits are the largest objects. The count and the
measured wall time per cell are recorded in the map.

**If the pilot's measured cost exceeds 1.6× this projection**, the response is a
dated amendment reducing `R` or dropping grid cells — decided before the full
run, recorded in this file, never by silently shrinking later.

---

## 7. Multiple comparisons

- **Hypotheses:** 6, each with one pre-declared region and one decision rule.
- **Cells:** 128, each producing descriptive estimands (E3.1–E3.7) that are
  **not tested**. Cells are the map; hypotheses are the claims.
- **Correction:** Holm–Bonferroni at family-wise `α = 0.05` across the six
  hypotheses, applied to the `p`-values implied by the decision rules. Holm, not
  Bonferroni, because the six are ordered by importance and Holm is uniformly
  more powerful at the same family-wise error rate.
- **Exploratory separation:** the two exploratory hypotheses (H6.1, H6.2) are
  reported **outside** the Holm family, labelled exploratory, and cannot support
  the paper's headline. Their `p`-values are given for completeness with the
  label attached.
- **All cells are reported.** The map ships 128 rows whatever they say. No cell
  is dropped for being unflattering, and a cell where the estimator fails is a
  result (section 4 of the rules).

---

## 8. Stopping rule

`R = 2000` per cell is fixed. It is **not increased** because a hypothesis is
close to its threshold, and it is **not decreased** because a cell is slow. A
cell that cannot complete at `R = 2000` within the compute window is reported
with the replications it has, the shortfall named in the map, and the hypothesis
it bears on marked inconclusive.

The run stops when all 128 cells report a completion marker, or when an owner
action is required (sandbox block, disk, crash). A crash is resumed from the
last completed cell; no replication is re-run with a different seed.

---

## 9. What will be published either way

Committed in advance, so that a null result cannot be quietly reframed:

1. **All six hypothesis verdicts**, each with its deciding number, whether
   confirmed, refuted or inconclusive.
2. **All 128 cells** in the shipped map, including cells where the estimator
   fails, where convergence is poor, and where the verdict is `unreliable`.
3. **The convergence rate per cell** as a first-class result, not a footnote.
4. **Failed and non-converged fits**, with their recorded reason, and coverage
   reported both conditionally and unconditionally.
5. **The SE honesty ratio `q` per block**, with its sign stated in words: if the
   library understates uncertainty, the paper says so in the abstract.
6. **A null result if that is what comes out.** If `q ≈ 1` everywhere and the
   verdict separates coverage, that is published as the finding: the conditioning
   thresholds are adequate. The study is not designed to produce a scandal.
7. **The exploratory leakage in H6.1 and H6.2**, disclosed in the paper's honesty
   section, not buried in a methods footnote.

Nothing is submitted for publication at this gate, and no claim of publishability
is made.

---

## 10. The RNG determinism contract

Data are generated by the compiled simulator (PCG64 seeded through SplitMix64,
ADR-005). Seeds are derived by:

```
cell_seed = SplitMix64( int(sha256("h6-v1|<M>|<N>|<rho>|<r>|<c>")[:16], 16) )
rep_seed  = _core.seed_stream(cell_seed, rep_index)
```

so a single cell can be re-run alone and reproduce bit-for-bit, and a change in
`R` does not change the seed of any earlier replication. The derivation is
implemented in `studies/grid.py` and asserted against a golden vector committed
alongside it.

## 11. What this pre-registration does not cover

`shared_decay`, `zero_diagonal`, M > 4, `rho > 0.95`, N > 50000, censoring,
partial observation, and any model outside the exponential-kernel Hawkes process.
Queries in those regions get `"unknown"` from the shipped lookup, and the paper's
limitations section names them.

---

## Amendment 1 — 2026-10-20, correcting section 10

**What changed.** Section 10 said the seed derivation "is implemented in
`studies/grid.py` and asserted against a golden vector committed alongside it."
At the moment this file was tagged `H6-preregistration` (commit `7bb8fae`) that
sentence was false: `studies/grid.py` does not exist yet. The harness is Phase 2
work and had not been written when the design was frozen, which is the correct
order — the design must not depend on the code that runs it.

**Correction.** The derivation in section 10 is **normative**: it states what the
harness must implement, not what it does. `studies/grid.py` and its golden seed
vector will be committed before the pilot, and the pilot's first assertion is that
the golden vector reproduces. Every number that the harness produces is checkable
against a sentence that existed before the harness.

**Why an amendment and not an edit.** The text above the amendment is what a
referee reads at the tag. Quietly fixing a false claim would defeat the point of
freezing it, and the false claim is itself informative: it shows the freeze
happened before the code, which is the property the freeze is for.

**Nothing else changed.** No hypothesis, threshold, grid point, replication count
or decision rule is affected.

---

## Amendment 2 — 2026-10-20, correcting the anchor claim in section 5.1

**What changed.** Section 5.1 says that at `rho = 0.3028, c = 1` the construction
"reproduces the H3 configuration exactly". It does not. H3's configuration has
`rho = 0.3028235666139891`; the grid point is `0.3028`, which is
**7.782 292e-05 relative** away. Scaling `alpha` by that ratio changes every
entry in the fifth decimal:

| entry | H3 | grid anchor | absolute difference |
|---|---|---|---|
| `alpha[0,0]` | 0.20 | 0.19998444 | 1.556e-05 |
| `alpha[0,1]` | 0.10 | 0.09999222 | 7.782e-06 |
| `alpha[1,0]` | 0.15 | 0.14998833 | 1.167e-05 |
| `alpha[1,1]` | 0.25 | 0.24998054 | 1.946e-05 |

**Why it is left as it is.** The grid point is **not** changed. A 7.8e-5 relative
shift in the excitation entries cannot move any estimand in section 3 by an amount
this study could resolve — `R = 2000` resolves relative bias to 1.1e-2, which is
140 times larger. Changing a frozen grid point to fix a discrepancy four orders of
magnitude below the noise floor would be a worse error than the one being
corrected: it would be adjusting the design to a cosmetic ideal.

**What the reader should take instead.** The `rho = 0.3028` cell is the H3
configuration **to within 8e-5 relative**, which is far closer than any statistic
this study computes. It is the calibration anchor in that sense, and the paper
states the tolerance rather than the word "exactly".

**What this costs.** Nothing measurable. If a later reader wants an exact
reproduction of H3, `theta_0` can be built directly from
`alpha = [[0.20, 0.10], [0.15, 0.25]]`; the grid's job is comparability across
cells, and a common construction rule delivers that better than four hand-picked
arrays would.

---

## Amendment 3 — 2026-10-20, decisions taken before the full run

Written after the pilot (20 replications in each of 8 cells) and before any
full-grid cell has been run. It resolves four points on which this file was silent
or ambiguous. It changes no hypothesis threshold, no grid point, no `R`, and no
decision rule in section 4. Where it adds a rule, the rule is stated here, in
advance of the data it governs, and is derived from quantities fixed in
`studies/theta0.json` rather than from any estimate.

### 3.1 The seed derivation (section 10)

Section 10 writes `sha256(...)[:16]` and does not say whether `16` counts bytes or
hexadecimal characters. The two readings give different seeds. For the anchor cell
`h6-v1|2|2000|0.3028|0.0|1.0`:

| reading | `cell_seed` |
|---|---|
| first 16 **bytes**, big-endian (32 hex characters) | `4711469738829716385` |
| first 16 **hex characters** (8 bytes) | `13345796171862938757` |

**The first reading is normative and is what `studies/grid.py` implements.** The
digest's leading 16 bytes are read big-endian as a 128-bit integer, which
`SplitMix64` then reduces modulo 2^64. Neither reading is statistically better;
both yield well-separated streams. The choice is recorded so that a referee can
reproduce every seed from this file alone. `tests/test_study_harness.py` pins the
anchor value above.

### 3.2 Burn-in (section 3, "stationary start")

Section 3 asks for a stationary start and does not specify a burn-in. The harness
simulates from time `-b` and discards events before 0, with

    b = 10 / (min(beta) * (1 - rho)).

This is normative. It was chosen because a cold start realises only 5 to 12
percent of `N_target` at `rho = 0.95, c = 1e-3` (measured over 300 paths per cell,
`studies/HARNESS_NOTES.md` Q2), which would contradict section 5.1's definition of
`N` as the *target expected count*. Two relaxation times were tried and are not
enough (first-decile rate z = -25 at `N = 50000`). The simulator is `thinning`,
matching H3, whose bias finding H6.1 replicates.

### 3.3 Quantisation and the `c = 1e-3` cells (H6.4, section 5.1)

Quantisation is applied to the data before the fit, with `delta = r / min(beta)`,
rounding to the nearest tick and clipping into `[0, floor(T/delta) * delta]`.

Section 5.1 freezes this `delta` for every `c`. At `c = 1e-3` it is 10 or 100 time
units against windows of 12 to 3000, so some cells contain only a handful of
ticks. In the pilot, **all 20 replications of `M2_N50000_rho0.95_r0.1_c0.001`
returned no standard errors** (the Hessian could not be inverted). That is the
frozen design producing a region where the estimator is undefined, not a harness
fault.

**Rule, fixed here and defined only from the frozen grid.** Let
`ticks = T / delta` for a cell. An `r > 0` cell is **resolved** if `ticks >= 100`
and **unresolved** otherwise. Of the 80 `M = 2` cells with `r > 0`, **50 are
resolved** (all 40 at `c = 1`, whose minimum is 119.4 ticks, and 10 of the 40 at
`c = 1e-3`) and 30 are unresolved. The threshold of 100 is stated before the full
run and is not tuned to any result.

- **H6.4 is evaluated on resolved `r > 0` cells only**, each compared with its
  matching `r = 0` cell at the same `(N, rho, c)`. Its threshold, direction and
  falsifier in section 4 are unchanged.
- **Unresolved cells are run, stored and reported.** They stay in the shipped map
  with their convergence and `no_se_rate`, labelled "estimator undefined at this
  tick resolution". They are not dropped, and they are not evidence about H6.4 in
  either direction.
- **No cell is added, removed or re-pointed.** The 128-cell grid and its digest
  are unchanged.

If, after the run, fewer than 10 resolved cells have both a converged fit and a
standard error at `R = 2000`, H6.4 is reported **inconclusive** and the count is
stated.

### 3.4 The pilot's replications are the study's replications

`studies/pilot.py` runs `run_cell` with the study's own seed derivation, so the
first 20 replications of each pilot cell are the same draws as replications 1 to
20 of the full run. They are not independent data and are not discarded: the full
run regenerates them identically and the pilot files are not used in any estimand.
No hypothesis was evaluated on them. What the pilot did inform is stated
completely here: the per-fit cost, the peak working set per worker, the
`c = 1e-3` finding above, and the burn-in. Nothing in section 4 was changed in
response to a pilot estimate.

### 3.5 Compute

Measured against the section 6 projection, the pilot's grid estimate is 9.8 hours
at one worker against a projected 10.0, a ratio of 0.977, below the 1.6 amendment
trigger. The pilot's per-worker peak working set was 97 MB. The harness will run
with 12 workers, the physical core count. That figure is a cap, not a measurement:
scaling past 8 workers was not observable with 8 cells, and the first hour of the
full run is the measurement. A wall-time shortfall is a scheduling matter and
changes nothing above. If `R = 2000` cannot complete for a cell, section 9
applies unchanged.

**Nothing else changed.** No hypothesis, threshold, grid point, replication count
or decision rule is affected.

---

## Amendment 4 — 2026-10-20, after the full grid and before any estimand

**Disclosure first.** The full grid has run (256 000 rows, every cell produced at
commit `58b6b0b`, which is the commit that appended Amendment 3). A counts-only
pass over those rows, `studies/RUN_REPORT.md`, was read **before** this amendment
was written. It computed no bias, coverage, `q` or hypothesis test, but it did show
the shape of the data, and this amendment responds to that shape. A reader should
weigh it accordingly: it is a decision made with knowledge of a feature of the
data, not a prediction made without it. The case for making it anyway is that the
alternative is to find the feature after the estimands are computed and add
something silently. No estimand has been computed and no `analyze.py` exists.

What the pass showed, in three counts. At `c = 1`, `r = 0`, `N <= 2000`, a share of
converged fits return a `beta_hat` more than ten times the largest true beta
(48.2 percent at `N = 200, rho = 0.3028`; 4.7 percent at `N = 2000, rho = 0.3028`;
0.1 percent or less at `N >= 10 000`). In the anchor cell, `beta[0,1]` has median
1.305 and mean 37.99 against a true 1.2, with a maximum of 43 914. And the mean is
not a stable summary of a quantity with that tail.

### 4.1 What is **not** changed

E3.1 to E3.7 are exactly as defined in section 3, are computed exactly as written,
and are the quantities every hypothesis in section 4 is decided on. Every
threshold, direction, region, decision rule and falsifier in section 4 is
unchanged, except the pooling clarification in 4.4 below. The Holm family, the
exploratory separation and `R = 2000` are unchanged. **Nothing in this amendment
can turn a refuted or inconclusive hypothesis into a confirmed one, or the
reverse.**

### 4.2 Companion estimands (added, never substituted)

For each cell, block `B` and coordinate `j`, the following are computed **in
addition**, from the same rows, and reported in a separate table labelled
"robust companions":

- **E4.1 Median bias.** `medbias_B = mean_{j∈J(B)} ( median_r theta_hat_r^j −
  theta_0^j )`, and `medrel_B = medbias_B / mean_{j∈J(B)} |theta_0^j|`.
- **E4.2 Robust spread.** `mad_B = mean_{j∈J(B)} 1.4826 · median_r |theta_hat_r^j −
  median_r theta_hat_r^j|`, the median absolute deviation scaled to a standard
  deviation under normality.
- **E4.3 Robust honesty ratio.** `qrob_B = mean_{j∈J(B)} median_r( se_r^j ) /
  mad_j`, over replications that have a standard error. It answers the same
  question as E3.6 with a statistic that a tail of 43 914 cannot move.
- **E4.4 Tail share of `beta`.** `tail`: the share of **converged** replications in
  which any `beta_hat` coordinate exceeds `10 · max_j beta_0^j`. This is the
  quantity the counts-only pass reported, defined here exactly as that pass
  computed it. It counts the phenomenon; it is not a test.

Monte Carlo standard errors for E4.1 to E4.3 are obtained by a **nonparametric
bootstrap over replications within the cell, 1000 resamples, with a seed derived
from the cell seed** by the section 10 construction applied to the message
`"h6-v1-boot|<cell key>"`. Percentile intervals are reported. The bootstrap seed
is fixed here, before it is used.

**These companions decide nothing.** They are reported next to E3.1, E3.3 and E3.6
so that a reader can see whether the frozen mean-based estimand and a robust one
agree. Where they disagree materially, the paper reports both and says which
hypothesis verdicts would differ **if** the companion had been the estimand,
labelled as a sensitivity statement and not as a result. If a hypothesis is
confirmed on E3.x and the companion disagrees in sign, the verdict stays
"confirmed" and the disagreement is stated in the same sentence.

### 4.3 Why this is an addition and not a replacement

Replacing a mean by a median after seeing that the mean misbehaves is the standard
way an analysis acquires the answer its author expected. It is not done here. The
frozen estimands are the pre-registered claim. A robust companion is a
pre-registered **check on that claim**, added before any estimand is computed, with
its own seed and its own rule for when it may be mentioned. The paper states in its
honesty section that the companions were added after the raw rows were seen and
before any estimand was computed, and cites this amendment.

### 4.4 A clarification to H6.5's pooling, resolved without reference to results

H6.5's region reads "all cells with `N ≥ 2000`, `c = 1`, `r = 0`, weighted by
coordinate count". Read literally that includes the four `M = 4` satellite cells
(`N ∈ {2000, 20000}`, `rho ∈ {0.3028, 0.85}`). Counting coordinates, the region
holds 12 `M = 2` cells at 10 parameters each (120 coordinates) and 4 `M = 4`
satellite cells at 36 parameters each (144 coordinates). **The satellite would
carry 55 percent of the weight**, which contradicts section 5.2, which describes
it as "a single guard against a result that is an artefact of M = 2; it is not a
second full grid."

The reading adopted, which is the one consistent with section 5.2: **H6.5's pooled
`q` is computed over the 12 `M = 2` cells only.** The four satellite cells are
reported separately with their own `q`, and the paper states whether the satellite
agrees in direction with the `M = 2` pooled result. This is derived from the
structure of the grid in `studies/theta0.json` and from section 5.2's stated
purpose, not from any estimate.

### 4.5 `analyze.py` is held to the preregistration, not to this amendment

`analyze.py` implements section 3's formulas as written and the section 4 decision
rules as written, and adds the E4 companions. Its tests include a hand-computed
fixture for E3.1 to E3.7 so that a transcription error in an estimand cannot
survive. Any number in the paper is produced by it and nothing is typed by hand.

### 4.6 What would require a further amendment

A change of estimand, threshold, region or rule; a different treatment of the
`c = 1e-3` cells than Amendment 3.3's; a different bootstrap seed or resample
count; or the addition of any further companion after `analyze.py` has produced a
result. Each would be appended, dated, and labelled with what had been seen at the
time.

**Nothing else changed.** The grid, its digest, `R`, and every hypothesis threshold
and decision rule are as at the tag, with Amendments 1 to 3.

---

## Amendment 5 — 2026-10-20, the multiplicity procedure, before `analyze.py` exists

No estimand has been computed. `studies/analyze.py` does not exist. The raw rows
have been seen only through the counts in `studies/RUN_REPORT.md` and the
disclosure in Amendment 4. This amendment supplies a procedure that section 7
names ("the `p`-values implied by the decision rules") and does not define, and
corrects two statements in this file that are wrong against the frozen grid. It
changes no threshold, region, direction or decision rule.

### 5.1 The Holm family has four members, not six

Section 7 says Holm–Bonferroni is applied "across the six hypotheses" and, two
bullets later, that H6.1 and H6.2 are reported **outside** the Holm family. Both
cannot hold. The second is the explicit and later-stated design, and it follows
from section 2's rule that an exploratory result cannot carry the headline. The
family is therefore **H6.3, H6.4, H6.5 and H6.6**, `m = 4`. H6.1 and H6.2 are
reported with their own `z` and one-sided `p`, labelled exploratory, outside the
family. "Six" in section 7 is read as "six hypotheses in total".

### 5.2 The statistic and the `p`-value for each hypothesis

Every decision rule in section 4 has the form *statistic minus `k` standard errors
exceeds a threshold*, or a difference of two such statistics. Each rule therefore
implies a **standardised statistic** and a **one-sided `p`-value** under the null
that sits at the threshold:

    z = (T - tau) / SE(T),        p = 1 - Phi(z)

with `T` the estimand, `tau` the threshold in that hypothesis's rule, and `SE(T)`
the Monte Carlo standard error section 3 prescribes for it, with the changes in
5.3. `Phi` is the standard normal CDF. The one-sided form is used because every
hypothesis states a direction.

| Hypothesis | `T` | `tau` | `SE(T)` |
|---|---|---|---|
| H6.3 | `cov(0.3028) - cov(0.95)`, pooled over `N ∈ {2000, 10 000}` | 0 | `sqrt(SE(cov_0.3028)^2 + SE(cov_0.95)^2)` |
| H6.4 | `rel_beta(r=0.1) - rel_beta(r=0)`, mean over resolved cells | 0.01 | root sum of squares of the two cell-level SEs, combined across cells as the SE of their mean |
| H6.5 | pooled `q` over the 12 `M = 2` cells (Amendment 4.4) | 1, direction `q < 1`, so `z = (1 - q)/SE(q)` | bootstrap, 5.3 |
| H6.6 | `Delta = cov_reliable - cov_unreliable` | 0.02 | `SE(Delta)` by the delta method on the two binomial coverages |

H6.3 is a **conjunction** of its threshold clause and its monotonicity clause
(section 4). Its `p`-value is that of the threshold clause. Confirmation requires
both clauses; the monotonicity clause cannot rescue a failed threshold clause, and
a failed monotonicity clause blocks confirmation whatever `p` is.

### 5.3 The standard error of `q` is the bootstrap's, not the normal-theory one

Section 3 says E3.6's standard error is "by the delta method". The delta method for
`q = mse / sd` uses the large-sample variance of `sd`, which for `R` replications of
normal data is about `sd^2 / (2(R - 1))`. A check on simulated data with `R = 2000`
shows the relative standard error of `sd` is **0.015 for normal data and 0.34 for a
`t` distribution with 2.2 degrees of freedom**, a factor of 22. `beta_hat` in the
small-`N` cells has a tail of that kind (Amendment 4: median 1.305, mean 37.99,
maximum 43 914), so the delta-method standard error would be wrong in the
direction that makes `q` look more precise than it is.

**For H6.5 only,** `SE(q)` is therefore the standard deviation of `q` over the 1000
bootstrap resamples already specified in Amendment 4.2, resampling replications
within each cell, with the pre-fixed seed `"h6-v1-boot|<cell key>"`. The pooled
`q` is recomputed in each resample, so the bootstrap carries the pooling. The
delta-method value is computed and reported alongside as a sensitivity check,
labelled as such. If the two differ by more than a factor of 2, both are reported
and the **larger** governs the decision, so that the correction can only make
H6.5 harder to confirm.

This changes a standard error, not a threshold or a direction, and it can only move
a decision towards "inconclusive".

### 5.4 The Holm procedure

The four `p`-values are ordered ascending. At step `k = 1..4` the `k`-th smallest is
compared with `0.05 / (5 - k)`; the procedure stops at the first failure and
declares the remaining hypotheses not confirmed.

| step | threshold on `p` | equivalent `z` |
|---|---|---|
| 1 | 0.0125 | 2.241 |
| 2 | 0.01667 | 2.128 |
| 3 | 0.025 | 1.960 |
| 4 | 0.05 | 1.645 |

**Two bars apply, and both must be cleared.** Section 4's own rule (`T - 2·SE > tau`,
`z > 2`) is looser than Holm at steps 1 and 2 (`z >= 2.241`, `2.128`) and stricter
at steps 3 and 4 (`z >= 1.960`, `1.645`). A hypothesis is **confirmed** only if it
passes its section 4 rule **and** survives Holm. A hypothesis that passes section 4
but not Holm is reported as **"confirmed before correction, not confirmed after"**,
with both numbers. A hypothesis that fails section 4 is not confirmed whatever its
Holm standing. Section 4's existing clause stands unchanged: a result within two MC
standard errors of its threshold is reported **inconclusive** rather than claimed
in either direction. No further inconclusive band is added here.

### 5.5 Clarification to Amendment 3.3: which resolved cells H6.4 uses

Amendment 3.3's counts are correct: of the 80 `M = 2` cells with `r > 0`, 50 are
resolved (`ticks >= 100`), 40 at `c = 1` and 10 at `c = 1e-3`. Its sentence "H6.4 is
evaluated on resolved `r > 0` cells only" is looser than section 4, which frames
H6.4 on **`r = 0.1` cells only**. Section 4 governs. Split by `r`, the 50 resolved
cells are:

| | `c = 1` | `c = 1e-3` | total |
|---|---|---|---|
| `r = 0.01` | 20 | 8 | 28 |
| `r = 0.1` | 20 | 2 | **22** |

- **H6.4's population is the 22 resolved `r = 0.1` cells,** each compared with its
  matching `r = 0` cell. The pre-committed floor in 3.3 (fewer than 10 resolved
  cells with a converged fit and a standard error is inconclusive) is applied to
  those 22. Twenty are at `c = 1`, where the fit is defined. The 2 at `c = 1e-3`
  are expected to carry no standard error (`studies/RUN_REPORT.md`, section 2) and
  are counted out by the floor's own wording.
- The 28 resolved `r = 0.01` cells are reported in the map. They are not evidence
  for or against H6.4.
- This clarification reduces H6.4's population from the 50 that 3.3's wording
  could be read to imply to the 22 that section 4 states. It moves no threshold.

### 5.6 What `analyze.py` must produce for this amendment

Per hypothesis: `T`, `tau`, `SE(T)` and which standard error was used, `z`, the
one-sided `p`, the section 4 verdict, the Holm step and threshold it met or
missed, and the final label from {confirmed, confirmed before correction only,
not confirmed, inconclusive}. For H6.5, the bootstrap and delta-method standard
errors side by side. The test suite includes a fixture in which the Holm ordering
and the "both bars" rule produce a known outcome by hand.

### 5.7 What this amendment cannot do

It cannot change which side of any threshold a hypothesis falls on, except that the
bootstrap standard error in 5.3 and the Holm bar in 5.4 can only move a result
towards "not confirmed" or "inconclusive". It adds no hypothesis, no region and no
cell.

**Nothing else changed.** The grid, its digest, `R`, every hypothesis threshold and
decision rule, and Amendments 1 to 4 are as written.

---

## Amendment 6 — 2026-10-21, resolving D1 and the form-disagreement rule

**What had been seen.** `analyze.py` has run on the raw rows (analysis commit
`a6427a9`), and its results exist in `studies/results/analysis/`. The H6.4 label is
`pending owner decision` because four defensible SE/population combinations give
different section 4 verdicts. This amendment resolves that, and it is written with
the results in front of it. It is disclosed as such.

The four combinations were left open because Amendment 5 did not say how to combine
cell-level standard errors (C3) and because Amendment 5.5 assumed the two
`c = 1e-3` cells would carry no standard error and be counted out by the floor (C4).
The second assumption is false against the data: those cells do carry standard
errors in 22 and 2 of 2000 replications.

### 6.1 The population is the 22 resolved cells; no cell is dropped

C4 form A (all 22) is adopted, consistent with section 4's region, Amendment 5.5's
count, and the standing rule that a cell is never dropped for being unflattering.
The two `c = 1e-3` cells stay in. Their matched `r = 0` arms have `rel_beta` of
1.1e8 and 2.6e8 because the `c = 1e-3` estimator runs to its bound, and so they
dominate any mean. That domination is **reported as the reason the mean is not
interpretable in this region**, not removed by dropping them.

### 6.2 The SE of the mean is the independent-cell form

C3 form A, `SE = sqrt(sum(se_i^2)) / K`, is adopted. It is the form that treats the
`K` cells as the independent runs they are, and it is the more conservative of the
two here at `K = 22` (`3.50e6` against `1.27e7` — it is the *narrower* one, so this
choice is stated plainly rather than justified as conservative). The between-cell
form is reported alongside for every hypothesis it applies to, as a sensitivity
value.

**This choice changes no threshold and no direction, and it is made after the
results are known.** A reader who believes B is the better estimator will find B's
value in the same output, labelled as a sensitivity form.

### 6.3 When forms disagree, the label is the least favourable

The general rule, replacing `pending owner decision`:

**The final label is the least favourable label any admissible form produces**, with
order `confirmed` > `confirmed before correction only` > `inconclusive` >
`not confirmed`.

The direction is one-way on purpose: a disagreement between admissible
formulations can only weaken a claim, never strengthen it. Under this rule H6.4's
label is **not confirmed**, because C3A-C4A gives `z = -4.85` and section 4 refutes
it.

### 6.4 H6.4's substantive result, which the label does not express

Section 4 already says a significantly negative difference is a refutation "with
its direction". The direction is the finding and is stated wherever the verdict is:

- At `N >= 10 000`, `c = 1`, every one of the eight `r = 0.1` cells has
  `rel_beta(0.1) - rel_beta(0) between -0.37 and -0.62` with cell-level SE below
  `0.008`: quantisation biases `beta` **downward** by roughly 40 to 60 percent, the
  opposite of the hypothesis.
- The mean over the 22 cells is dominated by the small-`N` cells, whose `r = 0` arm
  is inflated by the heavy tail of `beta_hat` (`rel_beta` of +8 at `N = 2000` and
  +260 at `N = 200`). The large negative mean is an artefact of that tail, not
  evidence of a large downward effect at every sample size.

Both statements go in the paper, and the second is why the first is the one to
believe. The verdict "not confirmed" is correct and the direction reversal is the
result.

### 6.5 The c = 1e-3 cells in this hypothesis

They remain in the population under 6.1, and the paper states that their `r = 0`
arms are estimator-undefined, so their contribution to the mean reflects a fit at
its bound rather than a quantisation effect. This is the same handling as the map's
`estimator undefined` label, applied in words.

### 6.6 What this amendment cannot do

It cannot turn H6.4 into a confirmation. It changes no threshold, no direction, no
region and no cell. It fixes two open readings and supplies a rule for form
disagreement that can only move a label toward "not confirmed".

**Nothing else changed.** The grid, its digest, `R`, every threshold and decision
rule, and Amendments 1 to 5 are as written.
