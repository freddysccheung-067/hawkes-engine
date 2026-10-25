"""Parametric bootstrap standard errors for the fit driver.

Simulate from the fitted model, refit, repeat. The spread of the refits is an
estimate of the sampling distribution that makes no asymptotic approximation,
which is exactly what is wanted on a ridge where the Hessian-based SE is the
thing under suspicion.

Two decisions worth naming:

**Processes, not threads.** Every worker spends its life inside the compiled
core, which releases the GIL around the event loop but re-acquires it at the
boundary; the Python wrapper around each evaluation is enough to serialize
threads in practice. A process pool has no such contention.

**Seed streams, not a shared generator.** Each replication gets its own seed,
derived from the caller's seed and the replication index by a SplitMix-style
mixer. Drawing seeds from one shared generator would make the result depend on
the order in which workers happened to start, which is not reproducible.

That second decision is what makes the pool survivable. Because a replication's
draw depends on its index alone, a pool that dies part-way can be replaced by
running the same jobs in this process, and the answer is the draws the pool
would have produced had it finished. ``_serial`` is that replacement, and
``parametric_bootstrap`` falls back to it rather than losing the fit to a
worker that was killed. A pool that dies *and* leaves the serial pass with
nothing is still an error, because that is what a missing
``if __name__ == "__main__":`` guard looks like and the guard is the fix.

The default replication count is small on purpose: 200 is enough for a
percentile interval to be stable to about a percent of the interval width, and
a bootstrap that costs an hour is a bootstrap nobody runs.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

import numpy as np

from hawkes_engine._layout import Layout
from hawkes_engine._typing import FloatArray

__all__ = ["BootstrapResult", "parametric_bootstrap"]

_GOLDEN_INT = 0x9E3779B97F4A7C15
_MASK_INT = 0xFFFFFFFFFFFFFFFF


@dataclass(frozen=True)
class BootstrapResult:
    """Standard errors from the refit distribution, and the raw draws."""

    se: dict[str, FloatArray] | None
    cov_log: FloatArray | None
    draws: FloatArray
    notes: tuple[str, ...]


def _child_seed(seed: int | None, index: int) -> int:
    """A seed that depends only on the caller's seed and the replication index.

    The mixing is SplitMix64's finaliser, written in Python integers rather than
    ``np.uint64``. The multiplications are meant to wrap at 64 bits, and NumPy
    says so with an overflow warning on every call; masking an arbitrary-precision
    integer gives the same result silently and exactly.
    """
    mask = _MASK_INT
    z = ((0 if seed is None else seed) ^ (index + 1)) & mask
    z = (z + _GOLDEN_INT) & mask
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
    return (z ^ (z >> 31)) & mask


def _one(args: tuple) -> np.ndarray | None:
    """Simulate once and refit. Returns the log-space free vector, or ``None``."""
    (seed, times, types, T, M, shared, mu, alpha, beta, zero_diagonal) = args
    from hawkes_engine._simulate import simulate_thinning
    from hawkes_engine.fit import fit

    rng = np.random.default_rng(seed)
    sim = simulate_thinning(mu, alpha, beta, T, M, rng, shared_decay=shared)
    if sim.times.size == 0:
        return None
    try:
        refit = fit(
            sim.times,
            sim.types,
            T=T,
            M=M,
            shared_decay=shared,
            zero_diagonal=zero_diagonal,
            seed=int(rng.integers(0, 2**31 - 1)),
            se_method=None,
        )
    except ValueError:
        return None
    if refit.theta is None or not np.all(np.isfinite(refit.theta)):
        return None
    return np.asarray(refit.theta, dtype=np.float64)


def _serial(jobs: list[tuple]) -> list[np.ndarray]:
    """Run every job in this process, in submission order.

    The replacement for a pool that died. It produces the same draws as a pool
    that had finished because ``_one`` takes its seed from ``_child_seed`` and
    its arguments, never from a shared generator or from the order workers
    started, so replication ``i`` depends only on ``i``.
    """
    out: list[np.ndarray] = []
    for job in jobs:
        draw = _one(job)
        if draw is not None:
            out.append(draw)
    return out


def parametric_bootstrap(
    times: FloatArray,
    types: np.ndarray,
    T: float,
    M: int,
    shared_decay: bool,
    mu: FloatArray,
    alpha: FloatArray,
    beta: FloatArray,
    layout: Layout,
    *,
    n_bootstrap: int = 200,
    seed: int | None = None,
    zero_diagonal: bool = False,
    workers: int | None = None,
) -> BootstrapResult:
    """Refit on ``n_bootstrap`` simulations from the fitted model."""
    from hawkes_engine.hessian import natural_standard_errors

    jobs = [
        (
            _child_seed(seed, i),
            times,
            types,
            T,
            M,
            shared_decay,
            mu,
            alpha,
            beta,
            zero_diagonal,
        )
        for i in range(n_bootstrap)
    ]
    draws = []
    pool_note = ""
    if workers == 1:
        # A single worker does not want a pool. `ProcessPoolExecutor(1)` would
        # still spawn one process per replication and pay an interpreter import
        # every time, which on Windows is most of the cost: measured at about
        # 0.4 s per replication of pure start-up, against 0.05 s of work. Running
        # in this process is the same computation with none of that, and the
        # caller who asked for one worker has already decided not to use the
        # machine's cores.
        draws = _serial(jobs)
    else:
        try:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for out in pool.map(_one, jobs):
                    if out is not None:
                        draws.append(out)
        except BrokenProcessPool as exc:
            # Where workers are spawned (Windows, macOS) a script with no
            # `if __name__ == "__main__":` guard re-runs itself in every worker, and
            # the pool dies with this error and no hint of why. It is not the only
            # cause (a worker killed for memory gives the same error), and a high
            # worker count on a large event stream can trigger it with a guard
            # present: the pool is not reliable enough to be the only route.
            #
            # The two cases are told apart by how far the pool got. A missing guard
            # kills every worker on import, so it dies before one job completes; a
            # worker killed under load dies after the pool has been working.
            # Measured at this size: 0 completions unguarded, 12 when the load race
            # fired. So a pool that produced anything is retried here — the seed
            # streams make the draws identical — and a pool that produced nothing
            # keeps the error, because there the guard is the fix and this message
            # is the only thing that says so.
            if not draws:
                raise RuntimeError(
                    "the bootstrap worker pool died. If this script has no "
                    '`if __name__ == "__main__":` guard, add one: on Windows and macOS '
                    "each worker re-imports the main module. "
                    "Otherwise a worker was killed, for example for lack of memory; "
                    "try fewer replications (n_bootstrap) or se_method='hessian'."
                ) from exc
            completed = len(draws)
            serial = _serial(jobs)
            if not serial:
                raise RuntimeError(
                    "the bootstrap worker pool died after "
                    f"{completed} of {len(jobs)} replications, and re-running the "
                    "remaining work in this process produced no usable refit; no "
                    "bootstrap standard errors are reported. If this script has no "
                    '`if __name__ == "__main__":` guard, add one.'
                ) from exc
            draws = serial
            pool_note = (
                f"the bootstrap worker pool died ({type(exc).__name__}) after "
                f"{completed} of {len(jobs)} replications; the work was recomputed "
                f"serially in the calling process, which gives the same draws "
                f"because each replication's seed comes from its index, at a wall "
                f"time that is not the same"
            )

    notes: list[str] = []
    if pool_note:
        notes.append(pool_note)
    if len(draws) < max(10, n_bootstrap // 2):
        notes.append(
            f"only {len(draws)} of {n_bootstrap} bootstrap replications produced a "
            f"usable refit; no bootstrap standard errors are reported"
        )
        return BootstrapResult(None, None, np.empty((0, layout.n_params)), tuple(notes))

    matrix = np.vstack(draws)
    cov_log = np.cov(matrix, rowvar=False, ddof=1)
    if cov_log.ndim == 0:  # pragma: no cover - a single-parameter model
        cov_log = np.asarray([[float(cov_log)]])
    se = natural_standard_errors(cov_log, np.exp(np.mean(matrix, axis=0)), layout)
    notes.append(
        f"bootstrap standard errors from {len(draws)} of {n_bootstrap} replications; "
        f"they estimate the sampling spread of the refits, not the width of a "
        f"percentile interval"
    )
    return BootstrapResult(se, cov_log, matrix, tuple(notes))
