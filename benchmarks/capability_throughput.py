"""Phase 3 of H7: the throughput rows the committed CSVs do not cover.

Covered already (``loglik_2026-10-19.csv``, ``simulate_2026-10-19.csv``) and not
repeated here: likelihood at M in {2, 4, 8}, simulators at M in {2, 4, 8} for
rho in {0.5, 0.9}. Added:

  * likelihood at M = 6, pair and shared, value and gradient, N in {1e5, 1e6},
    plus the pair/shared ratio at every M from the two files combined by
    ``capability_report.py``;
  * both simulators at M in {2, 4, 6, 8} for rho = 0.85, about 1e6 events.

Timings are the median of five runs after one warm-up, with the minimum and
maximum recorded. Writes ``benchmarks/results/throughput_<date>.csv``.
"""

from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hawkes_engine  # noqa: E402
from hawkes_engine import _core  # noqa: E402

from benchmarks._common import RESULTS, machine_lines, problem, today  # noqa: E402

REPEATS = 5


def _time(fn) -> tuple[float, float, float]:
    fn()
    s = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        fn()
        s.append(time.perf_counter() - t0)
    return statistics.median(s), min(s), max(s)


def _loglik_calls(times, types, mu, alpha, beta, bs, T):
    """The four likelihood calls for one problem, bound to its arrays."""
    return {
        ("pair", "value"): lambda: hawkes_engine.loglik(times, types, mu, alpha, beta, T),
        ("pair", "value+grad"): lambda: hawkes_engine.loglik(
            times, types, mu, alpha, beta, T, grad=True
        ),
        ("shared", "value"): lambda: hawkes_engine.loglik(
            times, types, mu, alpha, bs, T, shared_decay=True
        ),
        ("shared", "value+grad"): lambda: hawkes_engine.loglik(
            times, types, mu, alpha, bs, T, grad=True, shared_decay=True
        ),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"throughput_{today()}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in machine_lines():
            fh.write(line + "\n")
        fh.write(f"# median of {REPEATS} after one warm-up\n")
        w = csv.writer(fh)
        w.writerow(
            [
                "what",
                "kernel_or_method",
                "M",
                "rho",
                "N",
                "median_s",
                "min_s",
                "max_s",
                "ns_per_event",
            ]
        )

        # Likelihood at M = 6. Same generator as bench_loglik.py.
        for n in (100_000, 1_000_000):
            m = 6
            rng = np.random.default_rng(m * 1000 + n % 1000)
            mu = rng.uniform(0.2, 1.0, m)
            alpha = rng.uniform(0.0, 0.2 / m, (m, m))
            beta = rng.uniform(0.8, 2.0, (m, m))
            times = np.sort(rng.uniform(0.0, float(n), n))
            types = rng.integers(0, m, n).astype(np.uint8)
            T = float(times[-1] + 1.0)
            bs = beta[0].copy()
            calls = _loglik_calls(times, types, mu, alpha, beta, bs, T)
            for (kernel, work), fn in calls.items():
                med, lo, hi = _time(fn)
                w.writerow(
                    [
                        f"loglik_{work}",
                        kernel,
                        m,
                        "",
                        n,
                        f"{med:.6g}",
                        f"{lo:.6g}",
                        f"{hi:.6g}",
                        f"{med / n * 1e9:.2f}",
                    ]
                )
                print(f"loglik {kernel:6s} {work:10s} M={m} N={n:>9,d} {med:.4f}s", flush=True)

        # Simulators at rho = 0.85.
        for m in (2, 4, 6, 8):
            mu, alpha, beta = problem(m, 0.85)
            rate = float(_core.stationary_mean(mu, alpha, beta).sum())
            T = 1_000_000 / rate
            for method in ("thinning", "cluster"):
                holder = {}

                def run(method=method, mu=mu, alpha=alpha, beta=beta, T=T, holder=holder):
                    t, _ = hawkes_engine.simulate(mu, alpha, beta, T, method=method, seed=0)
                    holder["n"] = t.size

                med, lo, hi = _time(run)
                n = holder["n"]
                w.writerow(
                    [
                        "simulate",
                        method,
                        m,
                        0.85,
                        n,
                        f"{med:.6g}",
                        f"{lo:.6g}",
                        f"{hi:.6g}",
                        f"{med / n * 1e9:.2f}",
                    ]
                )
                print(
                    f"simulate {method:8s} M={m} rho=0.85 N={n:>9,d} {n / med:,.0f}/s", flush=True
                )
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
