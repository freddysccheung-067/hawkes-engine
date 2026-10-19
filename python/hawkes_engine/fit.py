"""Maximum-likelihood fit of the multivariate exponential-kernel Hawkes model.

The optimizer works in log space, ``mu = e**a``, ``alpha = e**b``, ``beta =
e**c`` (ADR-002). Positivity is then structural: no candidate is rejected for
being infeasible, and ``beta``, which spans orders of magnitude between a fast
and a slow market, gets a step size scaled to itself. The objective is the
negative log-likelihood and the gradient is the core's analytic one, transformed
once by the chain rule inside the compiled extension. Nothing here
finite-differences the objective.

Two things this module deliberately does *not* claim:

* that the reported optimum is a global one. It is the best of ``n_starts``
  runs. On the alpha-beta ridge all of them may reach the same likelihood at
  different parameter vectors, which ``tests/test_fit.py`` pins by asserting
  the likelihood and not the parameters.
* that a converged fit is a trustworthy one. Convergence is about the
  optimizer; conditioning is about the data. ``trust.report`` answers the
  second question and the result carries its verdict.
"""

from __future__ import annotations

import numpy as np

from hawkes_engine import _core
from hawkes_engine._layout import Layout
from hawkes_engine._typing import FloatArray
from hawkes_engine.hessian import (
    Z_95,
    delta_interval,
    information,
    natural_standard_errors,
    observed_information,
    spectral_radius_gradient,
)
from hawkes_engine.model import FitResult

__all__ = ["fit"]

# A converged fit must sit at a stationary point of the log-space objective.
# The tolerance is relative to |loglik| because a likelihood of 1e6 carries
# rounding at 1e-10 and an absolute 1e-6 bound would be unreachable there.
_GRADIENT_RTOL = 1e-6

# The observation window is fixed, so beta is only identified down to the
# resolution of the data: a decay far faster than the smallest gap is
# indistinguishable from no decay, and one far slower than the window is
# indistinguishable from a constant baseline. The search is confined to
# [1/(10T), 10/min_positive_gap] and a hit on either end is reported rather
# than silently returned.
_BETA_LOW_FRACTION = 1.0 / 10.0
_BETA_HIGH_FACTOR = 10.0

# Documented multi-start geometry. The first start is the moment estimate; the
# rest perturb it in log space. beta is drawn log-uniform over one e-fold in
# either direction, and each alpha row is scaled by a Gamma(shape=k) draw so
# that excitation mass moves between sources without changing its scale.
_START_BETA_LOG_WIDTH = 1.0
_START_ALPHA_SHAPE = 2.0

# Branching ratio of the moment start. The start is a point to leave from, not
# an estimate; half-critical keeps the initial mean intensity finite and the
# initial likelihood away from the compensator's exploding region.
_START_RHO = 0.5

BOUND_TOL = 1e-6


class _Problem:
    """The negative log-likelihood in log coordinates, with its gradient."""

    def __init__(
        self,
        times: FloatArray,
        types: np.ndarray,
        T: float,
        layout: Layout,
    ) -> None:
        self.times = times
        self.types = types
        self.T = T
        self.layout = layout
        self.M = layout.M
        self.shared = layout.shared_decay
        self._s_mu, self._s_alpha, self._s_beta = layout.slices
        self._evaluations = 0

    def __call__(self, theta: FloatArray) -> tuple[float, FloatArray]:
        self._evaluations += 1
        theta = np.asarray(theta, dtype=np.float64)
        if not np.all(np.isfinite(theta)):
            return 1e300, np.zeros_like(theta)
        # A step outside the representable range would raise from the core's
        # validation layer; the optimizer treats it as an infeasible point.
        if np.max(theta) > 700.0:
            return 1e300, np.zeros_like(theta)
        mu, alpha, beta = self.layout.unpack_log(theta)
        try:
            out = _core.loglik_grad_log_space(
                self.times, self.types, mu, alpha, beta, self.T, self.M, self.shared
            )
        except ValueError:
            return 1e300, np.zeros_like(theta)
        value = float(out["value"])
        if not np.isfinite(value):
            return 1e300, np.zeros_like(theta)
        g = self.layout.restrict_gradient(out["dmu"], out["dalpha"], out["dbeta"])
        return -value, -g

    def negative_loglik(self, theta: FloatArray) -> float:
        return self(theta)[0]

    def gradient_natural(self, x: FloatArray) -> FloatArray:
        """``d ell / d theta`` in natural space over the free entries.

        Recomputes the likelihood rather than reusing the optimizer's last
        call: the point being differentiated is the returned one, and scipy's
        gradient belongs to whatever point it stopped at, which need not be
        the same.
        """
        mu, alpha, beta = self.layout.unpack_natural(np.asarray(x, dtype=np.float64))
        out = _core.loglik(
            self.times, self.types, mu, alpha, beta, self.T, self.M, self.shared, True
        )
        return self.layout.restrict_gradient(out["dmu"], out["dalpha"], out["dbeta"])

    def gradient_log(self, theta: FloatArray) -> FloatArray:
        return -self(theta)[1]


def _validate_inputs(
    times: object, types: object, T: float, M: int, shared: bool
) -> tuple[FloatArray, np.ndarray]:
    """Check the event stream through the compiled validation layer.

    The core already validates events and names the offending index and value
    in its message, so the check is done there rather than duplicated in Python,
    where the two messages could disagree. The probe uses a parameter block that
    is valid by construction, so the only way it can raise is on the events.
    """
    t = np.ascontiguousarray(times, dtype=np.float64)
    k = np.ascontiguousarray(types)
    if k.dtype != np.uint8:
        if k.size and (k.min() < 0 or k.max() > 255):
            bad = int(np.argmax((k < 0) | (k > 255)))
            raise ValueError(f"event type {k.ravel()[bad]} at index {bad} is outside 0..255")
        k = k.astype(np.uint8)

    probe_mu = np.full(M, 1e-12)
    probe_alpha = np.zeros((M, M))
    probe_beta = np.ones((M,) if shared else (M, M))
    # Raises ValueError naming index and value on any violation.
    _core.loglik(t, k, probe_mu, probe_alpha, probe_beta, float(T), M, shared, False)

    if t.size and float(t[-1]) > float(T):
        raise ValueError(
            f"T={T!r} is before the last event at index {t.size - 1}, value {float(t[-1])!r}"
        )
    return t, k


def _moment_start(
    times: FloatArray, types: np.ndarray, T: float, M: int
) -> tuple[FloatArray, FloatArray]:
    """A starting point built from the stationary-mean identity.

    ``nu_i = n_i / T`` estimates the mean intensity. Requiring
    ``nu = (I - Gamma)^{-1} mu`` with a rank-one ``Gamma = rho * nu 1^T / sum(nu)``
    and ``mu = (1 - rho) nu`` satisfies it exactly, because ``nu`` is then an
    eigenvector of ``Gamma`` with eigenvalue ``rho``. ``rho = 0.5`` keeps the
    start away from criticality, where the compensator explodes and the first
    likelihood evaluation is useless.

    Decay is seeded from the median gap of the pooled stream: one over the
    median gap is the rate at which density halves, which is the right order of
    magnitude for a kernel whose scale is the data's own scale.
    """
    counts = np.bincount(types, minlength=M).astype(np.float64) if types.size else np.zeros(M)
    nu = np.maximum(counts / T, 1e-6 / T)
    gaps = np.diff(times)
    positive = gaps[gaps > 0.0]
    median_gap = float(np.median(positive)) if positive.size else T / max(types.size, 1)
    beta0 = max(1.0 / median_gap, 1.0 / (10.0 * T))

    total = float(nu.sum())
    gamma = _START_RHO * np.outer(nu, np.ones(M)) / total
    mu = (1.0 - _START_RHO) * nu
    alpha = gamma * beta0
    return mu, alpha


def _log_bounds(times: FloatArray, T: float, layout: Layout) -> tuple[FloatArray, FloatArray]:
    """Log-space lower and upper bounds for each free coordinate."""
    gaps = np.diff(times)
    positive = gaps[gaps > 0.0]
    min_gap = float(np.min(positive)) if positive.size else T
    beta_low = _BETA_LOW_FRACTION / T
    beta_high = _BETA_HIGH_FACTOR / max(min_gap, 1e-12)

    lo = np.full(layout.n_params, np.log(1e-10))
    hi = np.full(layout.n_params, np.log(1e10))
    s_mu, s_alpha, s_beta = layout.slices
    lo[s_mu] = np.log(1e-10 / T)
    hi[s_mu] = np.log(1e3 * max(1.0, float(times.size) / T))
    lo[s_beta] = np.log(beta_low)
    hi[s_beta] = np.log(beta_high)
    return lo, hi


def _initial_vectors(
    theta0: FloatArray,
    lo: FloatArray,
    hi: FloatArray,
    layout: Layout,
    n_starts: int,
    rng: np.random.Generator,
) -> list[FloatArray]:
    """The moment start, then ``n_starts - 1`` perturbations of it.

    Deterministic given the generator, which is what makes a seeded multi-start
    reproducible. The perturbations are multiplicative in log space, so they
    are symmetric about the moment estimate on the natural scale and cannot
    leave the positive orthant.
    """
    starts = [np.clip(theta0, lo + 1e-9, hi - 1e-9)]
    if n_starts <= 1:
        return starts
    s_mu, s_alpha, s_beta = layout.slices
    n_beta = layout.n_beta
    n_alpha = layout.n_alpha
    for _ in range(n_starts - 1):
        theta = theta0.copy()
        theta[s_beta] += rng.uniform(-_START_BETA_LOG_WIDTH, _START_BETA_LOG_WIDTH, n_beta)
        # Row-wise rescaling moves excitation mass between sources; the draw is
        # Gamma(shape) rather than uniform so that a row is rarely driven to
        # nearly zero, which would make the start degenerate.
        if n_alpha:
            if layout.shared_decay:
                scale = rng.gamma(_START_ALPHA_SHAPE, 1.0 / _START_ALPHA_SHAPE, layout.M)
                theta[s_alpha] += np.log(scale)[np.repeat(np.arange(layout.M), layout.M)]
            else:
                scale = rng.gamma(_START_ALPHA_SHAPE, 1.0 / _START_ALPHA_SHAPE, layout.M)
                rows = np.repeat(np.arange(layout.M), layout.M)
                theta[s_alpha] += np.log(scale)[rows]
        starts.append(np.clip(theta, lo + 1e-9, hi - 1e-9))
    return starts


def _spectral_radius(alpha: FloatArray, beta: FloatArray) -> float:
    gamma = np.asarray(alpha, dtype=np.float64) / np.asarray(beta, dtype=np.float64)
    if gamma.size == 0:
        return 0.0
    return float(np.max(np.abs(np.linalg.eigvals(gamma))))


def _converged(opt: object, gradient_inf: float, loglik: float) -> bool:
    """Stationarity, judged on the recomputed gradient.

    The mathematical criterion is ``||grad||_inf <= 1e-6 * max(1, |loglik|)``.
    scipy's ``status`` is reported alongside but is not sufficient: status 2
    ("abnormal termination in line search") also fires when the line search
    fails because there is nothing left to gain, so a fit that sits at a
    stationary point can carry it. The gradient is the evidence; the status is
    context. Status 1 (iteration limit) is a real failure and is never
    overridden.
    """
    gradient_ok = gradient_inf <= _GRADIENT_RTOL * max(1.0, abs(loglik))
    status = int(getattr(opt, "status", -1))
    return bool(gradient_ok and status in (0, 2))


def _bound_report(
    theta: FloatArray, lo: FloatArray, hi: FloatArray, layout: Layout
) -> tuple[bool, tuple[str, ...]]:
    names = layout.names
    hit = []
    for i, name in enumerate(names):
        if theta[i] <= lo[i] + BOUND_TOL or theta[i] >= hi[i] - BOUND_TOL:
            side = "lower" if theta[i] <= lo[i] + BOUND_TOL else "upper"
            hit.append(f"{name} ({side} bound)")
    return bool(hit), tuple(hit)


def _gaps_summary(times: FloatArray, types: np.ndarray, M: int) -> dict[str, float]:
    gaps = np.diff(times)
    counts = np.bincount(types, minlength=M) if types.size else np.zeros(M, dtype=int)
    return {
        "median_gap": float(np.median(gaps)) if gaps.size else 0.0,
        "max_gap": float(np.max(gaps)) if gaps.size else 0.0,
        "mean_gap": float(np.mean(gaps)) if gaps.size else 0.0,
        "n_per_type": counts.astype(float).tolist(),
    }


def fit(
    times: object,
    types: object,
    mu: object = None,
    alpha: object = None,
    beta: object = None,
    T: float | None = None,
    *,
    M: int | None = None,
    shared_decay: bool = False,
    n_starts: int = 1,
    init: str = "moment",
    seed: int | None = None,
    se_method: str | None = "hessian",
    ridge_report: bool = True,
    zero_diagonal: bool = False,
    n_bootstrap: int = 200,
) -> FitResult:
    """Fit the model by maximum likelihood.

    Parameters
    ----------
    times, types
        The event stream, as for :func:`hawkes_engine.loglik`.
    mu, alpha, beta
        Optional fixed values. A block supplied here is held constant and is not
        estimated; this is what makes a Poisson-limit test possible without a
        second entry point. ``None`` estimates that block.
    T
        End of the observation window. Defaults to the last event time.
    M
        Number of types. Inferred from ``mu`` or ``alpha`` when given, otherwise
        required.
    shared_decay
        Estimate one decay per source rather than one per pair (ADR-002).
    n_starts
        Number of independent optimizer runs. The best log-likelihood wins.
    init
        ``"moment"`` (the only value in v0.1). See :func:`_moment_start`.
    seed
        Seed for the multi-start generator and the bootstrap stream. ``None``
        draws from the OS entropy pool, so a fit without a seed is not
        reproducible; with one it is bit-reproducible.
    se_method
        ``"hessian"`` for the observed information, ``"bootstrap"`` for a
        parametric bootstrap, or ``None`` to skip standard errors entirely.
    ridge_report
        Reserved for the H6 calibration map; in v0.1 it changes nothing,
        because the reliability report always runs.
    zero_diagonal
        Constrain ``alpha_ii = 0``. Masked out of the free vector, not projected
        after the fact: a projected coordinate is still a coordinate.
    n_bootstrap
        Replications for ``se_method="bootstrap"``.

    Returns
    -------
    FitResult
    """
    from scipy.optimize import minimize  # type: ignore[import-untyped]

    if se_method not in ("hessian", "bootstrap", None):
        raise ValueError(f"se_method must be 'hessian', 'bootstrap' or None, got {se_method!r}")
    if init != "moment":
        raise ValueError(f"init must be 'moment' in v0.1, got {init!r}")
    if n_starts < 1:
        raise ValueError(f"n_starts must be at least 1, got {n_starts!r}")
    if M is None:
        M = _infer_M(mu, alpha)
    if M is None:
        raise ValueError("M is required when mu and alpha are both None")
    M = int(M)

    t_arr = np.ascontiguousarray(times, dtype=np.float64)
    T_value = float(t_arr[-1]) if T is None and t_arr.size else float(T if T is not None else 0.0)
    t_arr, k_arr = _validate_inputs(t_arr, types, T_value, M, shared_decay)

    fixed = _fixed_blocks(mu, alpha, beta, M, shared_decay)
    layout = Layout(
        M=M,
        shared_decay=shared_decay,
        zero_diagonal=zero_diagonal,
        free_mu=fixed.mu is None,
        free_alpha=fixed.alpha is None,
        free_beta=fixed.beta is None,
        mu_const=fixed.mu,
        alpha_const=fixed.alpha,
        beta_const=fixed.beta,
    )
    rng = np.random.default_rng(seed)

    mu_init, alpha_init = _moment_start(t_arr, k_arr, T_value, M)
    beta_init = _beta_start(t_arr, T_value, M, shared_decay, layout)
    packed = layout.pack_natural(mu_init, alpha_init, beta_init)
    if np.any(packed <= 0.0):
        # The moment start is positive by construction; a supplied fixed block
        # that zeroes a free coordinate would not be, and the log would be -inf.
        raise ValueError(
            "the starting point has a non-positive free parameter, which the "
            "log-space optimizer cannot represent; supply a positive starting value"
        )
    theta0 = np.log(packed)
    lo, hi = _log_bounds(t_arr, T_value, layout)
    problem = _Problem(t_arr, k_arr, T_value, layout)
    data_gaps = _gaps_summary(t_arr, k_arr, M)

    best = None
    for start in _initial_vectors(theta0, lo, hi, layout, n_starts, rng):
        result = minimize(
            problem,
            start,
            jac=True,
            method="L-BFGS-B",
            bounds=list(zip(lo, hi, strict=True)),
            options={"maxiter": 5000, "ftol": 1e-14, "gtol": 1e-10, "maxcor": 30},
        )
        if best is None or float(result.fun) < best[0]:
            best = (float(result.fun), result)
    assert best is not None
    _, opt = best
    theta = np.clip(np.asarray(opt.x, dtype=np.float64), lo, hi)

    mu_hat, alpha_hat, beta_hat = layout.unpack_log(theta)
    loglik = -float(problem.negative_loglik(theta))
    grad_log = np.abs(problem.gradient_log(theta))
    gradient_inf = float(np.max(grad_log)) if grad_log.size else 0.0

    converged = _converged(opt, gradient_inf, loglik)
    rho = _spectral_radius(alpha_hat, beta_hat)
    bound_hit, bound_names = _bound_report(theta, lo, hi, layout)

    x_natural = layout.pack_natural(mu_hat, alpha_hat, beta_hat)

    hess_nat: FloatArray | None = None
    cov_log: FloatArray | None = None
    se: dict[str, FloatArray] | None = None
    condition: float | None = None
    notes: list[str] = []
    if bound_hit:
        notes.append(
            "the optimum sits on the search boundary at "
            + ", ".join(bound_names)
            + "; the estimate is a boundary value, not a stationary point"
        )

    if se_method == "hessian":
        # Every free coordinate is strictly positive, so the difference probes
        # must stay in the open half-line.
        hess_nat = observed_information(
            problem.gradient_natural, x_natural, positive=np.ones(layout.n_params, dtype=bool)
        )
        info = information(hess_nat, x_natural, layout.names)
        condition = info.condition
        cov_log = info.cov_log
        notes.extend(info.notes)
        if cov_log is not None:
            se = natural_standard_errors(cov_log, x_natural, layout)
            se = _mask_fixed(se, layout)
    elif se_method == "bootstrap":
        from hawkes_engine._boot import parametric_bootstrap

        boot = parametric_bootstrap(
            t_arr,
            k_arr,
            T_value,
            M,
            shared_decay,
            mu_hat,
            alpha_hat,
            beta_hat,
            layout,
            n_bootstrap=n_bootstrap,
            seed=seed,
            zero_diagonal=zero_diagonal,
        )
        se = boot.se
        cov_log = boot.cov_log
        notes.extend(boot.notes)

    rho_ci = None
    if cov_log is not None:
        grad_rho = spectral_radius_gradient(alpha_hat, beta_hat, layout)
        if grad_rho is not None:
            rho_ci = delta_interval(rho, grad_rho, cov_log, Z_95)
        else:
            notes.append(
                "the branching matrix has a repeated dominant eigenvalue, so d(rho) "
                "does not exist and no interval is reported for rho"
            )

    from hawkes_engine.trust import report as _trust_report

    result = FitResult(
        mu=mu_hat,
        alpha=alpha_hat,
        beta=beta_hat,
        loglik=loglik,
        converged=converged,
        status=int(opt.status),
        nit=int(opt.nit),
        gradient_inf_norm=gradient_inf,
        n_params=layout.n_params,
        rho=rho,
        rho_ci=rho_ci,
        se=se,
        cov=cov_log,
        hessian=hess_nat,
        hessian_condition=condition,
        reliable="unknown",
        notes=tuple(notes),
        data={
            "n_events": int(t_arr.size),
            "T": T_value,
            "M": M,
            "shared_decay": shared_decay,
            "zero_diagonal": zero_diagonal,
            "seed": seed,
            "n_starts": n_starts,
            "se_method": se_method,
            "residual_gaps_summary": data_gaps,
        },
        bound_hit=bound_hit,
        bound_coordinates=bound_names,
        theta=theta,
    )
    return _apply_trust(result, _trust_report)


class _Fixed:
    """Blocks the caller supplied, held constant through the fit."""

    def __init__(
        self,
        mu: FloatArray | None,
        alpha: FloatArray | None,
        beta: FloatArray | None,
    ) -> None:
        self.mu = mu
        self.alpha = alpha
        self.beta = beta


def _infer_M(mu: object, alpha: object) -> int | None:
    if mu is not None:
        return int(np.asarray(mu, dtype=np.float64).reshape(-1).size)
    if alpha is not None:
        a = np.asarray(alpha, dtype=np.float64)
        if a.ndim != 2 or a.shape[0] != a.shape[1]:
            raise ValueError(f"alpha must be square to infer M, got shape {a.shape}")
        return int(a.shape[0])
    return None


def _fixed_blocks(
    mu: object,
    alpha: object,
    beta: object,
    M: int,
    shared: bool,
) -> _Fixed:
    """Convert the caller's fixed blocks, rejecting ones that are not valid.

    A block is either fully fixed or fully estimated. A partially fixed block
    would need a mask per entry, and nothing in H3 asks for it; refusing is
    clearer than silently ignoring the supplied entries.
    """
    out = _Fixed(None, None, None)
    if mu is not None:
        arr = np.ascontiguousarray(mu, dtype=np.float64).reshape(-1)
        if arr.size != M:
            raise ValueError(f"mu has {arr.size} entries, expected M = {M}")
        if np.any(arr <= 0.0) or np.any(~np.isfinite(arr)):
            raise ValueError("fixed mu must be finite and strictly positive")
        out.mu = arr
    if alpha is not None:
        arr = np.ascontiguousarray(alpha, dtype=np.float64)
        if arr.shape != (M, M):
            raise ValueError(f"alpha must have shape ({M}, {M}), got {arr.shape}")
        if np.any(arr < 0.0) or np.any(~np.isfinite(arr)):
            raise ValueError("fixed alpha must be finite and non-negative")
        out.alpha = arr
    if beta is not None:
        arr = np.ascontiguousarray(beta, dtype=np.float64)
        shape = (M,) if shared else (M, M)
        if arr.shape != shape:
            raise ValueError(f"beta must have shape {shape}, got {arr.shape}")
        if np.any(arr <= 0.0) or np.any(~np.isfinite(arr)):
            raise ValueError("fixed beta must be finite and strictly positive")
        out.beta = arr
    return out


def _beta_start(times: FloatArray, T: float, M: int, shared: bool, layout: Layout) -> FloatArray:
    """A decay rate on the scale of the data, or the supplied block unchanged."""
    if not layout.free_beta and layout._template_beta().size:  # noqa: SLF001
        return layout._template_beta()  # noqa: SLF001
    gaps = np.diff(times)
    positive = gaps[gaps > 0.0]
    rate = 1.0 / float(np.median(positive)) if positive.size else 1.0 / T
    return np.full((M,) if shared else (M, M), rate)


def _mask_fixed(se: dict[str, FloatArray], layout: Layout) -> dict[str, FloatArray]:
    """A fixed block's standard error is zero, not NaN: nothing was estimated."""
    out = dict(se)
    for family, free in (
        ("mu", layout.free_mu),
        ("alpha", layout.free_alpha),
        ("beta", layout.free_beta),
    ):
        if not free:
            out[family] = np.zeros_like(out[family])
    return out


def _apply_trust(result: FitResult, trust_fn: object) -> FitResult:
    """Attach the reliability verdict. Imported lazily to break the cycle."""
    from dataclasses import replace

    report = trust_fn(result)  # type: ignore[operator]
    notes = tuple(result.notes) + tuple(report.notes)
    return replace(result, reliable=report.verdict, notes=notes)
