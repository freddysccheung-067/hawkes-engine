"""Measured coverage and SE honesty from the H6 study, looked up by regime.

This is the H6 calibration map (study ``h6-v1``, preregistration tag
``H6-preregistration``). It is **separate** from :mod:`hawkes_engine.trust`,
whose conditioning verdict is a statement about one fit. This module reports
what was **measured** over 2000 simulated replications in the grid cell nearest
the query, and how far the query is from that cell. It is not a guarantee about
the query's own fit.

The measured box is ``M = 2`` (plus the ``M = 4`` satellite), pair decay,
``rho <= 0.95``, ``200 <= N <= 50 000``, ``beta * delta <= 0.13``, with
``beta_min * T`` inside the range the grid measured. A fitted ``rho`` below the
lowest grid value (0.3028) is answered from the nearest cell, and the reported
distance says how far that is. Outside it the answer is ``"unknown"``. In a cell where the estimator
is undefined (unresolved ticks, or most fits returning no standard error) the
answer is ``"estimator undefined in this regime"`` and carries no coverage
number.

The map is a CSV in the repository at ``data/trust/v1_excitation_only.csv``;
reading it needs only the standard library. CSV rather than Parquet so that the
runtime dependencies stay numpy and scipy. ``MAP_PATH`` resolves inside a source
checkout; the wheel does not yet carry the file (``wheel.packages`` lists only the
package directory), so an installed build must pass ``rows=load_map(path)``.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

__all__ = ["MAP_PATH", "STUDY_ID", "MapAnswer", "load_map", "lookup"]

STUDY_ID = "h6-v1"
MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "trust" / "v1_excitation_only.csv"

UNKNOWN = "unknown"
UNDEFINED = "estimator undefined in this regime"
MEASURED = "measured"

# The grid's axes. A query is placed on each axis by its position between grid
# values; the distance reported is in these coordinates.
_N_AXIS = (200.0, 1000.0, 2000.0, 10000.0, 50000.0)
_RHO_AXIS = (0.3028, 0.60, 0.85, 0.95)
_R_AXIS = (0.0, 0.01, 0.1)


@dataclass(frozen=True)
class MapAnswer:
    """What the map can say about a regime, and how far away it measured it."""

    status: str
    cell: str | None
    distance: float | None
    coverage: dict[str, tuple[float, float]] | None
    q: dict[str, tuple[float, float]] | None
    convergence_rate: float | None
    no_se_rate: float | None
    study_id: str
    note: str


def load_map(path: Path = MAP_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ids = {row["study_id"] for row in rows}
    if ids != {STUDY_ID}:
        raise ValueError(f"map study_id is {sorted(ids)}, expected {STUDY_ID!r}")
    return rows


def _float(text: str) -> float:
    return float(text) if text not in ("", None) else math.nan


def _distance(row: dict[str, str], N: float, rho: float, r: float, beta_T: float) -> float:
    """Euclidean distance in grid-step units on (log10 N, rho, r, log10 beta_min T).

    Each axis is divided by a typical grid step (log10 N by log10 5, rho by 0.25,
    r by 0.1, log10 beta T by 1), so a distance of 1 is about one grid step. The
    fourth axis is what separates the ``c = 1`` cells from the ``c = 1e-3`` cells
    at the same ``(N, rho, r)``: their windows hold 1000 times fewer decay times.
    """
    dN = (math.log10(N) - math.log10(_float(row["N"]))) / math.log10(5.0)
    dr = (rho - _float(row["rho"])) / 0.25
    dq = (r - _float(row["r"])) / 0.1
    db = math.log10(beta_T) - math.log10(_float(row["beta_min_T"]))
    return math.sqrt(dN * dN + dr * dr + dq * dq + db * db)


def lookup(
    N: float,
    rho_hat: float,
    beta: float,
    T: float,
    resolution: float = 0.0,
    *,
    M: int = 2,
    rows: list[dict[str, str]] | None = None,
) -> MapAnswer:
    """The measured cell nearest to a fitted model's regime.

    Parameters
    ----------
    N
        Number of events the model was fitted to.
    rho_hat
        The fitted branching ratio.
    beta
        The smallest fitted decay rate, the decay scale of the slowest kernel.
    T
        The observation window.
    resolution
        Timestamp resolution in the same units as ``T``; 0 for exact times.
    M
        Number of event types. Only 2 (and 4, the satellite) were measured.

    Returns
    -------
    MapAnswer
        ``status`` is ``"measured"``, ``"unknown"`` or
        ``"estimator undefined in this regime"``. Coverage and ``q`` are given
        only when measured, each as ``(estimate, Monte Carlo SE)`` per block, with
        the distance to the cell they were measured in.
    """
    rows = load_map() if rows is None else rows
    beta_T = beta * T
    r = beta * resolution

    def unknown(note: str) -> MapAnswer:
        return MapAnswer(UNKNOWN, None, None, None, None, None, None, STUDY_ID, note)

    if M not in (2, 4):
        return unknown(f"M = {M} was not measured (only M = 2 and the M = 4 satellite)")
    if not 0.0 < rho_hat <= 0.95:
        return unknown(f"rho = {rho_hat:g} is outside (0, 0.95]")
    if not 200 <= N <= 50000:
        return unknown(f"N = {N:g} is outside the measured range [200, 50000]")
    if beta <= 0 or T <= 0:
        return unknown("beta and T must be positive")
    if not 0.0 <= r <= 0.13:
        return unknown(f"beta * delta = {r:g} is outside the measured range [0, 0.13]")
    candidates = [row for row in rows if int(row["M"]) == M]
    lo = min(_float(row["beta_min_T"]) for row in candidates)
    hi = max(_float(row["beta_min_T"]) for row in candidates)
    if not lo <= beta_T <= hi:
        return unknown(f"beta * T = {beta_T:g} is outside the measured range [{lo:g}, {hi:g}]")
    best = min(candidates, key=lambda row: _distance(row, N, rho_hat, r, beta_T))
    dist = _distance(best, N, rho_hat, r, beta_T)
    undefined = best["estimator_undefined"] == "1"
    cov: dict[str, tuple[float, float]] | None = None
    q: dict[str, tuple[float, float]] | None = None
    if not undefined:
        blocks = ("mu", "alpha", "beta", "all")
        cov = {b: (_float(best[f"{b}_cov_all"]), _float(best[f"{b}_se_cov_all"])) for b in blocks}
        q = {b: (_float(best[f"{b}_q"]), _float(best[f"{b}_se_q_boot"])) for b in blocks}
    return MapAnswer(
        status=UNDEFINED if undefined else MEASURED,
        cell=best["cell"],
        distance=dist,
        coverage=cov,
        q=q,
        convergence_rate=_float(best["convergence_rate"]),
        no_se_rate=_float(best["no_se_rate"]),
        study_id=STUDY_ID,
        note=(
            "the nearest measured cell returns no usable standard error in most "
            "replications, or holds too few ticks; no coverage is reported"
            if undefined
            else "measured over 2000 replications at the nearest grid cell; coverage "
            "counts a missing standard error as a miss"
        ),
    )
