# ADR-001: Language and Binding Stack

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

hawkes-engine implements numerical algorithms for multivariate Hawkes processes:
log-likelihood evaluation with an O(NM²) recursion, gradient computation, MLE
optimization, and two independent simulators (thinning and branching). The core
recursion (§4 of mathematics.md) touches every event and updates M² state
variables, making it CPU-bound. A pure Python implementation is too slow for
N > 10⁴ events. We need compiled performance with Python ergonomics.

The binding layer must support zero-copy NumPy arrays (events in, parameters
out), handle errors cleanly, and expose a Pythonic API. Build complexity
matters: every dependency is a CI maintenance surface and a user installation
risk.

Trade space: pure Python (easy, unusable), Cython (fast, messy), ctypes
(manual, error-prone), pybind11 (mature), nanobind (new), or a Rust/Julia
rewrite (too far).

## Decision

- **Core language**: C++20 (not C++17; need concepts, ranges, designated initializers)
- **Linear algebra**: Eigen 3.4+ (header-only, mature, MPL2 license). Not
  required for the H2 recursion, which is scalar; adopted when the estimator
  and standard-error code at H3 needs it.
- **Bindings**: pybind11 2.11+ (NumPy integration, mature ecosystem)
- **Build system**: scikit-build-core 0.10+ (modern CMake bridge, not setuptools)
- **Python support**: 3.10+
- **Compiler requirements**: GCC 10+, Clang 11+, MSVC 2019+ (C++20 support)

### Amendment: the build backend

This ADR originally named scikit-build-core, but the scaffold that landed at H0
used setuptools, on the reasoning that a pure-Python package needs no compiler.
That left the ADR describing a system that did not exist. As of 2026-10-19 the
build backend is scikit-build-core with a CMake project and a compiled
`hawkes_engine._core` extension, and the ADR and the code agree.

The reason to resolve it towards the ADR rather than towards setuptools is that
H2 is a C++ gate. A build system that only knows how to copy Python files would
have had to be replaced at exactly the moment the project becomes load-bearing,
taking the CI configuration with it. Doing it at H1, with a trivial extension,
means the compilation path is exercised on all three platforms before there is
anything in it to go wrong.

## Alternatives Considered

### Option 1: Pure Python + NumPy
- **Pros**: No compilation, instant iteration, one language
- **Cons**: 50–100× slower than C++, unusable for N > 10⁴, no way to hide the recursion state
- **Why rejected**: Performance is non-negotiable. The recursion updates M² states per event; vectorization cannot eliminate the loop.

### Option 2: Cython
- **Pros**: Gradual optimization (Python → typed Python → C), NumPy support, mature
- **Cons**: Type annotations pollute code, debugging is harder (mixed stacktraces), harder to reason about what gets compiled vs interpreted, bindings generation is semi-manual
- **Why rejected**: C++ concepts and Eigen are cleaner than Cython's memoryview syntax. We want the core in a language designed for systems work.

### Option 3: nanobind (instead of pybind11)
- **Pros**: Smaller binaries (~40% of pybind11), faster compile, modern C++17+ only
- **Cons**: Younger than pybind11, smaller community, fewer third-party integrations
- **Why rejected**: Maturity wins. Binary size is acceptable (a few MB vs 1 MB is irrelevant for a numerical library).

### Option 4: C (not C++) + ctypes
- **Pros**: Minimal ABI, smaller binaries, no C++ runtime dependency
- **Cons**: Manual memory management for every array, no RAII (error-prone resource cleanup), Eigen is C++, NumPy C API is painful to use correctly
- **Why rejected**: Eigen's expression templates and C++20 ranges make the recursion code more readable. The risk of memory leaks in manual ctypes outweighs the binary size win.

### Option 5: Rust + PyO3
- **Pros**: Memory safety, fast, modern tooling
- **Cons**: The author does not know Rust; no Eigen equivalent (ndarray is less mature); slower compile times
- **Why rejected**: C++ is the known quantity for this project, and a numerical library with a fixed gate timeline is the wrong place to learn a new systems language.

## Consequences

**Positive**:
- Zero-copy NumPy ↔ C++: pybind11 handles `py::array_t<double>` → Eigen maps
- Modern C++ features: concepts for template constraints, ranges for cleaner loops, designated initializers for parameter structs
- Mature ecosystem: pybind11 works with pytest, sphinx, mypy stubs, and scikit-build-core out of the box
- Header-only Eigen: no runtime dependency, one `#include`, CMake FetchContent trivial

**Negative**:
- C++20 compiler requirement: MSVC 2019+ (Windows), GCC 10+ (Linux), Clang 11+ (macOS). This excludes CentOS 7 (GCC 4.8) and Ubuntu 18.04 (GCC 7), both EOL.
- Larger binaries than nanobind: ~3 MB vs ~1 MB. Acceptable for a library that saves hours of compute.
- Compile times: Eigen templates and pybind11 generate a lot of code. Use ccache in CI.
- Everyone who installs from source needs a compiler and CMake 3.24+. Wheels avoid this for end users, but contributors feel it. Documented in the README.

**Neutral**:
- scikit-build-core locks us to CMake, but CMake is the de facto standard for C++ scientific libraries (Eigen, BLAS, HDF5 all use it)
- NumPy ABI changes: pybind11 handles this via `py::array_t`, but wheels must be built per Python version. CI matrix handles this.

## References

- [pybind11 documentation](https://pybind11.readthedocs.io/)
- [Eigen documentation](https://eigen.tuxfamily.org/)
- [scikit-build-core](https://scikit-build-core.readthedocs.io/)
- mathematics.md §4: recursion structure dictates memory layout and loop patterns
- C++20 feature support: [cppreference compiler support](https://en.cppreference.com/w/cpp/compiler_support/20)
