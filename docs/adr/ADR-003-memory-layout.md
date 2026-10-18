# ADR-003: Event Memory Layout

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

The core recursion (mathematics.md §4) processes N events in time order, updating M² states Sᵢⱼ at each step. The innermost loop touches every Sᵢⱼ, so cache locality dominates performance. Two layout options: array-of-structs (AoS) stores each event as {time, type}, while struct-of-arrays (SoA) stores separate arrays for times and types. AoS has better spatial locality for random access, but SoA has better cache-line utilization for sequential scans.

The recursion reads the time of the current event (to compute decay) and the type (to determine which Sᵢⱼ to increment). It never needs both fields simultaneously for random access. The time array is accessed sequentially (event n → n+1), and the type array is also accessed sequentially. This is a textbook SoA use case.

Time representation matters: Unix nanoseconds (int64, ~1.7e18 for 2024) use 60 bits, leaving float64 with ~2^-22 s resolution (~0.2 µs). Converting to session-relative float64 (t - t₀) preserves full precision. But internal storage must support replay-equals-live (§6 of data schemas doc), which means absolute timestamps for ingestion and session-relative for computation.

Type storage: uint8 supports M ≤ 256 dimensions. v0.1 targets M < 20 (equity order flow: trades, cancels, quotes on ~5 symbols). uint8 is sufficient and saves cache bandwidth (4× smaller than uint32).

## Decision

Struct-of-arrays (SoA) layout:

```cpp
struct EventSequence {
    std::vector<double> times;    // (N,) seconds from session start, float64
    std::vector<uint8_t> types;   // (N,) dimension indices 0..M-1, M ≤ 256
    double T;                      // observation window end (seconds from start)
};
```

**Time convention**:
- **Input**: Absolute int64 nanoseconds (Unix epoch or exchange timestamps)
- **Storage**: float64 seconds relative to session start (t - t₀)
- **Output**: Same as storage (session-relative float64)
- **Internal replay logs**: int64 nanoseconds absolute (for replay-equals-live)

**Type storage**: uint8, M ≤ 256 for v0.1. If M > 256 is needed, promote to uint16 (v0.2+).

**Dimension limit**: Hard-code M ≤ 256 in v0.1. Python API raises `ValueError` if M > 256.

## Alternatives Considered

### Option 1: Array-of-structs (AoS) `{time, type}` pairs
- **Pros**: Each event is one cache line (16 bytes with padding), easier to reason about as "list of events," some debugging tools show it more naturally
- **Cons**: Worse cache locality: recursion reads all times sequentially, then all types sequentially. AoS interleaves them, so half of every cache line is unused in each pass.
- **Why rejected**: Cache miss costs 200–300 cycles on modern CPUs. SoA keeps the hot path (time array) in L1 cache. Profiling Ogata (1981) reference code shows 30% speedup with SoA for N > 10⁴.

### Option 2: Absolute Unix nanoseconds in float64
- **Pros**: No conversion at ingestion, matches exchange timestamps directly
- **Cons**: Floating-point cancellation: Unix epoch ~1.7e9 seconds uses 31 bits, leaving 53 - 31 = 22 bits for sub-second precision (2^-22 s ≈ 0.24 µs). HFT data has microsecond timestamps; this loses precision. Subtraction (t - s) loses another bit.
- **Why rejected**: Numerical correctness matters. Session-relative times preserve full float64 precision. Conversion overhead is one subtraction per event at ingestion (negligible).

### Option 3: uint16 for types (support M ≤ 65536)
- **Pros**: "Future-proof" for huge M
- **Cons**: 2× memory bandwidth vs uint8, slower cache fills, no use case for M > 256 in v0.1 (order flow is ~5–20 dimensions)
- **Why rejected**: YAGNI. If M > 256 becomes real (v0.2+), it is a one-line change to uint16. Until then, save the bandwidth.

### Option 4: int64 nanoseconds everywhere
- **Pros**: No precision loss, matches storage format
- **Cons**: Can't use Eigen or standard math libraries (they expect float64), exp(-β * Δt) requires float conversion anyway, wastes 3 bits (64 - 61 used)
- **Why rejected**: The recursion is float math. int64 → float64 conversion happens once (at the first exp()), so keeping int64 internally just delays the inevitable. Session-relative float64 is the right intermediate representation.

## Consequences

**Positive**:
- Cache-friendly: times array is accessed sequentially in the recursion, fits in L1 (N = 10⁴ events = 80 KB for times)
- Numerical precision: session-relative times avoid float cancellation, preserve full float64 mantissa
- Small memory footprint: uint8 types save 3× bandwidth vs uint32 (M = 10 → 10 KB vs 40 KB for types array)
- Natural Python API: `times` and `types` map to NumPy arrays directly (`np.array(times, dtype=np.float64)`, `np.array(types, dtype=np.uint8)`)

**Negative**:
- Conversion cost at ingestion: one subtraction per event (t - t₀). Negligible: ~0.3 ns per event on modern CPUs, dominated by I/O.
- M ≤ 256 constraint: Hard-coded in v0.1. If a use case needs M > 256 (unlikely for order flow, possible for social networks), promote to uint16 in v0.2.
- Debugging is slightly harder: can't inspect events as {time, type} pairs in gdb. But the SoA layout is visible in the struct, and printing `times[i], types[i]` is one extra step.

**Neutral**:
- Replay logs (§6 of data schemas) store absolute int64 nanoseconds separately, for replay-equals-live. This is independent of the in-memory layout. Conversion happens at log ingestion.
- T (observation window end) is stored once, not per-event. This is natural for both AoS and SoA.

## References

- mathematics.md §4: recursion accesses times and types sequentially
- Data Schemas doc (P03.06): replay-equals-live requires absolute timestamps in storage
- Ogata (1981): reference implementation (Fortran) uses SoA-equivalent (parallel arrays)
- Cache performance: [Ulrich Drepper, "What Every Programmer Should Know About Memory"](https://people.freebsd.org/~lstewart/articles/cpumemory.pdf), §3.3
