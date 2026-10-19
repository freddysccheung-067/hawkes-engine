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
from hawkes_engine._arrays import as_real_1d, as_real_2d, flat

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


def _params(
    mu: npt.ArrayLike, alpha: npt.ArrayLike, beta: npt.ArrayLike
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """The three parameter arrays, flattened to the layout the core reads."""
    mu_a = as_real_1d(mu, "mu")
    alpha_a = as_real_2d(alpha, "alpha")
    beta_a = as_real_2d(beta, "beta")
    if alpha_a.shape != beta_a.shape:
        raise ValueError(f"alpha has shape {alpha_a.shape}, beta has shape {beta_a.shape}")
    m = mu_a.shape[0]
    if alpha_a.shape != (m, m):
        raise ValueError(f"alpha must have shape ({m}, {m}), got {alpha_a.shape}")
    return mu_a, flat(alpha_a), flat(beta_a)


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
    mu_a, alpha_a, beta_a = _params(mu, alpha, beta)
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

    The parameters are converted once and the flattened arrays are reused for
    every path, so the per-path cost is the simulation and not the argument
    marshalling.
    """
    if n_paths < 0:
        raise ValueError(f"n_paths must be non-negative, got {n_paths}")
    if method not in ("thinning", "cluster"):
        raise ValueError(f"method must be 'thinning' or 'cluster', got {method!r}")
    base = _seed(seed)
    mu_a, alpha_a, beta_a = _params(mu, alpha, beta)
    T_value, t0_value = float(T), float(t0)
    return [
        _core.simulate(
            mu_a,
            alpha_a,
            beta_a,
            T_value,
            method,
            _core.seed_stream(base, k),
            t0_value,
            float(burn_in),
        )
        for k in range(n_paths)
    ]
