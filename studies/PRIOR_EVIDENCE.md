# Prior evidence about estimator behaviour

Everything observed about this estimator before the H6 hypotheses were written,
with its configuration and sample size. Compiled 2026-10-20 from `docs/STATE.md`
at commit `8f98914` (the last revision that carried the H3 recovery table; the
H5 rewrite at `9f9186d` dropped it), `tests/test_fit.py` at `6b2a8ab`, and commit
bodies `2db5770` and `c36404c`.

This file exists because H6 must not present itself as confirmatory. Real bias in
the excitation entries was measured at 2000 events before any H6 hypothesis
existed. Section 2 of `docs/preregistration.md` says which hypotheses this costs.

## 1. The H3 configuration, in full

Because a bias number without its `theta_0` is not evidence:

```
mu    = (0.5, 0.3)                 M = 2, pair decay (not shared)
alpha = [[0.20, 0.10], [0.15, 0.25]]
beta  = [[1.0,  1.2 ], [1.1,  1.3 ]]
```

Measured properties of this `theta_0` (recomputed for this file by
`hawkes_engine._core`, not copied):

- `Gamma = alpha / beta = [[0.2000, 0.0833], [0.1364, 0.1923]]`
- spectral radius `rho = 0.3028235666139891`
- stationary mean `= (0.6756, 0.4855)`, total rate `1.1611` events per unit time

Every number in section 2 below is at **rho = 0.3028 and nothing else**. No
recovery measurement in the repository has ever varied rho, M above 2, the decay
window, or the timestamp resolution.

## 2. H3: standardized bias, worst case per sample size

100 independent replications per size, thinning simulator, `se_method="hessian"`,
estimates standardized by the Monte Carlo standard error of the mean
(`bias / (sd / sqrt(R))`), intervals at nominal 95%.

| Size (~N) | worst \|z\| | mean \|z\| | worst bias/sd | coverage range |
|---|---|---|---|---|
| 200 (`T`=180) | **4.44** | 1.81 | 0.67 | not asserted |
| 2000 (`T`=1800) | **4.63** | 0.90 | 0.46 | 0.90 – 0.95 |
| 20000 (`T`=18000) | **2.00** | 0.75 | 0.21 | 0.93 – 0.96 |

What the 2000-event result means, in the words of the commit that recorded it:

- The 4.63 z is **not a numerical artefact**. Bootstrapping the mean over the 100
  replications gives a standard error within 2% of the naive one, so the excess is
  real finite-sample **bias**, not a bad estimate of the noise.
- The bias is concentrated at `alpha[0,1]` / `beta[0,1]` — the corner where
  branching is smallest and the decay is least identified. Measured `bias/sd` at
  that corner: `+0.46` (alpha) and `+0.40` (beta).
- The sampling distribution there is right-skewed: `beta[0,1]` has a 95th
  percentile of 8.6 against a truth of 1.2.
- The same z is `+0.11` at 20000 events. The bias shrinks with window length.

**Consequence for H6: the per-parameter 3-sigma property is already known to be
false at 2000 events, at rho = 0.30, before H6 was designed.** Any H6 hypothesis
that excitation-entry bias exists at moderate N is a replication, not a test.

## 3. H0–H3: six defects already found and fixed

Recorded in `2db5770`. Not re-listed individually here; the relevant point for H6
is that the estimator's infrastructure has been through one round of defect
repair, which is why the harness may assume `fit()` is correct and focus on what
`fit()` measures.

## 4. H4: properties that turned out false

Two were false **as originally stated**, and two more were corrections of an
assumed property:

1. **Mean cluster size equals `1/(1-rho)`** — false under truncation. At `T`=400,
   rho=0.6 the window removes 0.009 of a 2.5 mean, which is three standard errors
   at 20000 paths. The test now compares against the exact truncated value
   `1/(1-rho) - rho(1-e^{-bT})/(beta(1-rho)^2 T)` and separately asserts it is
   within 1% of `1/(1-rho)`. **Lesson for H6: analytic asymptotics in this
   process are systematically off by O(1/T); finite-window corrections are real.**
2. **Gap independence** — consecutive gaps inside one path are dependent, so the
   pooled-gap KS keeps every 10th gap. Calibration confirms the nominal level
   (1 rejection in 200).
3. **Translation equivariance** — assumed, false. Shifting by `s` gives exactly
   `ell_shifted(theta) = ell(theta) - s * sum(mu)`, so there is no equivariance of
   the *estimate*. Measured at 20000 events: shifting by 10 moves `rho` by 0.4%
   and the loglik by 3.4e-4 per event; shifting by 100 moves them by 4.2% and
   3.4e-3. `mu` is the coordinate most affected.
4. **`mu`-monotonicity at alpha = 0** (`c36404c`) — false as requested. With no
   excitation, `d ell / d mu_i = n_i / mu_i - T`, positive whenever a type has
   more events than its baseline explains over the window.

Also measured at H4 and relevant to interpreting any H6 standard error: the
**variance-to-mean ratio of counts is 3.5 to 4.2 at rho = 0.6**, so a Poisson
standard error would understate by a factor of about 1.9. Overdispersion is
structural here, not a defect.

## 5. H5: throughput and fit cost

Simulator throughput (about 1e6 events, median of three, Windows 11 / MSVC):

- thinning: 3.7e6 to 2.2e7 events/s over M in {2..8}
- cluster: 3.6e6 to 8.0e6 events/s

Fit cost, `benchmarks/results/*_2026-10-19.csv`, one machine:

- M=2: **49 ms** per iteration at N=1e5; **217 ms** at N=1e6
- M=4: **39 ms** at N=1e5; **368 ms** at N=1e6
- a Hessian pass adds `2 * n_params` gradient evaluations

**Peak memory per fit has never been measured.** `tests/test_zero_copy.py` asserts
no RSS growth across 20 repeated `simulate` calls, which catches the leak class but
is not a memory budget. Any figure quoted as bytes-per-fit has no source in this
repository and must not appear in H6.

## 6. Timing probe run for this file (no estimand measured)

Run 2026-10-20 at the section-1 `theta_0`, single process, to support the R
derivation in the preregistration. This measured **wall time only** — no bias, no
coverage, no standard error. It is not an H6 result and does not consume the
pre-registration.

| M | N | sim ms | fit ms | nit | cond(H) | verdict |
|---|---|---|---|---|---|---|
| 2 | 205 | 0.3 | 18.1 | 60 | 4.46e13 | unreliable |
| 2 | 971 | 0.1 | 15.2 | 32 | 1.43e03 | reliable |
| 2 | 1958 | 0.3 | 25.9 | 39 | 7.21e03 | reliable |
| 2 | 4897 | 0.5 | 46.4 | 34 | 7.74e02 | reliable |
| 2 | 20007 | 2.0 | 200.4 | 34 | 5.42e02 | reliable |
| 2 | 49952 | 4.9 | 414.8 | 34 | 4.57e02 | reliable |

M=4 (rho=0.6, `n_params`=36): 177.5 ms at N=1759; 288.7 ms at N=4564; 998.0 ms at
N=20060.

Cost models fitted to those points and used in the preregistration:

- M=2: `t_fit(N) ≈ 10 + 0.008·N` ms
- M=4: `t_fit(N) ≈ 98 + 0.0448·N` ms

One incidental observation worth carrying carefully, because it is a single draw
and not a result: at N≈205 the condition number was 4.46e13 and the verdict
`unreliable`, while every larger N was `reliable` with condition below 1e4. A
single replication says nothing about a rate; H6 measures whether the verdict
tracks coverage, and that is what H6.6 is for.

## 7. What is *not* known, stated plainly

- Behaviour at any rho other than 0.30. The entire high-rho region, which is the
  regime users care about most, is unmeasured.
- Behaviour at M > 2 beyond one H3 single-fit check.
- Whether the Hessian standard errors understate or overstate sampling spread.
  H3 measured `bias` against Monte Carlo error and `coverage` against the
  intervals, but never `mean reported SE` against `empirical SD` as a ratio. That
  comparison has never been made and is the primary contribution H6 can offer.
- The effect of timestamp quantisation. The library has no resolution parameter;
  `fit()` accepts any float times including ties. Quantisation is therefore an
  input-transform question, not a library question.
- Whether the `trust.py` thresholds (condition 1e6, events-per-parameter 10)
  separate anything. They are documented as uncalibrated engineering judgement.
