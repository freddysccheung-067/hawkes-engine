"""The coverage floor is a measured number, and it does not go down.

CI enforces `[tool.coverage.report] fail_under`; nothing stops a later change
lowering it to make a red run green, which is the same failure as loosening a
test. This pins the floor at the value measured when it was added, and pins the
comment that says it is a ratchet, so lowering it has to be a deliberate edit to
a test that says why.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - the test extra installs tomli below 3.11
    import tomli as tomllib


def _config() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_the_coverage_floor_is_at_least_the_measured_value() -> None:
    """91 was measured at 91.04 percent on 2026-10-25; it may rise, not fall."""
    floor = _config()["tool"]["coverage"]["report"]["fail_under"]
    assert floor >= 91, (
        f"the coverage floor is {floor}. It is a ratchet: raise it when coverage "
        f"rises, and if it must fall, say in the commit body what left."
    )


def test_the_selftest_is_excluded_because_pytest_never_imports_it() -> None:
    """A file no test process can execute must not count against the floor.

    `_selftest.py` runs inside CIBW_TEST_COMMAND against an installed wheel. It was
    53 of the 153 uncovered statements, so keeping it in the denominator would
    make the floor mostly a number about a file the suite cannot reach.
    """
    omit = _config()["tool"]["coverage"]["run"]["omit"]
    assert any("_selftest.py" in pattern for pattern in omit)


@pytest.mark.parametrize("key", ["fail_under"])
def test_the_report_keeps_missing_lines_visible(key: str) -> None:
    report = _config()["tool"]["coverage"]["report"]
    assert report["show_missing"] is True
