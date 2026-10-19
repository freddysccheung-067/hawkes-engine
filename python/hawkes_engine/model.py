"""The result object a fit returns.

A ``FitResult`` is frozen because it is a statement about a finished
computation, not a workbook. Everything in it was measured or derived at the
moment of the fit; nothing is recomputed lazily, so serialising it is exact and
two fits with the same inputs produce equal objects.

Spaces are named on every field that could be misread. ``hessian`` is the
observed information in **natural** space; ``cov`` is the covariance in
**log** space, because that is the space the optimizer stepped in and the space
in which the excitation parameters are comparable; ``se`` is back in **natural**
space, because that is the space the user writes parameters in. The three are
related by delta-method transforms, and a silent mix-up between them is the
most likely defect in an estimator of this kind, so the names are explicit and
the conversions happen in exactly one place (:mod:`hawkes_engine.hessian`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from hawkes_engine._typing import FloatArray, JsonObject

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FitResult:
    """A maximum-likelihood fit and everything known about its trustworthiness.

    Attributes
    ----------
    mu, alpha, beta
        Natural-space estimates. ``alpha`` is ``(M, M)`` row = target, column =
        source (ADR-002). ``beta`` is ``(M, M)`` or ``(M,)`` when the decay is
        shared, in which case ``beta_ij = beta_j``.
    loglik
        The log-likelihood at the estimate.
    converged
        The optimizer finished *and* the recomputed log-space gradient is
        within the convergence tolerance. ``status`` and ``nit`` are scipy's.
    gradient_inf_norm
        ``||d ell / d theta||_inf`` at the returned point, recomputed here
        rather than read from the optimizer's last call.
    rho
        Spectral radius of the branching matrix ``Gamma = alpha / beta``.
    rho_ci
        Delta-method 95% interval for ``rho``, or ``None`` when the covariance
        is unavailable. It is a first-order interval and is not valid at a
        boundary; it is reported because ``rho`` is the headline number and an
        interval is more honest than a point even when it is approximate.
    se, cov
        ``cov`` is the log-space covariance of the free parameters; ``se`` maps
        ``"mu"``, ``"alpha"``, ``"beta"`` to natural-space standard errors of
        the same shape as the estimates. Both are ``None`` when the information
        matrix is not invertible to the stated tolerance — never a number the
        library does not believe.
    hessian
        Observed information ``-d2 ell / d theta2`` in natural space over the
        free parameters, in :class:`~hawkes_engine._layout.Layout` order.
    hessian_condition
        ``cond(H)`` from the singular values, not the ratio of diagonal entries.
    reliable
        One of ``"reliable"``, ``"marginal"``, ``"unreliable"``, ``"unknown"``.
        This states whether the fit converged and is well conditioned. It does
        **not** state whether the estimator is unbiased or whether an interval
        covers at the nominal rate; those are properties of the estimator, not
        of this fit, and are the subject of the pre-registered study at H6.
    notes
        One line per reason a field is ``None``, non-finite, or not to be
        trusted. Empty when there is nothing to say.
    data
        The inputs and derived summaries: ``n_events``, ``T``, ``M``,
        ``shared_decay``, ``seed``, ``zero_diagonal``, ``residual_gaps_summary``.
    """

    mu: FloatArray
    alpha: FloatArray
    beta: FloatArray
    loglik: float
    converged: bool
    status: int
    nit: int
    gradient_inf_norm: float
    n_params: int
    rho: float
    rho_ci: tuple[float, float] | None
    se: dict[str, FloatArray] | None
    cov: FloatArray | None
    hessian: FloatArray | None
    hessian_condition: float | None
    reliable: str
    notes: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
    bound_hit: bool = False
    bound_coordinates: tuple[str, ...] = ()
    theta: FloatArray | None = None

    def __repr__(self) -> str:
        m = self.data.get("M", self.mu.size)
        conv = "converged" if self.converged else f"not converged (status {self.status})"
        return (
            f"FitResult(M={m}, n_params={self.n_params}, loglik={self.loglik:.6g}, "
            f"rho={self.rho:.6g}, {conv}, reliable={self.reliable!r})"
        )

    def to_dict(self) -> JsonObject:
        """A JSON-serialisable mapping. Stable: see ``SCHEMA_VERSION``."""
        return {
            "schema": SCHEMA_VERSION,
            "mu": self.mu.tolist(),
            "alpha": self.alpha.tolist(),
            "beta": self.beta.tolist(),
            "loglik": self.loglik,
            "converged": self.converged,
            "status": self.status,
            "nit": self.nit,
            "gradient_inf_norm": self.gradient_inf_norm,
            "n_params": self.n_params,
            "rho": self.rho,
            "rho_ci": None if self.rho_ci is None else list(self.rho_ci),
            "se": None if self.se is None else {k: v.tolist() for k, v in self.se.items()},
            "cov": None if self.cov is None else self.cov.tolist(),
            "hessian": None if self.hessian is None else self.hessian.tolist(),
            "hessian_condition": self.hessian_condition,
            "reliable": self.reliable,
            "notes": list(self.notes),
            "data": _jsonable(self.data),
            "bound_hit": self.bound_hit,
            "bound_coordinates": list(self.bound_coordinates),
            "theta": None if self.theta is None else self.theta.tolist(),
        }

    @classmethod
    def from_dict(cls, payload: JsonObject) -> FitResult:
        """Rebuild from :meth:`to_dict`. Rejects a schema it does not know."""
        schema = payload.get("schema")
        if schema != SCHEMA_VERSION:
            raise ValueError(
                f"FitResult schema {schema!r} is not supported by this version, "
                f"which reads schema {SCHEMA_VERSION}"
            )
        se = payload["se"]
        return cls(
            mu=np.asarray(payload["mu"], dtype=np.float64),
            alpha=np.asarray(payload["alpha"], dtype=np.float64),
            beta=np.asarray(payload["beta"], dtype=np.float64),
            loglik=float(payload["loglik"]),
            converged=bool(payload["converged"]),
            status=int(payload["status"]),
            nit=int(payload["nit"]),
            gradient_inf_norm=float(payload["gradient_inf_norm"]),
            n_params=int(payload["n_params"]),
            rho=float(payload["rho"]),
            rho_ci=None
            if payload["rho_ci"] is None
            else (float(payload["rho_ci"][0]), float(payload["rho_ci"][1])),
            se=None if se is None else {k: np.asarray(v, dtype=np.float64) for k, v in se.items()},
            cov=None if payload["cov"] is None else np.asarray(payload["cov"], dtype=np.float64),
            hessian=None
            if payload["hessian"] is None
            else np.asarray(payload["hessian"], dtype=np.float64),
            hessian_condition=None
            if payload["hessian_condition"] is None
            else float(payload["hessian_condition"]),
            reliable=str(payload["reliable"]),
            notes=tuple(str(n) for n in payload["notes"]),
            data=dict(payload["data"]),
            bound_hit=bool(payload["bound_hit"]),
            bound_coordinates=tuple(str(c) for c in payload["bound_coordinates"]),
            theta=None
            if payload.get("theta") is None
            else np.asarray(payload["theta"], dtype=np.float64),
        )


def _jsonable(value: Any) -> Any:
    """Recursively convert NumPy scalars and arrays to plain JSON types."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value
