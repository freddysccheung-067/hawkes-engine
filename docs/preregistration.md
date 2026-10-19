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
cells, **SHA-256 `61420226892fdddec46df0a8734afc75aad433df441f66487383ee375352f4f7`**,
committed in the same commit as this file. The run compares the hash before its
first cell and refuses to start on a mismatch.

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
