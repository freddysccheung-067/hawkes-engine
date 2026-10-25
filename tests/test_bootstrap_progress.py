"""The bootstrap reports progress, and progress changes nothing.

A 200-replication bootstrap is minutes of silence, which the paper names as a
complaint against this library. ``fit(..., bootstrap_progress=...)`` is the
answer, and the only thing a progress hook may do is observe: these tests pin
that it is called once per replication, in order, and that the standard errors
are identical with and without it.
"""

from __future__ import annotations

import numpy as np
import pytest
from hawkes_engine.fit import fit

MU = np.array([0.5, 0.4])
ALPHA = np.array([[0.2, 0.1], [0.1, 0.2]])
BETA = np.full((2, 2), 2.0)


@pytest.fixture(scope="module")
def data():
    from hawkes_engine.simulation import simulate

    return simulate(MU, ALPHA, BETA, 400.0, method="thinning", seed=3)


def _fit(times, types, progress=None):
    return fit(
        times,
        types,
        M=2,
        T=400.0,
        seed=1,
        se_method="bootstrap",
        n_bootstrap=12,
        bootstrap_workers=1,
        bootstrap_progress=progress,
    )


def test_progress_is_called_once_per_replication_in_order(data) -> None:
    times, types = data
    seen: list[tuple[int, int]] = []
    _fit(times, types, progress=lambda done, total: seen.append((done, total)))
    assert [d for d, _ in seen] == list(range(1, 13))
    assert all(total == 12 for _, total in seen)


def test_progress_does_not_change_the_standard_errors(data) -> None:
    times, types = data
    quiet = _fit(times, types)
    watched = _fit(times, types, progress=lambda done, total: None)
    assert quiet.se is not None and watched.se is not None
    for block in quiet.se:
        assert np.array_equal(quiet.se[block], watched.se[block]), block


def test_no_progress_hook_is_still_the_default(data) -> None:
    """The argument is optional and its absence is not a behaviour change."""
    times, types = data
    out = fit(
        times,
        types,
        M=2,
        T=400.0,
        seed=1,
        se_method="bootstrap",
        n_bootstrap=12,
        bootstrap_workers=1,
    )
    assert out.se is not None
