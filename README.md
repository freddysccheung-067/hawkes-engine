# hawkes-engine

Multivariate Hawkes processes for Python, built around a question most libraries
leave to the user: *when can you trust the fit?*

A Hawkes process is a point process that excites itself: every event raises the
intensity for a while afterwards, so events cluster. Fitting one to real data is
routine; knowing whether the parameters mean anything is not. As the branching
ratio approaches one, the decay rates and the excitation weights trade off
against each other, the likelihood flattens along a ridge, and an optimizer will
return a confident-looking number that is wrong by an order of magnitude.
hawkes-engine reports that region instead of hiding it.

[![Tests](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml/badge.svg)](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml)
[![Docs](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/docs.yml/badge.svg)](https://freddysccheung-067.github.io/hawkes-engine/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Status

**Pre-alpha.** Gate H5 of nine is complete; H9 is the first release.

What exists today:

- A written specification (`docs/spec/mathematics.md`) covering the likelihood,
  gradient, stability condition and both simulation algorithms
- A frozen NumPy reference implementation, verified against complex-step
  differentiation over every parameter entry, and unchanged since it was tagged
- A compiled C++20 likelihood and gradient, agreeing with that reference to a
  measured 7.5e-14 relative on the value and 3.6e-12 per gradient entry
- A maximum-likelihood estimator with analytic gradients, Hessian standard
  errors, a parametric bootstrap, and a reliability verdict per fit
- Two independent exact simulators (Ogata thinning and the branching
  representation) that are tested against each other and against the stationary
  mean
- Time-rescaling diagnostics: rescaled gaps, KS and Ljung-Box tests, Q-Q data
- Wheels for CPython 3.10-3.12 on Linux x86-64, macOS x86-64 and arm64, and
  Windows AMD64, built by CI

What does not exist yet: the performance characterisation (H7) and a PyPI
release (H9). The trust calibration map ships as of H6, measured over 128
simulation cells and 2000 replications per cell; `trust_lookup` answers from it or
says `"unknown"` outside the measured box. `FitResult.reliable` is separate and
reports only whether *this* fit is well conditioned, not whether it is unbiased.

## Installation

**Not on PyPI.** During pre-alpha, build from source or install a CI wheel:

```bash
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"   # .venv\Scripts\ on Windows
```

This needs a C++20 compiler and CMake 3.24. `docs/install.md` has the exact
commands for each OS, including the Visual Studio workload on Windows.

## Usage

```python
import numpy as np
import hawkes_engine as he

rng = np.random.default_rng(0)
mu = np.array([0.6, 0.9])
alpha = np.array([[0.10, 0.35], [0.20, 0.05]])   # row = target, column = source
beta = np.array([[1.30, 1.70], [1.30, 1.70]])

times, types = he.simulate(mu, alpha, beta, T=2000.0, seed=1)
result = he.fit(times, types, M=2, seed=1)
print(result)
print(result.reliable, result.rho)
```

Convince yourself of the conventions before using them: **rows are targets and
columns are sources**, so `alpha[i, j]` is the excitation a type-`j` event applies
to the intensity of type `i`. Two events at the same timestamp do not excite each
other. `loglik` takes the parameters explicitly and needs no fit:

```python
out = he.loglik(times[:100], types[:100], mu, alpha, beta, T=times[100], grad=True)
print(out["value"], out["dmu"], out["dalpha"], out["dbeta"], sep="\n")
```

## What a fit does and does not claim

`fit` returns a `FitResult` carrying the estimates, their standard errors where
the information matrix is invertible, the branching ratio and its delta-method
interval, and a `reliable` verdict built from the conditioning of the observed
information, whether a coordinate stopped on a search bound, the alpha-beta
correlation, and the event count per parameter.

The verdict is about the fit, not the estimator. A `"reliable"` fit is a
well-conditioned stationary point. Whether the estimator is unbiased at that
sample size, and whether an interval covers at its nominal rate, are measured in
the pre-registered study at H6 and are not claimed yet.

## Design

| Document | Contents |
|----------|----------|
| [docs/spec/mathematics.md](docs/spec/mathematics.md) | The specification. Normative. |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Gates H0-H9 and their exit tests |
| [docs/STATE.md](docs/STATE.md) | What is measured, what is open, what is next |
| [docs/verification-rule.md](docs/verification-rule.md) | How correctness is established, and why the reference is frozen |
| [docs/adr/](docs/adr/) | Architecture decision records |

The reference implementation is written from the specification before the fast
one exists, and is frozen with a pre-commit hook. Everything compiled is tested
against it. The point is that the thing doing the checking cannot be quietly
edited to agree with the thing being checked.

Releasing the GIL is part of the contract, not an optimisation: a multi-second
likelihood evaluation must not stall every other thread in the caller's process.
`tests/test_gil.py` proves it by measuring a Python counter's rate during a C++
call against its rate on its own.

## Cost

Measured fit times, peak memory and bootstrap cost for one machine, across M, N
and the branching ratio, are in
[benchmarks/results/capability_2026-10-21.md](benchmarks/results/capability_2026-10-21.md),
including the configurations that are slow. Each figure there is produced by a
script in `benchmarks/`.

## Contributing

The repository is a work in progress and the gates are sequential; the most
useful contribution right now is a defect report against the specification or the
reference implementation. See `CLAUDE.md` for build commands and the rules the
code is held to.

## License

MIT: see [LICENSE](LICENSE).
