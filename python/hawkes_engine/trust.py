"""What a single fit can say about its own trustworthiness, and nothing more.

This module answers one question: *given this fit and this data, is the
estimate a well-conditioned stationary point?* It reports whether the fit
converged and is well-conditioned. It does **not** report whether the estimator
is unbiased, whether the intervals cover at the nominal rate, or whether the
model fits. Those are properties of the estimator and the model, measurable
only by a pre-registered study over repeated simulations, which is the subject
of gate H6. A number here is evidence about this dataset; it is not a claim
about the procedure.

Every threshold lives in :data:`THRESHOLDS` with the argument for its value, so
that H6 replaces a number rather than editing logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hawkes_engine.model import FitResult

__all__ = ["ReliabilityReport", "THRESHOLDS", "report"]

# Thresholds, each with the reasoning behind the value. H6 calibrates these
# against measured coverage; until then they are engineering judgement and are
# labelled as such.
THRESHOLDS: dict[str, float] = {
    # cond(H) below this leaves at least three digits of the inverse intact,
    # which is enough for an SE to mean something. The information matrix is a
    # squared quantity, so 1e6 in H is 1e3 in the parameters.
    "condition_marginal": 1e6,
    # Above this the inverse has lost more than half its significant digits and
    # the SE is a rounding artifact. Matches hessian.COND_LIMIT deliberately:
    # a matrix the inverted refused cannot be called reliable here.
    "condition_unreliable": 1e10,
    # rho within this of 1 is the near-critical regime where (I - Gamma) is
    # nearly singular, the stationary mean explodes, and the finite-sample
    # distribution of rho is strongly skewed. 1e-3 is tighter than the 0.95
    # warning in ADR-002 because it flags a region, not a preference.
    "rho_critical_margin": 1e-3,
    # A correlation of 0.99 between a log-alpha and a log-beta coordinate is the
    # alpha-beta ridge of section 7: the two parameters trade off against each
    # other along a direction the data barely constrains. 0.99 rather than
    # 0.95 because ordinary excitation under correlated counting already
    # produces correlations near 0.9.
    "ridge_correlation": 0.99,
    # Fewer than this many events per estimated parameter and the asymptotic
    # normal approximation behind the Hessian SEs cannot be expected to hold.
    # Ten is the conventional rule of thumb for a likelihood fit of this size.
    "events_per_param_marginal": 10.0,
    "events_per_param_unreliable": 3.0,
}


@dataclass(frozen=True)
class ReliabilityReport:
    """The verdict, the evidence for it, and the reasons against it."""

    verdict: str
    condition: float | None
    bound_hit: bool
    rho: float
    rho_near_critical: bool
    ridge_active: bool
    ridge_correlation: float | None
    events_per_param: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __repr__(self) -> str:
        return (
            f"ReliabilityReport(verdict={self.verdict!r}, condition={self.condition!r}, "
            f"rho={self.rho:.6g}, ridge={self.ridge_active}, "
            f"events_per_param={self.events_per_param:.3g})"
        )


def _alpha_beta_correlation(model: FitResult) -> float | None:
    """Largest ``|corr|`` between a log-alpha and a log-beta coordinate.

    The correlation is read off the log-space covariance, which is the space in
    which the ridge is linear: ``alpha`` and ``beta`` trade off along
    ``alpha/beta = const``, so their logs move in opposite directions with
    equal magnitude when the ridge is exact.
    """
    cov = model.cov
    theta = model.theta
    if cov is None or theta is None:
        return None
    n_alpha = int(np.size(model.alpha))
    if model.data.get("zero_diagonal"):
        n_alpha -= int(model.data.get("M", 0))
    n_mu = int(np.size(model.mu))
    a = slice(n_mu, n_mu + n_alpha)
    b = slice(n_mu + n_alpha, cov.shape[0])
    if a.stop > cov.shape[0] or b.start >= cov.shape[0]:
        return None
    std = np.sqrt(np.maximum(np.diag(cov), 1e-300))
    corr = cov / np.outer(std, std)
    block = np.abs(corr[a, b])
    return float(block.max()) if block.size else None


def report(model: FitResult, n_events: int | None = None) -> ReliabilityReport:
    """Assess conditioning from this fit alone.

    Parameters
    ----------
    model
        A fitted :class:`~hawkes_engine.FitResult`. Only fields the fit already
        computed are read; nothing is refitted.
    n_events
        Event count to compare against the parameter count. ``None`` reads
        ``model.data["n_events"]``, which is what the fit recorded.

    Returns
    -------
    ReliabilityReport
        A verdict of ``"reliable"``, ``"marginal"`` or ``"unreliable"``, the
        evidence, and one note per reason.

    Notes
    -----
    Reads the Hessian condition number, whether a coordinate stopped on a search
    bound, the branching ratio, the alpha-beta correlation implied by the
    covariance, and the event count per parameter. It reports whether the fit
    converged and is well-conditioned, not whether it is unbiased.
    """
    t = THRESHOLDS
    n_events = int(n_events if n_events is not None else model.data.get("n_events", 0))
    per_param = n_events / max(model.n_params, 1)
    condition = model.hessian_condition
    rho = float(model.rho)
    rho_near = abs(rho - 1.0) <= t["rho_critical_margin"]
    corr = _alpha_beta_correlation(model)
    ridge = corr is not None and corr >= t["ridge_correlation"]

    notes: list[str] = []
    verdict = "reliable"

    if not model.converged:
        verdict = "unreliable"
        notes.append(
            f"the optimizer did not reach a stationary point "
            f"(status {model.status}, ||grad||_inf = {model.gradient_inf_norm:.3g})"
        )
    if condition is None:
        if model.cov is None:
            verdict = "unreliable"
            notes.append(
                "no Hessian conditioning number is available, so standard errors "
                "could not be computed"
            )
    elif condition > t["condition_unreliable"]:
        verdict = "unreliable"
        notes.append(
            f"the observed information is singular to working precision "
            f"(cond = {condition:.3g} > {t['condition_unreliable']:.0g})"
        )
    elif condition > t["condition_marginal"]:
        if verdict == "reliable":
            verdict = "marginal"
        notes.append(
            f"the observed information is poorly conditioned "
            f"(cond = {condition:.3g} > {t['condition_marginal']:.0g}); "
            f"the standard errors are inflated along the flat direction"
        )
    if model.bound_hit:
        if verdict == "reliable":
            verdict = "marginal"
        notes.append(
            "at least one coordinate stopped on a search bound: "
            + ", ".join(model.bound_coordinates)
        )
    if rho_near:
        if verdict == "reliable":
            verdict = "marginal"
        notes.append(
            f"the branching ratio is within {t['rho_critical_margin']:g} of criticality "
            f"(rho = {rho:.6g}); the stationary mean is near its pole"
        )
    if ridge:
        if verdict == "reliable":
            verdict = "marginal"
        notes.append(
            f"the alpha-beta ridge is active: |corr(log alpha, log beta)| = {corr:.4f} "
            f">= {t['ridge_correlation']:g}. The likelihood is flat along "
            f"alpha/beta = const, so these standard errors are not individually "
            f"meaningful"
        )
    if per_param < t["events_per_param_unreliable"]:
        verdict = "unreliable"
        notes.append(
            f"{per_param:.2f} events per estimated parameter is below "
            f"{t['events_per_param_unreliable']:g}; the asymptotics behind the "
            f"standard errors do not apply"
        )
    elif per_param < t["events_per_param_marginal"] and verdict == "reliable":
        verdict = "marginal"
        notes.append(
            f"{per_param:.2f} events per estimated parameter is below the "
            f"rule-of-thumb {t['events_per_param_marginal']:g}"
        )

    return ReliabilityReport(
        verdict=verdict,
        condition=condition,
        bound_hit=model.bound_hit,
        rho=rho,
        rho_near_critical=rho_near,
        ridge_active=ridge,
        ridge_correlation=corr,
        events_per_param=per_param,
        notes=tuple(notes),
    )
