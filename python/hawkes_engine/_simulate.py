"""Ogata thinning, used by the parametric bootstrap.

This lives in the package because the bootstrap is a public feature and a
public feature cannot import from the test tree: a wheel installed from PyPI has
no ``tests`` directory, and ``se_method="bootstrap"`` would fail on every
machine that is not this checkout.

It is not exported from :mod:`hawkes_engine`. The test-only reference simulator
in ``tests/_simulate_reference.py`` carries an independently written cluster
simulator and must keep agreeing with this one; H4's C++ simulators must agree
with both. Sharing one implementation between the product and the *thinning*
half of the reference is deliberate: the reference's value is that its two
simulators use no machinery in common, and duplicating this loop would create a
second copy of the same bug rather than a second opinion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

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
