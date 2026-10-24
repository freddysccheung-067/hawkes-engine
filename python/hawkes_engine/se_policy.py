"""The ``se_method="auto"`` decision: what to do about a standard-error interval.

This module implements `docs/se_policy.md`. It does not compute a standard error
and does not touch the likelihood. It reads the shipped calibration map, decides
which of four actions applies, and returns a record that a fit stores and a user
can audit.

The four actions, in the order they are checked:

``none``
    The map says the estimator is undefined in this regime. No interval is
    reported at all.
``hessian`` (unmapped)
    The map does not cover this regime. The Hessian interval is used and labelled
    uncalibrated, because nothing measured supports anything better.
``bootstrap``
    The map is measured and an estimated block's 2-SE interval around ``q``
    excludes 1, so the direction of the miscalibration is resolved. The parametric
    bootstrap is used, if it fits in the caller's time limit.
``hessian`` (calibrated)
    The map is measured and no block is miscalibrated by that rule.

A fifth outcome shares the ``hessian`` action: a bootstrap was indicated but its
projected cost exceeded ``auto_max_seconds``. The action is recorded as
``hessian_after_limit`` so the audit shows it was not an oversight.

Everything here is a pure function of the fitted parameters, the window, and the
map, so it can be tested without running a fit.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from hawkes_engine._typing import JsonObject
from hawkes_engine.trust_map import (
    MEASURED,
    UNDEFINED,
    UNKNOWN,
    MapAnswer,
    lookup,
)

__all__ = [
    "AUTO_MAX_SECONDS",
    "BOOTSTRAP_REPLICATIONS",
    "CALIBRATION_Z",
    "AutoDecision",
    "decide",
]

# Twice the Monte Carlo standard error of the measured ratio. See
# docs/se_policy.md: a q whose 2-SE interval excludes 1 has a miscalibration
# larger than the study's own uncertainty about it, at the study's R = 2000.
CALIBRATION_Z = 2.0

# The bootstrap's replication count in auto mode. Matches the default of
# se_method="bootstrap" and the figure the capability table timed.
BOOTSTRAP_REPLICATIONS = 200

# The cost of one bootstrap replication, as a power law fitted to every serial
# row of benchmarks/results/capability_2026-10-21.md section 3 (the B = 200 runs at
# (M, N) = (2, 1e4), (2, 1e5), (4, 1e4) and (4, 1e5)). Four points, three
# parameters: per_rep = 3.722e-06 * M**2.798 * N**0.828 seconds. It reproduces
# each of the four measured rows within 3 percent, and tests/test_auto.py pins
# that.
#
# A projection from the fit time instead was tried and rejected: a refit starts at
# the fitted parameters and converges in a few iterations, so its cost is not the
# cost of a fit, and a fit-time model over-projected the 2000-event case by a
# factor of seven. A model linear in N could not describe M = 2 and M = 4 at the
# same time, because the core's per-event cost grows with M**2.
CALIBRATION_NOTE = "benchmarks/results/capability_2026-10-21.md, section 3"
_REPLICATION_PREFACTOR = 3.722e-06
_REPLICATION_EXP_M = 2.7981
_REPLICATION_EXP_N = 0.8279
_MEASURED_ROWS = (
    # (M, N, measured serial seconds for B = 200)
    (2, 9_669, 10.58),
    (2, 100_505, 69.95),
    (4, 9_560, 69.38),
    (4, 100_233, 510.08),
)

# Measured parallel efficiency, as the ratio of a pool's per-replication cost to
# one worker's. It is not 1/workers, and pretending it is would project 86 s as
# 21 s: the table shows four workers buying 3.6x at M = 4, N = 1e5 but 5.7x at
# M = 4, N = 1e4, and the 24-process default pool buying 5.9x on the first.
_FOUR_WORKER_EFFICIENCY = 0.691 / (510.08 / 200.0)  # 0.271
_DEFAULT_POOL_EFFICIENCY = 86.42 / 510.08  # 0.169, measured on 24 logical cores

# From this worker count up the projection uses the measured default-pool
# efficiency, because a pool that size was measured and anything between four and
# the default was not.
_DEFAULT_POOL_THRESHOLD = 8

# The default ceiling on a switch's projected cost. It admits the measured
# M = 4, N = 1e5 bootstrap on the default 24-process pool (86.42 s) and refuses it
# on one worker (510.08 s). A user who needs the larger run raises it explicitly.
AUTO_MAX_SECONDS = 120.0

# The blocks the policy can test. A block the caller fixed is not estimated and is
# skipped: its standard error is exactly zero, and a ratio against zero spread
# says nothing about the method.
_BLOCKS = ("mu", "alpha", "beta")

_ACTION_LABELS = {
    "none": "none",
    "hessian_unmapped": "hessian",
    "hessian_calibrated": "hessian",
    "hessian_after_limit": "hessian",
    "bootstrap": "bootstrap",
}


@dataclass(frozen=True)
class AutoDecision:
    """What the policy decided, what it read, and what it cost.

    Every field is JSON-serialisable, so the record survives ``to_dict`` without a
    conversion layer.

    Attributes
    ----------
    action
        One of ``"none"``, ``"hessian_unmapped"``, ``"hessian_calibrated"``,
        ``"hessian_after_limit"``, ``"bootstrap"``. The first two words name the
        method that was used; the suffix says why.
    se_source
        ``"hessian"``, ``"bootstrap"`` or ``"none"``. This is the field a caller
        reads when it does not care why.
    note
        One sentence. It is the ``se_note`` on the result unless a later failure
        replaces it.
    status, cell, distance
        The map's answer: ``"measured"``, ``"unknown"``, ``"estimator undefined in
        this regime"``; the nearest cell key; the distance in grid steps.
    q, se_q
        Per estimated block, the measured ratio and its bootstrap SE. Empty when
        the map did not answer with numbers.
    threshold
        ``CALIBRATION_Z``, recorded so the record states the rule it applied.
    firing_blocks
        The estimated blocks whose 2-SE interval excluded 1, with the direction.
    projected_seconds, max_seconds
        The cost estimate for this bootstrap and the limit it was compared with.
        ``None`` when no bootstrap was considered.
    """

    action: str
    se_source: str
    note: str
    status: str
    cell: str | None
    distance: float | None
    q: dict[str, float]
    se_q: dict[str, float]
    threshold: float
    firing_blocks: tuple[tuple[str, str], ...]
    projected_seconds: float | None
    max_seconds: float | None

    def to_dict(self) -> JsonObject:
        return {
            "action": self.action,
            "se_source": self.se_source,
            "note": self.note,
            "status": self.status,
            "cell": self.cell,
            "distance": self.distance,
            "q": dict(self.q),
            "se_q": dict(self.se_q),
            "threshold": self.threshold,
            "firing_blocks": [list(pair) for pair in self.firing_blocks],
            "projected_seconds": self.projected_seconds,
            "max_seconds": self.max_seconds,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AutoDecision:
        return cls(
            action=str(payload["action"]),
            se_source=str(payload["se_source"]),
            note=str(payload["note"]),
            status=str(payload["status"]),
            cell=None if payload.get("cell") is None else str(payload["cell"]),
            distance=None if payload.get("distance") is None else float(payload["distance"]),
            q={str(k): float(v) for k, v in dict(payload.get("q", {})).items()},
            se_q={str(k): float(v) for k, v in dict(payload.get("se_q", {})).items()},
            threshold=float(payload.get("threshold", CALIBRATION_Z)),
            firing_blocks=tuple(
                (str(pair[0]), str(pair[1])) for pair in payload.get("firing_blocks", [])
            ),
            projected_seconds=None
            if payload.get("projected_seconds") is None
            else float(payload["projected_seconds"]),
            max_seconds=None
            if payload.get("max_seconds") is None
            else float(payload["max_seconds"]),
        )


def _pool_workers(workers: int | None) -> int:
    """The number of processes the bootstrap would actually use.

    ``parametric_bootstrap`` passes ``workers`` straight to
    ``ProcessPoolExecutor``, whose ``None`` means the machine's CPU count. The
    projection has to use the same number or it is not a projection of this run.
    """
    if workers is not None:
        return max(1, int(workers))
    try:
        return max(1, len(os.sched_getaffinity(0)))  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - Windows and macOS have no affinity call
        return max(1, os.cpu_count() or 1)


def project_seconds(n_bootstrap: int, M: int, N: int, workers: int | None = None) -> float:
    """Projected wall time of a bootstrap of ``n_bootstrap`` replications.

    The projection is the capability table's measured cost, as a power law in
    ``(M, N)``, times the measured pool efficiency. Both are measurements from one
    machine, and the docstring that publishes the figure says so; the default
    limit is set from them rather than from a guess.

    It is a projection, not a bound. It fits the four measured serial rows to
    within 3 percent, so inside the measured box it is as accurate as a projection
    can be. Outside it (M >= 6, N above 1e5) nothing was timed and the number is an
    extrapolation of a fitted surface; ``auto`` still refuses to exceed the limit,
    but a caller relying on the figure at M = 8 should read it as an order of
    magnitude.
    """
    per_rep = (
        _REPLICATION_PREFACTOR
        * (max(int(M), 1) ** _REPLICATION_EXP_M)
        * (max(int(N), 1) ** _REPLICATION_EXP_N)
    )
    pool = _pool_workers(workers)
    if workers is None or pool >= _DEFAULT_POOL_THRESHOLD:
        efficiency = _DEFAULT_POOL_EFFICIENCY
    elif pool == 1:
        efficiency = 1.0
    else:
        # Two to seven workers: interpolate toward the four-worker measurement,
        # the only intermediate point that was timed.
        efficiency = 1.0 + (_FOUR_WORKER_EFFICIENCY - 1.0) * (pool - 1) / 3.0
        efficiency = max(efficiency, _FOUR_WORKER_EFFICIENCY)
    return float(n_bootstrap) * float(per_rep) * float(efficiency)


def _seconds(value: float) -> str:
    """A projected cost, at a precision that never rounds a real wait to zero."""
    return f"{value:.1f}" if value < 10.0 else f"{value:.0f}"


def _firing_blocks(answer: MapAnswer, free: dict[str, bool]) -> tuple[tuple[str, str], ...]:
    """Estimated blocks whose 2-SE interval around q excludes 1, and the direction."""
    if answer.q is None:
        return ()
    firing: list[tuple[str, str]] = []
    for block in _BLOCKS:
        if not free.get(block, True):
            continue
        pair = answer.q.get(block)
        if pair is None:
            continue
        q, se = pair
        if not (math.isfinite(q) and math.isfinite(se)):
            continue
        if q + CALIBRATION_Z * se < 1.0:
            firing.append((block, "narrow"))
        elif q - CALIBRATION_Z * se > 1.0:
            firing.append((block, "wide"))
    return tuple(firing)


def _describe(firing: tuple[tuple[str, str], ...]) -> str:
    return ", ".join(f"{block} ({direction})" for block, direction in firing)


def decide(
    *,
    N: int,
    rho_hat: float,
    beta_min: float,
    T: float,
    resolution: float = 0.0,
    M: int = 2,
    free: dict[str, bool] | None = None,
    n_bootstrap: int = BOOTSTRAP_REPLICATIONS,
    auto_max_seconds: float | None = AUTO_MAX_SECONDS,
    workers: int | None = None,
    rows: list[dict[str, str]] | None = None,
) -> AutoDecision:
    """Choose the standard-error method for a fitted regime.

    Parameters
    ----------
    N, rho_hat, beta_min, T, resolution, M
        The fitted regime, in the coordinates :func:`hawkes_engine.trust_lookup`
        takes. ``beta_min`` is the smallest fitted decay rate.
    free
        Which blocks the caller estimated. ``{"mu": True, "alpha": False, ...}``.
        ``None`` treats every block as estimated, which is the common case.
    n_bootstrap
        Replications the bootstrap would run.
    auto_max_seconds
        Ceiling on the projected cost. ``None`` removes the ceiling.
    workers
        Process count the pool would use; ``None`` means the machine's count.
    rows
        Map rows, for tests. ``None`` loads the shipped map.

    Returns
    -------
    AutoDecision
        The action, the method, one sentence of justification, and the evidence
        the decision read.
    """
    free = {"mu": True, "alpha": True, "beta": True} if free is None else dict(free)
    answer = lookup(N=N, rho_hat=rho_hat, beta=beta_min, T=T, resolution=resolution, M=M, rows=rows)
    q = {b: pair[0] for b, pair in (answer.q or {}).items() if b in _BLOCKS}
    se_q = {b: pair[1] for b, pair in (answer.q or {}).items() if b in _BLOCKS}

    if answer.status == UNDEFINED:
        rate = answer.no_se_rate
        axis = "beta_min*T" if rate is not None and rate < 0.5 else "no_se_rate"
        detail = (
            f"the nearest measured cell returns a usable standard error in only "
            f"{100.0 * (1.0 - rate):.1f} percent of replications"
            if rate is not None
            else "the nearest measured cell holds too few decay times"
        )
        return AutoDecision(
            action="none",
            se_source="none",
            note=(
                f"the calibration map reports the estimator undefined in this regime "
                f"({detail}); the failing axis is {axis} and no interval is reported"
            ),
            status=answer.status,
            cell=answer.cell,
            distance=answer.distance,
            q=q,
            se_q=se_q,
            threshold=CALIBRATION_Z,
            firing_blocks=(),
            projected_seconds=None,
            max_seconds=None,
        )

    if answer.status == UNKNOWN:
        return AutoDecision(
            action="hessian_unmapped",
            se_source="hessian",
            note=(
                "no measured calibration for this regime; the interval is "
                "uncalibrated and no bootstrap was run, because none would carry "
                "a measured property"
            ),
            status=answer.status,
            cell=answer.cell,
            distance=answer.distance,
            q=q,
            se_q=se_q,
            threshold=CALIBRATION_Z,
            firing_blocks=(),
            projected_seconds=None,
            max_seconds=None,
        )

    assert answer.status == MEASURED
    firing = _firing_blocks(answer, free)
    if not firing:
        return AutoDecision(
            action="hessian_calibrated",
            se_source="hessian",
            note=(
                "the calibration map's 2-SE intervals around q all contain 1 for the "
                "estimated blocks; the Hessian interval is used"
            ),
            status=answer.status,
            cell=answer.cell,
            distance=answer.distance,
            q=q,
            se_q=se_q,
            threshold=CALIBRATION_Z,
            firing_blocks=(),
            projected_seconds=None,
            max_seconds=None,
        )

    projected = project_seconds(n_bootstrap, M, N, workers)
    if auto_max_seconds is not None and projected > auto_max_seconds:
        return AutoDecision(
            action="hessian_after_limit",
            se_source="hessian",
            note=(
                f"a bootstrap was indicated by {_describe(firing)} but projected to "
                f"cost {_seconds(projected)} s, above auto_max_seconds = "
                f"{_seconds(auto_max_seconds)}; the uncalibrated Hessian interval is used"
            ),
            status=answer.status,
            cell=answer.cell,
            distance=answer.distance,
            q=q,
            se_q=se_q,
            threshold=CALIBRATION_Z,
            firing_blocks=firing,
            projected_seconds=projected,
            max_seconds=auto_max_seconds,
        )

    return AutoDecision(
        action="bootstrap",
        se_source="bootstrap",
        note=(
            f"the calibration map's 2-SE interval around q excludes 1 for "
            f"{_describe(firing)}; bootstrap standard errors replace the Hessian's, "
            f"projected at {_seconds(projected)} s"
        ),
        status=answer.status,
        cell=answer.cell,
        distance=answer.distance,
        q=q,
        se_q=se_q,
        threshold=CALIBRATION_Z,
        firing_blocks=firing,
        projected_seconds=projected,
        max_seconds=auto_max_seconds,
    )
