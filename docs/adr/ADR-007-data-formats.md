# ADR-007: Data Formats and I/O Strategy

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

hawkes-engine ingests event sequences (time, type), saves fit results, and
optionally writes simulations to disk. Formats in play: text (CSV, JSON),
binary columnar (Parquet), and in-memory (NumPy arrays).

The priorities differ by direction. Input is large and machine-generated, so
parse speed and type safety matter most. Output is small and human-read, so
readability matters most. One format for both would serve neither.

## Decision

**Input**: Parquet as the primary format, CSV as a fallback.
- Parquet schema: `time: int64` (nanoseconds), `type: uint8`; optional metadata
  columns are ignored by the loader
- CSV schema: `time,type`, parsed with explicit dtypes so times are not
  silently parsed as floats
- Both convert to the in-memory representation of ADR-003 at load

**Output**: JSON for fit results.
- Small (well under 1 KB for typical M), diffable in git, readable without a
  tool
- Contains `mu`, `alpha`, `beta` as nested lists, the log-likelihood, ρ(Γ), and
  the diagnostics that accompany them

**Simulation output**: Parquet, same schema as input, so that
`simulate → save → load → fit` round-trips.

**Dependencies**: PyArrow is optional, required only for Parquet. CSV and JSON
use the standard library. NumPy arrays are the primary API; users who want
pandas can wrap them.

## Alternatives Considered

### Option 1: CSV everywhere
- **Pros**: Universal, no dependency
- **Cons**: Parse overhead, large files, and — most importantly here — type
  ambiguity: a nanosecond timestamp parsed as a float silently loses precision,
  which is exactly the failure mode mathematics.md §4 warns about.
- **Why rejected**: Precision, not just speed. A format that rounds timestamps
  silently is disqualified for this library.

### Option 2: HDF5
- **Pros**: Scientific standard, handles N-dimensional arrays, compression
- **Cons**: Heavy dependency, and the v0.1 payload is two 1-D arrays. Also the
  least pleasant of these options to build and ship on Windows.
- **Why rejected**: Overkill for 1-D arrays; Parquet covers the case with a
  lighter dependency.

### Option 3: Protocol Buffers
- **Pros**: Compact, schema-enforced
- **Cons**: Not readable without a schema and a tool, and the payload is under
  1 KB, so compactness buys nothing.
- **Why rejected**: The output's job is to be read by a person.

### Option 4: pandas DataFrame as the primary API
- **Pros**: Familiar, self-documenting columns
- **Cons**: Heavy dependency, index and column overhead, and a second
  representation to keep consistent with the NumPy one.
- **Why rejected**: NumPy arrays are the native currency of the C++ boundary.
  pandas can wrap them; the library need not require it.

**Note on removed claims**: the original ADR asserted specific throughput
figures (~50 ms vs ~500 ms for 10⁶ events, "10× smaller with Parquet"). These
were not measured. They are removed; H5 will benchmark the loader that is
actually implemented.

## Consequences

**Positive**:
- Timestamps keep integer precision end to end
- Parquet reads map onto NumPy without a per-element parse
- Fit output can be inspected and diffed with no tooling
- No mandatory heavy dependency: PyArrow only if Parquet is used

**Negative**:
- Parquet support means an optional extra. A user who installs bare
  `hawkes-engine` and calls `load_events("x.parquet")` gets an ImportError,
  which has to be written to say what to install.
- Two input formats means two loaders to test.

**Neutral**:
- Extra Parquet columns are ignored rather than rejected, so producers can add
  fields without breaking consumers.
- The fit JSON has no formal schema in v0.1; it is documented and stable, and a
  schema can be added if external consumers appear.

## References

- [PyArrow Parquet](https://arrow.apache.org/docs/python/parquet.html)
- [Apache Parquet](https://parquet.apache.org/)
- mathematics.md §4: the float64 epoch-precision trap this format choice avoids
