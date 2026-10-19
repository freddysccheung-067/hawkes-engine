"""Log-likelihood of the multivariate exponential-kernel Hawkes process.

This module is a typed, documented face over the compiled core. It does the
shape checks the compiled core cannot express conveniently and then hands the
arrays over unchanged; it performs no arithmetic of its own, on purpose, so that
the number a user gets is the number the C++ tests verified.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import numpy.typing as npt

from hawkes_engine import _core

__all__ = ["LoglikResult", "loglik"]


class LoglikResult(TypedDict, total=False):
    """Return value of :func:`loglik`.

    ``value`` is always present. The gradient blocks are present only when
    ``grad=True``: ``dmu`` has shape ``(M,)``, ``dalpha`` and the pair ``dbeta``
    have shape ``(M, M)``, and the shared-decay ``dbeta`` has shape ``(M,)``.

    When the intensity is not strictly positive at some event, ``value`` is
    ``-inf`` and every gradient entry is ``nan``. Nothing is clipped: a fit that
    reaches that region has found something wrong, and it should be able to see
    it.
    """

    value: float
    dmu: npt.NDArray[np.float64]
    dalpha: npt.NDArray[np.float64]
    dbeta: npt.NDArray[np.float64]


def _check_array(
    name: str, value: npt.ArrayLike, dtype: npt.DTypeLike, ndim: int | None
) -> npt.NDArray[np.generic]:
    arr = np.ascontiguousarray(value, dtype=dtype)
    if ndim is not None and arr.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional, got shape {arr.shape}")
    return arr


def loglik(
    times: npt.ArrayLike,
    types: npt.ArrayLike,
    mu: npt.ArrayLike,
    alpha: npt.ArrayLike,
    beta: npt.ArrayLike,
    T: float,
    *,
    grad: bool = False,
    shared_decay: bool = False,
) -> LoglikResult:
    """Evaluate the log-likelihood of a multivariate Hawkes process.

    Implements ``docs/spec/mathematics.md`` section 3:

    .. math::

        \\ell(\\theta) = \\sum_i \\left[ \\sum_k \\log \\lambda_i(t^i_k)
        - \\int_0^T \\lambda_i(t)\\,dt \\right]

    Parameters
    ----------
    times
        Event times, shape ``(N,)``, non-decreasing, seconds from the start of
        the session. Convert epoch timestamps to a session-relative origin
        before calling (ADR-003).
    types
        Type index of each event, shape ``(N,)``, castable to ``uint8``.
    mu
        Baseline intensities, shape ``(M,)``, non-negative.
    alpha
        Excitation block, shape ``(M, M)``, non-negative. Row is the target
        type, column the source (ADR-002).
    beta
        Decay rates, shape ``(M, M)`` for a distinct decay per pair, or ``(M,)``
        when ``shared_decay`` is true, in which case ``beta_ij = beta_j``. All
        entries strictly positive.
    T
        End of the observation window. Must be at least the last event time.
    grad
        Also compute the gradient with respect to the natural-space parameters.
    shared_decay
        Use the source-only decay parameterization, O(N*M) instead of O(N*M*M).

    Returns
    -------
    LoglikResult
        ``value`` and, when requested, ``dmu``, ``dalpha``, ``dbeta``.

    Notes
    -----
    The gradient is in natural space. The optimizer's log-space gradient is
    ``natural * parameter`` entrywise; that conversion is applied once, in the
    objective wrapper, not here (ADR-002).

    Two events at the same timestamp do not excite each other: the intensity
    sums over strictly earlier events.
    """
    t = _check_array("times", times, np.float64, 1)
    k = _check_array("types", types, np.uint8, 1)
    m = _check_array("mu", mu, np.float64, 1)
    a = _check_array("alpha", alpha, np.float64, 2)
    b = _check_array("beta", beta, np.float64, 1 if shared_decay else 2)

    dim = int(m.shape[0])
    if a.shape != (dim, dim):
        raise ValueError(f"alpha must have shape ({dim}, {dim}), got {a.shape}")
    expected_beta = (dim,) if shared_decay else (dim, dim)
    if b.shape != expected_beta:
        raise ValueError(f"beta must have shape {expected_beta}, got {b.shape}")
    if t.shape[0] != k.shape[0]:
        raise ValueError(
            f"times and types must have the same length, got {t.shape[0]} and {k.shape[0]}"
        )

    out = _core.loglik(t, k, m, a, b, float(T), dim, shared_decay, grad)
    result: LoglikResult = {"value": float(out["value"])}
    if grad:
        result["dmu"] = out["dmu"]
        result["dalpha"] = out["dalpha"]
        result["dbeta"] = out["dbeta"]
    return result


def loglik_grad_log_space(
    times: npt.ArrayLike,
    types: npt.ArrayLike,
    mu: npt.ArrayLike,
    alpha: npt.ArrayLike,
    beta: npt.ArrayLike,
    T: float,
    *,
    shared_decay: bool = False,
) -> LoglikResult:
    """Log-likelihood with the gradient in log-space coordinates.

    Supplied for the optimizer at H3, which works in ``log`` coordinates so that
    positivity is structural rather than a bound (ADR-002). Same arguments as
    :func:`loglik` with ``grad=True``; the gradient blocks are
    ``d/d(log x)``, not ``d/dx``.
    """
    t = _check_array("times", times, np.float64, 1)
    k = _check_array("types", types, np.uint8, 1)
    m = _check_array("mu", mu, np.float64, 1)
    a = _check_array("alpha", alpha, np.float64, 2)
    b = _check_array("beta", beta, np.float64, 1 if shared_decay else 2)

    dim = int(m.shape[0])
    out = _core.loglik_grad_log_space(t, k, m, a, b, float(T), dim, shared_decay)
    return {
        "value": float(out["value"]),
        "dmu": out["dmu"],
        "dalpha": out["dalpha"],
        "dbeta": out["dbeta"],
    }
