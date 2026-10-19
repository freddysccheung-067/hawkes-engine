"""Events per second of the two simulators.

For each M in {2, 4, 8} and rho in {0.5, 0.9}, T is chosen from the stationary
mean to give about 1e6 events. Timings are the median of three runs after one
warm-up. Results are written to ``benchmarks/results/simulate_<date>.csv`` with
the machine description in the leading comment lines. Nothing here is a claim
about other hardware.
"""

from __future__ import annotations

import csv
import datetime
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import hawkes_engine  # noqa: E402
from hawkes_engine import _core  # noqa: E402

TARGET_EVENTS = 1_000_000


def params(M: int, rho: float):
    rng = np.random.default_rng(M)
    beta = rng.uniform(0.8, 2.0, (M, M))
    mu = rng.uniform(0.3, 0.7, M)
    gamma = rng.uniform(0.3, 1.0, (M, M))
    alpha = gamma * beta
    alpha *= rho / _core.spectral_radius(mu, alpha, beta)
    return mu, alpha, beta


def main() -> None:
    rows = []
    for M in (2, 4, 8):
        for rho in (0.5, 0.9):
            mu, alpha, beta = params(M, rho)
            rate = float(_core.stationary_mean(mu, alpha, beta).sum())
            T = TARGET_EVENTS / rate
            for method in ("thinning", "cluster"):
                hawkes_engine.simulate(mu, alpha, beta, T / 50, method=method, seed=0)
                times, n = [], 0
                for rep in range(3):
                    t0 = time.perf_counter()
                    t, _ = hawkes_engine.simulate(mu, alpha, beta, T, method=method, seed=rep)
                    times.append(time.perf_counter() - t0)
                    n = t.size
                sec = statistics.median(times)
                rows.append((method, M, rho, round(T, 1), n, round(sec, 4), round(n / sec)))
                print(f"{method:9s} M={M} rho={rho}: {n} events, {sec:.3f}s, {n / sec:,.0f}/s")

    out = Path(__file__).parent / "results" / f"simulate_{datetime.date.today():%Y-%m-%d}.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# machine: {platform.platform()}; {platform.processor()}\n")
        f.write(f"# python {platform.python_version()}, numpy {np.__version__}, ")
        f.write(f"core {_core.build_info()}\n")
        w = csv.writer(f)
        w.writerow(["method", "M", "rho", "T", "events", "seconds", "events_per_second"])
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
