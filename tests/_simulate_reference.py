"""Test-only reference simulators in NumPy. Not part of the package.

The third, independent implementation. The C++ thinning and cluster simulators
(H4) are checked against these, in the same way ``oracle/hawkes_oracle.py``
checks the likelihood. The fit tests also draw their ground truth from here, so
that they do not depend on the code whose agreement is under test.

Both algorithms are written out in full and share nothing with the package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class Simulation:
    times: npt.NDArray[np.float64]
    types: npt.NDArray[np.uint8]


__all__ = ["Simulation", "simulate_thinning", "simulate_cluster", "stationary_mean"]


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
    """Ogata's modified thinning, per mathematics.md section 6.

    State is ``S_ij(t) = sum_{t^j_m < t} exp(-beta_ij (t - t^j_m))``, advanced by
    the one-step recursion of section 4, so the cost is O(N M^2) rather than the
    O(N^2 M^2) of re-summing at every probe.

    The bound is the total intensity immediately after the last accepted event.
    That is valid because the intensity only decays between events: an
    excitation is added all at once and then decays. On a rejection the clock
    advances to the probe and the bound is reset to the current total, which is
    again an upper bound for the same reason.
    """
    mu_arr = np.asarray(mu, dtype=np.float64)
    alpha_arr = np.asarray(alpha, dtype=np.float64)
    beta_arr = np.asarray(beta, dtype=np.float64)
    if shared_decay:
        beta_arr = np.broadcast_to(beta_arr[None, :], (M, M))

    times: list[float] = []
    types: list[int] = []
    S = np.zeros((M, M))
    clock = 0.0
    bound = float(mu_arr.sum())
    while bound > 0.0:
        t_next = clock + float(rng.exponential(1.0 / bound))
        S *= np.exp(-beta_arr * (t_next - clock))
        clock = t_next
        if t_next >= T:
            break
        lam = mu_arr + (alpha_arr * S).sum(axis=1)
        total = float(lam.sum())
        if rng.random() * bound <= total:
            kind = int(rng.choice(M, p=lam / total))
            times.append(t_next)
            types.append(kind)
            S[:, kind] += 1.0
            # Immediately after the jump the total is the accepted rate plus
            # this event's contribution, which is the next valid bound.
            bound = total + float(alpha_arr[:, kind].sum())
        else:
            bound = total
    return Simulation(np.asarray(times, dtype=np.float64), np.asarray(types, dtype=np.uint8))


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
