# ADR-006: Build Strategy and Compiler Flags

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

Published wheels must run on any x86-64 machine (2010+ CPUs, generic SSE2). But developer builds and power users want maximum speed: AVX2, FMA, `-march=native`. The tension: ship fast wheels (risky, breaks on old CPUs) or ship portable wheels (safe, 10–20% slower).

`-march=native` compiles for the *build machine's* CPU, not the user's. A wheel built on a 2023 Ryzen (AVX2, AVX512) crashes with SIGILL on a 2015 Xeon (SSE4.2 only). `-ffast-math` breaks IEEE 754: allows `x - x ≠ 0`, reorders FP ops, breaks NaN/inf handling. The likelihood returns -inf when λᵢ → 0 (mathematics.md §4 numerical traps); `-ffast-math` can turn this into NaN, silently breaking optimization.

Sanitizers (AddressSanitizer, UndefinedBehaviorSanitizer) catch memory bugs and UB in CI but add 2–5× overhead. Can't ship wheels with sanitizers enabled. Must run in CI only.

SIMD is the real win: AVX2 gives 2× speedup for exp() (the recursion bottleneck). But AVX2 is not universal (2013+ CPUs). Runtime dispatch (detect CPU at startup, call AVX2 or SSE2 path) is the gold standard but requires duplicate codegen. v0.1 is too early; punt to v0.2.

## Decision

**Published wheels** (PyPI, conda-forge):
- Target: Generic x86-64 (baseline SSE2, no AVX/AVX2)
- Flags: `-O3` (GCC/Clang), `/O2` (MSVC), **no `-march=native`**, **no `-ffast-math`**
- Reason: Must run on any x86-64 machine, no SIGILL risk, correct NaN/inf handling

**User opt-in builds** (pip install --no-binary):
- CMake flag: `-DNATIVE_OPTIMIZATIONS=ON` enables `-march=native`
- Documented in README: "15–20% faster on your CPU, but binary won't run on other machines"
- Still no `-ffast-math` (IEEE correctness non-negotiable)

**CI sanitizer builds**:
- Debug target: `-fsanitize=address,undefined` (Clang/GCC)
- Runs in CI only (not in wheels)
- Catches: buffer overflows, use-after-free, signed integer overflow, null derefs

**SIMD roadmap** (v0.2+):
- Runtime CPU detection: `#ifdef __AVX2__` + CPUID check at module load
- Duplicate critical paths: `likelihood_recursion_sse2()` and `likelihood_recursion_avx2()`
- Dispatch at runtime: call AVX2 if available, fall back to SSE2
- Tooling: Clang's `-mavx2` flag, GCC's `__attribute__((target("avx2")))`

## Alternatives Considered

### Option 1: Ship wheels with `-march=native`
- **Pros**: 15–20% faster out of the box, users don't need to rebuild
- **Cons**: Wheel built on dev machine (2023 CPU) crashes on user machine (2015 CPU) with SIGILL (illegal instruction). This is a support nightmare: "it works on my machine" is not acceptable for a library.
- **Why rejected**: PyPI/conda wheels must be universal. A crashy wheel is worse than a slow wheel. Users who want native performance can rebuild.

### Option 2: Enable `-ffast-math` for 5% speedup
- **Pros**: Small speedup (exp() is ~5% faster), some papers enable it
- **Cons**: Breaks IEEE 754 guarantees. Specifically:
  - Can reorder `x + y - y` to `x`, but if `x` is NaN, result changes
  - Can optimize `x - x` to `0`, but if `x` is inf, mathematically it's NaN
  - Likelihood returns `-inf` when λᵢ rounds to 0 (mathematics.md §4). `-ffast-math` can turn this into NaN, breaking the optimizer (NaN gradients propagate, L-BFGS fails).
- **Why rejected**: Numerical correctness > 5% speedup. Debugging `-ffast-math` issues is a black hole (results are platform-dependent, irreproducible). The 5% is not worth the risk.

### Option 3: Multiple wheels per Python version (SSE2, AVX2, AVX512)
- **Pros**: Users automatically get the fastest wheel for their CPU (pip selects based on platform tags)
- **Cons**: 3× CI time (build 3 wheels per Python version × 3 versions = 9 wheels per platform × 3 platforms = 27 wheels), 3× PyPI bandwidth, platform tags are messy (manylinux_2_28_x86_64_avx2 is not standard), detection can fail (user has AVX2 but pip downloads SSE2 wheel)
- **Why rejected**: Complexity exceeds benefit for v0.1. Runtime dispatch in v0.2 is a better solution (one wheel, dynamic choice).

### Option 4: Profile-guided optimization (PGO)
- **Pros**: 5–10% speedup by optimizing hot paths (inline decisions, branch prediction)
- **Cons**: Requires two-pass build (compile → run benchmark → recompile with profile), CI complexity, profile must match real workload (what if user has different N, M?), MSVC PGO is painful
- **Why rejected**: Premature optimization for v0.1. PGO is a v0.3+ concern, after profiling shows it matters.

## Consequences

**Positive**:
- Wheels work on all x86-64 machines (2010+ CPUs, SSE2 baseline)
- Correct IEEE 754 behavior: NaN/inf propagate correctly, likelihood returns -inf (not NaN) when λᵢ → 0
- Sanitizers catch bugs in CI (memory leaks, buffer overflows, UB)
- Users who want native speed can rebuild with `-DNATIVE_OPTIMIZATIONS=ON` (documented in README)

**Negative**:
- Published wheels are 15–20% slower than `-march=native` builds. Acceptable: most time is in Python overhead and I/O, not the C++ recursion. For N = 10⁴, difference is ~5 ms (recursion) vs ~50 ms (total runtime).
- No AVX2 in v0.1: exp() could be 2× faster with SIMD. But runtime dispatch is nontrivial (duplicate code, CPUID checks, dispatch overhead). Punt to v0.2.

**Neutral**:
- `-O3` vs `/O2`: GCC/Clang default to `-O2`, but `-O3` enables more aggressive inlining (useful for Eigen expression templates). MSVC `/O2` is already max optimization (`/O3` doesn't exist). The difference is ~5% on GCC/Clang.
- Link-time optimization (LTO): `-flto` enables cross-translation-unit inlining. Adds 2× to build time, saves ~5% runtime. Enabled in release builds (scikit-build-core handles this), but not required.

## References

- Intel Intrinsics Guide: [AVX2 instruction set](https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html)
- GCC optimization flags: [GCC manual, §3.10 Options That Control Optimization](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)
- `-ffast-math` dangers: [Krister Walfridsson, "Fast-math semantics"](https://kristerw.github.io/2021/10/19/fast-math/)
- AddressSanitizer: [Google Sanitizers project](https://github.com/google/sanitizers)
- mathematics.md §4: Numerical traps (likelihood underflow)
- manylinux tags: [PEP 600](https://peps.python.org/pep-0600/)
