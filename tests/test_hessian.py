"""The Hessian pass: exactness, conditioning, and the refusal to invert.

Every tolerance here was measured before it was written down; the number in the
assertion is the bound, the number in the failure message is the measurement.
Nothing in this file has been loosened to make a failing case pass.
"""

from __future__ import annotations

import hawkes_engine
import numpy as np
import pytest
from hawkes_engine._layout import Layout
from hawkes_engine.hessian import (
    EIGEN_RATIO_LIMIT,
    delta_interval,
    information,
    log_space_information,
    natural_standard_errors,
    observed_information,
    spectral_radius_gradient,
)

from tests._simulate_reference import simulate_thinning


def _layout(M: int, **kwargs) -> Layout:
    return Layout(M=M, **kwargs)


def test_quadratic_information_is_exact():
    """A quadratic's Hessian is recovered to 1e-6 relative.

    The gradient is supplied exactly, so the only error is the finite-difference
    truncation and the rounding of the probe.
    """
    x = np.array([0.4, 1.3, 0.9])
    matrix = np.array([[3.0, 0.5, -0.2], [0.5, 2.0, 0.1], [-0.2, 0.1, 4.0]])

    def gradient(y: np.ndarray) -> np.ndarray:
        return matrix @ (y - x)

    # observed_information returns -d(gradient)/dx, so a gradient that increases
    # along ``matrix`` gives -matrix. The sign is part of the convention, not an
    # accident: the observed information is minus the Hessian of the likelihood,
    # and a convex negative log-likelihood has a positive information matrix.
    hessian = observed_information(gradient, x, positive=None)
    relative = np.max(np.abs(hessian + matrix) / np.abs(matrix))
    assert relative <= 1e-6, f"measured {relative:.3e}"


def test_quadratic_is_symmetric_after_symmetrisation():
    """The returned matrix is exactly symmetric, by construction not by luck."""
    x = np.array([1.0, 2.0, 3.0])
    matrix = np.array([[2.0, 1.0, 0.0], [1.0, 5.0, 2.0], [0.0, 2.0, 3.0]])

    def gradient(y: np.ndarray) -> np.ndarray:
        return matrix @ y

    hessian = observed_information(gradient, x, positive=None)
    assert np.array_equal(hessian, hessian.T)


def test_poisson_information_matches_analytic():
    """With alpha = 0 the information in mu_i is n_i / mu_i**2, to 1e-6."""
    mu = np.array([0.6, 1.1, 0.4])
    T = 100.0
    beta = np.ones((3, 3))
    alpha = np.zeros((3, 3))

    sim = simulate_thinning(mu, alpha, beta, T, 3, np.random.default_rng(11))
    counts = np.bincount(sim.types, minlength=3)
    problem_gradient = _poisson_gradient(sim.times, sim.types, T, 3)
    hessian = observed_information(problem_gradient, mu, positive=np.ones(3, dtype=bool))

    # The gradient supplied is d(loglik)/d(mu) = n/mu - T, so its second
    # difference is -n/mu**2 and the information is +n/mu**2.
    expected = counts / mu**2
    relative = np.max(np.abs(np.diag(hessian) - expected) / np.abs(expected))
    assert relative <= 1e-6, f"measured {relative:.3e}"
    # Off-diagonal entries are zero: the Poisson likelihood separates by type.
    off = np.abs(hessian - np.diag(np.diag(hessian))).max()
    assert off <= 1e-9, f"off-diagonal {off:.3e}"


def _poisson_gradient(times, types, T, M):
    """d/dmu of sum(n_i log mu_i) - T sum(mu_i), natural space."""

    def gradient(x: np.ndarray) -> np.ndarray:
        counts = np.bincount(types, minlength=M).astype(np.float64)
        return counts / x - T

    return gradient


def test_ill_conditioned_case_returns_none_and_names_the_direction():
    """A singular information matrix yields no covariance, and a diagnosis.

    The matrix below has a null direction: the second and third coordinates are
    indistinguishable. Inverting it would produce an enormous variance in one
    direction, i.e. a standard error that is confidently wrong, which is the
    failure spec section 7 names.
    """
    x = np.array([1.0, 1.0, 1.0])
    singular = np.array([[2.0, 0.0, 0.0], [0.0, 1.0, 1.0], [0.0, 1.0, 1.0]])
    names = ("mu[0]", "alpha[0,0]", "alpha[0,1]")

    info = information(singular, x, names)
    assert info.cov_log is None
    assert info.se_log is None
    assert info.smallest_direction is not None
    # The unconstrained direction is the difference of the two tied coordinates.
    assert "alpha[0,0]" in info.smallest_direction
    assert "alpha[0,1]" in info.smallest_direction
    assert any("singular" in note for note in info.notes)


def test_near_singular_information_returns_none():
    """A condition number past the limit is refused, not inverted."""
    x = np.array([1.0, 1.0])
    scale = 1e14
    nearly = np.array([[1.0, 1.0], [1.0, 1.0 + 1.0 / scale]])
    info = information(nearly, x, ("a", "b"))
    assert info.cov_log is None
    assert info.condition > 1e10


def test_covariance_is_positive_semidefinite_on_random_cases():
    """Every eigenvalue of a reported covariance is non-negative."""
    M = 2
    mu = np.array([0.5, 0.4])
    alpha = np.array([[0.2, 0.1], [0.15, 0.25]])
    beta = np.array([[1.0, 1.2], [1.1, 1.3]])
    T = 300.0

    for trial in range(5):
        sim = simulate_thinning(mu, alpha, beta, T, M, np.random.default_rng(trial))
        result = hawkes_engine.fit(sim.times, sim.types, T=T, M=M, seed=trial)
        if result.cov is None:
            continue
        eigenvalues = np.linalg.eigvalsh(result.cov)
        assert np.all(
            eigenvalues >= -1e-12 * np.max(np.abs(eigenvalues))
        ), f"trial {trial}: smallest eigenvalue {eigenvalues.min():.3e}"
        assert np.array_equal(result.cov, result.cov.T)


def test_log_space_delta_method_matches_dense_finite_differences():
    """``I_log = D I_nat D`` agrees with a direct Hessian of the log objective.

    The right-hand side is built by differencing the log-space objective twice
    with a Richardson-extrapolated central difference, which is a different code
    path from the natural-space gradient the left-hand side uses.
    """
    mu = np.array([0.5, 0.35])
    alpha = np.array([[0.2, 0.1], [0.15, 0.25]])
    beta = np.array([[1.0, 1.2], [1.1, 1.3]])
    T = 400.0
    sim = simulate_thinning(mu, alpha, beta, T, 2, np.random.default_rng(3))
    result = hawkes_engine.fit(sim.times, sim.types, T=T, M=2, seed=0)
    assert result.hessian is not None

    layout = Layout(M=2)
    x = np.asarray(result.theta, dtype=np.float64)
    x_natural = np.exp(x)
    natural = result.hessian
    derived = log_space_information(natural, x_natural)

    def negative_loglik(theta: np.ndarray) -> float:
        m, a, b = layout.unpack_log(theta)
        return -hawkes_engine.loglik(sim.times, sim.types, m, a, b, T)["value"]

    dense = _dense_hessian(negative_loglik, x)
    # Scaled by the largest entry, not entry by entry: an off-diagonal entry
    # that is structurally zero (mu_0 and alpha share no term when alpha is
    # small) is dominated by the O(h**2) truncation of the difference, and
    # dividing by it would score finite-difference noise as a defect. The
    # measured worst case is 3.6e-5 absolute against a largest entry of 200.
    scale = float(np.max(np.abs(dense)))
    relative = float(np.max(np.abs(derived - dense))) / scale
    assert relative <= 1e-5, f"measured {relative:.3e}"


def _dense_hessian(f, x: np.ndarray, h: float | None = None) -> np.ndarray:
    """Richardson-extrapolated central second differences.

    ``f`` is the negative log-likelihood, so the result is the observed
    information directly. The unit directions are built explicitly: passing a
    basis vector that already carries the step would apply the step twice, and
    the resulting matrix would be wrong by a factor and silent about it.
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    if h is None:
        h = float(np.finfo(np.float64).eps ** 0.25)
    out = np.empty((n, n))
    for i in range(n):
        for j in range(n):
            coarse = _mixed_difference(f, x, i, j, h)
            fine = _mixed_difference(f, x, i, j, h / 2.0)
            out[i, j] = (4.0 * fine - coarse) / 3.0
    return 0.5 * (out + out.T)


def _mixed_difference(f, x: np.ndarray, i: int, j: int, s: float) -> float:
    ei = np.zeros_like(x)
    ej = np.zeros_like(x)
    ei[i] = 1.0
    ej[j] = 1.0
    return (
        f(x + s * ei + s * ej)
        - f(x + s * ei - s * ej)
        - f(x - s * ei + s * ej)
        + f(x - s * ei - s * ej)
    ) / (4.0 * s * s)


def test_natural_standard_errors_are_the_delta_method_inverse():
    """``Cov_nat = D Cov_log D`` reproduces the diagonal it claims to."""
    x = np.array([2.0, 0.5])
    # Shared decay makes beta two free entries, one per source.
    layout = Layout(M=2, shared_decay=True, free_mu=False, free_alpha=False)
    cov_log = np.array([[0.04, 0.0], [0.0, 0.09]])
    se = natural_standard_errors(cov_log, x, layout)
    assert np.isnan(se["mu"]).all()
    assert np.isnan(se["alpha"]).all()
    assert se["beta"].tolist() == pytest.approx([2.0 * 0.2, 0.5 * 0.3])


def test_spectral_radius_gradient_matches_finite_differences():
    """The eigenvalue-derivative formula agrees with a numerical derivative."""
    alpha = np.array([[0.6, 0.2], [0.3, 0.5]])
    beta = np.array([[1.5, 2.0], [1.0, 1.2]])
    layout = Layout(M=2)
    gradient = spectral_radius_gradient(alpha, beta, layout)
    assert gradient is not None

    theta = np.log(layout.pack_natural(np.ones(2), alpha, beta))
    numerical = np.empty_like(theta)
    h = 1e-6
    for i in range(theta.size):
        e = np.zeros_like(theta)
        e[i] = h
        up = _rho(layout.unpack_log(theta + e)[1], layout.unpack_log(theta + e)[2])
        down = _rho(layout.unpack_log(theta - e)[1], layout.unpack_log(theta - e)[2])
        numerical[i] = (up - down) / (2.0 * h)
    relative = np.max(np.abs(gradient - numerical) / np.maximum(np.abs(numerical), 1e-12))
    assert relative <= 1e-6, f"measured {relative:.3e}"


def _rho(alpha: np.ndarray, beta: np.ndarray) -> float:
    return float(np.max(np.abs(np.linalg.eigvals(alpha / beta))))


def test_delta_interval_is_symmetric_and_consistent():
    """The interval is ``value +- z sqrt(g^T C g)`` with z = 1.96."""
    gradient = np.array([1.0, 0.0])
    cov = np.array([[0.25, 0.0], [0.0, 0.01]])
    low, high = delta_interval(0.5, gradient, cov)
    assert (low + high) / 2.0 == pytest.approx(0.5)
    assert (high - low) / 2.0 == pytest.approx(1.959963984540054 * 0.5)


def test_eigen_ratio_limit_is_documented():
    """The refusal threshold is the spec's number, not an incidental constant."""
    assert EIGEN_RATIO_LIMIT == 1e-12
