# ADR-001: Language and Binding Stack

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

hawkes-engine implements numerical algorithms for multivariate Hawkes processes: log-likelihood evaluation with O(NM²) recursion, gradient computation, MLE optimization, and two independent simulators (thinning and branching). The core recursion (§4 of mathematics.md) touches every event and updates M² state variables, making it CPU-bound. Python alone is 50–100× too slow for N > 10⁴ events. We need compiled performance with Python ergonomics.

The binding layer must support zero-copy NumPy arrays (events in, parameters out), handle errors cleanly, and expose a Pythonic API. Build complexity matters: every dependency is a CI maintenance surface and a user installation risk. The choice cascades: C vs C++, header-only vs linked libraries, manual bindings vs generated, and which build system orchestrates it all.

Trade space: pure Python (easy, unusable), Cython (fast, messy), ctypes (manual, error-prone), pybind11 (mature), nanobind (new), or a Rust/Julia rewrite (too far). We need production-ready today with a 10-year maintenance horizon.

## Decision

- **Core language**: C++20 (not C++17; need concepts, ranges, designated initializers)
- **Linear algebra**: Eigen 3.4+ (header-only, mature, MPL2 license)
- **Bindings**: pybind11 2.11+ (NumPy integration, mature ecosystem)
- **Build system**: scikit-build-core 0.5+ (modern CMake bridge, not setuptools)
- **Python support**: 3.10+ (structural pattern matching, better type hints)
- **Compiler requirements**: GCC 10+, Clang 11+, MSVC 2019+ (C++20 support)

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
- **Cons**: Only 2 years old (vs pybind11's 8), smaller community, less StackOverflow coverage, fewer third-party integrations (e.g., pytest-cpp)
- **Why rejected**: Maturity wins. pybind11 has battle scars from 100k+ projects. Binary size is acceptable (a few MB vs 1 MB is irrelevant for a numerical library).

### Option 4: C (not C++) + ctypes
- **Pros**: Minimal ABI, smaller binaries, no C++ runtime dependency
- **Cons**: Manual memory management for every array, no RAII (error-prone resource cleanup), Eigen is C++, NumPy C API is painful to use correctly
- **Why rejected**: Eigen's expression templates and C++20 ranges make the recursion code 5× more readable. The risk of memory leaks in manual ctypes outweighs the binary size win.

### Option 5: Rust + PyO3
- **Pros**: Memory safety, fast, modern tooling
- **Cons**: Team does not know Rust, no Eigen equivalent (ndarray is less mature), slower compile times, PyO3 NumPy support is less polished than pybind11
- **Why rejected**: C++ is the known quantity. Rust is the right call for a new greenfield project with a team already fluent in it, not for a numerical library with a 6-month H-gate timeline.

## Consequences

**Positive**:
- Zero-copy NumPy ↔ C++: pybind11 handles `py::array_t<double>` → Eigen maps automatically
- Modern C++ features: concepts for template constraints, ranges for cleaner loops, designated initializers for parameter structs
- Mature ecosystem: pybind11 works with pytest, sphinx, mypy stubs, and scikit-build-core out of the box
- Header-only Eigen: no runtime dependency, one `#include`, CMake FetchContent trivial

**Negative**:
- C++20 compiler requirement: MSVC 2019+ (Windows), GCC 10+ (Linux), Clang 11+ (macOS). This excludes CentOS 7 (GCC 4.8) and Ubuntu 18.04 (GCC 7), but those are EOL or nearly so.
- Larger binaries than nanobind: ~3 MB vs ~1 MB. Acceptable for a library that saves hours of compute.
- Compile times: Eigen templates and pybind11 generate a lot of code. Clean builds take ~30s. Use ccache in CI.

**Neutral**:
- scikit-build-core locks us to CMake, but CMake is the de facto standard for C++ scientific libraries (Eigen, BLAS, HDF5 all use it)
- NumPy ABI changes: pybind11 handles this via `py::array_t`, but wheels must be built per-Python-version (3.10, 3.11, 3.12). CI matrix handles this.

## References

- [pybind11 documentation](https://pybind11.readthedocs.io/)
- [Eigen documentation](https://eigen.tuxfamily.org/)
- [scikit-build-core](https://scikit-build-core.readthedocs.io/)
- mathematics.md §4: recursion structure dictates memory layout and loop patterns
- C++20 feature support: [cppreference compiler support](https://en.cppreference.com/w/cpp/compiler_support/20)
