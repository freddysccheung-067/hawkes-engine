# ADR-004: Threading Model and GIL Policy

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

The likelihood recursion (mathematics.md §4) is O(NM²). It is worth being
precise about what in it is parallel, because the original version of this ADR
was not, and the error would have propagated into H2.

**The recursion is sequential over events.** Event *n* updates the state that
event *n+1* reads:

$$S_{ij}(\tau_n^-) = e^{-\beta_{ij}(\tau_n - \tau_{n-1})}\,S_{ij}(\tau_{n-1}^+)$$

The intensity at event *n+k* cannot be computed without having processed events
*n* through *n+k−1*. The claim in the original ADR that "each event's state
update is independent of other events' updates at the same timestep" is false,
and the OpenMP plan built on it would not have produced correct results.

What *is* parallel is the per-event inner work: updating the M² entries of S and
forming the M sums. At M = 10 that is a hundred multiply-adds — far too little
to justify a thread, and parallelising it would need a barrier per event, which
costs more than the work.

The second false claim was that thinning "runs M independent Poisson processes".
It does not. Thinning advances a single clock: one exponential draw from the
total intensity, then a draw deciding which type fired. It is one sequential
stream by construction. Only the *cluster* simulator is genuinely parallel, and
only across independent clusters.

GIL: a C extension holds the interpreter lock while it runs unless it releases
it explicitly. Release and re-acquire cost on the order of a microsecond, not
the 10 µs the original ADR used to justify its threshold.

## Decision

**v0.1: single-threaded core. Release the GIL around long calls.**

- The recursion is sequential, so there is no inner parallelism to add. No
  OpenMP anywhere in v0.1.
- Bindings that run longer than a few milliseconds (likelihood over a large
  event set, cluster simulation) release the GIL for the duration of the C++
  call via `py::gil_scoped_release`. This does not make the call faster; it lets
  the caller's other Python threads make progress.
- Trivial calls do not release it — the release would cost more than the work.

**Parallelism the library actually offers:**

- *Across fits* — grid search, bootstrap, cross-validation. Each fit is
  independent:

  ```python
  from joblib import Parallel, delayed
  results = Parallel(n_jobs=-1)(
      delayed(he.fit)(events, **init) for init in param_grid
  )
  ```

- *Across clusters* — the branching simulator, once the cluster representation
  lands at H4, draws independent clusters in parallel. This is real parallelism
  over independent state, and it is the one place threads pay.

**v0.2+, if profiling justifies it:** parallel cluster simulation. Not parallel
likelihood over time — that ordering cannot be broken.

## Alternatives Considered

### Option 1: OpenMP over the event loop
- **Pros**: Would be the obvious win if the recursion were independent
- **Cons**: It is not. Parallelising a recurrence needs either a prefix-scan
  reformulation or a blocking scheme, each a substantial piece of numerical
  work with its own error analysis.
- **Why rejected**: Built on a false premise about the algorithm.

### Option 2: OpenMP over the M² inner loop
- **Pros**: Correct, unlike option 1
- **Cons**: M² is 100 elements at M = 10. A barrier per event costs more than
  the loop, and the loop is vectorised by the compiler anyway.
- **Why rejected**: Negative expected speedup.

### Option 3: Cython `prange`
- **Pros**: Releases the GIL automatically
- **Cons**: We use C++ (ADR-001), so this is not available.
- **Why rejected**: Not applicable.

### Option 4: Never release the GIL
- **Pros**: Simplest binding code
- **Cons**: A multi-second likelihood evaluation blocks every other Python
  thread, including a progress bar or another request in a server.
- **Why rejected**: ~1 µs of overhead to avoid a multi-second stall.

### Option 5: Spawn processes from C++
- **Pros**: Bypasses the GIL entirely
- **Cons**: IPC overhead, process lifetime management, expensive on Windows.
- **Why rejected**: Python's `multiprocessing` already does this better.

## Consequences

**Positive**:
- No OpenMP dependency; the build stays simple on all three platforms
- Deterministic results: no summation order depends on thread scheduling, so
  the same input gives bit-identical output every run
- Users still get parallelism where it exists — across independent fits

**Negative**:
- One fit of a large event set cannot be accelerated by adding cores. That is a
  property of the algorithm, not a choice; the response is a faster core.
- Releasing the GIL correctly requires care: no Python object may be touched
  while it is released. NumPy arrays must be converted to C++ views before the
  release and kept alive for the duration.

**Neutral**:
- The policy is per-function. Simulation and the likelihood release the GIL;
  argument validation does not.
- If free-threaded Python builds become the default, this section is re-read
  rather than rewritten: the constraint is the algorithm's ordering, which does
  not change.

## References

- mathematics.md §4: the recursion, and why event *n+1* depends on event *n*
- mathematics.md §6: thinning advances one clock; clusters are independent
- Python/C API: [Thread state and the GIL](https://docs.python.org/3/c-api/init.html#thread-state-and-the-global-interpreter-lock)
- pybind11: [`gil_scoped_release`](https://pybind11.readthedocs.io/en/stable/advanced/misc.html#global-interpreter-lock-gil)
- joblib: [Parallel](https://joblib.readthedocs.io/en/latest/parallel.html)
