# ADR-003: Event Memory Layout

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

The core recursion (mathematics.md §4) processes N events in time order,
updating M² states Sᵢⱼ at each step. The innermost loop touches every Sᵢⱼ, so
cache locality dominates the inner cost. Two layout options: array-of-structs
(AoS) stores each event as {time, type}, while struct-of-arrays (SoA) stores
separate arrays for times and types.

The recursion reads the time of the current event (to compute decay) and the
type (to decide which state to increment). Both are read sequentially, event n
then event n+1. That is the textbook SoA case.

Time representation matters. A Unix-epoch timestamp in nanoseconds is about
1.7×10¹⁸, which needs 61 bits, leaving fewer than no bits for the fractional
part if stored in float64 — nanosecond epoch timestamps cannot be represented
in float64 at all, and second-resolution epoch timestamps leave only ~22 bits
(2⁻²² s ≈ 0.24 µs). Converting to session-relative float64 (t − t₀) restores
the full 53-bit mantissa over a window of a few hours. Storage keeps integer
nanoseconds so replay is exact; computation uses session-relative float64.

Type storage: uint8 supports M ≤ 256 dimensions. v0.1 targets M < 20. uint8 is
sufficient and saves cache bandwidth over uint32.

## Decision

Struct-of-arrays (SoA) layout:

```cpp
struct EventSequence {
    std::vector<double> times;    // (N,) seconds from session start, float64
    std::vector<uint8_t> types;   // (N,) dimension indices 0..M-1, M <= 256
    double T;                     // observation window end (seconds from start)
};
```

**Time convention**:
- **Input and on-disk storage**: absolute int64 nanoseconds
- **In memory**: float64 seconds relative to session start (t − t₀)
- **Replay logs**: int64 nanoseconds absolute, so replay matches live exactly
- **Python API boundary**: the conversion happens once, at load

**Type storage**: uint8, M ≤ 256 for v0.1. If M > 256 is needed, promote to
uint16 (v0.2+).

**Dimension limit**: M ≤ 256 enforced once, at the API boundary, raising
`ValueError`. The C++ core may assume it.

## Alternatives Considered

### Option 1: Array-of-structs (AoS) `{time, type}` pairs
- **Pros**: Each event is one cache line, easier to inspect as "a list of events"
- **Cons**: The recursion reads all times in one pass and all types in another.
  AoS interleaves them, so half of each cache line is unused in either pass.
- **Why rejected**: SoA keeps the hot time array dense in cache. The access
  pattern here is unambiguous, so this does not need a benchmark to settle.

### Option 2: Absolute Unix nanoseconds in float64
- **Pros**: No conversion at ingestion, matches exchange timestamps directly
- **Cons**: As above, ns-epoch values do not fit in float64 at all;
  second-epoch values lose sub-microsecond resolution, and differencing two of
  them loses more.
- **Why rejected**: Numerical correctness matters. The conversion is one
  subtraction per event at ingestion.

### Option 3: uint16 for types (support M ≤ 65536)
- **Pros**: "Future-proof" for large M
- **Cons**: 2× memory bandwidth, slower cache fills, no v0.1 use case
- **Why rejected**: YAGNI. If M > 256 becomes real, it is a one-line change.

### Option 4: int64 nanoseconds everywhere
- **Pros**: No precision loss, matches storage format
- **Cons**: `exp(-β·Δt)` needs float arithmetic anyway, and every arithmetic op
  on int64 timestamps has to guard against overflow
- **Why rejected**: The recursion is float math. Converting once at load is
  cheaper than converting at every use.

## Consequences

**Positive**:
- Cache-friendly: the times array is read sequentially and fits in L1 for
  N = 10⁴ (80 KB)
- Numerical precision: session-relative times preserve the full mantissa
- Small footprint: uint8 types
- Natural Python API: `times` and `types` map to NumPy arrays directly

**Negative**:
- One subtraction per event at ingestion, dominated by I/O
- M ≤ 256 constraint, enforced at the boundary
- Debugging is one step less direct: events are not visible as `{time, type}`
  pairs in a debugger

**Neutral**:
- Replay logs store absolute int64 nanoseconds separately, independent of the
  in-memory layout
- T is stored once, not per event

**Note on an earlier claim**: a previous version of this ADR cited a "30%
speedup with SoA for N > 10⁴" attributed to profiling Ogata (1981)'s reference
code. That was not measured by this project, and Ogata (1981) is a Fortran
paper, not an implementation we profiled. The claim has been removed rather
than carried forward as an unverified number: a number you have not computed is
not evidence. H7 will measure the layouts that are actually implemented.

## References

- mathematics.md §4: recursion accesses times and types sequentially
- mathematics.md §4: the epoch-precision trap
- Drepper, U., "What Every Programmer Should Know About Memory", §3.3
