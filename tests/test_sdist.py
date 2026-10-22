"""What a source distribution must and must not contain.

An sdist is what a user who cannot install a wheel downloads. Two failure modes
matter more than they look:

- A missing source file makes the sdist unbuildable, and the user discovers it
  as a compiler error against a truncated tree.
- A file that is the maintainer's working notes ships to everyone, and a
  maintainer's notes record the process, not the product.

The checks below read the tarball rather than the build configuration, because
the configuration can look right while the listing is wrong. Building an sdist
takes seconds; ``test_sdist_*`` builds one into a temporary directory.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 has no tomllib; tomli is the same parser
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]

# A source distribution has to carry every file the build reads.
REQUIRED_SUFFIXES = (
    "pyproject.toml",
    "LICENSE",
    "README.md",
    "CMakeLists.txt",
    "python/hawkes_engine/__init__.py",
    "python/hawkes_engine/_version.py",
    "python/hawkes_engine/py.typed",
    "data/trust/v1_excitation_only.csv",
    "cpp/src/_core.cpp",
    "cpp/src/bindings.cpp",
    "cpp/include/hawkes/types.hpp",
)

# The maintainer's process, not the project: status and working notes, the release
# checklist, and local editor configuration. This is the policy; pyproject.toml's
# sdist.exclude must carry exactly these, and the tarball must contain none.
EXCLUDED_FILES = (
    "docs/STATE.md",
    "docs/RELEASING.md",
    "studies/ANALYSIS_NOTES.md",
    "studies/HARNESS_NOTES.md",
    "CLAUDE.md",
    "wheelbuild.log",
)
EXCLUDED_TREES = (".claude/",)

# Generated or local state that must never be tracked into a tarball.
FORBIDDEN_FRAGMENTS = (
    "/studies/results/cells/",
    "/studies/results/logs/",
    "/benchmarks/.cache/",
    "/wheelhouse",
    "/dist/",
    "/build/",
    "/build-",
    "/.venv/",
    "/__pycache__/",
    "/.pytest_cache/",
    "/.mypy_cache/",
    "/.ruff_cache/",
    "/.hypothesis/",
    "/.vscode/",
    "/.idea/",
    ".log",
    ".whl",
    ".pyd",
    ".so",
)


@pytest.fixture(scope="module")
def sdist_members() -> list[str]:
    """Build the sdist once and return its member paths."""
    # `importorskip("build")` is not enough: the repository has a build/ directory
    # from the CMake presets, which imports as a namespace package and satisfies a
    # bare import while having no CLI. Require the module the command actually
    # runs, so a machine without the package skips instead of failing.
    pytest.importorskip("build.__main__")
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    tarball = out / f"hawkes_engine-{version}.tar.gz"
    # Run from a scratch directory, not the repository: `python -m build` puts the
    # current directory first on sys.path, and the repository has a build/ folder
    # from the CMake presets, so running it here resolves `build` to that folder
    # and dies with "No module named build.__main__". The package argument names
    # the project, so the build reads the same tree either way.
    with tempfile.TemporaryDirectory() as scratch:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", "--outdir", str(out), str(ROOT)],
            cwd=scratch,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        pytest.fail(f"sdist build failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    assert tarball.exists(), f"build reported success but {tarball} is missing"
    with tarfile.open(tarball) as tar:
        return tar.getnames()


def test_sdist_carries_every_source_file(sdist_members: list[str]) -> None:
    for suffix in REQUIRED_SUFFIXES:
        assert any(
            name.endswith(suffix) for name in sdist_members
        ), f"the sdist has no {suffix}; it could not build into a wheel"


def _relative(members: list[str]) -> list[str]:
    """Member paths without the leading `name-version/` directory."""
    return [name.split("/", 1)[1] for name in members if "/" in name]


def test_sdist_carries_no_maintainer_working_files(sdist_members: list[str]) -> None:
    relative = _relative(sdist_members)
    found = [r for r in relative if r in EXCLUDED_FILES or r.startswith(EXCLUDED_TREES)]
    assert not found, f"the sdist ships maintainer files: {found}"


def test_sdist_carries_no_generated_or_local_state(sdist_members: list[str]) -> None:
    found = [n for n in sdist_members if any(fragment in n for fragment in FORBIDDEN_FRAGMENTS)]
    assert not found, f"the sdist ships generated or local files: {found}"


def test_sdist_excludes_what_the_configuration_claims() -> None:
    """The configuration and the behaviour must say the same thing."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    excludes = config["tool"]["scikit-build"]["sdist"]["exclude"]
    expected = set(EXCLUDED_FILES) | {tree + "**" for tree in EXCLUDED_TREES}
    assert (
        set(excludes) == expected
    ), f"sdist.exclude is {sorted(excludes)}, the policy is {sorted(expected)}"


def test_sdist_is_small_enough_to_download() -> None:
    """A tarball that picked up the study outputs would be hundreds of megabytes."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    tarball = ROOT / "dist" / f"hawkes_engine-{version}.tar.gz"
    assert tarball.exists(), "run the sdist fixture first"
    size_mb = tarball.stat().st_size / 1e6
    assert size_mb < 10, f"the sdist is {size_mb:.1f} MB"
