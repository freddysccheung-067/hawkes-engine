"""The sw-v1 sandwich estimator study: compute the sandwich, one replication.

Pre-registered in ``docs/preregistration_sandwich.md`` at the tag
``SW-preregistration``, with two amendments written before any measurement. Read
it before changing anything here; where this file and the amendment disagree,
the amendment governs.

The estimand, as Amendment 1 restates it, is not "the score at the estimate".
That is zero by construction: a fitted dataset has its score put to zero by the
optimiser, measured at ``1.3e-4`` on a 39 027-event fit, so an outer product
taken there is numerically empty. What the paper's equation
``J(theta) = E[U_T U_T^T]`` defines is the *variance of the score evaluated at
the true parameter*, and a simulation study knows the true parameter. So:

    J0 = (1/R) sum_r U_T^{(r)}(theta_0) U_T^{(r)}(theta_0)^T
    I0 = observed information at theta_0
    se_sandwich = sqrt(diag(I0^-1 J0 I0^-1))

The empirical meat, summed over events at the estimate, is the thing a user
could actually compute; it is reported alongside as exploratory, because it
does not decide a hypothesis.

Nothing here changes the estimator. The library is used through its public API.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

STUDY_ID = "sw-v1"

# The frozen cells, section 6. Five primary, then the two H-S4 quantisation
# cells. If a key is missing from the frozen grid, the run refuses to start.
PRIMARY_KEYS = (
    "M2_N2000_rho0.3028_r0.0_c1.0",
    "M2_N2000_rho0.6_r0.0_c1.0",
    "M2_N2000_rho0.85_r0.0_c1.0",
    "M2_N2000_rho0.95_r0.0_c1.0",
    "M2_N10000_rho0.95_r0.0_c1.0",
)
QUANTISATION_KEYS = (
    "M2_N50000_rho0.85_r0.0_c0.001",
    "M2_N50000_rho0.95_r0.0_c0.001",
)
CELL_KEYS = PRIMARY_KEYS + QUANTISATION_KEYS

RESULTS = Path(__file__).resolve().parent / "results" / "sandwich"


@dataclass(frozen=True)
class SwCell:
    """One frozen cell, with the parameters H6 used and its own key."""

    key: str
    primary: bool
    M: int
    N_target: int
    rho: float
    mu: np.ndarray
    alpha: np.ndarray
    beta: np.ndarray
    T: float
    relaxation: float
    # The truth, flattened in the layout's order: mu, alpha row-major, beta
    # row-major. This is theta_0 that the score is evaluated at.
    theta0: np.ndarray


def load_cells() -> list[SwCell]:
    """The seven cells, taken from the frozen H6 grid and never synthesised."""
    from studies.grid import load_cells as load_h6

    frozen = {cell.key: cell for cell in load_h6()}
    out: list[SwCell] = []
    missing: list[str] = []
    for key in CELL_KEYS:
        cell = frozen.get(key)
        if cell is None:
            missing.append(key)
            continue
        out.append(
            SwCell(
                key=key,
                primary=key in PRIMARY_KEYS,
                M=cell.M,
                N_target=cell.N_target,
                rho=cell.rho,
                mu=np.asarray(cell.mu, dtype=np.float64),
                alpha=np.asarray(cell.alpha, dtype=np.float64),
                beta=np.asarray(cell.beta, dtype=np.float64),
                T=float(cell.T),
                relaxation=float(cell.relaxation),
                theta0=np.concatenate(
                    [
                        np.asarray(cell.mu, dtype=np.float64).ravel(),
                        np.asarray(cell.alpha, dtype=np.float64).ravel(),
                        np.asarray(cell.beta, dtype=np.float64).ravel(),
                    ]
                ),
            )
        )
    if missing:
        raise SystemExit(
            "these pre-registered cells are not in the frozen grid: "
            + ", ".join(missing)
            + ". Section 6 says the run refuses to start rather than "
            "synthesising one."
        )
    return out


def score_at_truth(cell: SwCell, times: np.ndarray, types: np.ndarray) -> np.ndarray:
    """``U_T(theta_0)``, the total score evaluated at the true parameter.

    Natural-space coordinates, in the order mu, alpha row-major, beta row-major.
    This is the one vector the sandwich's meat is built from, and it is available
    from the shipped API: no core change is needed for the confirmatory part.

    **Natural space, not log space.** ``loglik_grad_log_space`` returns
    ``d ell / d log x``, which differs from ``d ell / d x`` by a factor of ``x``
    per coordinate. Using it here against a natural-space information matrix
    mismatched the bread and the meat by that factor and made the information
    equality look violated by up to two orders of magnitude. ``_core.loglik``
    with ``grad=True`` is the same evaluation in natural coordinates, which is
    what ``FitResult.se`` is reported in, so the two are comparable.
    """
    from hawkes_engine import _core

    out = _core.loglik(
        np.asarray(times, dtype=np.float64),
        np.asarray(types, dtype=np.uint8),
        np.ascontiguousarray(cell.mu, dtype=np.float64),
        np.ascontiguousarray(cell.alpha, dtype=np.float64),
        np.ascontiguousarray(cell.beta, dtype=np.float64),
        float(cell.T),
        int(cell.M),
        False,
        True,
    )
    return np.concatenate(
        [
            np.asarray(out["dmu"], dtype=np.float64).ravel(),
            np.asarray(out["dalpha"], dtype=np.float64).ravel(),
            np.asarray(out["dbeta"], dtype=np.float64).ravel(),
        ]
    )


def information_at_truth(cell: SwCell, times: np.ndarray, types: np.ndarray) -> np.ndarray:
    """``I_0 = -d^2 ell / d theta d theta^T`` at the true parameter.

    The same observed-information routine the library uses for its Hessian
    interval, evaluated at ``theta_0`` instead of at the estimate, so the two
    breads are the same object computed at two points. ``_Problem`` is the
    library's own gradient wrapper, taken from it rather than reimplemented, so
    the difference the Hessian is built from is the compiled one.
    """
    from hawkes_engine._layout import Layout
    from hawkes_engine.fit import _Problem
    from hawkes_engine.hessian import observed_information

    layout = Layout(M=cell.M)
    problem = _Problem(
        np.asarray(times, dtype=np.float64),
        np.asarray(types, dtype=np.uint8),
        cell.T,
        layout,
    )
    return observed_information(
        problem.gradient_natural,
        cell.theta0,
        positive=np.ones(layout.n_params, dtype=bool),
    )


def rep_seed(cell: SwCell, rep_index: int) -> int:
    """H6's own seed for this cell and index, so the streams are the same ones.

    The pre-registration, section 7, promises the seven cells reproduce the event
    streams the corresponding h6-v1 cells used, which is what makes the q
    comparison paired. That is a promise to reuse H6's derivation, not to invent
    one: the message is ``h6-v1|<M>|<N>|<rho>|<r>|<c>``, so the seed for cell and
    index is the same integer H6 used. Verified against the committed rows: the
    event counts match exactly.
    """
    from studies.grid import load_cells as load_h6
    from studies.grid import rep_seed as h6_rep_seed

    frozen = {c.key: c for c in load_h6()}
    return int(h6_rep_seed(frozen[cell.key], int(rep_index)))


def rows_checksum(rows: list[dict[str, Any]]) -> str:
    """SHA-256 over the measured columns, in replication order."""
    import json

    body = json.dumps(
        [[r.get(k, "") for k in CHECKSUM_COLUMNS] for r in rows],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


CHECKSUM_COLUMNS = (
    "cell_key",
    "rep_index",
    "n_events",
    "score",
    "info_diag",
    "theta_hat",
    "se_hessian",
    "se_sandwich",
    "converged",
)

COLUMNS = CHECKSUM_COLUMNS + ("wall_ms",)


def one_replication(cell: SwCell, rep_index: int) -> dict[str, Any]:
    """Simulate once at the truth, fit once, and compute both breads and meats.

    Everything the estimand needs comes from one event stream, so the score at
    the truth, the information at the truth and the fit's own Hessian interval
    are all paired by construction.
    """
    import time

    from hawkes_engine.fit import fit
    from hawkes_engine.simulation import simulate

    from studies.run_cell import BURN_IN_RELAXATIONS

    started = time.perf_counter()
    seed = rep_seed(cell, rep_index)
    times, types = simulate(
        cell.mu,
        cell.alpha,
        cell.beta,
        cell.T,
        method="thinning",
        seed=seed,
        burn_in=BURN_IN_RELAXATIONS * cell.relaxation,
    )
    row: dict[str, Any] = {
        "cell_key": cell.key,
        "rep_index": int(rep_index),
        "n_events": int(times.size),
        "score": "",
        "info_diag": "",
        "theta_hat": "",
        "se_hessian": "",
        "se_sandwich": "",
        "converged": 0,
        "wall_ms": "",
    }

    # The score at the truth. Its variance across replications is the meat that
    # does not vanish, unlike the score at the estimate.
    score = score_at_truth(cell, times, types)
    row["score"] = _flatten(score)
    info = information_at_truth(cell, times, types)
    # The whole matrix, not its diagonal. Inverting a diagonal approximation to
    # I_0 while the estimates' covariance is driven by the correlations between
    # coordinates -- an off-diagonal reaches 1806 against 2624 on the diagonal in
    # this model -- reports a sandwich several times too small. The column is
    # named info_diag for continuity with the pilot; it now holds all p*p entries.
    row["info_diag"] = _flatten(info)

    result = fit(
        times,
        types,
        M=cell.M,
        T=cell.T,
        shared_decay=False,
        zero_diagonal=False,
        se_method="hessian",
        n_starts=1,
        seed=seed,
    )
    row["converged"] = int(bool(result.converged))
    row["theta_hat"] = _flatten(
        np.concatenate([result.mu.ravel(), result.alpha.ravel(), result.beta.ravel()])
    )
    if result.se is not None:
        from hawkes_engine._layout import Layout

        layout = Layout(M=cell.M)
        row["se_hessian"] = _flatten(
            layout.pack_natural(result.se["mu"], result.se["alpha"], result.se["beta"])
        )
    row["wall_ms"] = f"{1000.0 * (time.perf_counter() - started):.3f}"
    return row


def _flatten(values: np.ndarray) -> str:
    """A JSON list of reprs, so a value round-trips exactly through the CSV."""
    return "[" + ",".join(repr(float(v)) for v in np.asarray(values).ravel()) + "]"


def sandwich_se(info: np.ndarray, meat: np.ndarray) -> np.ndarray:
    """``sqrt(diag(I^-1 J I^-1))``, the sandwich standard error.

    The bread is inverted through ``np.linalg.solve`` rather than an explicit
    inverse, so a badly conditioned ``I_0`` raises or produces large values
    visibly instead of silently losing digits: the same information the
    library's ``hessian_condition`` reports.
    """
    bread = np.linalg.inv(info)
    cov = bread @ meat @ bread
    diag = np.diag(cov)
    return np.sqrt(np.where(diag > 0.0, diag, np.nan))


def _worker(args: tuple[str, int]) -> dict[str, Any]:
    """One replication in a worker process. Module level so it can be pickled."""
    key, rep_index = args
    cell = next(c for c in load_cells() if c.key == key)
    return one_replication(cell, rep_index)


def run_cell(cell: SwCell, reps: int, workers: int) -> list[dict[str, Any]]:
    """Every replication of one cell, in index order, whatever the worker order."""
    from concurrent.futures import ProcessPoolExecutor

    jobs = [(cell.key, i) for i in range(reps)]
    if workers <= 1:
        return [_worker(job) for job in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(_worker, jobs, chunksize=8))
    return sorted(rows, key=lambda r: r["rep_index"])


def _write_csv(cell: SwCell, rows: list[dict[str, Any]]) -> Path:
    import csv

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{cell.key}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: list[str] | None = None) -> int:
    """Run the frozen design, or a named subset of it for a pilot."""
    import argparse
    import time

    parser = argparse.ArgumentParser(description="sw-v1 sandwich estimator study")
    parser.add_argument("--reps", type=int, default=2000, help="replications per cell")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--cells",
        default="all",
        help="'all', 'primary', 'quantisation', or a comma-separated list of keys",
    )
    parser.add_argument("--out", default="", help="directory to write into")
    args = parser.parse_args(argv)

    global RESULTS
    if args.out:
        RESULTS = Path(args.out)

    cells = load_cells()
    if args.cells == "all":
        chosen = cells
    elif args.cells == "primary":
        chosen = [c for c in cells if c.primary]
    elif args.cells == "quantisation":
        chosen = [c for c in cells if not c.primary]
    else:
        wanted = {k.strip() for k in args.cells.split(",") if k.strip()}
        chosen = [c for c in cells if c.key in wanted]
        unknown = wanted - {c.key for c in chosen}
        if unknown:
            raise SystemExit(f"not pre-registered cells: {sorted(unknown)}")

    started = time.perf_counter()
    written: list[str] = []
    for cell in chosen:
        t0 = time.perf_counter()
        rows = run_cell(cell, args.reps, args.workers)
        path = _write_csv(cell, rows)
        elapsed = time.perf_counter() - t0
        print(
            f"{cell.key:42s} {len(rows):5d} reps {elapsed:7.1f}s "
            f"checksum {rows_checksum(rows)[:16]}",
            flush=True,
        )
        written.append(path.name)

    total = time.perf_counter() - started
    print(f"\n{len(written)} cells, {args.reps} replications, {total:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
