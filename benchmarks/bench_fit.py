"""Benchmark the fit driver end to end.

Writes one CSV per day to ``benchmarks/results/fit_<date>.csv`` with the machine
recorded in the file, so a later run can be compared against this one rather
than argued with. It times a complete ``fit`` call, which includes the optimizer,
the Hessian pass and the reliability report, and it reports iterations and the
time per iteration because the two move separately: the per-iteration cost is
what the compiled likelihood controls, and the iteration count is what the
optimizer and the starting point control.

No claim in the README is derived from these numbers.

Usage:
    python benchmarks/bench_fit.py [--sizes 100000,1000000] [--dims 2,4]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hawkes_engine  # noqa: E402

from tests._simulate_reference import simulate_thinning  # noqa: E402

RESULTS = ROOT / "benchmarks" / "results"


def _problem(rng: np.random.Generator, m: int, n: int):
    """A subcritical parameter set whose stationary rate is about one per unit."""
    mu = np.full(m, 0.5 / m * 1.5)
    off = rng.uniform(0.03, 0.06, (m, m))
    alpha = 0.35 * np.eye(m) + off
    beta = rng.uniform(1.0, 1.4, (m, m))
    # Stabilise: rescale the excitation so the spectral radius is 0.3.
    gamma = alpha / beta
    alpha *= 0.3 / float(np.max(np.abs(np.linalg.eigvals(gamma))))
    T = float(n) / float((np.linalg.solve(np.eye(m) - alpha / beta, mu)).sum())
    return mu, alpha, beta, T


def _machine() -> str:
    return (
        f"{platform.system()} {platform.release()}, {platform.machine()}, "
        f"Python {platform.python_version()}, NumPy {np.__version__}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="100000,1000000")
    parser.add_argument("--dims", default="2,4")
    args = parser.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]
    dims = [int(d) for d in args.dims.split(",")]

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"fit_{dt.date.today().isoformat()}.csv"
    new_file = not path.exists()

    with path.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(
                [
                    "implementation",
                    "kernel",
                    "M",
                    "n_events",
                    "nit",
                    "wall_s",
                    "s_per_iteration",
                    "loglik",
                    "rho",
                    "reliable",
                    "machine",
                ]
            )
        print(f"machine: {_machine()}")
        for m in dims:
            for n in sizes:
                rng = np.random.default_rng(0)
                mu, alpha, beta, T = _problem(rng, m, n)
                sim = simulate_thinning(mu, alpha, beta, T, m, np.random.default_rng(1))
                start = time.perf_counter()
                result = hawkes_engine.fit(sim.times, sim.types, T=T, M=m, seed=0)
                wall = time.perf_counter() - start
                nit = max(result.nit, 1)
                writer.writerow(
                    [
                        "hawkes-engine",
                        "pair",
                        m,
                        int(sim.times.size),
                        result.nit,
                        f"{wall:.4f}",
                        f"{wall / nit:.6f}",
                        f"{result.loglik:.6f}",
                        f"{result.rho:.6f}",
                        result.reliable,
                        _machine(),
                    ]
                )
                print(
                    f"M={m} N={sim.times.size} nit={result.nit} wall={wall:.2f}s "
                    f"{wall / nit * 1000:.1f} ms/iter loglik={result.loglik:.3g} "
                    f"rho={result.rho:.3f} {result.reliable}"
                )
    print(f"\nappended to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
