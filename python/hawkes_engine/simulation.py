"""Exact simulation of the multivariate exponential Hawkes process.

Two algorithms, written independently in C++ and sharing only the random
number generator and argument validation: Ogata's modified thinning and the
branching (cluster) representation. They sample the same law, and the test
suite checks that they do.

Seeds are explicit and results are reproducible across platforms for the same
seed. They do **not** match ``numpy.random``: the generator is PCG64 seeded
through SplitMix64 (ADR-005), and a NumPy generator with the same seed gives a
different stream.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import numpy.typing as npt

from hawkes_engine import _core

__all__ = ["simulate", "simulate_many"]

Method = Literal["thinning", "cluster"]
Path = tuple[npt.NDArray[np.float64], npt.NDArray[np.uint8]]

_MAX_SEED = 2**64


def _seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int | np.integer):
        raise TypeError(f"seed must be an int, got {type(seed).__name__}")
    seed = int(seed)
    if not 0 <= seed < _MAX_SEED:
        raise ValueError(f"seed must be in [0, 2**64), got {seed}")
    return seed


def simulate(
    mu: npt.ArrayLike,
    alpha: npt.ArrayLike,
    beta: npt.ArrayLike,
    T: float,
    *,
    method: Method = "thinning",
    seed: int,
    burn_in: float = 0.0,
    t0: float = 0.0,
) -> Path:
    """Simulate events on ``[t0, T)``; return ``(times, types)``.

    ``alpha`` and ``beta`` are ``M x M`` with row = target and column = source.
    ``times`` is sorted and ``types`` holds the type index of each event as
    ``uint8``. Equal times across types are possible only when the process
    produces them.

    ``burn_in = 0`` starts from an empty history, so the intensity early in the
    window is below its stationary level. A positive ``burn_in`` runs the process
    from ``t0 - burn_in`` and discards the events before ``t0``, which
    approximates a stationary start.

    Raises ``ValueError`` when the spectral radius of ``alpha / beta`` is 1 or
    more (the message states it), or for a malformed window.
    """
    mu_a = np.ascontiguousarray(mu, dtype=np.float64)
    alpha_a = np.ascontiguousarray(alpha, dtype=np.float64)
    beta_a = np.ascontiguousarray(beta, dtype=np.float64)
    if method not in ("thinning", "cluster"):
        raise ValueError(f"method must be 'thinning' or 'cluster', got {method!r}")
    return _core.simulate(
        mu_a, alpha_a, beta_a, float(T), method, _seed(seed), float(t0), float(burn_in)
    )


def simulate_many(
    mu: npt.ArrayLike,
    alpha: npt.ArrayLike,
    beta: npt.ArrayLike,
    T: float,
    *,
    n_paths: int,
    method: Method = "thinning",
    seed: int,
    burn_in: float = 0.0,
    t0: float = 0.0,
) -> list[Path]:
    """Simulate ``n_paths`` independent paths.

    Path ``k`` uses the seed ``seed_stream(seed, k)``, so the paths are
    independent streams of one generator family and the result is a function of
    ``(seed, k)`` alone. It does not depend on how many threads the caller uses,
    because the paths are produced serially here and any caller that splits the
    index range across threads draws the same per-path seeds.
    """
    if n_paths < 0:
        raise ValueError(f"n_paths must be non-negative, got {n_paths}")
    base = _seed(seed)
    return [
        simulate(
            mu,
            alpha,
            beta,
            T,
            method=method,
            seed=_core.seed_stream(base, k),
            burn_in=burn_in,
            t0=t0,
        )
        for k in range(n_paths)
    ]
