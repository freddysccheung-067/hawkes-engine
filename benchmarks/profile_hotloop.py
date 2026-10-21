"""Phase 5 of H7: where the time goes in the likelihood hot loop.

No native sampling profiler is available on the measurement machine (no
administrator rights for wpr, no Visual Studio profiler), so this is an
attributed measurement, and it names what it is:

1. cProfile of one fit (Python level): how much of the wall time is inside the
   compiled likelihood and how much is Python around it.
2. A scaling decomposition of the compiled call. Pass 1 of ``evaluate`` makes
   M*M ``exp`` calls per event, pass 2 makes M ``expm1``/``exp`` calls per
   event (plus M more for the gradient). Timing value and value+grad across M at
   fixed N, and a scalar ``exp`` reference, gives ns per transcendental.

Pair decay, rho 0.5, N about 1e5. Writes ``benchmarks/results/profile_<date>.txt``.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hawkes_engine  # noqa: E402

from benchmarks._common import RESULTS, machine_lines, problem, simulate_n, today  # noqa: E402


def _median(fn, reps=7):
    fn()
    s = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        s.append(time.perf_counter() - t0)
    return statistics.median(s)


def main() -> int:
    out = io.StringIO()
    out.write("\n".join(machine_lines()) + "\n")
    out.write(
        "# profiler: cProfile (Python level) plus timing decomposition; no native profiler\n\n"
    )

    times, types, T = simulate_n(4, 0.5, 100_000)
    pr = cProfile.Profile()
    pr.enable()
    hawkes_engine.fit(times, types, T=T, M=4, seed=0)
    pr.disable()
    out.write("== cProfile, fit(M=4, N=%d), top 8 by internal time ==\n" % times.size)
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(8)
    out.write(s.getvalue() + "\n")

    out.write("== compiled likelihood, N about 1e5, pair decay ==\n")
    out.write("M  value_ns/ev  grad_ns/ev  value/M^2  grad/M^2   (ns per event per M^2)\n")
    x = np.random.default_rng(0).uniform(0.5, 3.0, 5_000_000)
    exp_ns = _median(lambda: np.exp(-x)) / x.size * 1e9
    for m in (2, 4, 6, 8):
        t, ty, TT = simulate_n(m, 0.5, 100_000)
        mu, a, b = problem(m, 0.5)
        v = (
            _median(
                lambda t=t, ty=ty, mu=mu, a=a, b=b, TT=TT: hawkes_engine.loglik(t, ty, mu, a, b, TT)
            )
            / t.size
            * 1e9
        )
        g = (
            _median(
                lambda t=t, ty=ty, mu=mu, a=a, b=b, TT=TT: hawkes_engine.loglik(
                    t, ty, mu, a, b, TT, grad=True
                )
            )
            / t.size
            * 1e9
        )
        out.write(f"{m}  {v:11.1f}  {g:10.1f}  {v / m**2:9.2f}  {g / m**2:8.2f}\n")
    out.write(f"\nnumpy np.exp throughput on this machine: {exp_ns:.2f} ns per call (vectorised)\n")
    text = out.getvalue()
    path = RESULTS / f"profile_{today()}.txt"
    path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
