"""Smoke tests for the package and its compiled core."""

import hawkes_engine
from hawkes_engine import _version
from hawkes_engine._core import build_info


def test_package_imports() -> None:
    assert hawkes_engine is not None


def test_version_is_a_string() -> None:
    # The exact string is not repeated here: tests/test_version.py pins its shape
    # and holds it equal to pyproject.toml, CITATION.cff, docs/conf.py and the
    # compiled core. A literal in this file would be a fifth copy to forget.
    assert isinstance(hawkes_engine.__version__, str)
    assert hawkes_engine.__version__ == _version.__version__
    assert hawkes_engine.__version__.count(".") == 2


def test_license_is_mit() -> None:
    assert hawkes_engine.__license__ == "MIT"


def test_core_module_reports_build_info() -> None:
    info = build_info()
    assert info["cxx_standard"] == 20
    assert isinstance(info["compiler"], str) and info["compiler"] != "unknown"
    assert isinstance(info["pybind11_version"], str)
