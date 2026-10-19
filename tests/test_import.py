"""Smoke tests for the package and its compiled core."""

import hawkes_engine
from hawkes_engine._core import build_info


def test_package_imports() -> None:
    assert hawkes_engine is not None


def test_version_is_a_string() -> None:
    assert isinstance(hawkes_engine.__version__, str)
    assert hawkes_engine.__version__ == "0.1.0.dev0"


def test_license_is_mit() -> None:
    assert hawkes_engine.__license__ == "MIT"


def test_core_module_reports_build_info() -> None:
    info = build_info()
    assert info["cxx_standard"] == 20
    assert isinstance(info["compiler"], str) and info["compiler"] != "unknown"
    assert isinstance(info["pybind11_version"], str)
