"""
Reference implementation of Hawkes process likelihood and gradient.
Pure NumPy, O(N²M²) complexity. Used as oracle for C++ tests.

This is the source of truth. The spec (docs/spec/mathematics.md) is frozen.
If this oracle disagrees with the spec, the oracle is wrong.
"""

import numpy as np
from typing import Tuple


def loglik_oracle(
    times: np.ndarray,  # (N,) float64, sorted
    types: np.ndarray,  # (N,) uint8, dimension indices < M
    mu: np.ndarray,     # (M,) float64, baseline intensities > 0
    alpha: np.ndarray,  # (M, M) float64, excitation ≥ 0
    beta: np.ndarray,   # (M, M) float64, decay rates > 0
    T: float            # observation window
) -> float:
    """
    Compute log-likelihood ℓ(θ) = Σ_i [Σ_k log λ_i(t^i_k) - ∫_0^T λ_i(t) dt].

    Implements spec §3, equation for ℓ(θ).
    Uses naive O(N²M²) double loops — clarity over speed.

    Returns -inf if any intensity λ_i ≤ 0 at an event.
    """
    M = mu.shape[0]
    N = len(times)

    # Event term: Σ_i Σ_k log λ_i(t^i_k)
    # From spec §3: sum over all events of log(intensity at that event)
    event_term = 0.0
    for k in range(N):
        t_k = times[k]
        i = types[k]

        # Compute λ_i(t_k) = μ_i + Σ_j Σ_{t^j_m < t_k} α_{ij} exp(-β_{ij}(t_k - t^j_m))
        # From spec §1: intensity = baseline + sum of decaying bumps from past events
        lambda_i = mu[i]
        for j in range(M):
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    lambda_i += alpha[i, j] * np.exp(-beta[i, j] * (t_k - times[m]))

        if lambda_i <= 0:
            return -np.inf
        event_term += np.log(lambda_i)

    # Compensator term: ∫_0^T λ_i(t) dt
    # From spec §3: closed form for exponential kernels
    compensator = 0.0
    for i in range(M):
        # μ_i * T
        compensator += mu[i] * T

        # Σ_j Σ_m (α_{ij}/β_{ij}) * (1 - exp(-β_{ij}(T - t^j_m)))
        for j in range(M):
            for m in range(N):
                if types[m] == j:
                    compensator += (alpha[i, j] / beta[i, j]) * (
                        1 - np.exp(-beta[i, j] * (T - times[m]))
                    )

    return event_term - compensator


def grad_oracle(
    times: np.ndarray,
    types: np.ndarray,
    mu: np.ndarray,
    alpha: np.ndarray,
    beta: np.ndarray,
    T: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute gradient ∇ℓ(θ) = (∂ℓ/∂μ, ∂ℓ/∂α, ∂ℓ/∂β).

    Implements spec §5, gradient formulas.
    Uses naive O(N²M²) loops.

    Returns:
        grad_mu: (M,) array
        grad_alpha: (M, M) array
        grad_beta: (M, M) array
    """
    M = mu.shape[0]
    N = len(times)

    grad_mu = np.zeros(M)
    grad_alpha = np.zeros((M, M))
    grad_beta = np.zeros((M, M))

    # Event contributions
    # From spec §5: derivative at each event divided by λ, minus compensator derivative
    for k in range(N):
        t_k = times[k]
        i = types[k]

        # Compute λ_i(t_k) and S_{ij}(t_k) = Σ_{t^j_m < t_k} exp(-β_{ij}(t_k - t^j_m))
        lambda_i = mu[i]
        S = np.zeros((M, M))

        for j in range(M):
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    exp_term = np.exp(-beta[i, j] * (t_k - times[m]))
                    S[i, j] += exp_term
                    lambda_i += alpha[i, j] * exp_term

        if lambda_i <= 0:
            # Gradient undefined at -inf
            return np.full(M, np.nan), np.full((M, M), np.nan), np.full((M, M), np.nan)

        # ∂ℓ/∂μ_i: add 1/λ_i for this event
        # From spec §5: derivative of log(λ) w.r.t. μ is 1/λ
        grad_mu[i] += 1.0 / lambda_i

        # ∂ℓ/∂α_{ij}: add S_{ij} / λ_i
        # From spec §5: derivative of λ w.r.t. α_{ij} is S_{ij}
        for j in range(M):
            grad_alpha[i, j] += S[i, j] / lambda_i

        # ∂ℓ/∂β_{ij}: needs D_{ij} = ∂S_{ij}/∂β_{ij} = -Σ_m (t_k - t^j_m) exp(...)
        # From spec §5: derivative of S w.r.t. β involves time-weighted sum
        for j in range(M):
            D_ij = 0.0
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    D_ij -= (t_k - times[m]) * np.exp(-beta[i, j] * (t_k - times[m]))
            grad_beta[i, j] += alpha[i, j] * D_ij / lambda_i

    # Compensator contributions (subtract)
    # From spec §3 and §5: derivative of ∫λ dt
    for i in range(M):
        # ∂/∂μ_i: subtract T
        grad_mu[i] -= T

        for j in range(M):
            for m in range(N):
                if types[m] == j:
                    exp_term = np.exp(-beta[i, j] * (T - times[m]))

                    # ∂/∂α_{ij}: subtract (1/β_{ij})(1 - exp(...))
                    grad_alpha[i, j] -= (1 - exp_term) / beta[i, j]

                    # ∂/∂β_{ij}: subtract derivative of (α/β)(1 - exp(...))
                    # = -α/β² (1 - exp(...)) + α/β · (T - t_m) · exp(...)
                    grad_beta[i, j] -= (
                        -alpha[i, j] / beta[i, j]**2 * (1 - exp_term)
                        + alpha[i, j] / beta[i, j] * (T - times[m]) * exp_term
                    )

    return grad_mu, grad_alpha, grad_beta
