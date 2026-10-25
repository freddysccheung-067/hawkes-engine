# Pre-registration: the sandwich estimator study

- **Study ID:** `sw-v1`
- **Frozen:** 2026-10-25, before any `sw-v1` measurement and before the code that
  runs it exists. The freeze is recorded at the git tag `SW-preregistration`; the
  commit hash that tag points at is written into
  `studies/results/sandwich/provenance.json` when the study runs.
- **Supersedes:** nothing. It is a separate study from `h6-v1` and `auto-v1`, not
  an amendment to either.
- **Amendment rule:** if a hypothesis, threshold, cell, replication count or
  estimand changes after the freeze commit, the change is a **dated amendment
  section appended to this file**, stating what changed and why. Nothing above an
  amendment is edited.

The evidence this study builds on is `h6-v1`, frozen at `H6-preregistration` and
reported in `studies/results/analysis/`. It is binding context for section 2.

---

## 1. Why this study exists

The paper's theory section derives the sandwich covariance

    Cov(theta_hat) = I^-1 J I^-1,   I = -d^2 ell / d theta d theta^T,
                                    J = Var(s),  s = d ell / d theta,

and observes that when the information equality `J = I` holds, the sandwich
collapses to `I^-1`, which is what the library computes. `h6-v1` then measured
that the reported standard errors understate sampling spread: pooled
`q = mean SE / SD = 0.779 +/- 0.011` over the twelve `M = 2`, `N >= 2000`,
`c = 1`, `r = 0` cells.

The Jensen correction in the theory section predicts the *sign* and the *ordering*
of that shortfall but not its magnitude. So the paper can currently say what is
wrong and roughly why, and it says of the obvious remedy:

> "a sandwich estimator computed from a correctly evaluated J is the natural
> candidate for closing the gap ... the study did not store per-replication
> Hessians ... cannot be reconstructed from the committed analysis outputs."

That sentence is accurate. This study exists to replace it with a measurement.

## 2. What is already known, and what is not

**Known, from `h6-v1`:**

- The shortfall is real, pooled, and confirmed after Holm (`q = 0.779`,
  `T` against a null of 1 at `p = 1.08e-83`).
- It is worst where the branching ratio is high and `N` is small.
- `q` is an average over coordinates of `mean_r se_r^j / sd_j`, so a
  heavy-tailed coordinate distribution can drive it.

**Not known, and not knowable from the committed outputs:**

- Whether `I^-1 J I^-1` computed at the fitted point is closer to the empirical
  sampling covariance than `I^-1` is. No `J` was stored, and `J` cannot be
  recovered from `theta_hat` and `se` alone.
- Whether the shortfall is an `I` error or a `J` error. `q < 1` is consistent with
  both "`I` is too large" and "`J` is larger than `I`", and only computing both
  separates them.

## 3. The question

> For a two-type Hawkes process in the regimes `h6-v1` measured, does a sandwich
> standard error `sqrt(diag(I^-1 J I^-1))` computed at the fitted point match the
> empirical sampling standard deviation better than the inverse-Hessian standard
> error `sqrt(diag(I^-1))` does — and where it does not, is the residual explained
> by `J != I`?

A stranger can answer both parts from the outputs.

## 4. Estimands

All are defined over one population, as in `h6-v1` section 3: `theta_0` fixed,
data random, independent replications. Nothing conditions on an observed dataset.

For replication `r`, let `theta_hat_r` be the estimate, `I_r` the observed
information at `theta_hat_r` (already computed for the Hessian interval), and

    J_r = s_r s_r^T

the outer product of that replication's score vector at `theta_hat_r`. Note this
is the per-replication outer product, **not** a covariance across replications:
the sandwich is a statement about one dataset's sampling variance, so `J_r` is a
rank-one matrix and `I_r^-1 J_r I_r^-1` is that replication's sandwich.

**E4.1 Sandwich standard error.** `se_sw_r = sqrt(diag(I_r^-1 J_r I_r^-1))`, in
natural coordinates, per block `B in {mu, alpha, beta}` and per coordinate.

**E4.2 The ratio, per block, paired.** This is the study's primary estimand:

    rho_B = mean_r mean_{j in J(B)} se_sw_r^j  /  sd_B

with `sd_B` the empirical standard deviation across replications (E3.3 of
`h6-v1`), computed **on the same replications** as the numerator so the comparison
is paired. `rho_B = 1` means the sandwich matches the sampling spread.

**E4.3 The Hessian comparison, on the same replications.** `q_B` exactly as
`h6-v1` E3.6 defines it, restricted to the replications that produced a finite
`J_r`. Reporting `q_B` on the restricted set as well as on the full set is what
makes `rho_B` and `q_B` comparable: a cell where `se_sw` exists only on the
well-conditioned half must not be compared against a `q` computed on all of it.

**E4.4 Sandwich interval coverage.** `cov_sw_B` at nominal 0.95, using
`se_sw_r`, by `h6-v1` E3.5's rule, with a replication whose `se_sw` is absent
counted as a miss.

**E4.5 The information-gap diagnostic.** `g_B = mean_r mean_j (J_r^jj / I_r^jj)`,
the ratio of the score variance to the observed information per coordinate. This
is the quantity the information equality asserts is 1. It is reported because it
separates the two explanations in section 2: `g > 1` with `rho` near 1 means `J`
was the problem and the sandwich fixed it; `g` near 1 with `rho` still short means
the shortfall is not the information equality and the sandwich is not the remedy.

Every estimand carries a Monte Carlo standard error: `SE` by the delta method for
a ratio of means, and `sqrt(p(1-p)/R)` for a coverage. A number is reported as
`estimate +/- MC SE`, never bare.

## 5. Hypotheses

**H-S1 (confirmatory). The sandwich closes most of the gap.**
At each of the five primary cells (section 6), `|rho_Beta - 1| <= 0.10` on the
restricted replication set, and `|rho_Beta - 1|` is smaller than
`|q_Beta - 1|` on the same set by more than two paired standard errors.

The tolerance is 0.10, stated before the run, for this reason: `h6-v1`'s pooled
shortfall is 0.221, so closing it means moving `q` from 0.779 to at least 0.90 to
be distinguishable from doing nothing, and 0.90 is `|rho - 1| = 0.10`. A tighter
tolerance would be indistinguishable from the Monte Carlo error at `R = 2000`,
which is about 0.011 on a pooled `q`.

**H-S2 (confirmatory). The sandwich does not overshoot.**
At every primary cell, `rho_Beta <= 1.10`. A remedy that replaces an interval that
is too narrow with one that is too wide has not fixed a defect, it has moved it,
and the paper would have to say so.

**H-S3 (exploratory, reported either way). The information equality fails where
the map says the interval does.** `g_Beta > 1` at each primary cell, and larger
at `rho = 0.95` than at `rho = 0.3028`. This is exploratory because `h6-v1`'s own
pattern suggested the direction; it is not an independent prediction.

**H-S4 (confirmatory). The sandwich is not a universal fix.**
In the two `c = 1e-3` quantisation cells of section 6, `|rho_Beta - 1|` is
**not** smaller than `|q_Beta - 1|` by more than two paired standard errors. The
prediction is that where `h6-v1` found the beta biased by quantisation (H6.4, 37
to 62 percent downward at `N >= 10 000`), a covariance correction cannot help,
because the defect is in the point estimate and not in the interval around it.
Stating this in advance is what stops a null in those cells being read as a
failure of the sandwich.

**What would count as the sandwich not working, stated before the run:**

- `rho_Beta` outside `[0.90, 1.10]` at a primary cell, or
- `g_Beta` indistinguishable from 1 while `q_Beta` is short, which would say the
  shortfall is not an information-equality failure and the remedy is aimed at the
  wrong term, or
- `se_sw` failing to exist on more than 50 percent of converged replications in a
  cell, which would reproduce the estimator-undefined finding for the remedy
  itself.

Any of the three is a result and is reported as one. A null result is a result.

## 6. The cells

Seven cells, all `M = 2`, `r = 0`, taken from the frozen grid `studies/theta0.json`
so that the parameters are `h6-v1`'s and not chosen here.

The five **primary** cells are the anchor set `h6-v1`'s headline is pooled over,
restricted to `N = 2000` for cost, one per branching-ratio band:

| Cell | `rho` | `c` | Why it is here |
|---|---|---|---|
| `M2_N2000_rho0.3028_r0.0_c1.0` | 0.3028 | 1.0 | The `h6-v1` anchor; lowest shortfall in the `N = 2000` band |
| `M2_N2000_rho0.6_r0.0_c1.0` | 0.6 | 1.0 | Mid-band |
| `M2_N2000_rho0.85_r0.0_c1.0` | 0.85 | 1.0 | High branching, all blocks firing |
| `M2_N2000_rho0.95_r0.0_c1.0` | 0.95 | 1.0 | The worst cell in the map |
| `M2_N10000_rho0.95_r0.0_c1.0` | 0.95 | 1.0 | Does the remedy hold up as `N` grows |

The two **H-S4** cells are the quantisation arm, added because the sandwich is
predicted *not* to help there. The grid has no `N = 10000` quantisation cell, so
these are the smallest `r = 0` ones that exist, and the reason is recorded rather
than a cell being invented:

| Cell | `rho` | `c` |
|---|---|---|
| `M2_N50000_rho0.85_r0.0_c0.001` | 0.85 | 0.001 |
| `M2_N50000_rho0.95_r0.0_c0.001` | 0.95 | 0.001 |

Both are `N = 50 000`, the most expensive cells in the grid. They are in the
design because `h6-v1`'s H6.4 result is a finding about exactly these cells — the
37 to 62 percent downward beta bias was measured at `N >= 10 000` and these are
the quantisation cells that reach it. If the group is too expensive, the
stopping rule in section 10 applies to it as a group: either both cells run or
neither does, and H-S4 is reported as not run rather than decided on one.

If any of these seven cells is absent from `theta0.json`, the run refuses to
start rather than synthesising one. No cell is run that is not listed, and none
listed is dropped.

## 7. Replications

`R = 2000` per cell, the same as `h6-v1`, so the Monte Carlo standard error is
comparable: about 0.011 on a pooled `q`, which resolves a 0.10 tolerance with an
order of magnitude to spare.

Seeding is `h6-v1`'s, unchanged: replication `i` of a cell draws its event stream
from `_core.seed_stream(cell_seed, i)`, with the cell seed from
`sha256("<study>|<M>|<N>|<rho>|<r>|<c>")`. Because the stream depends only on the
cell and the index, the seven cells here reproduce **the same event streams** the
corresponding `h6-v1` cells used. That is what makes E4.3's comparison paired, and
it is a property to verify at run time, not to assume: the harness asserts that a
replication's `loglik` matches the `h6-v1` row for the same `(cell, rep_index)`
before using it.

## 8. The estimator is not changed

This study measures whether the sandwich **would** help. It does not ship it,
and `fit()` does not change. `J` is computed in the study harness, from a new
observation entry point in the core that returns the per-event score
contributions and reduces them; that entry point observes the existing event loop
and does not alter what `loglik` or `loglik_grad_log_space` return. A C++ test
asserts that the sum of the per-event contributions equals the existing total
gradient to 1e-12, so the observation is checked against the thing it observes.

**This is a change to the compiled core and is disclosed as one.** It is the
first change to `cpp/` that this study needs, and it is why the pre-registration
comes before the code.

## 9. Multiple comparisons

Five confirmatory tests are decided by section 5: H-S1 and H-S2 at five cells,
H-S4 at two. H-S3 is exploratory and outside the family. The family is Holm-
corrected in the order H-S1 (five cells pooled into one test, as `h6-v1` pooled),
H-S2 (five cells pooled), H-S4 (two cells pooled). A hypothesis is confirmed only
if it meets its own threshold at the Holm-adjusted level; pools are made by
requiring the condition at every cell in the pool, so pooling can only make a
claim harder, never easier.

## 10. Stopping rule

The full run is seven cells at 2000 replications. Cost is measured rather than
projected, from the `wall_ms` column of the committed `h6-v1` rows for the same
seven cells:

| Cell | Serial cost, 2000 replications |
|---|---|
| `M2_N2000_rho0.3028_r0.0_c1.0` | 63.5 s |
| `M2_N2000_rho0.6_r0.0_c1.0` | 56.6 s |
| `M2_N2000_rho0.85_r0.0_c1.0` | 60.3 s |
| `M2_N2000_rho0.95_r0.0_c1.0` | 72.8 s |
| `M2_N10000_rho0.95_r0.0_c1.0` | 201.8 s |
| `M2_N50000_rho0.85_r0.0_c0.001` | 2351.9 s |
| `M2_N50000_rho0.95_r0.0_c0.001` | 2329.2 s |
| **total** | **5136.1 s (1.43 h)** |

At the 1.6x speedup `h6-v1` measured at 12 workers, that is about 0.9 h, and the
per-event score pass of section 8 is one extra traversal of the same loop, so it
should not double it. The two `N = 50000` cells are 91 percent of the cost.

The study stops and reports what it has if the projected wall clock exceeds
**3 hours**, records the cells complete at the time in
`studies/results/sandwich/RUN_REPORT.md`, and uses no partial cell. If the two
expensive cells breach that on their own, H-S4 is reported as not run, which
section 11 requires to be reported as a result like any other.

## 11. What is reported either way

- Every cell: `rho_B`, `q_B` (restricted and full), `g_B`, `cov_sw_B` and
  `cov_B`, all with MC SEs and all three blocks.
- The label of every hypothesis, and the specific number that decided it, with
  the least favourable label where admissible readings disagree (the `h6-v1`
  Amendment 6.3 rule).
- `no_se_rate` for the sandwich separately from the Hessian, because the remedy
  failing to exist is one of the three stated null outcomes.
- The per-cell wall times.
- The paper's discussion paragraph, updated through
  `studies/make_paper_tex.py`, never by hand.
- A null result, reported as a null result, in `docs/STATE.md` and the paper's
  Limits page.

## 12. What this pre-registration does not cover

- **Whether to ship the sandwich.** A positive result makes it a candidate; it
  does not decide it. Shipping would need its own calibration map, since a
  sandwich changes the interval and the map was measured for the Hessian.
- **The auto policy.** `se_method="auto"` is unchanged by this study.
- **The point estimate.** Nothing here addresses bias, and H-S4 predicts a cell
  where the bias, not the interval, is the defect.
- **Other models.** `shared_decay=True` is a separate study (workstream 4 of the
  same session), and nothing measured here transfers to it.

---

## Amendment 1 — 2026-10-25, correcting the definition of J before any measurement

**What was wrong.** Section 4 defined the meat as
`J_r = s_r s_r^T`, "the outer product of that replication's score vector at
`theta_hat_r`", and described it as a rank-one matrix. That definition is
numerically empty and would have produced a meaningless null.

The total score of a fitted dataset is zero by the first-order condition, up to
the optimiser's tolerance. Measured on the README's own 39 027-event fit:
`gradient_inf_norm = 1.31e-4`, so `s s^T` has a largest entry of `1.7e-8` and its
diagonal is smaller still. A sandwich built from it is a zero matrix, `rho` would
come out near 0, and the study would "show" that the sandwich fails when in fact
it had been handed an empty meat.

**Why the paper's own equation does not license that definition.** Section 4 of
the theory chapter states `J(theta) = E[U_T(theta) U_T(theta)^T]` with
`U_T = grad ell_T(theta)`, and the asymptotic result
`sqrt(N)(theta_hat - theta) -> N(0, I^-1 J I^-1)`. Both are evaluated at the
**true** `theta`, not at the estimate. At `theta_0` the expectation of the score
is zero and its *variance* is `J(theta_0)`, a genuine `p x p` matrix. At
`theta_hat` there is no such thing: the score is identically zero there because
the estimator put it there.

**What is corrected.** Section 4's E4.1 and E4.2 are **superseded** by the
following definitions, which replace them for every purpose of this study. Section
4 is left standing and unedited, per the amendment rule at the top of this file;
where the two disagree, this amendment governs. The study reports both meats,
because they answer different questions:

- **The truth-evaluated meat, `J_0`.** `J_0 = (1/R) sum_r U_T^{(r)}(theta_0)
  U_T^{(r)}(theta_0)^T`, the sample covariance of the score vectors *evaluated at
  the true parameter*, one per replication. This is `J(theta_0)` in the paper's
  equation, estimated by its sample analogue. `I_0` is the observed information
  at `theta_0`. The truth-evaluated sandwich is `I_0^-1 J_0 I_0^-1`. This is the
  primary estimand, because it is what "does the information equality explain the
  shortfall" means. A simulation study knows `theta_0`, so this is computable
  here and would not be computable by a user, which is exactly why it is the
  diagnostic and not the product.
- **The empirical meat, `J_hat`.** `J_hat = sum_n s_n(theta_hat) s_n(theta_hat)^T`,
  summed over **events**, not over replications, where `s_n` is one event's
  contribution to the score. This does not vanish at the estimate, because
  individual contributions are non-zero even when they sum to the score. It is
  what a practitioner could actually compute from their own data, so it is the
  secondary estimand and the one that decides whether there is anything to ship.

**What this costs.** The truth-evaluated meat needs only `U_T` at `theta_0`,
which the shipped API already returns (`loglik_grad_log_space`), so section 8's
core change is needed for the empirical meat alone. It is still needed: `J_hat`
requires per-event contributions, which the core accumulates in place and never
materialises.

**What is unchanged.** The question, the cells, `R`, the hypotheses, their
directions, the 0.10 tolerance, the Holm family, the stopping rule, and the
statement of what would count as the sandwich not working. No measurement
existed when this amendment was written: the tag `SW-preregistration` points at
commit `24ee4cd`, and no `sw-v1` cell has been run.

**One consequential clarification, not a change of hypothesis.** H-S1 and H-S2
are stated about `rho_Beta`, which E4.2 defined from the meat. This amendment
fixes which meat: `rho` is computed from the **truth-evaluated** sandwich
`I_0^-1 J_0 I_0^-1` for the primary decision, because that is the quantity the
paper's equation is about. The empirical-meat ratio is reported alongside as
`rho_hat_B` and does not decide a hypothesis; it is the exploratory quantity
that says whether shipping anything is possible. Reading a hypothesis off the
secondary quantity would have meant deciding a claim about `J(theta_0)` from an
estimate of something else.

**A finding recorded against the paper, not fixed here.** Section 8 of this
document said the core change was required, and that remains true for `J_hat`.
The paper's theory chapter should probably say which `J` it means, because its
own prose ("a sandwich estimator computed from a correctly evaluated J") is
ambiguous between the two and a reader could implement the degenerate one. That
is a paper edit for the discussion update, not a change to this study.

## Amendment 2 — 2026-10-25, the primary estimand needs no core change

**What was found.** Amendment 1 split the meat in two. Before writing any harness
code, the primary one was tested for feasibility, and it is computable with the
shipped API alone: `loglik_grad_log_space` returns the total score, and evaluating
it at `theta_0` gives a vector whose variance across replications is the meat.
Measured on the anchor parameters at `T = 2000` over 40 replications, the score at
the truth has a largest coordinate mean of 3.33 against a per-coordinate spread
of 10.7, and `J_0`'s diagonal entries are 633, 1333, 12.8 and 170 — positive,
finite and far from degenerate.

**What this changes.** Section 8 said the study needs a new entry point in the
compiled core that returns per-event score contributions. For the hypotheses as
Amendment 1 restated them, it does not. `J_0` needs only what the core already
returns, so:

- **Sections 5, 9 and 10 stand unchanged.** The five primary cells, the two
  H-S4 cells, the four hypotheses, the Holm family and the stopping rule are
  decided entirely from the truth-evaluated sandwich.
- **Section 8 is superseded for the confirmatory part of the study.** No C++
  change is made for it. The empirical meat `J_hat` is reported where it is
  cheap, and its per-event requirement is why this amendment does not delete
  section 8's reasoning — it defers it. If a later study needs `J_hat` as a
  decided quantity rather than an exploratory one, the core change described in
  section 8 is what it will need, and that is where to read about it.

**Why this matters for the risk.** It removes the one part of this study that
touched a verified artefact. The compiled core is unchanged, its 1e-12 agreement
with the reference is untouched, and the study is a harness plus an analysis, both
in Python, both reading only the public API.

**No hypothesis, cell, replication count, tolerance or stopping rule changed.**
This amendment removes work; it does not add a claim.
