# Installing hawkes-engine

**There are no PyPI releases yet.** The project is pre-alpha and the first
release is gate H9 of nine. Everything below is either building from source or
installing a wheel built locally by CI; neither is a stable distribution.

## From a wheel built by CI

The `Build Wheels` workflow produces wheels for CPython 3.10-3.12 on Linux
(x86-64), macOS (x86-64 and arm64) and Windows (AMD64). They are attached to the
workflow run, not to a release:

1. Open the run on the [Actions page](https://github.com/freddysccheung-067/hawkes-engine/actions/workflows/wheels.yml)
   and download the `wheels-<os>` artefact for your platform.
2. Install it into an environment whose Python matches the wheel's tag:

```bash
python -m pip install hawkes_engine-0.1.0.dev0-cp312-cp312-win_amd64.whl
```

A wheel built for `cp312` will not install into 3.10 or 3.11; that is the ABI
tag, not an error.

## From source

You need a C++20 compiler, CMake 3.24 or newer, and Python 3.10-3.12 with
development headers. The build fetches pybind11 through scikit-build-core, so
the first build needs network access.

### Windows (verified on Windows 11, MSVC 19.44)

```powershell
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q -m "not slow"
```

Visual Studio 2022 with the "Desktop development with C++" workload is what
supplies `cl.exe`; the free Community edition is enough. `pip install -e` builds
the extension into `.venv\Lib\site-packages\hawkes_engine\_core.*.pyd` and links
the source tree through a path file, so an edit to `python/hawkes_engine/*.py`
takes effect without reinstalling while an edit to `cpp/` does not.

To build with the tests and warnings-as-errors locally:

```powershell
cmake --preset dev -Dpybind11_DIR="$(python -m pybind11 --cmakedir)"
cmake --build --preset dev --config Release
ctest --preset dev --build-config Release
```

### Linux (x86-64)

```bash
sudo apt-get install -y build-essential cmake python3-dev
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest -q -m "not slow"
```

GCC 10 or newer is required for C++20.

### macOS (x86-64 and arm64)

```bash
xcode-select --install
brew install cmake
git clone https://github.com/freddysccheung-067/hawkes-engine.git
cd hawkes-engine
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest -q -m "not slow"
```

## Building a wheel yourself

```bash
python -m pip install "cibuildwheel==4.3.1"
python -m cibuildwheel --output-dir wheelhouse
```

To build for the machine you are on rather than for a portable target, set
`NATIVE_OPTIMIZATIONS=ON` through the environment:

```bash
CMAKE_ARGS="-DNATIVE_OPTIMIZATIONS=ON" python -m pip install -e .
```

That adds `-march=native` on GCC and Clang. It has no effect on MSVC. Do not
publish a wheel built that way: it crashes on an older CPU rather than running
slower (ADR-006).

## Known limitations

- No PyPI wheels. `pip install hawkes-engine` will fail.
- Python 3.13 and 3.14 are not built. The wheel matrix is cp310-cp312; adding a
  version is a change to `CIBW_BUILD` and a test run, not a rebuild.
- musllinux is not built. The core has no libc-sensitive dependency, so those
  wheels would be untested duplicates of the manylinux ones.
- No 32-bit or ARM Windows wheels.
- `se_method="bootstrap"` refits the model `n_bootstrap` times and is slow. The
  default is `"hessian"`.
