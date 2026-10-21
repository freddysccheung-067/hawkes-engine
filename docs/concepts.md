# Concepts

The notation is that of the [specification](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/spec/mathematics.md),
which is normative and holds the derivations. This page states what the code
computes and what it costs.

## The model

There are $M$ event types. The intensity of type $i$ at time $t$ is

$$\lambda_i(t) = \mu_i + \sum_{j=1}^{M} \sum_{t^j_m < t} \alpha_{ij}\, e^{-\beta_{ij}(t - t^j_m)}.$$

$\mu_i$ is a baseline rate, $\alpha_{ij}$ the jump a type-$j$ event adds to the
intensity of type $i$, and $\beta_{ij}$ the rate at which that jump decays. Only
exponential kernels and non-negative $\alpha$ are supported. The sum is over
strictly earlier events, so two events at the same timestamp do not excite each
other.

**Index convention.** Row is the target, column is the source: `alpha[i, j]` acts
from type `j` onto type `i`. This is the transpose of some references and is fixed
by [ADR-002](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/adr/ADR-002-parameterization.md).
A transposed `alpha` runs without error and describes a different process.

## Branching ratio and stationarity

The branching matrix is $\Gamma_{ij} = \alpha_{ij} / \beta_{ij}$, the expected
number of type-$i$ children of one type-$j$ event. The process is stationary when
the spectral radius $\rho(\Gamma) < 1$, and its mean intensity is then
$(I - \Gamma)^{-1}\mu$. `spectral_radius` and `stationary_mean` compute both from
parameters alone. `simulate` refuses parameters with $\rho \ge 1$. `fit` does not
constrain $\rho$ to be below 1 and reports whatever it finds.

## The log-likelihood and the one-pass recursion

For events observed on $[0, T]$,

$$\ell(\theta) = \sum_{i=1}^{M}\left[\sum_k \log \lambda_i(t^i_k) - \int_0^T \lambda_i(t)\,dt\right].$$

Evaluated directly this is quadratic in the number of events $N$. Exponential
kernels allow a recursion: keep the $M^2$ states
$S_{ij}(t) = \sum_{t^j_m < t} e^{-\beta_{ij}(t - t^j_m)}$, decay all of them by
$e^{-\beta_{ij}\Delta}$ between consecutive events, and add 1 to $S_{id}$ for every
$i$ when an event of type $d$ arrives. The likelihood and its gradient come out of a
single pass over the sorted events.

**Cost.** One evaluation is $O(N M^2)$ time and $O(M^2)$ extra memory for pair
decay, and $O(NM)$ when the decay depends only on the source
(`shared_decay=True`). The measured cost per event, fit times and memory are on
[](performance.md). The reference implementation the compiled code is checked
against is the naive quadratic one.

## Two simulators

`simulate` has two algorithms, `method="thinning"` (Ogata's modified thinning) and
`method="cluster"` (the branching representation: Poisson immigrants, each event
producing Poisson($\Gamma_{ij}$) children after Exp($\beta_{ij}$) delays). They are
written separately and share only the random-number generator and the argument
checks. That is the reason there are two: each is tested against the analytic
stationary mean and against the other, so a defect in one is not hidden by the same
defect in the other. Both sample the same law; neither is a fallback.

Both start from an empty history unless `burn_in` is given, which leaves the
intensity below its stationary level early in the window. The calibration study
discarded ten relaxation times, $10 / (\beta_{\min}(1 - \rho))$.

## Time rescaling

If the parameters are right, the integrated intensity between consecutive events of
each type is an independent Exp(1) variable (Papangelou). `time_rescale` returns
those gaps per type. The first gap of a type runs from time 0, and the stretch
after its last event is dropped. `ks_test` checks the marginal law and
`hawkes_engine.diagnostics.ljung_box` checks independence; the first can pass while
the second fails.

## Time origin

Event times are floats. Epoch seconds near $1.7 \times 10^9$ leave about
$2 \times 10^{-7}$ s of resolution, so subtract the session start before calling
([ADR-003](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/adr/ADR-003-memory-layout.md)).
