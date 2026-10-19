"""Verification suite for the reference implementation.

The analytic gradient is checked against the likelihood by two independent
methods:

* **Complex-step differentiation**, which is exact to machine precision. It
  carries no subtractive cancellation, so it can distinguish a correct gradient
  from one that is wrong by 1e-9. This is the primary check.
* **Central finite differences**, which use no complex arithmetic at all. It is
  a cruder estimate, but it is implemented differently enough that a mistake in
  the complex-step harness cannot hide behind agreement between two copies of
  the same error.

Complex-step runs over every parameter entry at moderate N. Finite differences
also run over every entry, at smaller N, because the naive oracle makes a single
likelihood evaluation cost O(N^2 M^2).

The finite-difference tolerance is a pair rather than a single relative
bound. Central differences at h = 1e-6 carry O(h^2) truncation error, which
lands at 1e-8 relative on large gradients, and the relative error of a
difference of nearly equal numbers blows up when the true derivative is close to
zero while the absolute error stays tiny. Requiring both a large relative and a
large absolute error before failing separates finite-difference noise from a
defect: a sign error or a missing term produces errors of order 1e-2.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from hawkes_oracle import grad_oracle, loglik_oracle  # noqa: E402

M_GRID = (1, 2, 3)
N_GRID = (10, 30, 60)


def _random_case(rng: np.random.Generator, m: int, n: int) -> tuple:
    mu = rng.exponential(1.0, m)
    alpha = rng.exponential(0.5, (m, m))
    beta = rng.exponential(2.0, (m, m))
    times = np.sort(rng.uniform(0.0, 100.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    horizon = times[-1] + rng.uniform(1.0, 10.0)
    return mu, alpha, beta, times, types, horizon


def _complex_step_gradient(
    times: np.ndarray,
    types: np.ndarray,
    mu: np.ndarray,
    alpha: np.ndarray,
    beta: np.ndarray,
    horizon: float,
    h: float = 1e-20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gradient by complex-step: Im(f(x + ih)) / h, exact to machine precision."""
    mu_c = mu.astype(complex)
    alpha_c = alpha.astype(complex)
    beta_c = beta.astype(complex)
    m = mu.shape[0]

    g_mu = np.zeros(m)
    g_alpha = np.zeros((m, m))
    g_beta = np.zeros((m, m))

    for i in range(m):
        perturbed = mu_c.copy()
        perturbed[i] = complex(mu[i], h)
        g_mu[i] = loglik_oracle(times, types, perturbed, alpha_c, beta_c, horizon).imag / h

    for i in range(m):
        for j in range(m):
            perturbed = alpha_c.copy()
            perturbed[i, j] = complex(alpha[i, j], h)
            g_alpha[i, j] = loglik_oracle(times, types, mu_c, perturbed, beta_c, horizon).imag / h

            perturbed = beta_c.copy()
            perturbed[i, j] = complex(beta[i, j], h)
            g_beta[i, j] = loglik_oracle(times, types, mu_c, alpha_c, perturbed, horizon).imag / h

    return g_mu, g_alpha, g_beta


def _assert_close(
    actual: np.ndarray,
    expected: np.ndarray,
    rtol: float,
    atol: float,
    label: str,
) -> None:
    bad = ~np.isclose(actual, expected, rtol=rtol, atol=atol)
    if np.any(bad):
        idx = np.argwhere(bad)[0] if actual.ndim > 1 else (int(np.argwhere(bad)[0]),)
        raise AssertionError(
            f"{label}: worst entry {tuple(int(k) for k in idx)} "
            f"analytic={actual[tuple(idx)]!r} reference={expected[tuple(idx)]!r}"
        )


# --------------------------------------------------------------------------
# Primary check: complex-step, every entry
# --------------------------------------------------------------------------


def test_gradient_matches_complex_step() -> None:
    rng = np.random.default_rng(20261018)
    checks = 0

    for m in M_GRID:
        for n in N_GRID:
            for _ in range(8):
                mu, alpha, beta, times, types, horizon = _random_case(rng, m, n)
                g_mu, g_alpha, g_beta = grad_oracle(times, types, mu, alpha, beta, horizon)
                assert not np.any(
                    np.isnan(g_mu)
                ), "oracle gradient is undefined for a positive case"

                c_mu, c_alpha, c_beta = _complex_step_gradient(
                    times, types, mu, alpha, beta, horizon
                )

                _assert_close(g_mu, c_mu, 1e-9, 1e-10, f"d/dmu (M={m}, N={n})")
                _assert_close(g_alpha, c_alpha, 1e-9, 1e-10, f"d/dalpha (M={m}, N={n})")
                _assert_close(g_beta, c_beta, 1e-9, 1e-10, f"d/dbeta (M={m}, N={n})")
                checks += 1

    assert checks == len(M_GRID) * len(N_GRID) * 8


# --------------------------------------------------------------------------
# Independent check: central differences, every entry
# --------------------------------------------------------------------------


def test_gradient_matches_finite_differences() -> None:
    rng = np.random.default_rng(42)
    h = 1e-6
    cases = 40
    skipped = 0

    for _ in range(cases):
        m = int(rng.choice([2, 3]))
        n = 25
        mu, alpha, beta, times, types, horizon = _random_case(rng, m, n)

        g_mu, g_alpha, g_beta = grad_oracle(times, types, mu, alpha, beta, horizon)
        assert not np.any(np.isnan(g_mu))

        for i in range(m):
            plus, minus = mu.copy(), mu.copy()
            plus[i] += h
            minus[i] -= h
            plus_ell = loglik_oracle(times, types, plus, alpha, beta, horizon)
            minus_ell = loglik_oracle(times, types, minus, alpha, beta, horizon)
            numeric = (plus_ell - minus_ell) / (2 * h)
            _check_fd(g_mu[i], numeric, f"d/dmu[{i}]")

        for i in range(m):
            for j in range(m):
                if alpha[i, j] > h:
                    plus, minus = alpha.copy(), alpha.copy()
                    plus[i, j] += h
                    minus[i, j] -= h
                    numeric = (
                        loglik_oracle(times, types, mu, plus, beta, horizon)
                        - loglik_oracle(times, types, mu, minus, beta, horizon)
                    ) / (2 * h)
                    _check_fd(g_alpha[i, j], numeric, f"d/dalpha[{i},{j}]")
                else:
                    skipped += 1

                if beta[i, j] > h:
                    plus, minus = beta.copy(), beta.copy()
                    plus[i, j] += h
                    minus[i, j] -= h
                    numeric = (
                        loglik_oracle(times, types, mu, alpha, plus, horizon)
                        - loglik_oracle(times, types, mu, alpha, minus, horizon)
                    ) / (2 * h)
                    _check_fd(g_beta[i, j], numeric, f"d/dbeta[{i},{j}]")
                else:
                    skipped += 1

    # A skipped entry means the perturbation would have crossed zero, where the
    # derivative is not defined for the oracle's parameterisation.
    assert skipped < cases * 4


def _check_fd(analytic: float, numeric: float, label: str) -> None:
    abs_err = abs(analytic - numeric)
    rel_err = abs_err / max(abs(numeric), 1e-12)
    if rel_err > 1e-5 and abs_err > 1e-6:
        raise AssertionError(
            f"{label}: analytic={analytic!r} finite-difference={numeric!r} "
            f"(rel {rel_err:.2e}, abs {abs_err:.2e})"
        )


# --------------------------------------------------------------------------
# Edge cases with closed-form answers
# --------------------------------------------------------------------------


def test_zero_events() -> None:
    """With no events the likelihood is just minus the baseline compensator."""
    mu = np.array([0.5, 1.25, 2.0])
    alpha = np.zeros((3, 3))
    beta = np.ones((3, 3))
    horizon = 4.0

    ell = loglik_oracle(np.array([]), np.array([], dtype=np.uint8), mu, alpha, beta, horizon)
    assert np.isclose(ell, -mu.sum() * horizon)

    g_mu, g_alpha, g_beta = grad_oracle(
        np.array([]), np.array([], dtype=np.uint8), mu, alpha, beta, horizon
    )
    assert np.allclose(g_mu, -horizon)
    assert np.all(g_alpha == 0.0)
    assert np.all(g_beta == 0.0)


def test_single_event_single_type() -> None:
    """One event: the intensity at the event is the bare baseline."""
    mu = np.array([0.7])
    alpha = np.array([[0.3]])
    beta = np.array([[1.5]])
    times = np.array([2.0])
    types = np.array([0], dtype=np.uint8)
    horizon = 6.0

    decay = np.exp(-beta[0, 0] * (horizon - times[0]))
    expected = np.log(mu[0]) - mu[0] * horizon - (alpha[0, 0] / beta[0, 0]) * (1.0 - decay)
    assert np.isclose(loglik_oracle(times, types, mu, alpha, beta, horizon), expected)

    g_mu, g_alpha, g_beta = grad_oracle(times, types, mu, alpha, beta, horizon)
    assert np.isclose(g_mu[0], 1.0 / mu[0] - horizon)
    assert np.isclose(g_alpha[0, 0], -(1.0 - decay) / beta[0, 0])
    assert np.isclose(
        g_beta[0, 0],
        -(
            -alpha[0, 0] / beta[0, 0] ** 2 * (1.0 - decay)
            + alpha[0, 0] / beta[0, 0] * (horizon - times[0]) * decay
        ),
    )


def test_simultaneous_events_do_not_excite_each_other() -> None:
    """The spec sums over strictly earlier events: t^j_m < t, not <= t."""
    mu = np.array([0.5])
    alpha = np.array([[0.2]])
    beta = np.array([[1.0]])
    times = np.array([1.0, 1.0, 2.0])
    types = np.zeros(3, dtype=np.uint8)
    horizon = 5.0

    # At the second event at t=1 the first event is not strictly earlier, so the
    # intensity there is the baseline. Both t=1 events therefore contribute
    # log(0.5). At t=2 both earlier events are visible.
    lam_at_two = mu[0] + alpha[0, 0] * 2.0 * np.exp(-beta[0, 0] * (2.0 - 1.0))
    compensator = mu[0] * horizon + (alpha[0, 0] / beta[0, 0]) * (
        2.0 * (1.0 - np.exp(-beta[0, 0] * (horizon - 1.0)))
        + (1.0 - np.exp(-beta[0, 0] * (horizon - 2.0)))
    )
    expected = 2.0 * np.log(mu[0]) + np.log(lam_at_two) - compensator

    assert np.isclose(loglik_oracle(times, types, mu, alpha, beta, horizon), expected)


def test_single_type_multiple_events_matches_hand_recursion() -> None:
    """M=1 against an independently written recursion over the same events."""
    rng = np.random.default_rng(11)
    times = np.sort(rng.uniform(0.0, 20.0, 25))
    types = np.zeros(25, dtype=np.uint8)
    mu = np.array([0.4])
    alpha = np.array([[0.6]])
    beta = np.array([[0.9]])
    horizon = 25.0

    state = 0.0
    ell = 0.0
    for k, t_k in enumerate(times):
        if k > 0:
            state *= np.exp(-beta[0, 0] * (t_k - times[k - 1]))
        ell += np.log(mu[0] + alpha[0, 0] * state)
        state += 1.0
    compensator = mu[0] * horizon + (alpha[0, 0] / beta[0, 0]) * np.sum(
        1.0 - np.exp(-beta[0, 0] * (horizon - times))
    )
    assert np.isclose(loglik_oracle(times, types, mu, alpha, beta, horizon), ell - compensator)


def test_nonpositive_intensity_is_reported_not_clipped() -> None:
    """A zero baseline with zero excitation must give -inf, never a finite value."""
    times = np.array([1.0])
    types = np.array([0], dtype=np.uint8)
    mu = np.array([0.0])
    alpha = np.array([[0.0]])
    beta = np.array([[1.0]])

    assert loglik_oracle(times, types, mu, alpha, beta, 5.0) == -np.inf

    g_mu, g_alpha, g_beta = grad_oracle(times, types, mu, alpha, beta, 5.0)
    assert np.all(np.isnan(g_mu))
    assert np.all(np.isnan(g_alpha))
    assert np.all(np.isnan(g_beta))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("complex-step tolerance: rtol 1e-9, atol 1e-10")
    print("finite-difference tolerance: rel 1e-5 and abs 1e-6, both required")
