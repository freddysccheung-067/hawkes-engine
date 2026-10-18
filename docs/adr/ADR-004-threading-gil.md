# ADR-004: Threading Model and GIL Policy

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

The likelihood recursion (mathematics.md §4) is O(NM²) and embarrassingly parallelizable: each event's state update is independent of other events' updates at the same timestep. OpenMP could parallelize the inner loop over i (target types) or j (source types). Simulation (§6) is also parallelizable: thinning runs M independent Poisson processes, and cluster simulation can spawn children in parallel.

Python's GIL (Global Interpreter Lock) allows only one thread to execute Python bytecode at a time. C extensions can release the GIL via `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS`, but acquiring/releasing costs ~10 µs per call. pybind11 wraps this as `py::gil_scoped_release`. The question: is the parallelism worth the GIL overhead?

Breakeven analysis: For OpenMP overhead ~10 µs and single-threaded recursion ~0.1 µs per event (M = 10, modern CPU), parallelism wins when N > 10⁵. Most use cases are N < 10⁴ (one day of HFT data at 1 event/s). The 10⁵ crossover is v0.2 territory.

Alternative: users can parallelize across parameter sets (embarrassingly parallel MLE grid search or bootstrap) using Python's `multiprocessing` or `joblib`. This is easier to implement (no GIL complexity) and scales better (across machines).

## Decision

**v0.1**: Single-threaded C++ core, no OpenMP, no GIL release in the hot path.

**v0.2+**: Add OpenMP parallelization for N > 10⁵, gated by runtime check:
```cpp
if (N > 100000) {
    py::gil_scoped_release release;  // Release GIL
    #pragma omp parallel for
    // ... recursion ...
}
```

**Python-level parallelism**: Document idiom for parallelizing across fits:
```python
from joblib import Parallel, delayed
results = Parallel(n_jobs=-1)(
    delayed(he.fit)(events, mu0, alpha0, beta0) 
    for mu0, alpha0, beta0 in param_grid
)
```

**Why single-threaded v0.1**:
- Overhead dominates for N < 10⁵ (typical use case)
- Simpler debugging (no race conditions, deterministic execution)
- Faster iteration (no OpenMP CMake complexity in H1–H3 gates)
- Users can still parallelize fits across parameter sets (multiprocessing)

## Alternatives Considered

### Option 1: OpenMP from day 1
- **Pros**: Faster for large N (10⁶+), "looks impressive" in benchmarks
- **Cons**: GIL overhead costs 10 µs per call, breakeven at N ~ 10⁵, adds OpenMP to build deps (Windows MSVC needs `/openmp`, macOS needs `libomp`), harder to debug (race conditions, non-deterministic timings), premature optimization
- **Why rejected**: Most users have N < 10⁴. The v0.1 goal is correctness and clarity, not peak throughput. Add OpenMP in v0.2 when profiling shows it matters.

### Option 2: Cython prange (parallel range)
- **Pros**: Cython's `prange` releases GIL automatically, simpler than OpenMP pragmas
- **Cons**: We chose C++ over Cython (ADR-001), so this is not an option. Cython's parallel support is less mature than OpenMP.
- **Why rejected**: Not applicable (we're using C++, not Cython).

### Option 3: Always release GIL (even single-threaded)
- **Pros**: Allows other Python threads to run during C++ computation, useful for GUI apps or async I/O
- **Cons**: 10 µs overhead per call (2× the single-threaded recursion time for N = 100), user must explicitly spawn threads (doesn't help single-threaded scripts)
- **Why rejected**: Releasing the GIL only helps if the user has other Python threads running. Most scripts are single-threaded. If a user needs async (e.g., GUI), they can wrap the call in `asyncio.to_thread()`. Don't pay the cost by default.

### Option 4: Multiprocessing inside C++ (spawn processes in C++)
- **Pros**: Bypasses GIL entirely, scales across machines
- **Cons**: IPC overhead (serialize events, send to worker, wait for result), much higher latency (~1 ms vs 10 µs), harder to manage process lifetimes, Windows process spawning is expensive
- **Why rejected**: Python's `multiprocessing` or `joblib` already does this better. Don't reinvent the wheel in C++.

## Consequences

**Positive**:
- Simple, deterministic, fast for typical use cases (N < 10⁴)
- Users can parallelize fits across parameter sets with `multiprocessing` or `joblib` (embarrassingly parallel, no GIL issues)
- Easier debugging: no race conditions, no OpenMP, no GIL release/acquire
- Faster CI builds: no OpenMP dependency, simpler CMake, works on all platforms without extra flags

**Negative**:
- N > 10⁶ fits are slower than they could be (10× slower than OpenMP on 8 cores). Acceptable for v0.1; fix in v0.2.
- Users who want single-fit parallelism must wait for v0.2. But most users want to fit multiple parameter sets (grid search, bootstrap), which parallelizes naturally.

**Neutral**:
- v0.2 OpenMP addition is API-compatible: users see the same function, it just runs faster for large N. No user code breaks.
- GIL policy can change per-function: simulation might release GIL in v0.1 (it's slower, ~1 ms per call), while likelihood stays GIL-held. Decide per-function at implementation time.
- OpenMP threshold (N > 10⁵) is a heuristic: profile in v0.2 to find the real breakeven. Could be 10⁴ or 10⁶ depending on hardware.

## References

- mathematics.md §4: O(NM²) recursion structure
- Python GIL: [Python/C API Reference, Thread State and the GIL](https://docs.python.org/3/c-api/init.html#thread-state-and-the-global-interpreter-lock)
- pybind11 GIL management: [pybind11 docs, "Calling Python functions from C++"](https://pybind11.readthedocs.io/en/stable/advanced/misc.html#global-interpreter-lock-gil)
- OpenMP overhead benchmarks: [OpenMP ARB, "Using OpenMP" (2024), §2.4]
- joblib parallel idiom: [joblib documentation](https://joblib.readthedocs.io/en/latest/parallel.html)
