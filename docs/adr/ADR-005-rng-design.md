# ADR-005: RNG and Seed-Stream Design

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

Simulation (mathematics.md §6) needs random numbers for Poisson processes and
exponential waiting times. Reproducibility matters: the same seed must produce
the same event sequence on every run, on every platform, so that regression
tests mean something and a reported simulation can be re-run.

The original version of this ADR contained a design that cannot be built. It
specified "Philox 4×32-10, called from C++ via `numpy::random::Generator`" and
asserted "NumPy's Philox via pybind11 in v0.1". Neither exists. NumPy exposes
its bit generators through `numpy.random`, and its Philox header
(`numpy/random/src/philox/philox.h`) is internal to NumPy's build, not an
installed, linkable API. There is no C++ namespace `numpy::random`, and a
`Generator` is a Python object, not something a C++ core can call without
holding the GIL and paying a Python call per draw. Those claims are removed
below rather than argued with.

The decision below replaces them with a generator we own outright.

## Decision

- **Algorithm**: SplitMix64 as the seeding function, feeding a PCG64 engine
  (XSL-RR variant, 128-bit state, 64-bit output) for stream generation.
  Both are short, published, and implementable in ~80 lines of standard C++
  with no external dependency.
- **Uniforms**: `double` on the open interval (0, 1): the top 52 bits `k` of one
  64-bit draw, mapped to `(k + 1/2) * 2^-52`. Never 0 and never 1, so both
  `log(U)` and `log1p(-U)` are finite. The first version of this decision used
  53 bits in [0, 1); that admits 0, which breaks `log(U)`, and the 53-bit
  midpoint form rounds its largest value to exactly 1.
- **Exponentials**: inverse transform, `-log1p(-u)`. `log1p` keeps accuracy for
  small `u`, where `-log(u)` would lose it. One uniform per exponential.
- **Seeding**: `uint64_t seed`, expanded through SplitMix64 into the 128-bit
  PCG state. Explicit seed per call; no global state, no default seed.
- **Poisson**: inversion by sequential search for mean < 10, the PTRS
  transformed rejection of Hormann (1993) above. `std::poisson_distribution`
  and `std::exponential_distribution` are not used, because their output is
  implementation-defined.
- **Stream seeds**: `seed_stream(seed, i)` is injective in `i` for a fixed seed.
- **Where it lives**: C++, alongside the simulators. The Python API accepts a
  Python `int` and narrows it to `uint64`.

### What we are not promising

**Bit-matching NumPy's streams is not a goal.** A seed passed to
`hawkes_engine.simulate` will not reproduce what `numpy.random.default_rng(seed)`
would produce, and no test will require it to. This is a deliberate reversal of
the original ADR, which made cross-language bit-for-bit matching the headline
requirement and then could not implement it.

What is promised instead is reproducibility *within* the library: same seed,
same parameters, same version, same events, on every platform. That is the
property the regression tests actually need. If a user needs to reproduce a
NumPy run specifically, they can simulate with NumPy themselves and feed the
result in; the library does not need to be NumPy's twin to be useful.

The test that enforces this is a golden-vector test: a fixed list of
seed → first 16 uniforms, recorded once and checked on every platform in CI.
That catches both algorithm drift and accidental platform dependence.

## Alternatives Considered

### Option 1: Call NumPy's Generator from C++ through pybind11
- **Pros**: Streams match NumPy exactly, no RNG code to maintain
- **Cons**: One Python call and one GIL acquisition per draw. For a simulation
  drawing O(events) variates this dominates the run time, which defeats the
  purpose of having a C++ core. It also makes the core unusable without an
  initialized interpreter.
- **Why rejected**: The cost is in the hot loop, not at the boundary. Bitwise
  agreement with NumPy is not worth a per-draw Python call.

### Option 2: Vendor NumPy's Philox header
- **Pros**: Would actually match NumPy, since it is the same code
- **Cons**: The header is internal to NumPy's build, carries no stability
  promise, and would need to be copied and tracked against upstream. BSD-3
  permits the copying, but the maintenance burden is real for a benefit
  (matching NumPy bit-for-bit) that nothing in the library depends on.
- **Why rejected**: Not worth tracking a third party's private header to gain a
  property we have decided not to require.

### Option 3: `std::mt19937_64`
- **Pros**: In the standard library, no code to write
- **Cons**: The standard does not pin the output stream for all engines —
  `mt19937_64`'s output is specified, but distribution adaptors such as
  `std::uniform_real_distribution` are not, so results can differ between
  standard library implementations. That silently breaks cross-platform
  reproducibility, which is the one thing we are promising.
- **Why rejected**: Reproducibility would depend on which standard library the
  wheel was built against.

### Option 4: Global RNG state
- **Pros**: Seed once, all calls follow
- **Cons**: Breaks under multiprocessing, makes tests order-dependent, and is
  not thread-safe.
- **Why rejected**: Unchanged from the original ADR — explicit seeds only.

## Consequences

**Positive**:
- No external RNG dependency, so the core has no link-time coupling to NumPy.
- Fast: PCG64 is a handful of instructions per draw, entirely in-cache.
- Cross-platform reproducibility is ours to guarantee, and a golden-vector test
  makes that guarantee checkable rather than aspirational.
- The seed space is the full `uint64`.

**Negative**:
- We maintain the generator. It is ~80 lines, but it is ours to get right, and
  a bug in it corrupts every simulation without necessarily failing a test that
  only checks statistics. The golden vectors are the defence.
- Users cannot assume NumPy-compatible streams. The documentation has to say so
  clearly, and the docstring for `simulate` must repeat it.
- No jump-ahead in v0.1. PCG64 supports it in principle; if parallel simulation
  arrives in v0.2, the state advance has to be implemented and tested then.

**Neutral**:
- Seed type is `uint64`. Python `int` is arbitrary precision, so narrowing has
  to be checked explicitly at the API boundary rather than left to truncation.
- Cryptographic quality is not claimed and not needed. This is a simulation
  generator, and it is not used for anything security-relevant.

## References

- O'Neill, M. E. (2014), "PCG: A Family of Simple Fast Space-Efficient
  Statistically Good Algorithms for Random Number Generation", Harvey Mudd
  College technical report HMC-CS-2014-0905.
- Steele, G. L., Lea, D. & Flood, C. H. (2014), "Fast Splittable Pseudorandom
  Number Generators", OOPSLA 2014 — the SplitMix seeding scheme.
- mathematics.md §6: the two simulation algorithms that consume these streams.
- NumPy's own generator documentation, for the record of why matching it is a
  constraint we chose not to adopt: <https://numpy.org/doc/stable/reference/random/generator.html>
