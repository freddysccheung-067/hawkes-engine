"""Measure what the full H6 run will cost, before running it.

The preregistration projects 13.0 h single-core from the arithmetic model
``t_fit(N) = 10 + 0.008 N`` ms in section 6. That projection has never been
checked against a measured fit on this grid, and **peak memory per fit has never
been measured at all** (``PRIOR_EVIDENCE.md`` section 5 says so in as many
words). This script measures both, on the cheapest cell, the most expensive one,
and the M=4 satellite's largest cell.

It does not start the full run, and it never changes ``R`` or the grid. If the
projection is infeasible it says so; the response to that is a dated amendment,
which is an owner decision, not an engineering one.

Peak RSS per worker is read from the OS: on Windows through
``GetProcessMemoryInfo``'s ``PeakWorkingSetSize``, which the process itself can
read, so the measurement covers a real worker rather than an estimate.

Usage::

    python -m studies.pilot                 # 20 replications per cell
    python -m studies.pilot --reps 5
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import statistics
import time
from pathlib import Path

import numpy as np

from studies.grid import R, load_cells
from studies.run_cell import read_rows, run_cell

STUDIES = Path(__file__).resolve().parent
RESULTS = STUDIES / "results"
PILOT_DIR = RESULTS / "pilot"
PILOT_JSON = RESULTS / "pilot.json"

# The preregistration's own arithmetic model, section 6.
PROJECTED_MS = {200: 12, 1000: 18, 2000: 26, 10000: 90, 50000: 410}
PROJECTED_SWEEP_MS = 556.0  # sum over the five N values, M = 2
PROJECTED_HOURS_SINGLE = 13.0

# The headroom the worker count is chosen against. 0.7 leaves 30% of free RAM
# unclaimed, so the pilot's own measurement error and the OS cannot trip a
# swap-driven collapse; the preregistration's "8 workers against 5.4 GB" is the
# same shape of argument with a hand-made estimate in place of a measurement.
RAM_HEADROOM = 0.7


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_rss_bytes() -> int | None:
    """Peak resident set of this process, or ``None`` where unavailable.

    Windows: ``PeakWorkingSetSize`` from ``K32GetProcessMemoryInfo``. The
    prototypes are declared explicitly because ctypes' default return type is
    ``int``, which truncates a 64-bit process handle on Windows and makes the
    call fail silently -- the first version of this function returned 0 MB for
    every cell for exactly that reason.

    Other platforms: the high-water mark from ``/proc/self/status`` (Linux) or
    ``resource`` (macOS). A platform that answers ``None`` produces a pilot with
    no memory figure, which the report says rather than filling in.
    """
    if platform.system() == "Windows":
        from ctypes import wintypes

        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query = getattr(kernel32, "K32GetProcessMemoryInfo", None)
        if query is None:  # pragma: no cover - Windows 7
            query = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        query.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        query.restype = wintypes.BOOL
        ok = query(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return int(counters.PeakWorkingSetSize) if ok else None
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return peak if platform.system() == "Darwin" else peak * 1024
    except (ImportError, OSError):  # pragma: no cover - platform
        return None


def _quantile(values: list[float], q: float) -> float:
    """The ``q`` quantile by linear interpolation, without a SciPy dependency."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = q * (len(ordered) - 1)
    low = int(np.floor(position))
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return float(ordered[low] * (1.0 - weight) + ordered[high] * weight)


def _fit_ms(rows: list[dict[str, object]]) -> list[float]:
    """Per-fit wall time, excluding simulation.

    ``fit_ms`` on a row is the ``fit()`` call alone. The projection in section 6
    is a *fit* cost, so that is the column compared against it. ``wall_ms`` --
    simulate + quantise + fit, which is what the study actually pays -- is
    reported separately, because the full run's wall time is the sum of those and
    not of the fit alone.
    """
    return [float(row["fit_ms"]) for row in rows if str(row.get("fit_ms", "")).strip()]


def _wall_ms(rows: list[dict[str, object]]) -> list[float]:
    return [float(row["wall_ms"]) for row in rows if str(row.get("wall_ms", "")).strip()]


def measure_cell(key: str, reps: int) -> dict[str, object]:
    """Run one cell's pilot replications and report its cost."""
    cells = {cell.key: cell for cell in load_cells()}
    cell = cells[key]
    PILOT_DIR.mkdir(parents=True, exist_ok=True)

    before = peak_rss_bytes()
    started = time.perf_counter()
    result = run_cell(
        cell,
        reps,
        PILOT_DIR,
        force=True,
        worker="pilot",
        log=lambda message: print(f"  {message}"),
    )
    wall = time.perf_counter() - started
    after = peak_rss_bytes()

    rows = read_rows(result.rows_path)
    per_rep = _fit_ms(rows)
    total_rep = _wall_ms(rows)
    failures = sum(1 for row in rows if row.get("failure"))
    return {
        "cell_key": key,
        "reps": len(rows),
        "N_target": cell.N_target,
        "M": cell.M,
        "rho": cell.rho,
        "r": cell.r,
        "c": cell.c,
        "wall_seconds": wall,
        "ms_median": statistics.median(per_rep) if per_rep else float("nan"),
        "ms_p95": _quantile(per_rep, 0.95),
        "ms_mean": statistics.fmean(per_rep) if per_rep else float("nan"),
        "wall_ms_median": statistics.median(total_rep) if total_rep else float("nan"),
        "realised_n_mean": float(np.mean([float(row["n_events"]) for row in rows]))
        if rows and all(str(row.get("n_events", "")).strip() for row in rows)
        else float("nan"),
        "failures": failures,
        "peak_rss_before": before,
        "peak_rss_after": after,
        "checksum": result.checksum,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reps", type=int, default=20)
    parser.add_argument("--quick", action="store_true", help="cheapest cell only")
    parser.add_argument("--out", type=Path, default=PILOT_JSON, help="where to write the JSON")
    args = parser.parse_args(argv)

    cell_list = load_cells()
    cells = {cell.key: cell for cell in cell_list}
    # The preregistration names the cheapest cell (N=200, lowest rho) and the two
    # most expensive (N=50000 at rho=0.95 at M=2, and the satellite's N=20000).
    # All five N values at the anchor rho are measured as well, because the grid
    # estimate has to interpolate a cost curve and extrapolating it from N=200
    # alone is how a projection gets to be wrong by a factor of five.
    wanted = [
        "M2_N200_rho0.3028_r0.0_c1.0",
        "M2_N1000_rho0.3028_r0.0_c1.0",
        "M2_N2000_rho0.3028_r0.0_c1.0",
        "M2_N10000_rho0.3028_r0.0_c1.0",
        "M2_N50000_rho0.3028_r0.0_c1.0",
        "M2_N50000_rho0.95_r0.0_c1.0",
        "M2_N50000_rho0.95_r0.1_c0.001",
        "M4_N20000_rho0.85_r0.0_c1.0_sat",
    ]
    if args.quick:
        wanted = wanted[:1]
    missing = [key for key in wanted if key not in cells]
    if missing:
        print(f"pilot cells missing from the grid: {missing}")
        return 2

    print(f"pilot: {args.reps} replications per cell, {len(wanted)} cells")
    measurements = []
    for key in wanted:
        print(f"\n{key}")
        measurements.append(measure_cell(key, args.reps))

    # The measured cost of the whole grid, cell by cell. A cell's cost is taken
    # from the measured M=2 cell at the same N; the satellite's cells are scaled
    # by the measured ratio of M=4 to M=2 cost at the N they share, which is what
    # the preregistration's separate M=4 cost model does analytically.
    by_n = {int(m["N_target"]): m for m in measurements if m["M"] == 2}
    sat = next((m for m in measurements if m["M"] == 4), None)

    def m4_model(n: int) -> float:
        return 98.0 + 0.0448 * n

    def m2_ms(n: int) -> float:
        """Measured M=2 cost, interpolated linearly in N between measured sizes."""
        sizes = sorted(by_n)
        return float(np.interp(n, sizes, [by_n[k]["ms_median"] for k in sizes]))

    def cell_ms(cell) -> float:
        if cell.M == 2:
            return m2_ms(cell.N_target)
        # M=4: the measured cost at N=20000, carried to other N along the
        # preregistration's own M=4 curve. There is no other M=4 measurement.
        return sat["ms_median"] * m4_model(cell.N_target) / m4_model(int(sat["N_target"]))

    sat_scale = sat["ms_median"] / m4_model(int(sat["N_target"])) if sat else float("nan")
    # A partial pilot (--quick) lacks the sizes and the M=4 point the grid cost
    # needs, so it reports no grid estimate rather than inventing one.
    complete = sat is not None and len(by_n) >= 5
    grid_seconds = (
        sum(cell_ms(cell) / 1000.0 * R for cell in cell_list) if complete else float("nan")
    )

    # The preregistration's own model applied to the same grid, for the ratio
    # that section 6 calls the amendment trigger (1.6x).
    projected_seconds = 0.0
    for cell in cell_list:
        projected_ms = (
            10.0 + 0.008 * cell.N_target if cell.M == 2 else 98.0 + 0.0448 * cell.N_target
        )
        projected_seconds += (projected_ms / 1000.0) * R

    free_bytes = _free_ram_bytes()
    worst_rss = max((m["peak_rss_after"] or 0) for m in measurements)

    # A worker is not a fit: it is a Python interpreter with numpy and scipy
    # loaded, plus the biggest fit it ever holds. The baseline is measured here,
    # in this process, before the largest fit has run, so a cell's *marginal* peak
    # is its own peak minus the floor. Using the raw peak instead would charge
    # every worker for the interpreter once and understate the worker count; using
    # the marginal peak alone would understate RAM. The budget uses the measured
    # peak, which is the larger and therefore the safe number.
    baseline = measurements[0].get("peak_rss_before") or 0
    mem_workers = 1
    if worst_rss and free_bytes:
        mem_workers = max(1, int((free_bytes * RAM_HEADROOM) // worst_rss))

    # Two caps, and the smaller wins. The preregistration's "8 workers" was
    # derived from 5.4 GB free RAM; the measurement below says memory is no longer
    # the binding constraint, so the core count is, and the pilot reports both so
    # the recommendation cannot be read as "memory says 69".
    # Logical threads over-count: SMT siblings share an FPU, and a 24-thread part
    # is 12 physical cores here. A probe of 8 cells at N=10000 scaled 5.3x from 1
    # to 4 workers and 1.2x from 4 to 8, so the cap is half the logical count.
    cores = max(1, (os.cpu_count() or 2) // 2)
    workers = max(1, min(mem_workers, cores))

    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reps": args.reps,
        "measurements": measurements,
        "projection": {
            "model": "t_fit(N) = 10 + 0.008 N ms (preregistration section 6)",
            "projected_ms": PROJECTED_MS,
            "projected_sweep_ms": PROJECTED_SWEEP_MS,
            "projected_hours_single_core": PROJECTED_HOURS_SINGLE,
        },
        "estimate": {
            "grid_seconds_1_worker": grid_seconds,
            "grid_hours_1_worker": grid_seconds / 3600.0,
            "projected_seconds_same_grid": projected_seconds,
            "projected_hours_same_grid": projected_seconds / 3600.0,
            "measured_over_projected": grid_seconds / projected_seconds
            if projected_seconds
            else float("nan"),
            "amendment_trigger": 1.6,
            "amendment_needed": bool(complete and grid_seconds / projected_seconds > 1.6),
            "satellite_scale": sat_scale,
        },
        "recommendation": {
            "workers": workers,
            "free_ram_bytes": free_bytes,
            "worst_peak_rss_bytes": worst_rss,
            "baseline_rss_bytes": baseline,
            "per_worker_bytes": worst_rss,
            "ram_headroom": RAM_HEADROOM,
            "memory_limited_workers": mem_workers,
            "cores": cores,
            "grid_hours_at_workers": (grid_seconds / 3600.0) / max(workers, 1),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    _print_table(measurements, payload)
    print(f"\nwrote {args.out}")
    return 0


def _free_ram_bytes() -> int | None:
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo", encoding="ascii") as handle:
                for line in handle:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) * 1024
        except OSError:
            return None
    if platform.system() != "Windows":
        return None

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)


def _print_table(measurements: list[dict[str, object]], payload: dict[str, object]) -> None:
    print("\nmeasured per-replication cost (simulate + quantise + fit)")
    print(f"{'cell':40s} {'ms median':>10s} {'ms p95':>9s} {'peak RSS MB':>12s} {'fails':>6s}")
    for m in measurements:
        rss = m["peak_rss_after"] or 0
        print(
            f"{str(m['cell_key']):40s} {m['ms_median']:10.1f} {m['ms_p95']:9.1f} "
            f"{rss / 2**20:12.1f} {m['failures']:6d}"
        )
    est = payload["estimate"]
    print(
        f"\nwhole grid at one worker: {est['grid_hours_1_worker']:.1f} h "
        f"(preregistration projection {PROJECTED_HOURS_SINGLE:.1f} h)"
    )
    rec = payload["recommendation"]
    free = rec["free_ram_bytes"]
    free_text = f"{free / 2**30:.2f} GB" if free else "unknown"
    print(
        f"free RAM {free_text}, worst peak RSS "
        f"{rec['worst_peak_rss_bytes'] / 2**20:.0f} MB at {rec['ram_headroom']:.0%} headroom "
        f"-> {rec['workers']} workers"
    )
    print(f"whole grid at {rec['workers']} workers: {rec['grid_hours_at_workers']:.1f} h")


if __name__ == "__main__":
    raise SystemExit(main())
