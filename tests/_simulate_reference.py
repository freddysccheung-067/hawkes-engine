"""Test-only reference simulator. Not part of the package, not exported.

This is scaffolding for the H3 fit tests and nothing else. It exists so that a
recovery test has ground truth to recover from.

The **cluster** simulator below is the independent one and is the reason this
file exists: it draws a branching tree and sorts it, using none of the thinning
machinery, so a defect in either representation is unlikely to be reproduced by
the other. ``simulate_thinning`` delegates to ``hawkes_engine._simulate``
because the parametric bootstrap needs a simulator inside the installed
package, and two copies of the same loop would be one opinion, not two.

H4's C++ thinning and cluster simulators must agree with this file and with
``hawkes_engine._simulate``. When they arrive, that agreement is the check that
the fast implementations are right, in the same way
``oracle/hawkes_oracle.py`` checks the likelihood.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from hawkes_engine._simulate import Simulation, simulate_thinning

__all__ = ["Simulation", "simulate_thinning", "simulate_cluster", "stationary_mean"]


def _beta_block(beta: Any, M: int, shared_decay: bool) -> npt.NDArray[np.float64]:
    arr = np.asarray(beta, dtype=np.float64)
    if shared_decay:
        return np.broadcast_to(arr[None, :], (M, M))
    return arr


def simulate_cluster(
    mu: Any,
    alpha: Any,
    beta: Any,
    T: float,
    M: int,
    rng: np.random.Generator,
    *,
    shared_decay: bool = False,
    burn_in: float = 0.0,
) -> Simulation:
    """The branching representation, per mathematics.md section 6.

    Immigrants arrive as a Poisson process of rate ``mu_i``; every event of type
    ``j`` independently produces ``Poisson(Gamma_ij)`` type-``i`` children, each
    delayed by ``Exp(beta_ij)``. Recursing to exhaustion and then dropping
    everything after ``T`` is correct but undercounts the start of the window,
    because clusters that began before zero are missing; ``burn_in`` starts the
    immigrant process early and discards the early events, which is the
    approximation the spec names.
    """
    mu = np.asarray(mu, dtype=np.float64)
    alpha = np.asarray(alpha, dtype=np.float64)
    beta = _beta_block(beta, M, shared_decay)
    gamma = alpha / beta

    times: list[float] = []
    types: list[int] = []
    for i in range(M):
        if mu[i] <= 0.0:
            continue
        n_imm = int(rng.poisson(mu[i] * (T + burn_in)))
        for start in rng.uniform(-burn_in, T, n_imm):
            stack = [(float(start), i)]
            while stack:
                t, kind = stack.pop()
                if t > T:
                    continue
                if t >= 0.0:
                    times.append(t)
                    types.append(kind)
                for target in range(M):
                    n_children = int(rng.poisson(gamma[target, kind]))
                    if n_children:
                        delays = rng.exponential(1.0 / beta[target, kind], n_children)
                        stack.extend((t + float(d), target) for d in delays)

    order = np.argsort(np.asarray(times, dtype=np.float64), kind="stable")
    return Simulation(
        np.asarray(times, dtype=np.float64)[order],
        np.asarray(types, dtype=np.uint8)[order],
    )


def stationary_mean(mu: Any, alpha: Any, beta: Any) -> npt.NDArray[np.float64]:
    """``(I - Gamma)^{-1} mu``, the mean intensity of the stationary process."""
    mu_arr = np.asarray(mu, dtype=np.float64)
    gamma = np.asarray(alpha, dtype=np.float64) / np.asarray(beta, dtype=np.float64)
    return np.linalg.solve(np.eye(mu_arr.size) - gamma, mu_arr)
