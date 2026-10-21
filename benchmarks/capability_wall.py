"""Phase 2 of H7: where the wall is.

Wall-clock grid over M x N x rho, pair decay, one start, ``se_method="hessian"``.
Each cell runs in a fresh child process (``_child.py wall``) so the time is not
helped by warm allocator state, and a cell that exceeds ``--timeout`` is recorded
as a timeout rather than dropped. A cell that finishes in under ``--fast``
seconds is repeated until there are three runs and the median is reported with
the spread; slower cells are single runs and say so in the ``reps`` column.

Columns: iterations, total seconds, ms per iteration, and the Hessian pass timed
alone at the fitted point (seconds and gradient calls), so the dominant term can
be named per row without inference:
  iterations   if the optimiser's time is large because nit is large
  per-iter     if ms/iteration is large
  hessian      if the Hessian pass is a large share of the total

Writes ``benchmarks/results/wall_<date>.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks._common import RESULTS, cached_data, machine_lines, run_child, today  # noqa: E402

CHILD = "benchmarks/_child.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", default="2,4,6,8")
    ap.add_argument("--sizes", default="10000,100000,1000000")
    ap.add_argument("--rhos", default="0.3,0.85")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--fast", type=float, default=30.0)
    args = ap.parse_args()
    dims = [int(x) for x in args.dims.split(",")]
    sizes = [int(float(x)) for x in args.sizes.split(",")]
    rhos = [float(x) for x in args.rhos.split(",")]

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"wall_{today()}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in machine_lines():
            fh.write(line + "\n")
        fh.write("# pair decay, one start, se_method=hessian, seed 0, fresh child per run\n")
        fh.write(f"# cells under {args.fast:.0f} s are repeated to 3 runs (median, min, max)\n")
        w = csv.writer(fh)
        w.writerow(
            [
                "M",
                "rho_target",
                "n_events",
                "reps",
                "status",
                "nit",
                "rho_fit",
                "reliable",
                "total_s",
                "total_min_s",
                "total_max_s",
                "ms_per_iter",
                "hessian_s",
                "hessian_grad_calls",
                "hessian_share",
                "simulate_data_s",
            ]
        )
        for m in dims:
            for rho in rhos:
                for n in sizes:
                    import time

                    t0 = time.perf_counter()
                    data = cached_data(m, rho, n)
                    sim_s = time.perf_counter() - t0
                    runs = []
                    status = "ok"
                    reps_target = 1
                    while len(runs) < reps_target:
                        try:
                            p = run_child(
                                [CHILD, "wall", str(data), "--M", str(m)], timeout=args.timeout
                            )
                        except subprocess.TimeoutExpired:
                            status = f"timeout>{args.timeout:.0f}s"
                            break
                        line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
                        if not line:
                            status = "error"
                            print(p.stderr[-400:], file=sys.stderr)
                            break
                        runs.append(json.loads(line[0][7:]))
                        if len(runs) == 1 and runs[0]["wall_s"] < args.fast:
                            reps_target = 3
                    if not runs:
                        w.writerow([m, rho, n, 0, status] + [""] * 11)
                        fh.flush()
                        print(f"M={m} rho={rho} N={n:,d}: {status}", flush=True)
                        continue
                    walls = [r["wall_s"] for r in runs]
                    med = statistics.median(walls)
                    mid = sorted(runs, key=lambda r: r["wall_s"])[len(runs) // 2]
                    nit = max(mid["nit"], 1)
                    w.writerow(
                        [
                            m,
                            rho,
                            mid["n_events"],
                            len(runs),
                            status,
                            mid["nit"],
                            f"{mid['rho']:.3f}",
                            mid["reliable"],
                            f"{med:.3f}",
                            f"{min(walls):.3f}",
                            f"{max(walls):.3f}",
                            f"{(med - mid['hessian_s']) / nit * 1000:.2f}",
                            f"{mid['hessian_s']:.3f}",
                            mid["hessian_grad_calls"],
                            f"{mid['hessian_s'] / med:.3f}",
                            f"{sim_s:.1f}",
                        ]
                    )
                    fh.flush()
                    print(
                        f"M={m} rho={rho} N={mid['n_events']:>9,d}: nit={mid['nit']} "
                        f"{med:.2f}s ({min(walls):.2f}-{max(walls):.2f}) "
                        f"hess={mid['hessian_s']:.2f}s",
                        flush=True,
                    )
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
