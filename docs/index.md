# hawkes-engine

Multi-dimensional Hawkes process library with trust calibration.

**Status: pre-alpha.** Gate H5 of 9 is complete. The specification, the
architecture decisions, the frozen reference implementation, the compiled
likelihood with its gradient, the estimator, both exact simulators, the
time-rescaling diagnostics and the reliability report are in place. The trust
calibration map (H6), the performance characterisation (H7) and PyPI wheels (H9)
arrive in later gates.

## What is a Hawkes process

A Hawkes process is a point process whose intensity rises after every event and
decays back towards a baseline. One event makes the next more likely. The
multivariate form has one intensity per event type, with cross-type excitation:

$$
\lambda_i(t) = \mu_i + \sum_j \sum_{t^j_m < t} \alpha_{ij} e^{-\beta_{ij}(t - t^j_m)}
$$

Here $\mu_i$ is the baseline rate of type $i$, $\alpha_{ij}$ is the excitation
that a type-$j$ event injects into type $i$, and $\beta_{ij}$ is the decay rate
of that excitation.

## Contents

```{toctree}
:maxdepth: 1

install
ROADMAP
verification-rule
```

The specification (`docs/spec/mathematics.md`) and the architecture decision
records (`docs/adr/`) are kept in the repository rather than published here.
The specification is normative for every formula the code implements; the ADRs
record why decisions were made, which is useful to maintainers and noise for
users.

## Installation

See [](install.md) for building from source, installing a CI wheel, or building
your own wheel with cibuildwheel. hawkes-engine is not on PyPI yet.

## License

MIT. See `LICENSE` in the repository root.
