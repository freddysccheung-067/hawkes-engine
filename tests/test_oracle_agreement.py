"""Agreement between the C++ core and the frozen reference implementation.

The reference is imported by path and never edited. Every assertion here is an
error report first: when two implementations disagree, the numbers that disagree
are printed rather than a bare assertion message, because the next step is
diagnosis, not adjustment of a tolerance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "oracle"))

import hawkes_engine  # noqa: E402
from hawkes_oracle import grad_oracle, loglik_oracle  # noqa: E402

pytest.importorskip("hypothesis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _core(times, types, mu, alpha, beta, T, *, grad=False, shared=False):
    return hawkes_engine.loglik(
        np.ascontiguousarray(times, dtype=np.float64),
        np.ascontiguousarray(types, dtype=np.uint8),
        np.ascontiguousarray(mu, dtype=np.float64),
        np.ascontiguousarray(alpha, dtype=np.float64),
        np.ascontiguousarray(beta, dtype=np.float64),
        float(T),
        grad=grad,
        shared_decay=shared,
    )


def _rel(actual: float, expected: float) -> float:
    """Relative error with an absolute floor, for values that cross zero."""
    scale = max(abs(expected), 1e-300)
    return abs(actual - expected) / scale


def _entrywise_rel(actual: np.ndarray, expected: np.ndarray) -> tuple[float, tuple]:
    """Worst relative error, entry by entry, and where it occurred.

    The absolute backstop is a scale of 1e-12 relative to max|expected|: without
    it a true derivative of 1e-18 would report a relative error of 1 from
    rounding noise alone.
    """
    floor = 1e-12 * max(float(np.max(np.abs(expected))), 1e-300)
    with np.errstate(invalid="ignore", divide="ignore"):
        err = np.abs(actual - expected) / np.maximum(np.abs(expected), floor)
    err = np.nan_to_num(err, nan=np.inf)
    idx = np.unravel_index(int(np.argmax(err)), err.shape)
    return float(err[idx]), tuple(int(k) for k in idx)


def _case(rng, m, n, *, near_critical=False, ties=0):
    mu = rng.uniform(0.2, 1.5, m)
    alpha = rng.uniform(0.0, 0.4, (m, m))
    beta = rng.uniform(0.8, 3.0, (m, m))
    if m > 1 and alpha[0, 1] == alpha[0, 1]:
        # Keep every diagonal nonzero so a single-type spectral radius is
        # meaningful.
        np.fill_diagonal(alpha, rng.uniform(0.05, 0.3, m))
    if near_critical:
        gamma = alpha / beta
        rho = max(abs(np.linalg.eigvals(gamma)))
        if rho > 0:
            alpha = alpha * (0.95 / rho)
    times = np.sort(rng.uniform(0.0, 50.0, n))
    if ties and n >= 2:
        times[1] = times[0]
    types = rng.integers(0, m, n).astype(np.uint8)
    T = times[-1] + rng.uniform(0.5, 5.0) if n else float(rng.uniform(1.0, 10.0))
    return mu, alpha, beta, times, types, T


# ---------------------------------------------------------------------------
# Value agreement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("m", [1, 2, 3, 4, 6])
@pytest.mark.parametrize("n", [0, 1, 2, 10, 50, 200])
def test_value_matches_oracle(m, n):
    rng = np.random.default_rng(1000 + 17 * m + n)
    mu, alpha, beta, times, types, T = _case(rng, m, n)

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    got = _core(times, types, mu, alpha, beta, T)["value"]

    assert np.isfinite(expected)
    rel = _rel(got, expected)
    assert rel <= 1e-12, f"M={m} N={n}: core={got!r} oracle={expected!r} rel={rel:.3e}"


def test_value_matches_oracle_at_n1000():
    # Summation order differs between a running recursion and a double loop.
    # Measured worst case at this size is 7.5e-14 (M = 4, N = 1000), so the
    # 1e-12 bound is not reached and no relaxation is needed or taken. The
    # measurement is reproduced by tests/test_measured_agreement.py.
    rng = np.random.default_rng(77)
    mu, alpha, beta, times, types, T = _case(rng, 4, 1000)

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    got = _core(times, types, mu, alpha, beta, T)["value"]
    rel = _rel(got, expected)
    assert rel <= 1e-12, f"N=1000 rel={rel:.3e} core={got!r} oracle={expected!r}"


# ---------------------------------------------------------------------------
# Gradient agreement, entry by entry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("m", [1, 2, 3, 4])
@pytest.mark.parametrize("n", [1, 2, 10, 50, 200])
def test_gradient_matches_oracle(m, n):
    rng = np.random.default_rng(2000 + 13 * m + n)
    mu, alpha, beta, times, types, T = _case(rng, m, n)
    if n == 0:
        pytest.skip("covered by the closed-form cases")

    out = _core(times, types, mu, alpha, beta, T, grad=True)
    o_mu, o_alpha, o_beta = grad_oracle(times, types, mu, alpha, beta, T)
    assert not np.any(np.isnan(o_mu))

    for name, actual, expected in (
        ("dmu", out["dmu"], o_mu),
        ("dalpha", out["dalpha"], o_alpha),
        ("dbeta", out["dbeta"], o_beta),
    ):
        rel, idx = _entrywise_rel(np.asarray(actual), np.asarray(expected))
        assert rel <= 1e-10, (
            f"{name} M={m} N={n} entry {idx}: core={actual[idx]!r} "
            f"oracle={expected[idx]!r} rel={rel:.3e}"
        )


def test_gradient_matches_complex_step_of_oracle():
    """The core gradient against complex-step differentiation of the oracle.

    This check shares no code path with the analytic oracle gradient: it reads
    the derivative off the imaginary part of the oracle likelihood itself.
    """
    from test_oracle_gradient import _complex_step_gradient

    rng = np.random.default_rng(31)
    for m in (1, 2, 3):
        mu, alpha, beta, times, types, T = _case(rng, m, 20)
        out = _core(times, types, mu, alpha, beta, T, grad=True)
        c_mu, c_alpha, c_beta = _complex_step_gradient(times, types, mu, alpha, beta, T)
        for name, actual, expected in (
            ("dmu", out["dmu"], c_mu),
            ("dalpha", out["dalpha"], c_alpha),
            ("dbeta", out["dbeta"], c_beta),
        ):
            rel, idx = _entrywise_rel(np.asarray(actual), np.asarray(expected))
            assert rel <= 1e-9, (
                f"{name} M={m} entry {idx}: core={actual[idx]!r} "
                f"complex-step={expected[idx]!r} rel={rel:.3e}"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_simultaneous_timestamps():
    rng = np.random.default_rng(5)
    mu, alpha, beta, times, types, T = _case(rng, 3, 40)
    # Force several runs of ties.
    times[3:8] = times[3]
    types[3:8] = rng.integers(0, 3, 5)
    times[-2:] = times[-3]

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    out = _core(times, types, mu, alpha, beta, T, grad=True)
    assert _rel(out["value"], expected) <= 1e-12

    o_mu, o_alpha, o_beta = grad_oracle(times, types, mu, alpha, beta, T)
    for name, actual, exp in (
        ("dmu", out["dmu"], o_mu),
        ("dalpha", out["dalpha"], o_alpha),
        ("dbeta", out["dbeta"], o_beta),
    ):
        rel, idx = _entrywise_rel(np.asarray(actual), np.asarray(exp))
        assert rel <= 1e-10, f"{name} entry {idx} rel={rel:.3e}"


def test_events_at_time_zero():
    mu = np.array([0.9, 0.4])
    alpha = np.array([[0.1, 0.2], [0.3, 0.15]])
    beta = np.array([[1.0, 2.0], [1.5, 1.1]])
    times = np.array([0.0, 0.0, 0.5, 2.0])
    types = np.array([0, 1, 0, 1], dtype=np.uint8)
    T = 3.0

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    assert _rel(_core(times, types, mu, alpha, beta, T)["value"], expected) <= 1e-12


def test_horizon_equals_last_event():
    rng = np.random.default_rng(9)
    mu, alpha, beta, times, types, _ = _case(rng, 2, 30)
    T = float(times[-1])

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    assert _rel(_core(times, types, mu, alpha, beta, T)["value"], expected) <= 1e-12


def test_large_beta_times_dt_underflows_harmlessly():
    mu = np.array([1.0])
    alpha = np.array([[0.5]])
    beta = np.array([[1e6]])
    times = np.array([0.0, 1.0, 2.0])
    types = np.zeros(3, dtype=np.uint8)
    T = 3.0

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    got = _core(times, types, mu, alpha, beta, T)["value"]
    assert _rel(got, expected) <= 1e-12
    # The decay is gone, so the only excitation is the immediately preceding
    # event at its full height: alpha * 1, once, at t = 2.
    assert np.isclose(got, expected)


def test_nonpositive_intensity_returns_minus_infinity():
    times = np.array([1.0])
    types = np.array([0], dtype=np.uint8)
    mu = np.array([0.0])
    alpha = np.array([[0.0]])
    beta = np.array([[1.0]])

    out = _core(times, types, mu, alpha, beta, 5.0, grad=True)
    assert out["value"] == -np.inf
    assert np.all(np.isnan(out["dmu"]))
    assert np.all(np.isnan(out["dalpha"]))
    assert np.all(np.isnan(out["dbeta"]))

    assert loglik_oracle(times, types, mu, alpha, beta, 5.0) == -np.inf


def test_tiny_mu_forces_lambda_near_zero_but_stays_finite():
    mu = np.array([1e-300])
    alpha = np.array([[0.0]])
    beta = np.array([[1.0]])
    times = np.array([0.5])
    types = np.zeros(1, dtype=np.uint8)
    T = 1.0

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    got = _core(times, types, mu, alpha, beta, T)["value"]
    assert np.isfinite(got)
    assert _rel(got, expected) <= 1e-12


# ---------------------------------------------------------------------------
# Shared decay
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("m", [1, 2, 3, 4, 6])
@pytest.mark.parametrize("n", [0, 1, 10, 50, 200])
def test_shared_decay_agrees_with_pair_and_oracle(m, n):
    rng = np.random.default_rng(4000 + 7 * m + n)
    mu = rng.uniform(0.2, 1.5, m)
    alpha = rng.uniform(0.0, 0.4, (m, m))
    beta_shared = rng.uniform(0.8, 3.0, m)
    beta_pair = np.tile(beta_shared, (m, 1))
    times = np.sort(rng.uniform(0.0, 50.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = times[-1] + 2.0 if n else 5.0

    expected = loglik_oracle(times, types, mu, alpha, beta_pair, T)
    pair = _core(times, types, mu, alpha, beta_pair, T)["value"]
    shared = _core(times, types, mu, alpha, beta_shared, T, shared=True)["value"]

    assert _rel(shared, expected) <= 1e-12, f"shared={shared!r} oracle={expected!r}"
    assert _rel(pair, expected) <= 1e-12, f"pair={pair!r} oracle={expected!r}"
    assert _rel(shared, pair) <= 1e-13, f"shared={shared!r} pair={pair!r}"


def test_shared_decay_gradient_matches_pair_sum():
    rng = np.random.default_rng(12)
    m, n = 3, 40
    mu = rng.uniform(0.2, 1.5, m)
    alpha = rng.uniform(0.0, 0.4, (m, m))
    beta_shared = rng.uniform(0.8, 3.0, m)
    beta_pair = np.tile(beta_shared, (m, 1))
    times = np.sort(rng.uniform(0.0, 50.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = 60.0

    shared = _core(times, types, mu, alpha, beta_shared, T, grad=True, shared=True)
    pair = _core(times, types, mu, alpha, beta_pair, T, grad=True)

    assert _rel(shared["value"], pair["value"]) <= 1e-13
    np.testing.assert_allclose(shared["dmu"], pair["dmu"], rtol=1e-12, atol=0)
    np.testing.assert_allclose(shared["dalpha"], pair["dalpha"], rtol=1e-12, atol=0)
    # dbeta_j in the shared case is the sum down column j of the pair gradient.
    np.testing.assert_allclose(shared["dbeta"], pair["dbeta"].sum(axis=0), rtol=1e-12, atol=0)

    o_mu, o_alpha, o_beta = grad_oracle(times, types, mu, alpha, beta_pair, T)
    np.testing.assert_allclose(shared["dbeta"], o_beta.sum(axis=0), rtol=1e-10, atol=0)
    np.testing.assert_allclose(shared["dmu"], o_mu, rtol=1e-10, atol=0)
    np.testing.assert_allclose(shared["dalpha"], o_alpha, rtol=1e-10, atol=0)
