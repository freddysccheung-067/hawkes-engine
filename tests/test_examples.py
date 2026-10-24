"""Run every script in examples/ as a subprocess and check one line of its output.

Each example is deterministic (fixed seeds) and needs neither network access nor
files outside the repository. The expected line is a fact the example is meant to
show, not a transcript, so a change in the library that breaks an example's point
fails here rather than in a reader's terminal. All five run in a few seconds, so
none is marked slow.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 120

EXPECTED = {
    "01_simulate_and_fit.py": "true branching ratio rho = 0.2327",
    "02_time_rescaling_check.py": "diagnostic passes under the truth and rejects the wrong model",
    "03_trust_lookup.py": "status: estimator undefined in this regime",
    "04_se_understate.py": "study, same cell, 2000 replicates: q[mu] = 0.957",
    "05_shared_decay.py": "agree to 1e-10 relative: True",
    "06_auto_interval.py": "reason: a bootstrap was indicated by mu (narrow)",
}


def test_every_example_is_listed():
    on_disk = {p.name for p in (ROOT / "examples").glob("*.py")}
    assert on_disk == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_runs_and_prints_its_point(name):
    script = ROOT / "examples" / name
    assert len(script.read_text().splitlines()) < 60
    done = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert EXPECTED[name] in done.stdout


def test_examples_are_deterministic():
    first = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "01_simulate_and_fit.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=True,
    ).stdout
    second = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "01_simulate_and_fit.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=True,
    ).stdout
    assert first == second
