"""Run one H6 cell: R replications of simulate -> quantise -> fit -> row.

Everything in this module is dictated by ``docs/preregistration.md``. Where the
file is silent, the choice is named in ``studies/HARNESS_NOTES.md`` and marked in
the code with ``NOTE(H6)``, so a referee can find every place the design was
completed rather than followed.

The three properties the brief demands, and how each is obtained:

* **Failures are rows.** A non-converged fit, a bound hit, a ``-inf``
  likelihood, an exception from ``fit`` -- each produces a row carrying its
  reason and consumes one of the ``R`` replications. Coverage is reported
  conditioned and unconditioned (section 3, E3.5), which is only possible if the
  failures are stored rather than skipped.
* **Resumability.** Rows are appended and flushed as they complete, so a crash
  loses at most the replication in flight. A ``.done`` marker with a checksum
  makes a completed cell a no-op on re-invocation.
* **Determinism.** Row ``i`` is a pure function of ``(cell, rep_seed)``, so a
  resumed run and a ``--force`` re-run produce identical rows.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from hawkes_engine import fit as fit_fn
from hawkes_engine import simulate

from studies.grid import Cell, rep_seed

__all__ = [
    "BURN_IN_RELAXATIONS",
    "CellResult",
    "cell_paths",
    "is_complete",
    "read_rows",
    "rows_checksum",
    "run_cell",
]

# NOTE(H6): the preregistration specifies a "stationary start" but states no
# burn-in anywhere in section 5 or 10. Ten relaxation times --
# 10 / (beta_min (1 - rho)), a derived quantity, not a chosen one -- brings the
# realised count to within 0.5% of N_target on every cell tested; two times does
# not (z = -25 at c=1e-3, rho=0.95). The evidence and the alternatives are in
# studies/HARNESS_NOTES.md. This is the smallest rule consistent with "stationary
# start" and it changes no frozen quantity.
BURN_IN_RELAXATIONS = 10.0

# The simulator. PRIOR_EVIDENCE.md section 2 records H3 with the thinning
# simulator, and H6.1 is a replication of that measurement, so thinning is the
# consistent choice. NOTE(H6): the preregistration names neither simulator.
SIMULATOR_METHOD = "thinning"

COLUMNS = (
    "cell_key",
    "rep_index",
    "rep_number",
    "N_target",
    "M",
    "rho_axis",
    "r_axis",
    "c_axis",
    "satellite",
    "n_events",
    "T",
    "rep_seed",
    "theta0",
    "theta_hat",
    "converged",
    "status",
    "nit",
    "gradient_inf_norm",
    "loglik",
    "rho_hat",
    "se_mu",
    "se_alpha",
    "se_beta",
    "hessian_condition",
    "verdict",
    "bound_hit",
    "bound_coordinates",
    "failure",
    "sim_ms",
    "fit_ms",
    "wall_ms",
)

# Every column that carries a measured number, in order. The checksum covers
# these and no others: it is a statement about the data, not about the run's
# bookkeeping (a wall time differs between two runs of otherwise identical
# rows, so a checksum including it could never re-verify).
CHECKSUM_COLUMNS = (
    "cell_key",
    "rep_index",
    "n_events",
    "theta_hat",
    "loglik",
    "rho_hat",
    "se_alpha",
    "converged",
    "verdict",
    "failure",
)


@dataclass(frozen=True)
class CellResult:
    """What a completed cell run wrote, for the caller to report."""

    key: str
    requested: int
    completed: int
    skipped: bool
    wall_seconds: float
    checksum: str
    rows_path: Path
    done_path: Path


def cell_paths(cell: Cell, out_dir: Path) -> tuple[Path, Path]:
    """``(<key>.csv, <key>.done)`` under ``out_dir``.

    CSV rather than Parquet: ``pyproject.toml`` declares numpy and scipy only,
    and the brief forbids adding a dependency silently. A cell is at most 2000
    rows of scalars, so the format costs nothing in this study.
    """
    return out_dir / f"{cell.key}.csv", out_dir / f"{cell.key}.done"


def _flatten_text(array: np.ndarray) -> str:
    """A parameter block as compact JSON, so a row round-trips its own shapes."""
    return json.dumps(np.asarray(array, dtype=float).tolist(), separators=(",", ":"))


def _theta0_text(cell: Cell) -> str:
    """``mu``, ``alpha`` and ``beta`` flattened in that order, as one JSON list."""
    flat = (
        list(cell.mu)
        + [v for row in cell.alpha for v in row]
        + [v for row in cell.beta for v in row]
    )
    return json.dumps([float(v) for v in flat], separators=(",", ":"))


def quantise(times: np.ndarray, delta: float, T: float) -> np.ndarray:
    """Round timestamps to the nearest multiple of ``delta``, inside ``[0, T)``.

    ``delta = r / min(beta)`` is frozen per cell (section 5.1), so ``beta_ij *
    delta`` lands in ``[r, 1.3 r]``.

    Three decisions, none of them stated in the preregistration. All are in
    ``studies/HARNESS_NOTES.md``:

    1. **Round to nearest**, not floor. Nearest leaves a timestamp's expected
       displacement at zero; flooring would shift every event earlier by
       ``delta/2`` and add a bias that is not the one H6.4 states.
    2. **The window is not widened.** A rounded stamp is clipped to the last tick
       inside ``[0, T)``, ``floor(T/delta) * delta``, and to 0 at the bottom. Both
       are multiples of ``delta``, so the "every timestamp is a multiple" property
       survives the clip. Without it the tail of the distribution can round to or
       past ``T``; at ``c = 1e-3, r = 0.1`` the tick is 100 while ``T`` is 172, so
       the entire tail would otherwise leave the window.
    3. **The result is rounded to 12 decimals** so that a multiple of ``delta`` is
       an exact multiple in float terms, and the equality test in
       ``tests/test_study_harness.py`` is not at the mercy of a representation
       error in the multiplication.

    The clip is *not* cosmetic. It is where the frozen design stops being
    measurable, and the pilot reports it: see ``HARNESS_NOTES.md`` item Q1.
    """
    t = np.asarray(times, dtype=np.float64)
    if t.size == 0:
        return t
    tick_top = np.floor(T / delta) * delta
    if tick_top < 0.0:  # pragma: no cover - a delta wider than the window at T<0
        tick_top = 0.0
    stepped = np.round(t / delta) * delta
    np.clip(stepped, 0.0, tick_top, out=stepped)
    return np.round(stepped, 12)


def _numeric_row(row: dict[str, Any]) -> str:
    """The checksum's view of one row: the measured columns, canonically."""
    parts = []
    for name in CHECKSUM_COLUMNS:
        value = row.get(name, "")
        parts.append(f"{name}={value}")
    return "|".join(parts)


def rows_checksum(rows: list[dict[str, Any]]) -> str:
    """SHA-256 over the measured columns of every row, in replication order."""
    body = "\n".join(_numeric_row(row) for row in rows) + "\n"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _git_sha() -> str:
    """The commit this run is attributable to, or ``unknown`` outside git."""
    try:
        import subprocess

        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - environment
        return "unknown"


def read_rows(path: Path) -> list[dict[str, Any]]:
    """The rows already on disk, as dicts. Missing file is no rows."""
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def is_complete(cell: Cell, out_dir: Path) -> tuple[bool, str]:
    """Whether a cell is finished *and* its data re-verifies.

    Returns ``(complete, reason)``. A ``.done`` whose checksum does not match the
    rows beside it is **not** complete: the marker is a claim about the data, and
    a claim that fails its own check is not evidence.
    """
    csv_path, done_path = cell_paths(cell, out_dir)
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


def _empty_row(cell: Cell, rep_index: int) -> dict[str, Any]:
    return {
        "cell_key": cell.key,
        "rep_index": rep_index,
        "rep_number": rep_index + 1,
        "N_target": cell.N_target,
        "M": cell.M,
        "rho_axis": repr(cell.rho),
        "r_axis": repr(cell.r),
        "c_axis": repr(cell.c),
        "satellite": int(cell.satellite),
        "n_events": "",
        "T": repr(cell.T),
        "rep_seed": "",
        "theta0": _theta0_text(cell),
        "theta_hat": "",
        "converged": "",
        "status": "",
        "nit": "",
        "gradient_inf_norm": "",
        "loglik": "",
        "rho_hat": "",
        "se_mu": "",
        "se_alpha": "",
        "se_beta": "",
        "hessian_condition": "",
        "verdict": "",
        "bound_hit": "",
        "bound_coordinates": "",
        "failure": "",
        "sim_ms": "",
        "fit_ms": "",
        "wall_ms": "",
    }


def _one_replication(cell: Cell, rep_index: int) -> dict[str, Any]:
    """Simulate, quantise, fit, and return the row -- failure or not.

    Nothing in here raises on a fit failure. The only exceptions that escape are
    the ones that mean the *harness* is broken (a malformed cell), which is a
    different thing from an estimator that failed on a draw.
    """
    row = _empty_row(cell, rep_index)
    seed = rep_seed(cell, rep_index)
    row["rep_seed"] = seed

    mu = np.asarray(cell.mu, dtype=np.float64)
    alpha = np.asarray(cell.alpha, dtype=np.float64)
    beta = np.asarray(cell.beta, dtype=np.float64)

    started = time.perf_counter()
    try:
        times, types = simulate(
            mu,
            alpha,
            beta,
            cell.T,
            method=SIMULATOR_METHOD,
            seed=seed,
            burn_in=BURN_IN_RELAXATIONS * cell.relaxation,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        row["failure"] = f"simulate:{type(exc).__name__}:{exc}"
        row["wall_ms"] = f"{1000.0 * (time.perf_counter() - started):.3f}"
        return row
    row["sim_ms"] = f"{1000.0 * (time.perf_counter() - started):.3f}"

    if cell.delta > 0.0:
        times = quantise(times, cell.delta, cell.T)

    row["n_events"] = int(times.size)

    fit_started = time.perf_counter()
    try:
        result = fit_fn(
            times,
            types,
            M=cell.M,
            T=cell.T,
            shared_decay=False,
            zero_diagonal=False,
            se_method="hessian",
            # n_starts = 1 is the library default and the design says nothing
            # else; it is passed explicitly so the row's determinism does not
            # depend on a default that could later change. NOTE(H6).
            n_starts=1,
            seed=seed,
        )
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        row["failure"] = f"fit:{type(exc).__name__}:{exc}"
        row["fit_ms"] = f"{1000.0 * (time.perf_counter() - fit_started):.3f}"
        row["wall_ms"] = f"{1000.0 * (time.perf_counter() - started):.3f}"
        return row

    row["fit_ms"] = f"{1000.0 * (time.perf_counter() - fit_started):.3f}"
    row["wall_ms"] = f"{1000.0 * (time.perf_counter() - started):.3f}"
    row["theta_hat"] = _flatten_text(
        np.concatenate([result.mu, result.alpha.ravel(), result.beta.ravel()])
    )
    row["converged"] = int(bool(result.converged))
    row["status"] = int(result.status)
    row["nit"] = int(result.nit)
    row["gradient_inf_norm"] = repr(float(result.gradient_inf_norm))
    row["loglik"] = repr(float(result.loglik))
    row["rho_hat"] = repr(float(result.rho))
    row["hessian_condition"] = (
        "" if result.hessian_condition is None else repr(float(result.hessian_condition))
    )
    row["verdict"] = result.reliable
    row["bound_hit"] = int(bool(result.bound_hit))
    row["bound_coordinates"] = ";".join(result.bound_coordinates)

    if result.se is None:
        # A replication whose se is None counts as a coverage miss (section 3,
        # E3.5) and is counted separately as no_se_rate. The empty strings are
        # that fact, not a missing value.
        row["failure"] = "se:none"
    else:
        row["se_mu"] = _flatten_text(result.se["mu"])
        row["se_alpha"] = _flatten_text(result.se["alpha"])
        row["se_beta"] = _flatten_text(result.se["beta"])

    if not result.converged:
        row["failure"] = (row["failure"] + ";not_converged").lstrip(";")
    if not np.isfinite(result.loglik):
        row["failure"] = (row["failure"] + ";loglik_not_finite").lstrip(";")
    return row


def _write_done(
    cell: Cell,
    done_path: Path,
    *,
    requested: int,
    completed: int,
    wall_seconds: float,
    worker: str,
    checksum: str,
) -> None:
    payload = {
        "cell_key": cell.key,
        "reps_requested": requested,
        "reps_completed": completed,
        "wall_seconds": round(wall_seconds, 3),
        "worker": worker,
        "checksum": checksum,
        "git_sha": _git_sha(),
        "simulator": SIMULATOR_METHOD,
        "burn_in_relaxations": BURN_IN_RELAXATIONS,
        "quantise": "round_to_nearest" if cell.delta > 0.0 else "none",
    }
    tmp = done_path.with_suffix(".done.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, done_path)


def run_cell(
    cell: Cell,
    replications: int,
    out_dir: Path,
    *,
    force: bool = False,
    worker: str = "local",
    log: Any = None,
) -> CellResult:
    """Run ``cell`` to ``replications`` rows, resuming if it was interrupted.

    ``force`` discards whatever is on disk for this cell and starts again. Without
    it, a cell whose ``.done`` re-verifies is a no-op, and an incomplete cell
    resumes from the first missing replication.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, done_path = cell_paths(cell, out_dir)

    if not force:
        complete, reason = is_complete(cell, out_dir)
        if complete:
            done = json.loads(done_path.read_text(encoding="utf-8"))
            rows = read_rows(csv_path)
            return CellResult(
                key=cell.key,
                requested=int(done.get("reps_requested", replications)),
                completed=len(rows),
                skipped=True,
                wall_seconds=float(done.get("wall_seconds", 0.0)),
                checksum=str(done.get("checksum", "")),
                rows_path=csv_path,
                done_path=done_path,
            )
        if log is not None:
            log(f"{cell.key}: not complete ({reason}); starting or resuming")
    elif done_path.exists():
        done_path.unlink()

    existing = [] if force else read_rows(csv_path)
    if force and csv_path.exists():
        csv_path.unlink()
    if len(existing) > replications:
        existing = existing[:replications]

    started = time.perf_counter()
    mode = "a" if existing else "w"
    with csv_path.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if mode == "w":
            writer.writeheader()
            handle.flush()
        for rep_index in range(len(existing), replications):
            row = _one_replication(cell, rep_index)
            writer.writerow(row)
            # Flush per row: a crash then loses at most the row in flight, which
            # is the property the brief asks for and the one the .done checksum
            # can prove after the fact.
            handle.flush()
            os.fsync(handle.fileno())

    rows = read_rows(csv_path)[:replications]
    wall_seconds = time.perf_counter() - started
    checksum = rows_checksum(rows)
    _write_done(
        cell,
        done_path,
        requested=replications,
        completed=len(rows),
        wall_seconds=wall_seconds,
        worker=worker,
        checksum=checksum,
    )
    if log is not None:
        failures = sum(1 for r in rows if r.get("failure"))
        log(
            f"{cell.key}: {len(rows)}/{replications} rows, {failures} with a "
            f"recorded failure, {wall_seconds:.1f}s"
        )
    return CellResult(
        key=cell.key,
        requested=replications,
        completed=len(rows),
        skipped=False,
        wall_seconds=wall_seconds,
        checksum=checksum,
        rows_path=csv_path,
        done_path=done_path,
    )
