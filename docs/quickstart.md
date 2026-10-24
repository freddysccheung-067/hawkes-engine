# Quickstart

Simulate a two-type process from known parameters, fit it, read the result, check
the fit by time rescaling, and ask what the calibration study measured for this
regime. The code on this page runs as written after
`python -m pip install hawkes-engine`; see [](install.md) for the other ways to
install it.

```python
import numpy as np
import hawkes_engine as he
from hawkes_engine.diagnostics import ljung_box

mu = np.array([0.6, 0.9])
alpha = np.array([[0.10, 0.35], [0.20, 0.05]])  # row = target, column = source
beta = np.array([[1.30, 1.70], [1.30, 1.70]])
T = 20000.0

times, types = he.simulate(mu, alpha, beta, T=T, seed=1)
fit = he.fit(times, types, M=2, T=T, seed=1)
print(fit)
print("alpha_hat", fit.alpha.round(3).tolist(), "truth", alpha.tolist())
print("se(alpha)", fit.se["alpha"].round(3).tolist())
print("rho", round(fit.rho, 4), "95% interval", np.round(fit.rho_ci, 4).tolist())

gaps = he.time_rescale(times, types, fit.mu, fit.alpha, fit.beta)
print("KS p", he.ks_test(gaps).pvalue.round(3), "Ljung-Box p", ljung_box(gaps).pvalue.round(3))

answer = he.trust_lookup(N=len(times), rho_hat=fit.rho, beta=fit.beta.min(), T=T)
print(answer.status, answer.cell, round(answer.distance, 2))
```

On the reference machine (Windows 11, Python 3.12) this prints the following. The
digits of the estimates can differ in the last places on another platform.

```text
FitResult(M=2, n_params=10, loglik=-39142.4, rho=0.233095, converged, reliable='reliable')
alpha_hat [[0.123, 0.33], [0.182, 0.053]] truth [[0.1, 0.35], [0.2, 0.05]]
se(alpha) [[0.021, 0.018], [0.019, 0.016]]
rho 0.2331 95% interval [0.2115, 0.2547]
KS p [0.882 0.934] Ljung-Box p [0.729 0.617]
measured M2_N50000_rho0.3028_r0.0_c1.0 0.4
```

## What each field means, and what it does not

`simulate` returns `times` (sorted, float64) and `types` (uint8, values `0..M-1`).
The generator is the library's own, so the same seed reproduces the same path on
every platform but does not match `numpy.random`.

`fit` returns a `FitResult`:

| Field | What it is | What it is not |
|---|---|---|
| `mu`, `alpha`, `beta` | Maximum-likelihood estimates. `alpha[i, j]` is the excitation a type-`j` event applies to type `i`. | Not unbiased. The study measured bias in several regimes; see [](trust.md). |
| `se` | Square roots of the diagonal of the inverted observed information, in natural units. `None` when the information matrix cannot be inverted. | Not a measure of sampling spread. See the last paragraph below. |
| `rho`, `rho_ci` | Spectral radius of `alpha / beta` and a delta-method 95% interval. | The interval is first-order and is not valid at a boundary. |
| `converged` | The optimiser stopped at a point where the gradient is small. | Not a statement about the data. |
| `bound_hit` | A coordinate stopped on a search bound; the estimate is then a boundary value. | |
| `reliable` | `"reliable"`, `"marginal"` or `"unreliable"`: a conditioning report built from the Hessian condition number, bound hits, `rho`, the alpha-beta correlation and events per parameter. | Not a statement about bias or coverage. A fit with a wild `beta` can carry `"reliable"`. See [](limits.md). |

`time_rescale` maps the events to gaps that are independent Exp(1) if the
parameters are right. The Kolmogorov-Smirnov test checks their marginal law and the
Ljung-Box test checks their independence. A p-value above 0.05 is the absence of
evidence against the model. The parameters were fitted to the same events, so the
nominal p-values are not calibrated, and [](limits.md) shows a fit the check passes
that is far from the truth.

`trust_lookup` does not look at the fit's data. It takes the fitted regime
(number of events, `rho`, smallest decay rate, window length) and returns what the
H6 study measured at the nearest grid cell, with the distance to that cell. When the
regime is outside the measured box it says `"unknown"`. See [](trust.md).

## The standard errors understate sampling spread

The reported standard errors were measured to understate the sampling spread of the
estimates: over the twelve two-type cells with at least 2000 events the pooled ratio
of mean reported standard error to empirical standard deviation is 0.779 +/- 0.011,
and 0.61 for the decay block alone. The finding, its limits and its evidence are on
[](limits.md).
