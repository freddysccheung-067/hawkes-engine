"""Thinning for the parametric bootstrap, backed by the compiled simulator.

This lives in the package because the bootstrap is a public feature and a
public feature cannot import from the test tree: a wheel installed from PyPI has
no ``tests`` directory, and ``se_method="bootstrap"`` would fail on every
machine that is not this checkout.

The algorithm is the C++ Ogata thinning of :mod:`hawkes_engine.simulation`. The
NumPy implementation it replaced now lives in ``tests/_simulate_reference.py``
as an independent check, and ``tests/test_simulators.py`` holds the agreement
between the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from hawkes_engine.simulation import simulate

__all__ = ["Simulation", "simulate_thinning"]


@dataclass(frozen=True)
class Simulation:
    """A simulated event stream, sorted, with its types."""

    times: npt.NDArray[np.float64]
    types: npt.NDArray[np.uint8]

    def __repr__(self) -> str:
        counts = np.bincount(self.types).tolist() if self.types.size else []
        return f"Simulation(n={self.times.size}, types={counts})"


def simulate_thinning(
    mu: Any,
    alpha: Any,
    beta: Any,
    T: float,
    M: int,
    rng: np.random.Generator,
    *,
    shared_decay: bool = False,
) -> Simulation:
    """Simulate on ``[0, T)`` with a seed drawn from ``rng``.

    ``shared_decay`` broadcasts the length-``M`` decay vector over the targets.
    """
    beta_arr = np.asarray(beta, dtype=np.float64)
    if shared_decay:
        beta_arr = np.broadcast_to(beta_arr[None, :], (M, M))
    seed = int(rng.integers(0, 2**63))
    times, types = simulate(mu, alpha, beta_arr, T, method="thinning", seed=seed)
    return Simulation(times, types)
