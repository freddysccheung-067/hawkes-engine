"""What happens when the bootstrap pool dies with a guard in place.

The pool dies under load on this machine at the default worker count: measured
at 2 failures in 25 runs of the README's ``auto`` block, and once at 12
completions into a 200-replication bootstrap. The seed streams make the work
recoverable, so the bootstrap recomputes it in the caller's process and says so
in ``notes``; a pool that dies before a single replication is a different case
and keeps the error that names the missing ``__main__`` guard
(``test_bootstrap_guard.py``).

These tests substitute a pool that breaks on demand, so they do not depend on
the race firing. Nothing here lowers or changes the worker count: the failure is
handled, not hidden.
"""

from __future__ import annotations

from concurrent.futures.process import BrokenProcessPool

import numpy as np
import pytest
from hawkes_engine import _boot
from hawkes_engine._layout import Layout


class _BreakingPool:
    """A pool that yields ``completed`` results, then dies."""

    def __init__(self, *args, completed: int = 3, **kwargs) -> None:
        self._completed = completed
        self._drained = False

    def __enter__(self) -> _BreakingPool:
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def map(self, fn, jobs):
        for k, job in enumerate(jobs):
            if k >= self._completed:
                raise BrokenProcessPool("simulated worker death")
            self._drained = True
            yield fn(job)


@pytest.fixture(scope="module")
def data():
    from hawkes_engine.simulation import simulate

    mu = np.array([0.5, 0.4])
    alpha = np.array([[0.2, 0.1], [0.1, 0.2]])
    beta = np.full((2, 2), 2.0)
    times, types = simulate(mu, alpha, beta, 400.0, method="thinning", seed=3)
    return times, types


def _run(monkeypatch, times, types, completed: int, progress=None):
    layout = Layout(M=2)
    monkeypatch.setattr(
        _boot,
        "ProcessPoolExecutor",
        lambda *a, **k: _BreakingPool(*a, completed=completed, **k),
    )
    return _boot.parametric_bootstrap(
        times,
        types,
        400.0,
        2,
        False,
        np.array([0.5, 0.4]),
        np.array([[0.2, 0.1], [0.1, 0.2]]),
        np.full((2, 2), 2.0),
        layout,
        n_bootstrap=20,
        seed=1,
        progress=progress,
    )


def test_a_dead_pool_is_recomputed_serially_and_says_so(monkeypatch, data) -> None:
    times, types = data
    out = _run(monkeypatch, times, types, completed=3)
    assert out.se is not None, "a pool that died partway lost the whole bootstrap"
    # M = 2, nothing fixed: 2 mu + 4 alpha + 4 beta.
    assert out.draws.shape == (20, 10)
    note = next((n for n in out.notes if "pool died" in n), None)
    assert note is not None, out.notes
    assert "after 3 of 20 replications" in note
    assert "serially" in note


def test_the_serial_draws_are_the_draws_the_pool_would_have_made(monkeypatch, data) -> None:
    """Same coordinates, same result: the fallback is not a different sample."""
    times, types = data
    from_fallback = _run(monkeypatch, times, types, completed=3)
    monkeypatch.undo()
    direct = _boot.parametric_bootstrap(
        times,
        types,
        400.0,
        2,
        False,
        np.array([0.5, 0.4]),
        np.array([[0.2, 0.1], [0.1, 0.2]]),
        np.full((2, 2), 2.0),
        Layout(M=2),
        n_bootstrap=20,
        seed=1,
        workers=1,
    )
    assert np.array_equal(from_fallback.draws, direct.draws)
    assert from_fallback.se is not None and direct.se is not None
    for block in direct.se:
        assert np.array_equal(from_fallback.se[block], direct.se[block])


def test_the_fallback_reports_progress_for_the_recomputed_work(monkeypatch, data) -> None:
    """A caller watching an indicator sees the serial pass, not a stall at 3."""
    times, types = data
    seen: list[tuple[int, int]] = []
    _run(
        monkeypatch,
        times,
        types,
        completed=3,
        progress=lambda done, total: seen.append((done, total)),
    )
    assert [d for d, _ in seen] == list(range(1, 21))
    assert all(total == 20 for _, total in seen)


def test_a_pool_that_dies_before_one_replication_keeps_the_guard_error(monkeypatch, data) -> None:
    """Zero completions is what a missing ``__main__`` guard looks like."""
    times, types = data
    with pytest.raises(RuntimeError) as caught:
        _run(monkeypatch, times, types, completed=0)
    assert "the bootstrap worker pool died" in str(caught.value)
    assert "__main__" in str(caught.value)
