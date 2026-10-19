# hawkes-engine

Multivariate Hawkes processes for Python, built around a question most
libraries leave to the user: *when can you trust the fit?*

A Hawkes process is a point process that excites itself — every event raises the
intensity for a while afterwards, so events cluster. Fitting one to real data is
routine; knowing whether the resulting parameters mean anything is not. When
the branching ratio approaches one, the decay rates and excitation weights trade
off against each other, the likelihood flattens along a ridge, and an optimizer
will happily return a confident-looking number that is wrong by an order of
magnitude. hawkes-engine reports that region explicitly instead of hiding it.

[![Tests](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml/badge.svg)](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/test.yml)
[![Docs](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/docs.yml/badge.svg)](https://freddysccheung-067.github.io/hawkes-engine/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Status

**Pre-alpha.** Gate H1 of 9 is complete. What exists today:

- A written specification (`docs/spec/mathematics.md`) covering the likelihood,
  gradient, stability condition and both simulation algorithms
- A frozen reference implementation in NumPy, verified against complex-step
  differentiation over every parameter entry
- A C++20 build path that compiles and imports on Linux, macOS and Windows
- Eight architecture decision records

What does not exist yet: the estimator, the simulators, the Python API and the
trust map. Installation works; nothing in it is useful for fitting data.
See [docs/ROADMAP.md](docs/ROADMAP.md) for what each gate proves.

## Installation

Not on PyPI yet. Building from source requires a C++20 compiler and CMake 3.24
or newer:

```bash
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
pip install -e ".[test]"
pytest
```

On Windows this needs Visual Studio 2022 with the C++ workload; on macOS,
`xcode-select --install`; on Linux, GCC 10 or newer.

## Design

| Document | Contents |
|----------|----------|
| [docs/spec/mathematics.md](docs/spec/mathematics.md) | The specification. Normative. |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Gates H0–H9 and their exit tests |
| [docs/verification-rule.md](docs/verification-rule.md) | How correctness is established, and why the reference is frozen |
| [docs/adr/](docs/adr/) | Architecture decision records |

The reference implementation is written from the specification before the fast
one exists, and is frozen with a pre-commit hook. Everything compiled is tested
against it. The point is that the thing doing the checking cannot be quietly
edited to agree with the thing being checked.

## Contributing

The repository is a work in progress and the gates are sequential; the most
useful contribution right now is a defect report against the specification or
the reference implementation. See `CLAUDE.md` for build commands and the rules
the code is held to.

## License

MIT — see [LICENSE](LICENSE).
