"""Phase 2b of H7: what an honest interval costs.

``fit(se_method="bootstrap")`` does not expose the worker count, and its pool
defaults to every logical core. To time one worker and four workers this script
fits once with ``se_method=None`` and then calls
``hawkes_engine._boot.parametric_bootstrap`` directly with ``workers`` set, which
is exactly the call ``fit`` makes. One row also times the public
``fit(se_method="bootstrap")`` at its default pool size. Each configuration runs
in a fresh process so pool start-up and import cost are included, as a user
would pay them.

Writes ``benchmarks/results/bootstrap_<date>.csv``.
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

RHO = 0.5

_RUNNER = r"""
import json, sys, time
import numpy as np
sys.path.insert(0, r"{root}")
import hawkes_engine
from hawkes_engine._boot import parametric_bootstrap
from hawkes_engine._layout import Layout

d = np.load(r"{data}")
times, types, T = d["times"], d["types"], float(d["T"])
M, B, W = {M}, {B}, {W}
t0 = time.perf_counter()
if W == 0:
    r = hawkes_engine.fit(times, types, T=T, M=M, seed=0, se_method="bootstrap", n_bootstrap=B)
    total = time.perf_counter() - t0
    out = dict(total_s=total, fit_s=None, boot_s=None, notes=len(r.notes))
else:
    r = hawkes_engine.fit(times, types, T=T, M=M, seed=0, se_method=None)
    t1 = time.perf_counter()
    boot = parametric_bootstrap(times, types, T, M, False, r.mu, r.alpha, r.beta, Layout(M=M),
                                n_bootstrap=B, seed=0, workers=W)
    t2 = time.perf_counter()
    out = dict(total_s=t2 - t0, fit_s=t1 - t0, boot_s=t2 - t1, usable=int(boot.draws.shape[0]))
print("RESULT " + json.dumps(out))
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", default="2,4")
    ap.add_argument("--sizes", default="10000,100000")
    ap.add_argument("--B", default="50,200")
    ap.add_argument("--workers", default="1,4")
    ap.add_argument("--timeout", type=float, default=7200.0)
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"bootstrap_{today()}.csv"
    from benchmarks._common import ROOT

    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in machine_lines():
            fh.write(line + "\n")
        fh.write(f"# rho {RHO}, pair decay, seed 0; workers=0 means fit()'s default pool\n")
        w = csv.writer(fh)
        w.writerow(
            [
                "M",
                "n_events",
                "B",
                "workers",
                "reps",
                "total_s",
                "min_s",
                "max_s",
                "boot_s",
                "boot_s_per_replication",
                "usable",
            ]
        )
        configs = []
        for m in (int(x) for x in args.dims.split(",")):
            for n in (int(float(x)) for x in args.sizes.split(",")):
                for b in (int(x) for x in args.B.split(",")):
                    for wk in [int(x) for x in args.workers.split(",")]:
                        configs.append((m, n, b, wk))
                    if b == 200:
                        configs.append((m, n, b, 0))
        for m, n, b, wk in configs:
            data = cached_data(m, RHO, n)
            code = _RUNNER.format(root=str(ROOT), data=str(data), M=m, B=b, W=wk)
            runs = []
            reps = 3 if n <= 10_000 else 1
            for _ in range(reps):
                try:
                    p = run_child(["-c", code], timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    print(f"M={m} N={n} B={b} W={wk}: timeout", flush=True)
                    break
                line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
                if not line:
                    print(p.stderr[-400:], file=sys.stderr)
                    break
                runs.append(json.loads(line[0][7:]))
            if not runs:
                w.writerow([m, n, b, wk, 0, "timeout/error"] + [""] * 5)
                continue
            tot = [r["total_s"] for r in runs]
            boots = [r["boot_s"] for r in runs if r.get("boot_s") is not None]
            bs = statistics.median(boots) if boots else None
            w.writerow(
                [
                    m,
                    n,
                    b,
                    wk,
                    len(runs),
                    f"{statistics.median(tot):.2f}",
                    f"{min(tot):.2f}",
                    f"{max(tot):.2f}",
                    "" if bs is None else f"{bs:.2f}",
                    "" if bs is None else f"{bs / b:.4f}",
                    runs[0].get("usable", ""),
                ]
            )
            fh.flush()
            print(
                f"M={m} N={n:,d} B={b} workers={wk}: {statistics.median(tot):.2f}s "
                f"({min(tot):.2f}-{max(tot):.2f}, {len(runs)} runs)",
                flush=True,
            )
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
