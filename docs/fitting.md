# Fitting

`fit(times, types, ..., M=..., T=...)` maximises the log-likelihood over $\mu$,
$\alpha$ and $\beta$ and returns a `FitResult`. This page lists the choices and
what each one costs or hides. The reference entry is [](reference.md).

## Inputs

`times` must be sorted and non-negative, `types` integers in `0..M-1` (at most 256
types). `M` is required unless `mu` or `alpha` is passed. `T` is the end of the
observation window and defaults to the last event time; pass it explicitly when the
window runs past the last event, because the likelihood depends on it through the
compensator.

## Optimiser and start values

The optimiser is L-BFGS-B on the log of every parameter, with the analytic
gradient, so positivity is built in. The search for each $\beta$ is confined to
$[1/(10T),\; 10 / g_{\min}]$, where $g_{\min}$ is the smallest positive gap between
events. A coordinate that stops on either end is a boundary value, not a stationary
point; `bound_hit` is `True` and `bound_coordinates` names it.

The first start is a moment estimate: baselines from event counts, a rank-one
branching matrix with $\rho = 0.5$, and a decay set from the median gap. With
`n_starts > 1` the extra starts perturb it in log space and the best likelihood
wins. That is the best of the starts, not a proof of a global optimum: along the
alpha-beta ridge several parameter vectors can have the same likelihood. `seed`
makes a multi-start and a bootstrap reproducible; `seed=None` does not.

## Model options

- `shared_decay=True` estimates one decay per source ($\beta_{ij} = \beta_j$, `beta`
  of shape `(M,)`). This is a different model from the pair-decay one, with $M$
  decay rates instead of $M^2$. The calibration study measured pair decay only, so
  `trust_lookup` says nothing about a shared-decay fit.
- `zero_diagonal=True` fixes $\alpha_{ii} = 0$ by removing those coordinates from
  the free vector.
- `mu=`, `alpha=` or `beta=` hold a whole block fixed. A block is fixed entirely or
  estimated entirely.

## Standard errors

`se_method="hessian"` (the default) differentiates the analytic gradient to get the
observed information and inverts it. When the matrix cannot be inverted to the
stated tolerance, `se` and `cov` are `None` and `notes` says why; no number is
invented. The calibration study measured this method.

`se_method="bootstrap"` simulates from the fitted model and refits `n_bootstrap`
times (default 200). It is slow. From the [capability table](performance.md), at
two types and $N = 10^5$ with $B = 200$ it took 70 s on one worker; at four types
and $N = 10^5$ it took 8.5 min on one worker and 86 s on the default pool of that
machine's 24 logical cores. The calibration study did not measure this method, so
nothing here says it is more honest than the Hessian one. On Windows and macOS it
starts worker processes and the calling script needs an
`if __name__ == "__main__":` guard. Without one, Python 3.11 and later raise an
error that names it; Python 3.10 on Windows can hang instead, because of a
CPython defect, so use the guard there. It computes no Hessian condition number, so
`hessian_condition` is `None` and the conditioning checks in `reliable` are
skipped.

`se_method=None` computes no standard errors, and `reliable` is then
`"unreliable"` by construction.

For the Hessian method, the measured ratio of mean reported standard error to
empirical standard deviation is on [](limits.md).

## Reading the result

`converged` is true when the gradient of the log-parameterised objective,
recomputed at the returned point, is below $10^{-6}\max(1, |\ell|)$ and the
optimiser did not stop on its iteration limit. It is a statement about the
optimiser.

`reliable` is a **conditioning report**, nothing more. It reads the Hessian
condition number, whether a coordinate hit a bound, how close $\rho$ is to 1, the
largest correlation between a log-$\alpha$ and a log-$\beta$ coordinate, and the
number of events per free parameter, against thresholds that are engineering
judgement (`hawkes_engine.trust.THRESHOLDS`). The study measured it. It separates
coverage mostly because fits it labels `unreliable` mostly have no standard error,
and it labelled 3211 fits `reliable` whose $\hat\beta$ was more than ten times the
largest true $\beta$. Both are on [](limits.md) with their evidence.

`rho_ci` is a first-order delta-method interval for $\rho$, and is `None` when no
covariance exists.

## Assumptions the fit does not check

All events are observed: no censoring, no missing data. The kernel is a sum of
exponentials with non-negative weights; inhibition is not modelled. The events are
a single realisation on one window. None of this is tested on the input.
