"""The version string is written in one place and copied in five others.

Each copy exists for a reason that cannot be avoided: PyPI reads ``pyproject.toml``,
CMake reads ``CMakeLists.txt``, Zenodo-style tooling reads ``CITATION.cff``, Sphinx
reads ``docs/conf.py`` and the compiled core can only report a version that was
stamped into it at compile time. The risk is that a release bumps three of them.

This test is the guard. It reads every copy and asserts they agree, so a bump that
misses one fails here rather than shipping a wheel whose metadata, documentation
and compiled core name three different versions.

The one deliberate exception is the gate between development and release. While
the project is between releases the package version ends ``.dev0`` and CMake's
``PROJECT_VERSION`` does not, because CMake takes three numeric components only.
The rule below accepts that pair and nothing else, so a release bump cannot
silently leave a ``.dev0`` behind.
"""

from __future__ import annotations

import re
from pathlib import Path

import hawkes_engine
import pytest
from hawkes_engine import _version
from hawkes_engine._core import build_info

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 has no tomllib; tomli is the same parser
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _pyproject_version() -> str:
    return tomllib.loads(_read("pyproject.toml"))["project"]["version"]


def _cmake_version() -> str:
    found = re.search(r"^project\([^)]*?VERSION\s+([0-9][^)\s]*)", _read("CMakeLists.txt"), re.M)
    assert found, "CMakeLists.txt does not declare a project VERSION"
    return found.group(1)


def _citation_version() -> str:
    found = re.search(r"^version:\s*(\S+)", _read("CITATION.cff"), re.M)
    assert found, "CITATION.cff does not declare a version"
    return found.group(1).strip("\"'")


def _conf_version() -> str:
    """Import the Sphinx configuration and read the release it would stamp."""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT / "docs"))
    try:
        spec = importlib.util.spec_from_file_location("_conf_under_test", ROOT / "docs/conf.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return str(module.release)
    finally:
        sys.path.pop(0)


def test_package_version_is_a_string_with_three_numeric_parts() -> None:
    assert isinstance(hawkes_engine.__version__, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+", _version.__version__), _version.__version__
    assert _version.__version_tuple__ == tuple(int(p) for p in _version.__version__.split("."))


def test_init_reexports_the_one_version() -> None:
    """``__init__`` must not hold its own copy; it re-exports ``_version``."""
    assert hawkes_engine.__version__ is _version.__version__


def test_every_copy_of_the_version_agrees() -> None:
    package = _version.__version__
    pyproject = _pyproject_version()
    citation = _citation_version()
    conf = _conf_version()
    core = build_info()["version"]

    assert package == pyproject, f"pyproject.toml says {pyproject}, the package {package}"
    assert package == citation, f"CITATION.cff says {citation}, the package {package}"
    assert package == conf, f"docs/conf.py says {conf}, the package {package}"

    # CMake cannot carry a ".devN" suffix. Accept the development pair
    # (package 1.2.3.dev0, CMake 1.2.3) and nothing else.
    stripped = re.sub(r"\.dev\d+$", "", package)
    assert core == stripped, f"the compiled core says {core}, the package {package}"
    assert (
        _cmake_version() == stripped
    ), f"CMakeLists.txt says {_cmake_version()}, the package {package}"


def test_a_dev_version_does_not_hide_in_a_release_tree() -> None:
    """When the package is not a dev build, no other copy may claim to be one."""
    package = _version.__version__
    if ".dev" not in package:
        for label, value in (
            ("pyproject.toml", _pyproject_version()),
            ("CITATION.cff", _citation_version()),
            ("CMakeLists.txt", _cmake_version()),
            ("the compiled core", build_info()["version"]),
        ):
            assert ".dev" not in value, f"{label} still says {value} in a release tree"


def test_the_core_reports_the_version_it_exports() -> None:
    """The stub and the built module must describe the same keys."""
    info = build_info()
    assert set(info) == {
        "cxx_standard",
        "version",
        "compiler",
        "compiler_version",
        "pybind11_version",
    }


def test_changelog_has_a_section_for_the_current_version() -> None:
    """A release whose version has no changelog section is not documented."""
    if ".dev" in _version.__version__:
        pytest.skip("development version: CHANGELOG carries Unreleased only")
    assert f"## [{_version.__version__}]" in _read(
        "CHANGELOG.md"
    ), f"CHANGELOG.md has no section for {_version.__version__}"
