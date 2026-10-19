"""Observed information, standard errors, and the refusal to report neither.

Spec section 7: at the maximum, the observed information is minus the Hessian
of the log-likelihood, and standard errors are the square roots of the diagonal
of its inverse. When that matrix is near-singular the instruction is to report
*that* rather than a number, because a near-singular information matrix is the
alpha-beta ridge and an SE read off it is confidently wrong.

Three spaces meet here and each is named in the function that returns it:

``natural``
    The user's coordinates, theta = (mu, alpha, beta).
``log``
    The optimizer's coordinates, phi = log theta.
``information``
    A negative Hessian, not a covariance, and never both under one name.

The natural information ``I`` and the log-space information satisfy
``I_log = D I_nat D`` with ``D = diag(theta)``, because ``d/dphi = theta d/dtheta``.
The same ``D`` carries a covariance the other way, ``Cov_nat = D Cov_log D``.
Both directions are implemented once, below, and tested against a dense
finite-difference Hessian in ``tests/test_hessian.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from hawkes_engine._typing import BoolArray, FloatArray, GradientFn

if TYPE_CHECKING:  # pragma: no cover
    from hawkes_engine._layout import Layout

_EPS = float(np.finfo(np.float64).eps)

# Central differences of a gradient are optimal near eps**(1/3): below that the
# difference of two nearly equal gradients loses the signal to rounding, above
# it the O(h**2) truncation term dominates. The refined step scales the same
# constant by the local curvature length scale, which is the width of one
# standard error in that coordinate.
_STEP_CONST = _EPS ** (1.0 / 3.0)

# Relative floor: a step that is not representable in the parameter is not a
# step. Eight epsilons is the point at which the perturbation survives one
# rounding of the sum.
_STEP_FLOOR = 8.0 * _EPS

# A condition number above this, or an eigenvalue this far below the largest,
# makes the inverse meaningless at double precision. Both are spec section 7.
COND_LIMIT = 1e10
EIGEN_RATIO_LIMIT = 1e-12

Z_95 = 1.959963984540054


@dataclass(frozen=True)
class Information:
    """What the Hessian pass established, and what it declined to establish."""

    hessian_natural: FloatArray
    condition: float
    cov_log: FloatArray | None
    se_log: FloatArray | None
    smallest_direction: str | None
    notes: tuple[str, ...]


def steps(
    x: FloatArray, diagonal: FloatArray | None = None, *, positive: BoolArray | None = None
) -> FloatArray:
    """Per-coordinate central-difference steps.

    The base step is ``eps**(1/3) * max(|x_i|, 1)``: the rounding-optimal width
    for a difference of two function values carried at full precision, scaled to
    the magnitude of the coordinate so that a large parameter is not stepped in
    units too small to represent.

    When ``diagonal`` is supplied — the estimated ``|H_ii|`` from a first pass —
    the step is additionally capped at ``eps**(1/3) / sqrt(|H_ii|)``. That is
    ``eps**(1/3)`` times the curvature length scale, a small fraction of one
    standard error, i.e. the width over which the likelihood changes by O(1).
    For a quadratic the cap is irrelevant (the difference is exact either way);
    for a likelihood with a flat direction it is the difference between
    resolving the curvature and measuring rounding noise.

    ``positive`` marks coordinates whose domain is the open half-line. A
    symmetric probe would step below zero there, and the core rejects the point
    rather than returning a value, so the step is capped at half the coordinate.
    """
    scale = np.maximum(np.abs(x), 1.0)
    h = _STEP_CONST * scale
    if diagonal is not None:
        curvature = np.sqrt(np.maximum(np.abs(diagonal), 1e-300))
        h = np.minimum(h, _STEP_CONST / curvature)
        # A step larger than the coordinate itself is not a local probe.
        h = np.minimum(h, scale)
    h = np.maximum(h, _STEP_FLOOR)
    if positive is not None:
        # A parameter that must stay positive cannot be probed symmetrically
        # below zero. The step is capped at half the coordinate, which keeps both
        # probes inside the domain without giving up second-order accuracy for
        # any parameter above 2*eps**(1/3).
        h = np.where(positive, np.minimum(h, 0.5 * np.abs(x)), h)
    return np.asarray(h, dtype=np.float64)


def observed_information(
    gradient: GradientFn,
    x: FloatArray,
    *,
    refine: bool = True,
    positive: BoolArray | None = None,
) -> FloatArray:
    """``-d(gradient)/dx`` by central differences of the analytic gradient.

    ``gradient`` maps a free natural-space vector to the gradient of the
    log-likelihood in the same coordinates. Differencing the gradient is one
    order more accurate than differencing the likelihood twice, which is what
    spec section 7 asks for.

    ``positive`` marks coordinates that must stay strictly positive — every one
    of mu, alpha and beta in this model. Those get an asymmetric-block-safe step
    cap; see :func:`steps`.

    The matrix is symmetrised because the true Hessian is symmetric and the
    numerical one is not: the two triangles differ by O(h**2) truncation, and
    averaging them halves that error rather than leaving an asymmetry for the
    caller to interpret.
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if n == 0:  # pragma: no cover - an empty model is rejected before this
        return np.zeros((0, 0))
    h = steps(x, positive=positive)
    if refine:
        first = np.empty((n, n))
        for j in range(n):
            e = np.zeros(n)
            e[j] = h[j]
            first[:, j] = (gradient(x + e) - gradient(x - e)) / (2.0 * h[j])
        h = steps(x, np.diag(first), positive=positive)
    hess = np.empty((n, n))
    for j in range(n):
        e = np.zeros(n)
        e[j] = h[j]
        hess[:, j] = -(gradient(x + e) - gradient(x - e)) / (2.0 * h[j])
    symmetrised = 0.5 * (hess + hess.T)
    return np.asarray(symmetrised, dtype=np.float64)


def log_space_information(hessian_natural: FloatArray, x_natural: FloatArray) -> FloatArray:
    """``I_log = D I_nat D`` with ``D = diag(theta)``. Free coordinates only."""
    d = np.asarray(x_natural, dtype=np.float64)
    return (d[:, None] * hessian_natural) * d[None, :]


def _name_direction(vector: FloatArray, names: tuple[str, ...]) -> str:
    """The coordinate carrying most of an eigen-direction, plus the next two.

    Naming one coordinate would mislead when the direction is a ridge between
    alpha and beta rather than a single bad parameter, so the two runners-up
    are named as well.
    """
    order = np.argsort(np.abs(vector))[::-1][:3]
    return ", ".join(
        f"{names[i]} ({vector[i]:+.3f})" if i < len(names) else f"[{i}] ({vector[i]:+.3f})"
        for i in order
    )


def information(
    hessian_natural: FloatArray,
    x_natural: FloatArray,
    names: tuple[str, ...],
    *,
    cond_limit: float = COND_LIMIT,
    eigen_ratio_limit: float = EIGEN_RATIO_LIMIT,
) -> Information:
    """Invert the information by SVD, or explain why it will not be inverted.

    The inverse is taken through the singular values so that a zero or negative
    direction is a diagnosis rather than a NaN: a step along a direction the
    data does not constrain is exactly the confident wrong answer spec section 7
    forbids.
    """
    h = 0.5 * (hessian_natural + hessian_natural.T)
    information_log = log_space_information(h, x_natural)

    if np.any(~np.isfinite(information_log)):
        note = "information matrix has non-finite entries; no standard errors reported"
        return Information(h, float("nan"), None, None, None, (note,))

    u, s, vt = np.linalg.svd(information_log)
    largest = float(s[0]) if s.size else 0.0
    smallest = float(s[-1]) if s.size else 0.0
    condition = float("inf") if smallest <= 0.0 else largest / smallest
    direction = _name_direction(vt[-1], names) if s.size else None

    if smallest <= eigen_ratio_limit * largest or condition > cond_limit:
        note = (
            f"information matrix is singular to working precision "
            f"(cond={condition:.3g}; smallest singular value {smallest:.3g} "
            f"against {largest:.3g}). The unconstrained direction is {direction}. "
            f"No standard errors are reported."
        )
        return Information(h, condition, None, None, direction, (note,))

    cov_log = (vt.T / s) @ u.T
    cov_log = 0.5 * (cov_log + cov_log.T)
    diagonal = np.diag(cov_log)
    if np.any(diagonal < 0.0):
        note = (
            "log-space covariance has a negative diagonal entry, so the information "
            "matrix is not positive definite at this point; no standard errors are "
            "reported"
        )
        return Information(h, condition, None, None, direction, (note,))

    return Information(h, condition, cov_log, np.sqrt(diagonal), None, ())


def natural_standard_errors(
    cov_log: FloatArray, x_natural: FloatArray, layout: Layout
) -> dict[str, FloatArray]:
    """Delta-method standard errors in natural space, split by family.

    ``Cov_nat = D Cov_log D`` with ``D = diag(theta)`` is the same transform
    that produced ``I_log``, applied in the inverse direction. Doing it here,
    once, is why ``cov`` and ``se`` cannot drift apart.
    """
    d = np.asarray(x_natural, dtype=np.float64)
    cov_nat = (d[:, None] * cov_log) * d[None, :]
    se = np.sqrt(np.maximum(np.diag(cov_nat), 0.0))
    s_mu, s_alpha, s_beta = layout.slices
    return {
        "mu": layout.scatter(se[s_mu], "mu", fill=np.nan),
        "alpha": layout.scatter(se[s_alpha], "alpha", fill=np.nan),
        "beta": layout.scatter(se[s_beta], "beta", fill=np.nan),
    }


def spectral_radius_gradient(
    alpha: FloatArray, beta: FloatArray, layout: Layout
) -> FloatArray | None:
    """``d rho / d phi`` by the eigenvalue derivative, for the delta-method CI.

    For a simple eigenvalue ``lambda`` with right eigenvector ``v`` and left
    eigenvector ``u``, ``d lambda = u^T dG v / (u^T v)``. With ``G = alpha/beta``
    elementwise, ``dG_ij/d(log alpha_ij) = G_ij`` and ``dG_ij/d(log beta_ij) =
    -G_ij``.

    Returns ``None`` when the Perron root is not simple. That is the one case
    where the derivative does not exist, and an interval built on it would be
    fiction rather than an approximation.
    """
    alpha = np.asarray(alpha, dtype=np.float64)
    beta = np.asarray(beta, dtype=np.float64)
    gamma = alpha / beta
    values, vectors = np.linalg.eig(gamma)
    index = int(np.argmax(np.abs(values)))
    modulus = float(np.abs(values[index]))
    others = np.delete(np.abs(values), index)
    if others.size and abs(float(np.max(others)) - modulus) <= 1e-9 * max(modulus, 1e-300):
        return None

    right = np.real(vectors[:, index])
    # The left eigenvector is the matching row of V^{-1}; solve V^T y = e_i.
    left = np.linalg.solve(vectors.T, np.eye(values.size)[index])
    left = np.real(left)
    denominator = float(left @ right)
    if abs(denominator) < 1e-12:
        return None

    dg = np.outer(left / denominator, right)
    out = np.zeros(layout.n_params)
    s_mu, s_alpha, s_beta = layout.slices
    out[s_alpha] = (dg * gamma).ravel()[layout.alpha_idx]
    if layout.shared_decay:
        # beta_ij = beta_j, so the derivative with respect to beta_j sums over
        # every target that shares source j.
        out[s_beta] = -(dg * gamma).sum(axis=0)[layout.beta_idx]
    else:
        out[s_beta] = -(dg * gamma).ravel()[layout.beta_idx]
    return out


def delta_interval(
    value: float, gradient: FloatArray, cov_log: FloatArray, z: float = Z_95
) -> tuple[float, float]:
    """Normal interval ``value +- z sqrt(g^T C g)``."""
    variance = float(gradient @ cov_log @ gradient)
    half = z * float(np.sqrt(max(variance, 0.0)))
    return (value - half, value + half)
