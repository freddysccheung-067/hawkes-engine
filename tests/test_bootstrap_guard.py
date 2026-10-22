"""The parametric bootstrap runs in worker processes, and what happens without a guard.

On Windows and macOS workers are spawned, so a script that calls
``fit(..., se_method="bootstrap")`` at module level re-runs itself in every worker
and the pool dies. ``fit`` documents the need for an ``if __name__ == "__main__":``
guard; these tests check the documentation is true and that the failure names it.
Both run a child interpreter, so they do not depend on how pytest was started.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_BODY = """
    import numpy as np
    import hawkes_engine as he

    mu = np.array([0.5, 0.4])
    alpha = np.array([[0.2, 0.1], [0.1, 0.2]])
    beta = np.full((2, 2), 2.0)
    times, types = he.simulate(mu, alpha, beta, 400.0, seed=3)
    out = he.fit(times, types, M=2, T=400.0, se_method="bootstrap", n_bootstrap=12, seed=1)
    print("SE_KEYS", sorted(out.se) if out.se else None)
"""


def _run(script: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "script.py"
    path.write_text(script, encoding="utf-8")
    # Run from the temporary directory so the source tree is not on sys.path by
    # accident; the package under test is the installed one.
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


def test_bootstrap_runs_under_a_main_guard(tmp_path: Path) -> None:
    body = textwrap.indent(textwrap.dedent(_BODY), "    ")
    script = "if __name__ == '__main__':\n" + body
    done = _run(script, tmp_path)
    assert done.returncode == 0, done.stderr[-2000:]
    assert "SE_KEYS ['alpha', 'beta', 'mu']" in done.stdout, done.stdout + done.stderr[-1000:]


@pytest.mark.skipif(
    sys.platform not in ("win32", "darwin"),
    reason="workers are forked elsewhere, so a missing guard is harmless there",
)
def test_bootstrap_without_a_guard_names_the_guard(tmp_path: Path) -> None:
    done = _run(textwrap.dedent(_BODY), tmp_path)
    assert done.returncode != 0
    # Python's own spawn error, printed by each child, also contains "__main__", so
    # that string cannot tell the two apart. Assert on the library's message.
    assert "the bootstrap worker pool died" in done.stderr, done.stderr[-2000:]
    assert "__main__" in done.stderr
