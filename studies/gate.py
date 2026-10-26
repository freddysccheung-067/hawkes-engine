"""Make a fresh-venv install and the full gate list visible in one command.

    python -m studies.gate

Runs the checks a release must pass, in the order CI runs them, and prints one
line per gate. It is not the release checklist (`docs/releasing.md` is): it does
not tag, publish, or touch the network. It exists so a session that prepares a
release can say which gates it actually ran, and where one failed, rather than
summarising.

Each gate is a command with an expected exit status and, where it matters, a
pattern its output must contain. Nothing here is a proxy for a human reading the
diff.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]
    expect: int = 0
    must_contain: str | None = None
    skip: str | None = None


def _python() -> str:
    return sys.executable


GATES: tuple[Gate, ...] = (
    Gate(
        "lint",
        (_python(), "-m", "ruff", "check", "python/", "tests/", "studies/", "benchmarks/"),
    ),
    Gate(
        "format",
        (_python(), "-m", "ruff", "format", "--check", "python/", "tests/", "studies/"),
        skip=None,
    ),
    Gate("types", (_python(), "-m", "mypy", "python/hawkes_engine/")),
    Gate(
        "tests (fast)",
        (
            _python(),
            "-m",
            "pytest",
            "tests/",
            "-q",
            "-m",
            "not slow",
            "--ignore=tests/test_sdist.py",
            "--cov",
            "--cov-report=",
        ),
    ),
    Gate(
        "docs",
        (_python(), "-m", "sphinx", "-W", "--keep-going", "-b", "html", "docs", "docs/_build"),
    ),
    Gate(
        "examples",
        (_python(), "-m", "pytest", "tests/test_examples.py", "-q"),
    ),
    Gate(
        "paper structure",
        (_python(), "-m", "studies.check_paper"),
        must_contain="paper structure checks pass",
    ),
    Gate(
        "generated paper is current",
        (_python(), "-m", "studies.make_paper_tex", "--check"),
        must_contain="up to date",
    ),
    Gate(
        "grid freeze",
        (_python(), "-m", "studies.verify_grid"),
    ),
    Gate(
        "documentation claims",
        (_python(), "-m", "pytest", "tests/test_docs_claims.py", "-q"),
    ),
)


def run(gate: Gate) -> tuple[bool, str, float]:
    if gate.skip:
        return True, f"SKIP {gate.skip}", 0.0
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            list(gate.command), cwd=REPO, capture_output=True, text=True, timeout=3600
        )
    except FileNotFoundError as exc:
        return False, str(exc), time.perf_counter() - started
    except subprocess.TimeoutExpired:
        return False, "timed out after an hour", time.perf_counter() - started
    elapsed = time.perf_counter() - started
    ok = proc.returncode == gate.expect
    if ok and gate.must_contain and gate.must_contain not in proc.stdout:
        ok = False
        proc = subprocess.CompletedProcess(
            proc.args, 1, proc.stdout, proc.stderr + f"\nmissing {gate.must_contain!r}"
        )
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    if not ok:
        err = (proc.stderr.strip().splitlines() or [""])[-1]
        tail = f"{tail} | {err}" if err else tail
    return ok, tail, elapsed


def main(argv: list[str] | None = None) -> int:
    selected = set(argv or [])
    failures = 0
    for gate in GATES:
        if selected and gate.name not in selected:
            continue
        ok, tail, elapsed = run(gate)
        status = "PASS" if ok else "FAIL"
        print(f"{status:4s} {gate.name:28s} {elapsed:7.1f}s  {tail[:110]}")
        failures += 0 if ok else 1
    if not shutil.which(_python()):  # pragma: no cover - the interpreter just ran
        print("the running interpreter is not on PATH", file=sys.stderr)
        return 2
    print(f"\n{len(GATES) - failures} of {len(GATES)} gates passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
