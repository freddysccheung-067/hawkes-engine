# hawkes-engine

[![Tests](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml/badge.svg)](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml)

Multivariate Hawkes processes with exponential kernels for Python: a compiled
likelihood and gradient, a maximum-likelihood fit with standard errors, two
independent exact simulators, time-rescaling diagnostics, and a lookup of what a
pre-registered simulation study measured about the fit's standard errors in a given
regime.

## Status

**Pre-alpha. Not on PyPI.** 0.2.0 adds `se_method="auto"`: the fit consults a
pre-registered calibration study and, where the study measured that the
inverse-Hessian interval is too narrow in that regime, reports a bootstrap interval
instead, saying which it used and why. Where the study has no measurement it keeps
the Hessian interval and labels it uncalibrated; where it says the estimator is
undefined it reports no interval. The wheel matrix is CPython 3.10 to 3.12 on Linux
x86-64, macOS (x86-64 and arm64) and Windows AMD64, built by CI and not yet
published.

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
print(fit.se_source)  # "hessian": which method produced fit.se
print(fit.alpha.round(3).tolist(), fit.se["alpha"].round(3).tolist())
print(he.trust_lookup(N=len(times), rho_hat=fit.rho, beta=fit.beta.min(), T=20000.0).status)
```

Rows are targets and columns are sources: `alpha[i, j]` is the excitation a type-`j`
event applies to type `i`.

The default method is `"hessian"`, which costs nothing extra and is the method the
calibration study measured. `he.fit(..., se_method="auto")` lets that measurement
choose instead: it looks the fitted regime up, and where the reported interval was
measured to be too narrow it switches to a parametric bootstrap, which refits the
model 200 times. That is slower, so `auto` projects the cost first and refuses to
exceed `auto_max_seconds` (default 120), keeping the Hessian interval with a note
and a warning if it would. `fit.se_source` is `"hessian"`, `"bootstrap"` or
`"none"`, and `fit.se_note` is one sentence saying why.

## What was measured

Over 128 simulation cells with 2000 replications each, the standard errors the fit
reports were smaller than the spread of its estimates: the ratio of mean reported
standard error to empirical standard deviation is 0.779 +/- 0.011 pooled over the 12
cells of two types with at least 2000 events, and 0.61 for the decay block. The
estimator is undefined where the observation window holds only a fraction of one
decay time.

## What is not established

- Two of the six pre-registered hypotheses, H6.3 and H6.4, were not confirmed. H6.6
  was confirmed but is mostly mechanical: 96.4 percent of `unreliable` fits have no
  standard error to begin with.
- `FitResult.reliable` is a conditioning report, not a statement about bias or
  coverage. It labelled fits `reliable` whose decay estimate was more than ten times
  the truth.
- Nothing above one million events was timed, every timing is from one machine, and
  only two types (and a four-type satellite) were calibrated.
- No comparison with any other library has been made.

Each item, with its evidence, is on the [Limits page](docs/limits.md).

## Installation

Not on PyPI. Build from source (a C++20 compiler and CMake 3.24 are required) or
install a wheel from the Actions tab:

```bash
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"   # .venv\Scripts\ on Windows
.venv/bin/python examples/01_simulate_and_fit.py
```

[docs/install.md](docs/install.md) has the commands for each operating system.

## Where the evidence is

| Question | File |
|---|---|
| What the fit's standard errors were measured to do | [studies/results/analysis/hypotheses.json](studies/results/analysis/hypotheses.json), [paper/draft.md](paper/draft.md) |
| How the study was designed, before it ran | [docs/preregistration.md](docs/preregistration.md) at the tag `H6-preregistration` |
| What each gate established, and what is open | [docs/STATE.md](docs/STATE.md) |
| How long a fit takes, and how much memory | [benchmarks/results/capability_2026-10-21.md](benchmarks/results/capability_2026-10-21.md) |
| The mathematics the code implements | [docs/spec/mathematics.md](docs/spec/mathematics.md) |
| Why the reference implementation is frozen | [docs/verification-rule.md](docs/verification-rule.md) |

Documentation: https://freddysccheung-067.github.io/hawkes-engine/. The
`examples/` directory has five scripts that run in CI. See also
[CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[CHANGELOG.md](CHANGELOG.md).

## License

MIT: see [LICENSE](LICENSE).
