"""Phase 1 of H7: peak memory of a single fit, by component.

Every measurement runs in a fresh child process (``_child.py``) that reads its own
peak working set, so an earlier allocation cannot flatter a later one. The figure
reported is the peak minus the child's peak after imports and before any data is
loaded (``base_peak``).

Components, all as deltas over ``base_peak``:
  load      event arrays alone
  opt       fit(se_method=None): events plus the optimiser's workspace
  hessian   fit(se_method="hessian"): adds the Hessian pass
  boot      one bootstrap worker's share (refits on simulated data)

Outputs ``benchmarks/results/memory_<date>.csv`` and ``memory_fit_<date>.txt``.

Usage:
    python benchmarks/capability_memory.py [--sizes 1000,10000,100000,1000000]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks._common import (  # noqa: E402
    RESULTS,
    cached_data,
    machine_lines,
    run_child,
    today,
)

RHO = 0.5
CHILD = "benchmarks/_child.py"


def measure(mode: str, data: Path, M: int, reps: int, extra: list[str] | None = None):
    rows = []
    for _ in range(reps):
        p = run_child([CHILD, mode, str(data), "--M", str(M), *(extra or [])], timeout=7200)
        line = [x for x in p.stdout.splitlines() if x.startswith("RESULT ")]
        if not line:
            raise RuntimeError(f"child failed: {p.stderr[-500:]}")
        rows.append(json.loads(line[0][7:]))
    return rows


def delta_mib(rows) -> tuple[float, float, float]:
    d = [(r["peak"] - r["base_peak"]) / 2**20 for r in rows]
    return statistics.median(d), min(d), max(d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="1000,10000,100000,1000000")
    ap.add_argument("--dims", default="2,4,8")
    ap.add_argument("--big", default="10000000", help="extra N at M=2 to test extrapolation")
    ap.add_argument("--boot-n", type=int, default=10000)
    ap.add_argument("--boot-B", type=int, default=200)
    args = ap.parse_args()
    sizes = [int(float(s)) for s in args.sizes.split(",")]
    dims = [int(d) for d in args.dims.split(",")]

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"memory_{today()}.csv"
    cases = [(m, n) for m in dims for n in sizes]
    if args.big:
        cases.append((2, int(float(args.big))))

    with path.open("w", newline="", encoding="utf-8") as fh:
        for line in machine_lines():
            fh.write(line + "\n")
        fh.write(f"# rho: {RHO}, pair decay, one start, seed 0; fresh child per measurement\n")
        fh.write("# memory = child peak working set minus peak after imports (MiB)\n")
        w = csv.writer(fh)
        w.writerow(
            [
                "component",
                "M",
                "n_params",
                "n_events",
                "reps",
                "base_mib",
                "median_mib",
                "min_mib",
                "max_mib",
            ]
        )
        for m, n in cases:
            data = cached_data(m, RHO, n)
            reps = 3 if n <= 100_000 else 1
            n_params = m + m * m + m * m
            for mode in ("load", "opt", "hessian"):
                rows = measure(mode, data, m, reps)
                med, lo, hi = delta_mib(rows)
                base = statistics.median(r["base_peak"] for r in rows) / 2**20
                w.writerow(
                    [
                        mode,
                        m,
                        n_params,
                        rows[0]["n_events"],
                        reps,
                        f"{base:.1f}",
                        f"{med:.2f}",
                        f"{lo:.2f}",
                        f"{hi:.2f}",
                    ]
                )
                fh.flush()
                print(f"{mode:8s} M={m} N={rows[0]['n_events']:>9,d} +{med:8.2f} MiB", flush=True)

        # Bootstrap: one worker's serial share, at one representative size.
        for m in (2, 4):
            data = cached_data(m, RHO, args.boot_n)
            rows = measure("boot", data, m, 1, ["--B", str(args.boot_B)])
            r = rows[0]
            base = r["base_peak"] / 2**20
            w.writerow(
                [
                    f"boot_B{args.boot_B}",
                    m,
                    m + 2 * m * m,
                    r["n_events"],
                    1,
                    f"{base:.1f}",
                    f"{(r['peak'] - r['base_peak']) / 2**20:.2f}",
                    f"{(r['peak_after_fit'] - r['base_peak']) / 2**20:.2f}",
                    f"{r['wall_s']:.1f}",
                ]
            )
            fh.flush()
            print(f"boot M={m} N={r['n_events']} +{(r['peak'] - r['base_peak']) / 2**20:.2f} MiB")
        fh.write("# boot rows: min_mib = peak after the base fit, max_mib = wall seconds\n")

    # --- fit the two constants -------------------------------------------------
    rows = [
        r
        for r in csv.reader(
            ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")
        )
    ][1:]
    pts = [
        (int(r[1]), int(r[2]), int(r[3]), float(r[6]))
        for r in rows
        if r[0] == "hessian" and int(r[3]) >= 100_000
    ]
    if len(pts) >= 3:
        a = np.array([[n, p, 1.0] for (_, p, n, _) in pts])
        y = np.array([mib * 2**20 for (*_, mib) in pts])
        coef, *_ = np.linalg.lstsq(a, y, rcond=None)
        pred = a @ coef
        out = RESULTS / f"memory_fit_{today()}.txt"
        with out.open("w", encoding="utf-8") as f:
            for line in machine_lines():
                f.write(line + "\n")
            f.write("# least squares on hessian-mode deltas, N >= 1e5: bytes = a*N + b*P + c\n")
            f.write(f"a_bytes_per_event = {coef[0]:.2f}\n")
            f.write(f"b_bytes_per_param = {coef[1]:.1f}\n")
            f.write(f"c_bytes_const     = {coef[2]:.0f}\n")
            for (m, p, n, mib), pr in zip(pts, pred, strict=True):
                f.write(
                    f"M={m} P={p} N={n}: measured {mib:.2f} MiB, model {pr / 2**20:.2f} MiB, "
                    f"error {(pr / 2**20 - mib) / mib * 100:+.1f}%\n"
                )
        print(out.read_text(encoding="utf-8"))
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
