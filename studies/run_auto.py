"""Run the ``auto-v1`` study: Hessian against ``auto`` on shared event streams.

Everything this module does is fixed by ``docs/preregistration_auto.md``. Where
that document is silent the choice is named here, so a referee can find every
place the design was completed rather than followed.

    python -m studies.run_auto --dry-run
    python -m studies.run_auto --workers 12

Each replication simulates one event stream and fits it twice: once with the
Hessian interval, once with ``se_method="auto"``. The shared stream is what makes
the comparison paired, and it is legitimate because the two arms differ only in
how the interval is computed.

Rows are appended and flushed as they complete, and a completed cell carries a
checksummed ``.done`` marker, for the same reasons as H6's harness: a crash costs
one replication, and a resumed run reproduces the interrupted one exactly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

STUDIES = Path(__file__).resolve().parent
REPO = STUDIES.parent
RESULTS = STUDIES / "results" / "auto"
STUDY_ID = "auto-v1"
R = 2000
BOOTSTRAP_REPLICATIONS = 200

# The three cells, fixed in section 5 of the pre-registration. The keys are the
# frozen H6 grid's, so the parameters come from studies/theta0.json and are not
# retyped here.
CELL_KEYS = (
    "M2_N2000_rho0.3028_r0.0_c1.0",
    "M2_N2000_rho0.85_r0.0_c1.0",
    "M2_N2000_rho0.95_r0.0_c1.0",
)

COLUMNS = (
    "cell_key",
    "rep_index",
    "rep_seed",
    "n_events",
    "T",
    "converged",
    "rho_hat",
    # Hessian arm
    "h_se_mu",
    "h_se_alpha",
    "h_se_beta",
    "h_cov_mu",
    "h_cov_alpha",
    "h_cov_beta",
    "h_cov_all",
    "h_source",
    # auto arm
    "a_source",
    "a_action",
    "a_cell",
    "a_distance",
    "a_se_mu",
    "a_se_alpha",
    "a_se_beta",
    "a_cov_mu",
    "a_cov_alpha",
    "a_cov_beta",
    "a_cov_all",
    # cost
    "h_ms",
    "a_ms",
    "a_projected_s",
    "failure",
)

CHECKSUM_COLUMNS = (
    "cell_key",
    "rep_index",
    "n_events",
    "h_cov_all",
    "a_cov_all",
    "a_source",
    "failure",
)


@dataclass(frozen=True)
class AutoCell:
    """One study cell: an H6 grid cell's parameters with this study's seed."""

    key: str
    M: int
    N_target: int
    rho: float
    mu: tuple[float, ...]
    alpha: tuple[tuple[float, ...], ...]
    beta: tuple[tuple[float, ...], ...]
    delta: float
    T: float
    relaxation: float
    seed: int


def _splitmix64(state: int) -> int:
    """One SplitMix64 step, as the seed contract defines it (studies/grid.py)."""
    mask = (1 << 64) - 1
    state = (state + 0x9E3779B97F4A7C15) & mask
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
    return z ^ (z >> 31)


def auto_cell_seed(key: str, rho: float) -> int:
    """``auto-v1``'s own cell seed, derived as section 6 states.

    The message uses the study id and the cell's own coordinates, so a seed from
    this study cannot collide with one from H6's: the two strings differ in their
    first field, and the hash is over the whole string.
    """
    message = f"{STUDY_ID}|2|2000|{repr(float(rho))}|0.0|1.0"
    digest = hashlib.sha256(message.encode("utf-8")).digest()
    return _splitmix64(int.from_bytes(digest[:16], "big"))


def load_cells() -> list[AutoCell]:
    """The three cells, with parameters from the frozen H6 grid."""
    from studies.grid import load_cells as load_h6

    frozen = {cell.key: cell for cell in load_h6()}
    out: list[AutoCell] = []
    for key in CELL_KEYS:
        cell = frozen[key]
        out.append(
            AutoCell(
                key=key,
                M=cell.M,
                N_target=cell.N_target,
                rho=cell.rho,
                mu=cell.mu,
                alpha=cell.alpha,
                beta=cell.beta,
                delta=cell.delta,
                T=cell.T,
                relaxation=cell.relaxation,
                seed=auto_cell_seed(key, cell.rho),
            )
        )
    return out


def rep_seed(cell: AutoCell, rep_index: int) -> int:
    from hawkes_engine import _core

    return int(_core.seed_stream(cell.seed, int(rep_index)))


def cell_paths(cell: AutoCell) -> tuple[Path, Path]:
    return RESULTS / f"{cell.key}.csv", RESULTS / f"{cell.key}.done"


def rows_checksum(rows: list[dict[str, Any]]) -> str:
    body = "\n".join("|".join(f"{c}={r.get(c, '')}" for c in CHECKSUM_COLUMNS) for r in rows) + "\n"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def is_complete(cell: AutoCell) -> tuple[bool, str]:
    csv_path, done_path = cell_paths(cell)
    if not done_path.exists():
        return False, "no .done marker"
    if not csv_path.exists():
        return False, ".done exists but the rows file is missing"
    try:
        done = json.loads(done_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, ".done is not valid JSON"
    rows = read_rows(csv_path)
    if int(done.get("reps_completed", -1)) != len(rows):
        return False, f".done claims {done.get('reps_completed')} rows, file has {len(rows)}"
    if rows_checksum(rows) != done.get("checksum"):
        return False, "checksum does not re-verify"
    return True, "verified"


def _coverage(estimate: np.ndarray, se: np.ndarray | None, truth: np.ndarray) -> tuple[float, ...]:
    """Share of nominal-95% intervals covering the truth, masked to finite entries.

    A replication that returned no standard error contributes a miss for every
    entry it could not cover, which is H6's E3.5 rule: the interval is absent and
    an absent interval covers nothing. Entries that are not identified in this
    model (a fixed block, a masked diagonal) are excluded before the mean.
    """
    z = 1.959963984540054
    if se is None:
        return (0.0,)
    covered = (np.abs(estimate - truth) <= z * se).astype(float)
    return tuple(float(v) for v in covered.ravel())


def _arm_coverages(result: Any, truth: dict[str, np.ndarray]) -> dict[str, float]:
    """Per-block coverage for one arm of one replication."""
    out: dict[str, float] = {}
    if result.se is None:
        for block in ("mu", "alpha", "beta", "all"):
            out[f"cov_{block}"] = 0.0
        return out
    blocks: dict[str, list[float]] = {}
    for block in ("mu", "alpha", "beta"):
        est = np.asarray(getattr(result, block), dtype=np.float64)
        se = np.asarray(result.se[block], dtype=np.float64)
        blocks[block] = list(_coverage(est, se, truth[block]))
        out[f"cov_{block}"] = float(np.mean(blocks[block])) if blocks[block] else 0.0
    pooled = blocks["mu"] + blocks["alpha"] + blocks["beta"]
    out["cov_all"] = float(np.mean(pooled)) if pooled else 0.0
    return out


def one_replication(cell: AutoCell, rep_index: int) -> dict[str, Any]:
    """Simulate once, fit both arms on the same stream, return the row."""
    from hawkes_engine import fit as fit_fn
    from hawkes_engine import simulate

    row: dict[str, Any] = {c: "" for c in COLUMNS}
    row["cell_key"] = cell.key
    row["rep_index"] = rep_index
    seed = rep_seed(cell, rep_index)
    row["rep_seed"] = seed
    row["T"] = repr(cell.T)

    mu = np.asarray(cell.mu, dtype=np.float64)
    alpha = np.asarray(cell.alpha, dtype=np.float64)
    beta = np.asarray(cell.beta, dtype=np.float64)
    truth = {"mu": mu, "alpha": alpha, "beta": beta}

    try:
        times, types = simulate(
            mu,
            alpha,
            beta,
            cell.T,
            method="thinning",
            seed=seed,
            burn_in=10.0 * cell.relaxation,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        row["failure"] = f"simulate:{type(exc).__name__}:{exc}"
        return row
    row["n_events"] = int(times.size)

    t0 = time.perf_counter()
    try:
        hessian = fit_fn(times, types, T=cell.T, M=2, seed=seed, se_method="hessian")
    except Exception as exc:  # noqa: BLE001
        row["failure"] = f"hessian:{type(exc).__name__}:{exc}"
        return row
    row["h_ms"] = f"{1000.0 * (time.perf_counter() - t0):.2f}"

    t0 = time.perf_counter()
    try:
        auto = fit_fn(
            times,
            types,
            T=cell.T,
            M=2,
            seed=seed,
            se_method="auto",
            n_bootstrap=BOOTSTRAP_REPLICATIONS,
            auto_max_seconds=None,
            # One worker per replication's bootstrap. The study parallelises over
            # replications, and a second pool inside each of those would spawn
            # hundreds of processes and spend the machine on start-up.
            bootstrap_workers=1,
        )
    except Exception as exc:  # noqa: BLE001
        row["failure"] = f"auto:{type(exc).__name__}:{exc}"
        return row
    row["a_ms"] = f"{1000.0 * (time.perf_counter() - t0):.2f}"

    row["converged"] = int(hessian.converged)
    row["rho_hat"] = repr(float(hessian.rho))
    row["h_source"] = hessian.se_source
    row["a_source"] = auto.se_source
    row["a_action"] = auto.auto.action if auto.auto is not None else ""
    row["a_cell"] = auto.auto.cell if auto.auto is not None and auto.auto.cell else ""
    row["a_distance"] = (
        repr(float(auto.auto.distance))
        if auto.auto is not None and auto.auto.distance is not None
        else ""
    )
    row["a_projected_s"] = (
        repr(float(auto.auto.projected_seconds))
        if auto.auto is not None and auto.auto.projected_seconds is not None
        else ""
    )

    h = _arm_coverages(hessian, truth)
    a = _arm_coverages(auto, truth)
    for block in ("mu", "alpha", "beta", "all"):
        row[f"h_cov_{block}"] = repr(h[f"cov_{block}"])
        row[f"a_cov_{block}"] = repr(a[f"cov_{block}"])
    for block in ("mu", "alpha", "beta"):
        row[f"h_se_{block}"] = (
            repr(float(np.mean(hessian.se[block]))) if hessian.se is not None else ""
        )
        row[f"a_se_{block}"] = repr(float(np.mean(auto.se[block]))) if auto.se is not None else ""
    return row


def run_cell(cell: AutoCell, reps: int, *, force: bool = False) -> dict[str, Any]:
    """Run (or resume) one cell, appending each row as it completes."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    csv_path, done_path = cell_paths(cell)
    complete, reason = is_complete(cell)
    if complete and not force and reps >= R:
        return {"key": cell.key, "completed": R, "skipped": True, "reason": reason}

    existing = [] if force else read_rows(csv_path)
    done_indices = {int(r["rep_index"]) for r in existing}
    rows = list(existing)
    started = time.perf_counter()
    write_header = not csv_path.exists() or force
    if force and csv_path.exists():
        csv_path.unlink()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
        if write_header:
            writer.writeheader()
        for index in range(reps):
            if index in done_indices:
                continue
            row = one_replication(cell, index)
            writer.writerow(row)
            fh.flush()
            os.fsync(fh.fileno())
            rows.append(row)
    wall = time.perf_counter() - started
    payload = {
        "study_id": STUDY_ID,
        "cell": cell.key,
        "reps_completed": len(rows),
        "checksum": rows_checksum(rows),
        "wall_seconds": wall,
    }
    done_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "key": cell.key,
        "completed": len(rows),
        "skipped": False,
        "wall": wall,
        "checksum": payload["checksum"],
    }


def _worker(args: tuple[str, int, int]) -> dict[str, Any]:
    """One contiguous block of replications of one cell, in a worker process.

    Parallelising over replications rather than over cells is not a detail. There
    are three cells and many cores, so one cell per worker leaves most of the
    machine idle; and replications are independent by construction, since
    replication ``i``'s row is a pure function of ``(cell, i)``. Splitting them is
    therefore exact: the rows are identical to a serial run's, and the order they
    are written in is restored by the parent.
    """
    key, start, stop = args
    cell = next(c for c in load_cells() if c.key == key)
    out = []
    for index in range(start, stop):
        out.append(one_replication(cell, index))
    return {"key": key, "start": start, "rows": out}


def _chunks(indices: list[int], parts: int) -> list[tuple[int, int]]:
    """Split indices into contiguous ``(start, stop)`` half-open ranges."""
    if not indices:
        return []
    ordered = sorted(indices)
    size = max(1, len(ordered) // max(parts, 1))
    spans: list[tuple[int, int]] = []
    for i in range(0, len(ordered), size):
        block = ordered[i : i + size]
        spans.append((block[0], block[-1] + 1))
    return spans


def run_cells(cells: list[AutoCell], reps: int, workers: int, *, force: bool = False) -> list[dict]:
    """Run every requested cell, in chunks, writing each cell's rows as they arrive."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    jobs: list[tuple[str, int, int]] = []
    pending: dict[str, list[int]] = {}

    for cell in cells:
        csv_path, done_path = cell_paths(cell)
        complete, reason = is_complete(cell)
        if complete and not force and reps >= R:
            results.append({"key": cell.key, "completed": R, "skipped": True, "reason": reason})
            continue
        existing = [] if force else read_rows(csv_path)
        done_indices = {int(r["rep_index"]) for r in existing}
        todo = [i for i in range(reps) if i not in done_indices]
        pending[cell.key] = todo
        if not todo:
            _write_done(cell, existing, 0.0)
            results.append(
                {"key": cell.key, "completed": len(existing), "skipped": False, "wall": 0.0}
            )
            continue
        jobs.extend((cell.key, start, stop) for start, stop in _chunks(todo, workers))

    if not jobs:
        return results

    gathered: dict[str, list[dict[str, Any]]] = {}
    started = time.perf_counter()
    if workers <= 1:
        outputs = [_worker(job) for job in jobs]
    else:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            outputs = list(pool.map(_worker, jobs))
    for out in outputs:
        gathered.setdefault(out["key"], []).extend(out["rows"])
        print(f"  chunk {out['key']} [{out['start']}..): {len(out['rows'])} rows", flush=True)
    wall = time.perf_counter() - started

    for cell in cells:
        if cell.key not in pending:
            continue
        csv_path, _ = cell_paths(cell)
        existing = [] if force else read_rows(csv_path)
        by_index = {int(r["rep_index"]): r for r in existing}
        for row in gathered.get(cell.key, []):
            by_index[int(row["rep_index"])] = row
        rows = [by_index[i] for i in sorted(by_index)]
        tmp = csv_path.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(csv_path)
        _write_done(cell, rows, wall / max(len(cells), 1))
        results.append({"key": cell.key, "completed": len(rows), "skipped": False, "wall": wall})
        print(f"  done {cell.key}: {len(rows)} rows", flush=True)
    return results


def _write_done(cell: AutoCell, rows: list[dict[str, Any]], wall: float) -> None:
    _, done_path = cell_paths(cell)
    payload = {
        "study_id": STUDY_ID,
        "cell": cell.key,
        "reps_completed": len(rows),
        "checksum": rows_checksum(rows),
        "wall_seconds": wall,
    }
    done_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def projected_seconds(reps: int, workers: int) -> float:
    """The design's projection, from the measured cost in the pre-registration."""
    return 3.0 * reps * 2.7 / max(workers, 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reps", type=int, default=R)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--cells", nargs="*", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cells = load_cells()
    if args.cells:
        wanted = set(args.cells)
        cells = [c for c in cells if c.key in wanted]
        if not cells:
            print(f"no cell named in {sorted(wanted)}", file=sys.stderr)
            return 2

    print(f"{STUDY_ID}: {len(cells)} cells, R = {args.reps}, {args.workers} workers")
    print(f"projected wall clock: {projected_seconds(args.reps, args.workers) / 60:.1f} min")
    if args.reps > R:
        print(f"the pre-registration fixes R = {R}; --reps above it is not this study")
        return 2
    for cell in cells:
        complete, reason = is_complete(cell)
        print(f"  {cell.key}: {'complete' if complete else 'pending'} ({reason})")
    if args.dry_run:
        return 0

    results = run_cells(cells, args.reps, args.workers, force=args.force)
    total = sum(r.get("wall", 0.0) for r in results)
    done = sum(1 for r in results if not r.get("skipped"))
    print(
        f"finished: {len(results)} cells ({done} run, {len(results) - done} skipped), "
        f"{total:.0f} s wall"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
