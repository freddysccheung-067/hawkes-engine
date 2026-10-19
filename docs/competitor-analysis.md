# Hawkes Process Library Competitive Analysis

**Check date:** 2026-10-19
**Purpose:** record the state of the surrounding ecosystem so that claims about
hawkes-engine can be made against verified facts rather than recollection.

Every number and every yes/no statement below was read from a live endpoint on
2026-10-19. Where the endpoint is not obvious from context, the URL is given
inline. Star counts, push dates and release dates move; treat this document as a
snapshot and re-check before quoting it in public material. Claims that could not
be verified against a primary source were removed rather than softened, because
a hedged claim in a public repository reads as a verified one.

## Summary Table

| Library | Repository | Stars (checked 2026-10-19) | Last push | Latest release | Multivariate Hawkes | Notes |
|---|---|---|---|---|---|---|
| tick | X-DataInitiative/tick | 558 | 2026-06-15 | PyPI 0.8.0.2, 2026-05-04 | Yes | MKL-based C++ core; wheels for CPython 3.11–3.14 on x86_64 Linux, x86_64 Windows and both macOS architectures |
| hawkeslib | canerturkmen/hawkeslib | 72 | 2022-06-03 | PyPI 0.2.2, 2019-06-18 | README says no; source contains a multivariate class | README marks the project deprecated; documentation and code disagree |
| statsmodels | statsmodels/statsmodels | 11,691 | 2026-10-18 | PyPI 0.15.0, 2026-08-27 | No | No Hawkes or point-process module in the API index |
| PyMC | pymc-devs/pymc | 9,814 | 2026-10-18 | PyPI 6.3.2, 2026-09-08 | No built-in distribution | Hawkes likelihoods require a user-supplied custom distribution or potential |
| hawkes (CRAN) | none listed on CRAN | n/a | n/a | CRAN 0.0-4, 2014-05-19 | Yes, per the package description | Simulation and count moments; no release in more than twelve years |
| emhawkes (CRAN) | ksublee/emhawkes | 5 | 2026-10-18 | CRAN 1.0.1, 2026-10-18 | Yes | Exponential kernels, maximum likelihood, Rcpp |

The star and push values for the four GitHub repositories come from
`https://api.github.com/repos/OWNER/REPO`. Release versions and their dates come
from the PyPI JSON API and the CRAN package pages, both named in the sections
below.

## tick

tick is the largest and most complete of the libraries surveyed. The repository
`X-DataInitiative/tick` reported 558 stars, a `pushed_at` of 2026-06-15 and
`archived: false` (checked 2026-10-19). The most recent commit returned by
`/commits?per_page=1` is `a40d19f868c22469be90c1e6c50bc3dab26ff070`, committed
2026-05-04. The difference between those two dates is normal: `pushed_at` counts
pushes to any branch, the commit query reports the default branch.

On PyPI the package `tick` is at 0.8.0.2, uploaded 2026-05-04, with
`requires_python` `>=3.11` (`https://pypi.org/pypi/tick/json`). The 0.8.0.2
release consists of sixteen wheels and no source distribution: CPython 3.11
through 3.14, each in `macosx_11_0_arm64`, `macosx_11_0_x86_64`,
`manylinux_2_27/2_28_x86_64` and `win_amd64` builds. There is no Linux AArch64
wheel. Anyone on an ARM Linux machine still compiles from source, and a source
build needs the C++ toolchain that the README describes, along with Intel MKL,
which the project uses as its numerical backend.

The documentation describes the process as "a \(D\)-dimensional counting
process" and its `SimuHawkes` constructor takes an `n_nodes` argument that one
bundled example annotates as "dimension of the Hawkes process"
(`https://x-datainitiative.github.io/tick/modules/hawkes.html`). Multivariate
Hawkes is therefore a documented feature, not an inference from the feature
list.

The documentation does not name the sampling algorithm behind `SimuHawkes`.
Neither the Hawkes module page nor the example index mentions Ogata thinning,
cluster construction or any other method, so this analysis makes no statement
about how tick generates paths. Estimation covers maximum likelihood and
least squares with exponential, sum-of-exponential and Gaussian basis kernels,
and non-parametric learners including an EM variant following Lewis and Mohler
(2011).

## hawkeslib

`canerturkmen/hawkeslib` reported 72 stars, `pushed_at` 2022-06-03 and
`archived: false` (checked 2026-10-19). The latest commit,
`6837948f6379711ae27332bfd1faea6bc5230da8`, carries the same 2022-06-03
timestamp. The repository is not archived, so it could resume, but nothing has
been pushed in more than four years.

On PyPI, `hawkeslib` is at 0.2.2, uploaded 2019-06-18, with `requires_python`
`>=2.7.5` (`https://pypi.org/pypi/hawkeslib/json`). No release has been made
since 2019.

The project's own README marks it deprecated. It states that the author can no
longer develop or support the library and points users to `tick` or `pyhawkes`
instead. It describes the scope as "plain-vanilla" Hawkes processes "with
factorized triggering kernels with exponential decay functions", which is a
univariate, exponential-kernel claim.

The source does not match that description. `hawkeslib/model/mv_exp.py` defines
a `MultivariateExpHawkesProcess` class whose `fit` method documents EM, and
whose `sample` method states that it relies "on the clustering property of
Hawkes processes (and not Ogata's thinning method)". A multivariate
exponential-kernel fit and a branching sampler therefore exist in the tree, but
they are undocumented in the README and the project that produced them is
abandoned. Anyone evaluating hawkeslib should read `mv_exp.py` rather than the
README, and should expect no maintenance.

Two claims in earlier versions of this document are not supported and have been
removed: that hawkeslib supports power-law kernels (no power-law support appears
in the README, the docs or the model directory), and that its simulator is a
single Ogata loop (the one sampler in the tree explicitly is not Ogata thinning).

## statsmodels

`statsmodels/statsmodels` reported 11,691 stars, `pushed_at` 2026-10-18 and
`archived: false` (checked 2026-10-19). PyPI `statsmodels` is at 0.15.0,
uploaded 2026-08-27, `requires_python` `>=3.10`.

statsmodels has no Hawkes module and no point-process module. The word "Hawkes"
does not occur on the time-series API page
(`https://www.statsmodels.org/stable/tsa.html`) or in the full API index
(`https://www.statsmodels.org/stable/api.html`); the nearest neighbours are
count models such as Poisson and negative binomial, which model counts per
period rather than event times. A user who needs a Hawkes likelihood writes it
themselves.

This is a scope boundary rather than a deficiency. statsmodels is an
econometrics library, and its ARIMA, VAR, state-space and count-model
implementations are what most users come for. The relevant consequence for this
project is only that statsmodels will not absorb a Hawkes workload, so a
dedicated library has somewhere to sit.

## PyMC

`pymc-devs/pymc` reported 9,814 stars, `pushed_at` 2026-10-18 and
`archived: false` (checked 2026-10-19). PyPI `pymc` is at 6.3.2, uploaded
2026-09-08, `requires_python` `>=3.12`.

PyMC ships no Hawkes distribution. The distributions index
(`https://www.pymc.io/projects/docs/en/stable/api/distributions.html`) has no
entry containing "Hawkes", and its time-series family covers `AR`, `GARCH11`,
`EulerMaruyama` and random walks. A Hawkes model has to be expressed through
`CustomDist` or `Potential`, with the log-likelihood written by hand, and the
resulting posterior sampling cost scales with the number of events because the
likelihood touches every event pair.

PyMC is the right tool when the goal is a posterior over parameters with
priors, hierarchy or latent structure. It is not a substitute for a frequentist
estimator, and no claim here should be read as one being faster in general:
no benchmark comparing the two exists in this repository, because this project
has no estimator to run.

## CRAN: hawkes and emhawkes

The CRAN package `hawkes` is at version 0.0-4, published 2014-05-19
(`https://cran.r-project.org/web/packages/hawkes/`). It is maintained by Riadh
Zaatour and depends on R 3.0.2 or later, Rcpp and RcppArmadillo. Its description
states that it simulates Hawkes processes "both in univariate and multivariate
settings" and computes moments of the jump count over an interval, including
mean, variance and autocorrelation at a lag. The landing page does not state
which kernel form it implements. No release in twelve years means the package
predates most of the modern R ecosystem, and its behaviour on current R versions
is something a user would have to test rather than assume.

The CRAN package `emhawkes` is at version 1.0.1, published 2026-10-18
(`https://cran.r-project.org/web/packages/emhawkes/`). It simulates and fits
multivariate Hawkes models with exponential kernels, including marked,
state-dependent and multi-kernel specifications, by maximum likelihood
following Ozaki (1979), using either the optional `maxLik` package or R's own
optimisers. It requires R 4.0.0 or later and uses Rcpp, so installation
compiles. The corresponding GitHub repository `ksublee/emhawkes` reported 5
stars, `pushed_at` 2026-10-18 and `archived: false` (checked 2026-10-19).

Neither the emhawkes README nor its vignette names the algorithm behind `hsim`.
The vignette describes the shape of the input and output but not the sampling
method, so this document makes no claim about whether it uses thinning or a
branching construction.

The obvious limitation of both R packages is the language boundary. Neither can
be called from a Python process without an R bridge, and neither interoperates
with NumPy arrays at the API level.

## Where hawkes-engine stands

hawkes-engine is pre-alpha. Gate H0 and gate H1 of the nine-gate plan are
complete: the package skeleton exists and imports, and there is a frozen
reference implementation of the likelihood and gradient whose gradient agrees
with complex-step differentiation to 1e-10. Gate H2, the C++ likelihood and
gradient, is next (`docs/ROADMAP.md`).

Nothing user-facing exists yet. There is no estimator, no simulator, no public
fit API, no PyPI release, no published wheel and no trust map. The library
cannot currently fit or simulate a Hawkes process, and no statement in this
document should be read as claiming otherwise.

The planned work, in the order the roadmap sets it, is the C++ likelihood at H2,
maximum likelihood estimation with standard errors at H3, thinning and
branching simulators at H4, the Python API and I/O at H5, the trust calibration
study at H6, performance characterisation at H7, documentation at H8 and the
v0.1.0 release with wheels at H9. The distinguishing feature of the project,
the map from parameter values to expected recovery error, is produced and
validated at H6. Until then the roadmap commits only to reporting the branching
ratio with every fit and treating a value near one as a warning.

Because no code in this repository can fit or simulate anything yet, no speed
or accuracy comparison against any library in this document has been run, and
none is reported. The earlier claim of a four- to ten-fold speed advantage over
hawkeslib had no measurement behind it and has been removed. A benchmark would
need an estimator first, which H3 provides, and would be meaningful only once
the performance characterisation at H7 defines what is being measured.

The honest summary of the comparison is narrow. tick is actively maintained,
supports multivariate Hawkes and now publishes wheels for the common platforms,
though it is MKL-based, has no Linux AArch64 wheel and does not document its
simulation algorithm. hawkeslib is deprecated and undocumented. statsmodels and
PyMC do not model Hawkes processes directly. The two CRAN packages are
functional but R-only. Whether a new Python library improves on any of this is
a question that gates H3 through H7 have to answer with measurements, and this
document will be rewritten then rather than anticipating the result.
