# ADR-005: RNG and Seed-Stream Design

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

Simulation (mathematics.md §6) requires random number generation for Poisson processes and exponential inter-arrival times. Reproducibility is non-negotiable: same seed → same event sequence, across platforms and languages. This enables regression tests, debugging, and scientific reproducibility.

NumPy uses Philox 4×32-10 (default since 1.17, 2019) or PCG64 (opt-in). C++ `<random>` has `std::mt19937` (Mersenne Twister) but no Philox. We need bit-for-bit reproducibility between Python and C++, which means: use the same RNG algorithm in both.

Two approaches: (1) vendor a standalone Philox implementation in C++, or (2) call NumPy's RNG from C++ via pybind11. Option 1 is self-contained but adds maintenance (keep in sync with NumPy). Option 2 is a runtime dependency on NumPy, which we already have (ADR-001). The question: is the coupling worth the simplicity?

Seed management: global state (np.random.seed()) is bad for parallel code and testing. Explicit per-call seeds (simulate(..., seed=42)) are better but verbose. The standard NumPy pattern is Generator objects: `rng = np.random.default_rng(seed)`, then `rng.exponential()`. For v0.1, explicit seeds are simpler.

## Decision

- **RNG algorithm**: Philox 4×32-10 (NumPy default, matches numpy.random.Generator)
- **Seeding**: Explicit seed per call (not global state)
  - Python API: `simulate(mu, alpha, beta, T, seed=42)` → same events every time
  - C++ API: takes `uint64_t seed`, constructs internal Philox state
- **Implementation**: Use NumPy's Philox via pybind11 in v0.1 (calls Python-side Generator), vendor standalone C++ Philox in v0.2 if performance matters
- **C++ fallback**: If standalone C++ is needed, use the reference implementation from [numpy/numpy](https://github.com/numpy/numpy/blob/main/numpy/random/src/philox/philox.h) (BSD-3-Clause)

Why Philox:
- NumPy default (reproducibility across Python/C++)
- Fast: 2–3 ns per random uint32 (vs 10 ns for Mersenne Twister)
- Small state: 160 bits (vs 2.5 KB for mt19937)
- Passes BigCrush (TestU01 suite, gold standard for RNGs)
- Counter-based: can jump ahead efficiently (useful for parallel simulation in v0.2+)

## Alternatives Considered

### Option 1: PCG64 (alternative NumPy RNG)
- **Pros**: Slightly faster than Philox (~1.5 ns per draw), smaller state (128 bits)
- **Cons**: Not NumPy default (user must opt in via `np.random.Generator(np.random.PCG64(seed))`), less widely tested, not counter-based (can't jump ahead easily)
- **Why rejected**: Philox is the NumPy default. Reproducibility with default NumPy behavior is more valuable than 30% RNG speed (RNG is <5% of simulation time anyway).

### Option 2: Mersenne Twister (std::mt19937)
- **Pros**: C++ standard library, no dependencies, widely known
- **Cons**: Huge state (2.5 KB), slow (10 ns per draw), doesn't match NumPy (reproducibility fails), 32-bit output (need to combine two draws for float64), fails some statistical tests (LinearComp in BigCrush)
- **Why rejected**: Can't reproduce NumPy results. Non-negotiable for a scientific library.

### Option 3: Global RNG state (np.random.seed(42))
- **Pros**: User calls seed once, all subsequent calls use that stream
- **Cons**: Global state breaks parallel code (multiprocessing workers share seed, produce identical output), hard to test (one test's seed affects the next), not thread-safe, discouraged by NumPy since 1.17
- **Why rejected**: Explicit seeds are the NumPy-recommended pattern since 2019. Global state is a bug magnet.

### Option 4: Pass Generator object (like NumPy)
- **Pros**: Idiomatic NumPy (`rng = np.random.default_rng(42); he.simulate(mu, alpha, beta, T, rng=rng)`), user controls seed lifetime
- **Cons**: More verbose for one-shot calls (`he.simulate(..., seed=42)` is shorter), pybind11 must wrap Generator (doable but adds boilerplate)
- **Why rejected**: v0.1 optimizes for simplicity. Explicit int seed is one less concept. Can add Generator support in v0.2 if users ask.

## Consequences

**Positive**:
- Reproducible across Python and C++: same seed → same events, bit-for-bit
- Deterministic tests: `simulate(mu, alpha, beta, T, seed=42)` returns the same 1000 events in every test run, on every platform
- Fast: Philox is 3–5× faster than Mersenne Twister, small state fits in L1 cache
- Counter-based: can skip ahead (useful for parallel simulation in v0.2, where thread k uses seed + k as the counter base)

**Negative**:
- NumPy dependency in C++ (via pybind11): simulation calls Python-side `numpy.random.Generator.exponential()`. Adds ~100 ns overhead per draw (vs ~10 ns for pure C++). For N = 1000 events, this is 0.1 ms (negligible).
- v0.2 will vendor standalone Philox: copy NumPy's C implementation, test against NumPy for reproducibility. This is ~200 lines of C code (permissible under BSD-3-Clause). Until then, accept the Python callback overhead.

**Neutral**:
- Seed type: uint64 (not int32). Philox uses 64-bit seeds; passing int32 would truncate the space (2³² seeds instead of 2⁶⁴). Python `int` is arbitrary precision, so this is safe.
- Seed=None: Python API could default to `seed=None` (random seed from OS entropy). v0.1 requires explicit seeds (no default) to force users to think about reproducibility. Can relax in v0.2.

## References

- NumPy random API: [numpy.random.Generator](https://numpy.org/doc/stable/reference/random/generator.html)
- Philox paper: Salmon, Moraes, Dror & Shaw (2011), "Parallel Random Numbers: As Easy as 1, 2, 3"
- BigCrush test suite: [TestU01](http://simul.iro.umontreal.ca/testu01/tu01.html)
- NumPy Philox source: [numpy/random/src/philox/philox.h](https://github.com/numpy/numpy/blob/main/numpy/random/src/philox/philox.h) (BSD-3-Clause)
- mathematics.md §6: Simulation algorithms (thinning and cluster)
