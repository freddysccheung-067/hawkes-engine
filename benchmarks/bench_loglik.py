"""Benchmark the likelihood core.

Writes raw timings and the machine they were taken on to
``benchmarks/results/loglik_<date>.csv``. Nothing here is a claim about how the
library compares to another one: these numbers describe one build on one
machine, and they exist so that later changes can be measured against this
baseline rather than argued about.

The reference implementation is O(N^2 M^2), so it is timed only at small N.
Timing it at 1e6 would take days and say nothing useful.

Usage:
    python benchmarks/bench_loglik.py [--sizes 1e5,1e6] [--dims 2,4,8]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "oracle"))

import hawkes_engine  # noqa: E402

RESULTS = ROOT / "benchmarks" / "results"


def _problem(rng, m: int, n: int):
    mu = rng.uniform(0.2, 1.0, m)
    alpha = rng.uniform(0.0, 0.2 / max(m, 1), (m, m))
    beta = rng.uniform(0.8, 2.0, (m, m))
    times = np.sort(rng.uniform(0.0, float(n), n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = float(times[-1] + 1.0)
    return times, types, mu, alpha, beta, T


def _time_call(fn, repeats: int) -> tuple[float, float]:
    """Return (best, median) seconds over `repeats` calls."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return min(samples), statistics.median(samples)


def _rows():
    return [
        ("hawkes-engine", "pair", "value"),
        ("hawkes-engine", "pair", "value+grad"),
        ("hawkes-engine", "shared", "value"),
        ("hawkes-engine", "shared", "value+grad"),
        ("oracle", "naive", "value"),
        ("oracle", "naive", "value+grad"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="100000,1000000")
    parser.add_argument("--dims", default="2,4,8")
    parser.add_argument("--oracle-max-n", type=int, default=2000)
    parser.add_argument(
        "--oracle-sizes",
        default="200,1000,2000",
        help="sizes at which the O(N^2 M^2) reference is also timed",
    )
    args = parser.parse_args()

    sizes = [int(float(s)) for s in args.sizes.split(",")]
    dims = [int(d) for d in args.dims.split(",")]

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = RESULTS / f"loglik_{stamp}.csv"

    info = hawkes_engine.build_info()
    machine = {
        "date": stamp,
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "compiler": f"{info['compiler']} {info['compiler_version']}",
        "cxx_standard": info["cxx_standard"],
    }

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["implementation", "kernel", "work", "M", "N", "best_s", "median_s", "ns_per_event"]
        )

        for m in dims:
            for n in sizes:
                rng = np.random.default_rng(hash((m, n)) & 0xFFFFFFFF)
                times, types, mu, alpha, beta, T = _problem(rng, m, n)
                beta_shared = beta[0].copy()

                repeats = 3 if n <= 1_000_000 else 5
                calls = {
                    ("hawkes-engine", "pair", "value"): lambda t=times,
                    ty=types,
                    m_=mu,
                    a=alpha,
                    b=beta,
                    h=T: hawkes_engine.loglik(t, ty, m_, a, b, h),
                    ("hawkes-engine", "pair", "value+grad"): lambda t=times,
                    ty=types,
                    m_=mu,
                    a=alpha,
                    b=beta,
                    h=T: hawkes_engine.loglik(t, ty, m_, a, b, h, grad=True),
                    ("hawkes-engine", "shared", "value"): lambda t=times,
                    ty=types,
                    m_=mu,
                    a=alpha,
                    b=beta_shared,
                    h=T: hawkes_engine.loglik(t, ty, m_, a, b, h, shared_decay=True),
                    ("hawkes-engine", "shared", "value+grad"): lambda t=times,
                    ty=types,
                    m_=mu,
                    a=alpha,
                    b=beta_shared,
                    h=T: hawkes_engine.loglik(t, ty, m_, a, b, h, grad=True, shared_decay=True),
                }

                for (impl, kernel, work), call in calls.items():
                    best, median = _time_call(call, repeats)
                    writer.writerow(
                        [
                            impl,
                            kernel,
                            work,
                            m,
                            n,
                            f"{best:.6g}",
                            f"{median:.6g}",
                            f"{median / n * 1e9:.3f}",
                        ]
                    )
                    print(
                        f"{impl:14s} {kernel:7s} {work:11s} M={m} N={n:>9,d} "
                        f"best={best:.4f}s median={median:.4f}s"
                    )

        # The reference is quadratic, so it gets its own small grid rather than
        # a row in the large-N table where it would be skipped every time.
        from hawkes_oracle import grad_oracle, loglik_oracle

        for m in dims:
            for n in [int(s) for s in args.oracle_sizes.split(",") if s]:
                if n > args.oracle_max_n:
                    print(f"oracle         skipped   N={n:,d} exceeds --oracle-max-n")
                    continue
                rng = np.random.default_rng(hash((m, n, "oracle")) & 0xFFFFFFFF)
                times, types, mu, alpha, beta, T = _problem(rng, m, n)
                # Bind the arrays into the defaults rather than closing over the
                # loop variables: a closure would read whatever the last
                # iteration left behind if the timing loop ever outlived it.
                for work, call in (
                    (
                        "value",
                        lambda t=times, ty=types, m_=mu, a=alpha, b=beta, h=T: (
                            loglik_oracle(t, ty, m_, a, b, h)
                        ),
                    ),
                    (
                        "value+grad",
                        lambda t=times, ty=types, m_=mu, a=alpha, b=beta, h=T: (
                            grad_oracle(t, ty, m_, a, b, h)
                        ),
                    ),
                ):
                    best, median = _time_call(call, 1)
                    writer.writerow(
                        [
                            "oracle",
                            "naive",
                            work,
                            m,
                            n,
                            f"{best:.6g}",
                            f"{median:.6g}",
                            f"{median / n * 1e9:.3f}",
                        ]
                    )
                    print(
                        f"{'oracle':14s} {'naive':7s} {work:11s} M={m} N={n:>9,d} "
                        f"best={best:.4f}s median={median:.4f}s"
                    )

        writer.writerow([])
        writer.writerow(["# machine"])
        for key, value in machine.items():
            writer.writerow([f"# {key}", value])

    print(f"\nmachine: {machine}")
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
