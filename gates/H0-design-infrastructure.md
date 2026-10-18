# H0: DESIGN AND INFRASTRUCTURE

**Time**: 10 hours (Week 1–2)  
**Goal**: CI green, competitor analysis done, ADRs written, empty package builds  
**Models**: Sonnet 5.5 (research/design), Haiku 5.5 (boilerplate)

---

## OVERVIEW

H0 establishes the project foundation:
- Survey existing libraries (what we're beating, where we're unique)
- Document architecture decisions (8 ADRs)
- Set up CI skeleton (GitHub Actions workflows)
- Create minimal buildable package

**Exit criteria**: `pip install -e . && python -c "import hawkes_engine"` succeeds

---

## H0.1: COMPETITOR DEEP DIVE (3 hours, Sonnet 5.5)

**Prompt** (copy-paste into Claude Code):

```
ROLE: Technical researcher and competitive analyst

TASK: Deep survey of existing Hawkes process libraries (tick, hawkeslib, statsmodels, PyMC, R packages). For each:

1. Visit GitHub repo URL (use WebSearch or WebFetch)
2. Read README, docs, and note key features
3. Document in `D:\hawkes-engine-v2\docs\competitor-analysis.md`:
   - Repo URL, last commit date, stars (as of today)
   - Features: kernels supported, estimators (MLE/EM/Bayesian), diagnostics
   - Performance: stated complexity, any benchmarks in README/docs
   - Weaknesses: archived/unmaintained, slow, missing features, no wheels
   - Our edge over this library (2–3 sentences — be specific and honest)

LIBRARIES TO SURVEY:
- tick (https://github.com/X-DataInitiative/tick)
- hawkeslib (https://github.com/canerturkmen/hawkeslib)
- statsmodels (https://github.com/statsmodels/statsmodels) — check if Hawkes exists
- PyMC (https://github.com/pymc-devs/pymc) — Bayesian, check custom Hawkes use
- R: `hawkes` and `emhawkes` packages (describe from CRAN if accessible, don't install R)

OUTPUT FORMAT:
```markdown
# Hawkes Process Library Competitive Analysis

**Date**: [today's date]
**Purpose**: Establish where hawkes-engine fits in the ecosystem

## Summary Table

| Library | Status | Stars | Last Update | Features | Our Edge |
|---------|--------|-------|-------------|----------|----------|
| tick | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |

## Detailed Analysis

### 1. tick
- **URL**: ...
- **Status**: Archived/Active/Sporadic
- **Features**: ...
- **Weaknesses**: ...
- **Our edge**: ...

[repeat for each library]

## Positioning Summary

[2–3 paragraphs on where hawkes-engine sits: what niche we fill, which users we target]
```

EXIT CRITERIA:
- All 5+ libraries surveyed
- Table complete with accurate data (verify stars/dates are current)
- Document is 1000–1500 words
- "Our edge" is specific (not generic "we're faster")

VERIFICATION: Read the generated file, check completeness and honesty.

COMMIT: "H0.1: Competitor analysis — tick, hawkeslib, statsmodels"

DO NOT: Install unmaintained packages that fail build. Document from repo only.
```

---

## H0.2: WRITE 8 ADRs (4 hours, Sonnet 5.5)

**Prompt**:

```
ROLE: Principal architect

TASK: Write 8 Architecture Decision Records (ADRs) in `D:\hawkes-engine-v2\docs\adr\` following standard format.

ADR TEMPLATE:
```markdown
# ADR-00X: [Decision Title]

**Date**: [today]
**Status**: Accepted

## Context
[Why this decision matters, what problem it solves, 2–3 sentences]

## Decision
[What we chose, stated clearly]

## Alternatives Considered
[What we rejected and why, bulleted list with rationale]

## Consequences
[What this choice implies: benefits, costs, constraints]

## References
[Citations if needed, or "None"]
```

ADRs TO WRITE (create separate files ADR-001.md through ADR-008.md):

1. **ADR-001: Language and Binding Stack**
   - Decision: C++20 + Eigen + pybind11 + scikit-build-core
   - Alternatives: Rust + PyO3, pure NumPy, Cython
   - Context: Need speed (millions of events), portability (wheels), Python API
   - Rationale: Warm C++ from P02, Eigen vectorization, quant portfolio signal, pybind11 cleanest

2. **ADR-002: Excitation-Only v0.1 (α ≥ 0)**
   - Decision: No inhibition in v0.1
   - Alternatives: Ship inhibition anyway, never support it
   - Context: Negative α breaks thinning bound and gradient at max(0, λ) kink
   - Rationale: Clean math, v0.2 for inhibition with modified thinning + subgradient

3. **ADR-003: Parameterization and Index Convention**
   - Decision: Row i = target, col j = source; log-space params internally
   - Alternatives: Column = target, natural-space with bounds
   - Context: Fix indexing convention, handle positivity constraints
   - Rationale: Literature convention (Laub et al.), positivity automatic, no bound-active stalling

4. **ADR-004: Event Memory Layout (Structure-of-Arrays)**
   - Decision: SoA (times[], types[] separate, not struct-of-arrays)
   - Alternatives: Array-of-structs (AoS)
   - Context: Hot loop streams times, branches on type
   - Rationale: Cache-friendly, zero-copy from NumPy, padding wastes 7 bytes/event in AoS

5. **ADR-005: Threading Model and GIL Policy**
   - Decision: Single-threaded core, parallel multi-start, GIL release everywhere
   - Alternatives: Parallel likelihood (complex), no GIL release
   - Context: State recursion is serial, parallelism only in independent fits
   - Rationale: Test GIL release with 2-thread busy-loop, no global state

6. **ADR-006: RNG and Seed Streams**
   - Decision: std::mt19937_64, explicit seeds, SplitMix64 for thread streams
   - Alternatives: std::random_device (non-reproducible), PCG (not stdlib)
   - Context: Reproducibility (same seed → same output)
   - Rationale: Stdlib availability, test determinism, parallel MC derives seeds per replication

7. **ADR-007: Build and Wheel Strategy**
   - Decision: No -ffast-math, no -march=native in CI, cibuildwheel matrix
   - Alternatives: -ffast-math for speed, -march=native in wheels
   - Context: Wheels must run on other CPUs, -ffast-math breaks -inf return
   - Rationale: Local bench preset uses -march=native, CI is conservative x86-64-v2

8. **ADR-008: License**
   - Decision: MIT (or Apache 2.0)
   - Alternatives: GPL (limits commercial use)
   - Context: Maximize adoption, quant firms avoid GPL
   - Rationale: Permissive license, SPDX headers, CITATION.cff separate

Each ADR should be 200–400 words. Use template above. Be specific in rationales.

EXIT CRITERIA:
- 8 files in `D:\hawkes-engine-v2\docs\adr\`
- Each follows standard format (Context, Decision, Alternatives, Consequences)
- Decisions are justified with technical rationale, not hand-waving

VERIFICATION: Read each ADR, check format and substance.

COMMIT: "H0.2: ADRs 001–008 — language, threading, memory, build"
```

---

## H0.3: CI SKELETON (2 hours, Haiku 5.5)

**Prompt**:

```
ROLE: DevOps engineer

TASK: Create GitHub Actions CI skeleton in `D:\hawkes-engine-v2\repo-template\.github\workflows\`.

Create this directory first:
```
mkdir -p D:\hawkes-engine-v2\repo-template\.github\workflows
```

FILES TO CREATE:

1. **ci.yml**: Fast test matrix (Linux/macOS/Win, Py 3.10–3.12)
   ```yaml
   name: CI

   on:
     push:
       branches: [main]
     pull_request:

   jobs:
     test:
       runs-on: ${{ matrix.os }}
       strategy:
         matrix:
           os: [ubuntu-latest, macos-latest, windows-latest]
           python-version: ['3.10', '3.11', '3.12']
       
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: ${{ matrix.python-version }}
         - name: Install dependencies
           run: |
             python -m pip install --upgrade pip
             pip install -e . --no-build-isolation
         - name: Build C++
           run: |
             cmake --preset dev
             cmake --build --preset dev
         - name: Run C++ tests
           run: ctest --preset dev --output-on-failure
         - name: Run Python tests
           run: pytest -v
       
       timeout-minutes: 10
   ```

2. **wheels.yml**: Build wheels with cibuildwheel (triggered on git tag)
   ```yaml
   name: Build Wheels

   on:
     push:
       tags:
         - 'v*'

   jobs:
     build_wheels:
       name: Build wheels on ${{ matrix.os }}
       runs-on: ${{ matrix.os }}
       strategy:
         matrix:
           os: [ubuntu-latest, macos-latest, windows-latest]

       steps:
         - uses: actions/checkout@v4
         - uses: pypa/cibuildwheel@v2.16
           env:
             CIBW_BUILD: cp310-* cp311-* cp312-*
             CIBW_SKIP: "*-musllinux_*"
         - uses: actions/upload-artifact@v3
           with:
             name: wheels
             path: ./wheelhouse/*.whl
   ```

3. **pre-commit.yml**: Run clang-format, black, check oracle/ unchanged
   ```yaml
   name: Pre-commit

   on:
     pull_request:

   jobs:
     pre-commit:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
         - name: Install pre-commit
           run: pip install pre-commit
         - name: Run pre-commit
           run: pre-commit run --all-files
   ```

CONSTRAINTS:
- Use latest GitHub Actions syntax (actions/checkout@v4, actions/setup-python@v5)
- ci.yml must run in < 10 min (empty repo, just skeleton)
- Comment each step clearly
- All 3 files must pass `yamllint` (install with `pip install yamllint`, run `yamllint file.yml`)

EXIT CRITERIA:
- 3 YAML files in `D:\hawkes-engine-v2\repo-template\.github\workflows\`
- ci.yml has matrix (3 OS × 3 Python versions), runs on push
- wheels.yml triggers on tags
- All files pass yamllint (no errors)

VERIFICATION:
```
cd D:\hawkes-engine-v2\repo-template\.github\workflows
yamllint *.yml
```

COMMIT: "H0.3: CI skeleton — ci, wheels, pre-commit workflows"

DO NOT: Run actual builds yet (no CMakeLists.txt exists). Just create workflow files.
```

---

## H0.4: EMPTY PACKAGE SCAFFOLD (1 hour, Sonnet 5.5)

**Prompt**:

```
ROLE: Build engineer

TASK: Create minimal buildable package that imports successfully.

Create in `D:\hawkes-engine-v2\repo-template\` (this will be copied to actual repo later).

FILES TO CREATE:

1. **pyproject.toml**:
```toml
[build-system]
requires = ["scikit-build-core", "pybind11"]
build-backend = "scikit_build_core.build"

[project]
name = "hawkes-engine"
version = "0.0.1.dev"
description = "Multi-dimensional Hawkes process fitting and simulation with trust calibration"
authors = [{name = "Freddy", email = "your-email@example.com"}]
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.23",
    "scipy>=1.10",
    "pandas>=1.5",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "hypothesis>=6.0", "black", "isort", "mypy"]

[tool.scikit-build]
cmake.minimum-version = "3.20"
```

2. **CMakeLists.txt** (top-level):
```cmake
cmake_minimum_required(VERSION 3.20)
project(hawkes_engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Fetch Eigen
include(FetchContent)
FetchContent_Declare(
    Eigen
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(Eigen)

# Add subdirectories (will create in H2)
# add_subdirectory(cpp)
```

3. **cpp/CMakeLists.txt** (empty stub):
```cmake
# C++ library and bindings (to be populated in H2)
```

4. **python/hawkes_engine/__init__.py**:
```python
"""hawkes-engine: Hawkes process fitting and simulation with trust calibration."""

__version__ = "0.0.1.dev"
```

5. **cpp/src/bindings.cpp** (minimal pybind11 module):
```cpp
#include <pybind11/pybind11.h>

PYBIND11_MODULE(_core, m) {
    m.doc() = "hawkes_engine C++ core";
    m.attr("__version__") = "0.0.1.dev";
}
```

EXIT CRITERIA:
- All 5 files created in `D:\hawkes-engine-v2\repo-template\`
- `cd D:\hawkes-engine-v2\repo-template && pip install -e .` succeeds (builds extension)
- `python -c "import hawkes_engine; print(hawkes_engine.__version__)"` prints "0.0.1.dev"

VERIFICATION:
1. Create virtualenv: `python -m venv .venv && source .venv/bin/activate` (or Windows: `.venv\Scripts\activate`)
2. Run `pip install -e . --no-build-isolation`
3. Import hawkes_engine in Python
4. Check no errors

COMMIT: "H0.4: Empty package scaffold — builds and imports"

IMPORTANT: If build fails, debug with `pip install -v -e .` (verbose). Common issues:
- CMake not found → install CMake
- Compiler not found → install GCC/Clang/MSVC
- Eigen fetch fails → check network
```

---

## H0 EXIT TEST

After completing all 4 sub-tasks, verify:

```bash
cd D:\hawkes-engine-v2\repo-template
pip install -e . --no-build-isolation
python -c "import hawkes_engine; print(hawkes_engine.__version__)"
```

**Expected output**: `0.0.1.dev`

If this works, H0 is complete. Update STATE.md:

```markdown
## COMPLETED GATES

### H0 (Design and Infrastructure) — ✅ COMPLETE
- [x] H0.1: Competitor analysis
- [x] H0.2: 8 ADRs written
- [x] H0.3: CI skeleton
- [x] H0.4: Empty package builds

**Completed**: [date]
**Time**: [actual hours]
**Next**: H1 (Mathematics and Oracle)
```

---

## NEXT GATE

**H1: Mathematics and Oracle** (25 hours, YOU do the math)

See `gates/H1-mathematics-oracle.md` for prompts.
