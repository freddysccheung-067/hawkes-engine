"""One measurement in a fresh process. Not run directly; see capability_*.py.

Modes
-----
load      import, load the cached events, stop. Peak = imports + event arrays.
opt       fit(se_method=None): the optimiser alone.
hessian   fit(se_method="hessian"): optimiser plus the Hessian pass.
boot      the bootstrap replications run in-process, one worker's share.
wall      fit(se_method="hessian") timed, then the Hessian pass timed on its own.

Every mode prints one JSON line. ``base_peak`` is the peak working set after the
imports and before any data is touched; the memory figures are deltas against it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hawkes_engine  # noqa: E402
import numpy as np  # noqa: E402

from benchmarks._common import peak_working_set_self  # noqa: E402


def _hessian_pass(result, times, types, T, M):
    """Time the Hessian pass alone at the fitted point, counting gradient calls."""
    from hawkes_engine._layout import Layout
    from hawkes_engine.fit import _Problem
    from hawkes_engine.hessian import observed_information

    layout = Layout(M=M)
    problem = _Problem(times, types, T, layout)
    x = layout.pack_natural(result.mu, result.alpha, result.beta)
    calls = 0

    def counted(v):
        nonlocal calls
        calls += 1
        return problem.gradient_natural(v)

    t0 = time.perf_counter()
    observed_information(counted, x, positive=np.ones(layout.n_params, dtype=bool))
    return time.perf_counter() - t0, calls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["load", "opt", "hessian", "boot", "wall"])
    ap.add_argument("data")
    ap.add_argument("--M", type=int, required=True)
    ap.add_argument("--B", type=int, default=0, help="replications for mode boot")
    ap.add_argument("--shared", action="store_true")
    args = ap.parse_args()

    base_peak = peak_working_set_self()
    d = np.load(args.data)
    times, types, T = d["times"], d["types"], float(d["T"])
    M = args.M
    out: dict = {"mode": args.mode, "M": M, "n_events": int(times.size), "base_peak": base_peak}

    if args.mode == "load":
        out["wall_s"] = 0.0
    elif args.mode in ("opt", "hessian"):
        t0 = time.perf_counter()
        r = hawkes_engine.fit(
            times,
            types,
            T=T,
            M=M,
            shared_decay=args.shared,
            seed=0,
            se_method=None if args.mode == "opt" else "hessian",
        )
        out.update(wall_s=time.perf_counter() - t0, nit=r.nit, rho=r.rho)
    elif args.mode == "wall":
        t0 = time.perf_counter()
        r = hawkes_engine.fit(times, types, T=T, M=M, shared_decay=args.shared, seed=0)
        total = time.perf_counter() - t0
        t_h, calls = _hessian_pass(r, times, types, T, M)
        out.update(
            wall_s=total,
            hessian_s=t_h,
            hessian_grad_calls=calls,
            nit=r.nit,
            rho=r.rho,
            converged=bool(r.converged),
            reliable=str(r.reliable),
        )
    else:
        from hawkes_engine._boot import _child_seed, _one

        r = hawkes_engine.fit(times, types, T=T, M=M, seed=0, se_method=None)
        peak_fit = peak_working_set_self()
        t0 = time.perf_counter()
        ok = 0
        for i in range(args.B):
            job = (
                _child_seed(0, i),
                times,
                types,
                T,
                M,
                False,
                r.mu,
                r.alpha,
                r.beta,
                False,
            )
            ok += _one(job) is not None
        out.update(wall_s=time.perf_counter() - t0, usable=ok, peak_after_fit=peak_fit)

    out["peak"] = peak_working_set_self()
    print("RESULT " + json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
