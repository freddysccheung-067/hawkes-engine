# ADR-006: Build Strategy and Compiler Flags

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

Published wheels must run on any supported x86-64 machine. Developer builds and
power users want the build tuned to their own CPU. The two goals conflict.

`-march=native` compiles for the *build machine's* CPU, not the user's. A wheel
built on a recent CPU with AVX-512 crashes with an illegal-instruction fault on
an older one. `-ffast-math` relaxes IEEE 754: it permits reassociation and lets
the compiler assume values are finite. The likelihood returns -inf when λᵢ
underflows to 0 (mathematics.md §4); under `-ffast-math` that can become NaN,
and NaN propagates through an optimizer silently.

Sanitizers catch memory errors and undefined behaviour but add large run-time
overhead, so they belong in CI only, never in a shipped wheel.

## Decision

**Published wheels** (PyPI):
- Target: generic x86-64, no architecture-specific instructions
- Flags: the compiler's default optimisation for a release build; no
  `-march=native`, no `-ffast-math`
- Reason: must run everywhere the platform tag claims, and must handle NaN and
  inf correctly

**User opt-in builds** (from source):
- CMake option `-DNATIVE_OPTIMIZATIONS=ON` adds `-march=native` on GCC/Clang
- Still no `-ffast-math`
- The option has no effect on MSVC, where the equivalent is `/arch:AVX2` and
  the portability reasoning is the same

**CI**: a debug build with sanitizers (`-fsanitize=address,undefined`) on Linux,
run against the test suite. Not part of the wheel build.

**SIMD**: deferred. Runtime dispatch means two code paths and a CPU check at
module load. That is worth doing when there is a measured bottleneck to
dispatch to, which there is not until H2 and H7.

## Alternatives Considered

### Option 1: Ship wheels built with `-march=native`
- **Pros**: Faster out of the box
- **Cons**: The wheel runs only on CPUs at least as capable as the build
  machine, and fails with a hard crash, not a slow fallback, when it does not.
- **Why rejected**: A wheel that crashes is worse than a wheel that is slower.
  Users who want native performance can build it themselves.

### Option 2: Enable `-ffast-math`
- **Pros**: Some speedup in transcendental-heavy loops
- **Cons**: Breaks the -inf semantics the likelihood depends on, and makes
  results depend on compiler version and flag combination — contradicting the
  reproducibility guarantee in ADR-005.
- **Why rejected**: Numerical correctness is the product. A faster wrong
  answer has no market.

### Option 3: One wheel per instruction set
- **Pros**: Each user gets the fastest build their CPU supports
- **Cons**: Microarchitecture platform tags are not standard on PyPI; pip
  cannot reliably select on them.
- **Why rejected**: Complexity exceeds benefit, and the mechanism is unreliable.

### Option 4: Profile-guided optimisation
- **Pros**: Optimises for the real workload
- **Cons**: Two-pass build, CI complexity, and the profile has to match the
  user's parameter regime.
- **Why rejected**: Premature. Revisit after H7 has measurements.

**Note on removed claims**: the original version of this ADR contained specific
speedup figures ("AVX2 gives 2× speedup for exp()", "-O3 is ~5% faster", "LTO
saves ~5%") that were not measured by this project. They have been removed for
the same reason as the number in ADR-003: an unmeasured figure in a design
document becomes a claim someone repeats. H7 will produce real numbers for the
real implementation, and they will replace these.

## Consequences

**Positive**:
- Wheels run on every machine the platform tag claims
- Correct IEEE 754 behaviour, so -inf stays -inf
- One wheel per Python version per platform; a small publish matrix
- Sanitizers catch memory bugs that a sequential C++ core would otherwise hide
  until a user hits them

**Negative**:
- Published wheels leave some performance on the table. How much is unknown
  until H7 measures it, and this ADR will be amended with that measurement.
- No SIMD in v0.1.

**Neutral**:
- Compiler defaults differ between GCC, Clang and MSVC. Since no
  performance-critical tuning is applied, the differences are acceptable.
- LTO is left at the compiler default rather than forced.

## References

- mathematics.md §4: the underflow trap that `-ffast-math` would break
- GCC optimisation flags: [GCC manual, Optimize Options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)
- Walfridsson, K., ["Fast-math semantics"](https://kristerw.github.io/2021/10/19/fast-math/)
- AddressSanitizer: [Google sanitizers](https://github.com/google/sanitizers)
