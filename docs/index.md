# hawkes-engine

Multi-dimensional Hawkes process library with trust calibration.

**Status: pre-alpha.** Gate H1 of 9 is complete. The specification, the
architecture decisions, the frozen reference implementation and the compiled
build are in place. The estimator, simulators and trust map arrive in later
gates; see the [roadmap](ROADMAP.md).

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

## Design documents

- `docs/spec/mathematics.md` — the specification. Normative for every formula
  the code implements.
- `docs/adr/` — architecture decision records, numbered. They record why
  decisions were made, which is useful to maintainers and noise for users, so
  they are kept in the repository rather than published here.
- [Roadmap](ROADMAP.md) — the gates and what each one proves.
- [Verification rule](verification-rule.md) — how correctness is established,
  and why the reference implementation is frozen.

## Installation

hawkes-engine is not on PyPI yet. To build from source:

```bash
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
pip install -e "."
```

A C++20 compiler and CMake 3.24 or newer are required. Wheels will be published
at v0.1.0.

## License

MIT. See `LICENSE` in the repository root.
