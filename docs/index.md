# hawkes-engine

Multivariate Hawkes processes with exponential kernels for Python: a compiled
likelihood and gradient, a maximum-likelihood fit with standard errors, two
independent exact simulators, time-rescaling diagnostics, and a lookup of what a
pre-registered simulation study measured about the fit's standard errors in a given
regime.

**Status: 0.1.0 on [PyPI](https://pypi.org/project/hawkes-engine/), pre-alpha.**
`python -m pip install hawkes-engine`. See [](install.md) for the platforms it is
built for and for building from source.

## A fit in a few lines

```python
import numpy as np
import hawkes_engine as he

mu = np.array([0.6, 0.9])
alpha = np.array([[0.10, 0.35], [0.20, 0.05]])  # row = target, column = source
beta = np.array([[1.30, 1.70], [1.30, 1.70]])

times, types = he.simulate(mu, alpha, beta, T=20000.0, seed=1)
fit = he.fit(times, types, M=2, T=20000.0, seed=1)
print(fit)
print(he.trust_lookup(N=len(times), rho_hat=fit.rho, beta=fit.beta.min(), T=20000.0).status)
```

## What was measured

Over 128 simulation cells with 2000 replications each, the standard errors the fit
reports were smaller than the spread of its estimates: the ratio of mean reported
standard error to empirical standard deviation is 0.779 +/- 0.011 pooled over the
12 cells of two types with at least 2000 events, and 0.61 for the decay block. The
estimator is undefined where the window holds only a fraction of one decay time.

## What is not established

- Two of the six pre-registered hypotheses, H6.3 and H6.4, were not confirmed. H6.6
  was confirmed but is mostly mechanical: 96.4 percent of `unreliable` fits have no
  standard error to begin with.
- `FitResult.reliable` is a conditioning report. It labelled fits `reliable` whose
  decay estimate was more than ten times the truth.
- Nothing above one million events was timed, every timing is from one machine, and
  only two types (and a four-type satellite) were calibrated.
- No comparison with any other library has been made.

The full list, each item with its evidence, is on [](limits.md).

## Where the evidence is

The specification (`docs/spec/mathematics.md`), the architecture decision records
(`docs/adr/`), the pre-registration (`docs/preregistration.md`), the project state
(`docs/STATE.md`) and the competitor survey (`docs/competitor-analysis.md`) are kept
in the [repository](https://github.com/freddysccheung-067/hawkes-engine) rather than
published here. Measurements are in `studies/results/analysis/` and
`benchmarks/results/`.

```{toctree}
:maxdepth: 1
:caption: User guide

quickstart
concepts
fitting
trust
limits
performance
reference
```

```{toctree}
:maxdepth: 1
:caption: Project

install
ROADMAP
verification-rule
release_notes_0.1.0
```

## License

MIT. See `LICENSE` in the repository root.
