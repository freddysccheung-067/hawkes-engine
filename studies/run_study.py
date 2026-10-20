"""Run the frozen H6 grid, one cell per worker process.

The parallelism is over **cells**, not replications: every worker owns the cell
it is running and writes only that cell's two files, so two workers never touch
the same path and a crash costs the cell in flight at most (which resumes from
its last flushed row). Nothing is shared between workers but the process
scheduler.

On Windows the start method must be ``spawn``; a ``fork`` would hand the child a
copy of a SciPy/NumPy state that is not meant to be copied, and the guard in
:func:`main` is what keeps a spawned child from re-running the entry point.

The worker count defaults to the pilot's recommendation, never to the core
count: the binding constraint is RAM per worker, and the pilot measures it.

Usage::

    python -m studies.run_study --dry-run
    python -m studies.run_study --workers 8
    python -m studies.run_study --cells M2_N200_rho0.3028_r0.0_c1.0 --reps 5 --force
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from studies.grid import Cell, R, load_cells
from studies.run_cell import is_complete, run_cell

STUDIES = Path(__file__).resolve().parent
RESULTS = STUDIES / "results"
CELLS_DIR = RESULTS / "cells"
LOGS_DIR = RESULTS / "logs"
PILOT_PATH = RESULTS / "pilot.json"
DEFAULT_WORKERS = 8


def _worker_count_from_pilot() -> int | None:
    """The pilot's recommendation, if it has been run."""
    if not PILOT_PATH.exists():
        return None
    try:
        payload = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    workers = payload.get("recommendation", {}).get("workers")
    return int(workers) if isinstance(workers, int) and workers > 0 else None


def _run_one(args: tuple[str, int, str, bool]) -> tuple[str, int, bool, float, str]:
    """A cell, in a worker process. Returns the fields the parent logs."""
    key, reps, out_dir, force = args
    cells = {cell.key: cell for cell in load_cells()}
    cell: Cell = cells[key]
    log_path = LOGS_DIR / f"{key}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

    started = time.perf_counter()
    result = run_cell(
        cell, reps, Path(out_dir), force=force, worker=mp.current_process().name, log=log
    )
    log(
        f"done key={result.key} completed={result.completed} skipped={result.skipped} "
        f"checksum={result.checksum} wall={time.perf_counter() - started:.1f}s"
    )
    return result.key, result.completed, result.skipped, result.wall_seconds, result.checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--reps", type=int, default=R, help=f"replications per cell (frozen at {R})"
    )
    parser.add_argument("--cells", nargs="*", default=None, help="only these cell keys")
    parser.add_argument("--force", action="store_true", help="discard and re-run")
    parser.add_argument("--dry-run", action="store_true", help="list what would run")
    parser.add_argument(
        "--allow-reps-change",
        action="store_true",
        help="permit --reps to differ from the frozen R; refuses otherwise",
    )
    args = parser.parse_args(argv)

    cells = load_cells()  # verifies the digest
    if args.cells:
        wanted = set(args.cells)
        unknown = wanted - {cell.key for cell in cells}
        if unknown:
            print(f"unknown cell keys: {sorted(unknown)}", file=sys.stderr)
            return 2
        cells = [cell for cell in cells if cell.key in wanted]

    if args.reps != R and not args.allow_reps_change:
        print(
            f"R is frozen at {R}; --reps {args.reps} is a deviation from the "
            f"pre-registration. Pass --allow-reps-change for a harness test, or "
            f"append an amendment before running the study.",
            file=sys.stderr,
        )
        return 2

    todo = []
    for cell in cells:
        complete, reason = is_complete(cell, CELLS_DIR)
        if complete and not args.force:
            continue
        todo.append((cell, reason if not complete else "force"))

    workers = (
        args.workers or (_worker_count_from_pilot() if args.reps == R else 1) or DEFAULT_WORKERS
    )
    if args.dry_run:
        print(
            f"{len(todo)} of {len(cells)} cells would run, {workers} workers, {args.reps} reps each"
        )
        for cell, reason in todo:
            print(f"  {cell.key:44s} {reason}")
        return 0

    if not todo:
        print(f"all {len(cells)} cells are complete; nothing to do")
        return 0

    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"running {len(todo)} cells on {workers} workers, {args.reps} replications each")

    started = time.perf_counter()
    context = mp.get_context("spawn")
    payloads = [(cell.key, args.reps, str(CELLS_DIR), args.force) for cell, _ in todo]
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        futures = {pool.submit(_run_one, payload): payload[0] for payload in payloads}
        done = 0
        for future in as_completed(futures):
            key, completed, skipped, wall, checksum = future.result()
            done += 1
            state = "skipped" if skipped else "ran"
            print(
                f"[{done}/{len(todo)}] {key} {state} {completed} rows "
                f"{wall:.1f}s {checksum[:12]}",
                flush=True,
            )
    print(f"finished in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
