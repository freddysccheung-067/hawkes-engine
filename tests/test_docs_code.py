"""Run every ```python block in the README and the published pages.

A snippet that does not run is a defect in the documentation, however correct the
prose around it. Each block runs in its own interpreter from a scratch directory,
so it cannot lean on files in the repository. The quickstart's printed output is
checked for shape (same number of lines, same leading word on each), not for
digits, because the last places of a fit can differ between platforms.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "README.md",
    "docs/index.md",
    "docs/quickstart.md",
    "docs/concepts.md",
    "docs/fitting.md",
    "docs/trust.md",
    "docs/limits.md",
    "docs/performance.md",
]
FENCE = re.compile(r"```python\n(.*?)```", re.S)


def _blocks():
    for page in PAGES:
        text = (ROOT / page).read_text(encoding="utf-8")
        for k, code in enumerate(FENCE.findall(text)):
            yield pytest.param(page, code, id=f"{page}#{k}")


def _run(code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


@pytest.mark.parametrize(("page", "code"), list(_blocks()))
def test_python_block_runs(page, code, tmp_path):
    done = _run(code, tmp_path)
    assert done.returncode == 0, f"{page}\n{done.stderr[-1500:]}"


def test_there_are_blocks_to_run():
    assert len(list(_blocks())) >= 4


def test_quickstart_output_block_has_the_shape_of_the_real_output(tmp_path):
    text = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
    code = FENCE.search(text).group(1)
    shown = re.search(r"```text\n(.*?)```", text, re.S).group(1).strip().splitlines()
    real = _run(code, tmp_path).stdout.strip().splitlines()
    assert len(shown) == len(real)
    for a, b in zip(shown, real, strict=True):
        assert a.split()[0] == b.split()[0]
