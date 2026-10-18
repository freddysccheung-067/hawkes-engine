# ADR-007: Data Formats and I/O Strategy

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

hawkes-engine ingests event sequences (time, type), saves fit results (parameters, likelihood), and optionally logs simulations for replay. Three format families: text (CSV, JSON), binary (Parquet, HDF5, Protocol Buffers), and in-memory (NumPy arrays, Pandas DataFrames). Trade-offs: human readability, parse speed, type safety, file size, and ecosystem compatibility.

CSV is universal but slow (parse overhead) and type-unsafe (time as string "1609459200.123456" → float64 conversion, type as int/string ambiguity). JSON is human-readable and self-describing but verbose (1 MB CSV → 1.5 MB JSON). Parquet is columnar, compressed (10× smaller than CSV), and has zero-copy Arrow → NumPy integration. HDF5 is scientific-standard but heavyweight (h5py, libhdf5).

Use cases:
- **Input**: Load trade data (10⁴–10⁶ events) from CSV (legacy) or Parquet (modern)
- **Output**: Save fit results (μ, α, β, log-likelihood, ρ) as JSON (small, readable)
- **Replay logs**: Simulation output for validation, needs (time, type, metadata)

Parquet wins for large event sequences: Arrow → NumPy is zero-copy (no parsing), compression saves 10×, and PyArrow is a de facto standard (used by Pandas, Polars, DuckDB). JSON wins for fit results: small payloads (<1 KB), human-readable, universally supported. CSV is a fallback for legacy data.

## Decision

**Input formats** (event sequences):
- **Preferred**: Parquet with schema `{time: int64 (ns), type: uint8, [optional metadata columns]}`
  - Zero-copy via PyArrow: `pa.Table` → `np.ndarray` (no parsing overhead)
  - Compressed: ~10× smaller than CSV (gzip or snappy codec)
  - Type-safe: int64 timestamps, uint8 types (no ambiguity)
- **Fallback**: CSV with schema `time,type` (minimal, for legacy data)
  - Parse with `pandas.read_csv(dtype={'time': 'int64', 'type': 'uint8'})`
  - Convert to NumPy arrays before passing to C++

**Output formats** (fit results):
- **JSON** for parameters and diagnostics:
  ```json
  {
    "mu": [0.5, 0.3],
    "alpha": [[0.0, 0.2], [0.3, 0.0]],
    "beta": [[1.0, 1.0], [1.0, 1.0]],
    "loglik": -1234.56,
    "rho": 0.72,
    "trust": {"verdict": "reliable", "N": 1000, "rho_near_one": false}
  }
  ```
- Readable, diff-friendly (git), universally parseable
- Small (<1 KB per fit), so no compression needed

**Replay logs** (simulation output, optional):
- **Parquet** with schema `{time: int64 (ns), type: uint8, session_id: string, metadata: json}`
- Same format as input (can feed simulation output back into fit)
- Compressed: 1M events → ~10 MB (vs ~100 MB CSV)

**API**:
- Python: `he.load_events("data.parquet")` returns `(times: np.ndarray[float64], types: np.ndarray[uint8])`
- Python: `he.save_fit(result, "fit.json")` writes JSON
- C++: Takes raw NumPy arrays (no C++ I/O, pybind11 handles this)

## Alternatives Considered

### Option 1: CSV-only (input and output)
- **Pros**: Universal, human-readable, no dependencies (Python `csv` stdlib)
- **Cons**: Slow (parse overhead ~10× vs Parquet), large files (10× vs Parquet compressed), type-unsafe (time as string, need manual conversion), harder to append (must rewrite entire file)
- **Why rejected**: Parquet is faster and smaller, and PyArrow is widely adopted. CSV is a fallback for legacy data only, not the primary path.

### Option 2: HDF5 (instead of Parquet)
- **Pros**: Scientific standard (used by astronomy, genomics), supports multi-dimensional arrays (useful if we add tensor-valued parameters later), compression
- **Cons**: Heavyweight dependency (h5py, libhdf5 C library), overkill for 1D arrays (times, types), less ecosystem integration than Parquet (no Polars, DuckDB support), Windows binary wheels are fragile
- **Why rejected**: Parquet is lighter, faster, and better integrated with modern data tools. HDF5 is the right choice for multi-dimensional arrays (e.g., storing M×M×K parameter grids), but v0.1 doesn't need that.

### Option 3: Protocol Buffers (instead of JSON)
- **Pros**: Binary, compact, schema-enforced (no ad-hoc JSON parsing)
- **Cons**: Not human-readable (can't `cat fit.pb` and read it), requires schema definition (.proto file), overkill for small payloads (<1 KB), less ecosystem support than JSON
- **Why rejected**: JSON is readable, diff-friendly, and universally supported. Fit results are small (<1 KB), so binary encoding saves negligible space. If we later need streaming (e.g., live parameter updates), protobuf is an option for v0.2.

### Option 4: Pandas DataFrame as the primary API
- **Pros**: Idiomatic for data scientists, supports both CSV and Parquet, metadata (column names) is self-documenting
- **Cons**: Adds Pandas dependency (heavy, 100+ MB), DataFrame overhead (index, column objects), user must remember column order (df['time'], df['type'] vs NumPy arrays), pybind11 doesn't wrap DataFrames natively (need extra conversion)
- **Why rejected**: NumPy arrays are lighter and more explicit. Users can wrap in a DataFrame if they want (`pd.DataFrame({'time': times, 'type': types})`), but the library doesn't force it. Pandas is an *optional* dependency for CSV/Parquet I/O only.

## Consequences

**Positive**:
- Fast ingestion: Parquet → NumPy is zero-copy via Arrow (no parsing). 10⁶ events load in ~50 ms (vs ~500 ms for CSV).
- Small files: Parquet compression saves 10×. 1M events: 10 MB Parquet vs 100 MB CSV.
- Type-safe: int64 nanosecond timestamps (no float precision loss), uint8 types (no string → int conversion bugs).
- Readable output: JSON fit results can be inspected with `cat fit.json`, diffed in git, parsed by any language.
- Replay-friendly: Simulation output is same format as input, so `simulate()` → save → `load_events()` → `fit()` works.

**Negative**:
- PyArrow dependency: ~50 MB installed (acceptable, it's de facto standard). Required for Parquet, optional if user only uses CSV.
- CSV fallback is slower: 10× parsing overhead vs Parquet. But CSV is legacy-only; new workflows should use Parquet.
- JSON is verbose for large parameter arrays: M = 50 → α is 50×50 = 2500 numbers → ~40 KB JSON. Acceptable for v0.1 (M < 20), but if M > 50 becomes common, switch to Parquet for parameters too (v0.2+).

**Neutral**:
- Parquet schema flexibility: Can add optional columns (symbol, price, venue) without breaking existing code. The library only reads `time` and `type` columns; extra columns are ignored.
- JSON schema: No formal schema (no JSON Schema or Pydantic validation). Fit results are validated by Python type hints (`FitResult` dataclass with `mu: np.ndarray`, etc.). If external tools need to parse fit JSON, they rely on the documented structure.
- Compression codec: Parquet defaults to Snappy (fast, ~3× compression). Can switch to Gzip (~10× compression, slower) or Zstd (best of both) if file size matters more than speed. Configurable via PyArrow write options.

## References

- PyArrow documentation: [Reading Parquet](https://arrow.apache.org/docs/python/parquet.html)
- Parquet format spec: [Apache Parquet](https://parquet.apache.org/)
- Zero-copy NumPy: [PyArrow to NumPy](https://arrow.apache.org/docs/python/numpy.html)
- JSON schema: [JSON Schema](https://json-schema.org/) (not used in v0.1, but available if needed)
- mathematics.md §4: Time precision (int64 ns → float64 session-relative)
- Pandas I/O: [pandas.read_parquet](https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html)
