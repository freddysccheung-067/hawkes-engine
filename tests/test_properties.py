"""Structural properties of the likelihood.

These are statements about the mathematics, not about agreement with the
reference: a value that matched the oracle but violated one of these would mean
both implementations shared a defect. Each test is named for the property it
pins.
"""

from __future__ import annotations

import hawkes_engine
import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st


def _call(times, types, mu, alpha, beta, T, *, grad=False, shared=False):
    return hawkes_engine.loglik(
        np.asarray(times, dtype=np.float64),
        np.asarray(types, dtype=np.uint8),
        np.asarray(mu, dtype=np.float64),
        np.asarray(alpha, dtype=np.float64),
        np.asarray(beta, dtype=np.float64),
        float(T),
        grad=grad,
        shared_decay=shared,
    )


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-300)


def _poisson_limit_value(types, mu, T):
    counts = np.bincount(types, minlength=mu.shape[0]) if len(types) else np.zeros_like(mu)
    return float(np.sum(counts * np.log(mu)) - T * np.sum(mu))


# Small, well-conditioned instances: the properties hold at every size, but the
# oracle-free checks run fastest and clearest here.
_params = st.integers(min_value=1, max_value=4).flatmap(
    lambda m: st.tuples(
        st.lists(
            st.floats(min_value=0.15, max_value=2.0, allow_nan=False, allow_infinity=False),
            min_size=m,
            max_size=m,
        ),
        st.lists(
            st.floats(min_value=0.0, max_value=0.25, allow_nan=False, allow_infinity=False),
            min_size=m * m,
            max_size=m * m,
        ),
        st.lists(
            st.floats(min_value=0.9, max_value=3.0, allow_nan=False, allow_infinity=False),
            min_size=m * m,
            max_size=m * m,
        ),
    ).map(lambda t: (m, np.array(t[0]), np.array(t[1]).reshape(m, m), np.array(t[2]).reshape(m, m)))
)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(params=_params, data=st.data())
def test_poisson_limit(params, data):
    """With alpha = 0 the likelihood is exactly sum(n_i log mu_i) - T sum(mu_i)."""
    m, mu, _, beta = params
    n = data.draw(st.integers(min_value=0, max_value=30))
    times = np.sort(
        np.array(
            data.draw(
                st.lists(
                    st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
                    min_size=n,
                    max_size=n,
                )
            ),
            dtype=np.float64,
        )
    )
    types = np.array(
        data.draw(st.lists(st.integers(min_value=0, max_value=m - 1), min_size=n, max_size=n)),
        dtype=np.uint8,
    )
    T = float(times[-1] + 1.0) if n else 5.0

    got = _call(times, types, mu, np.zeros((m, m)), beta, T)["value"]
    assert _rel(got, _poisson_limit_value(types, mu, T)) <= 1e-13


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(params=_params, data=st.data())
def test_time_shift_invariance(params, data):
    """What a shift by s moves, and what it leaves alone.

    The likelihood is not invariant: the baseline compensator is mu_i T, so
    ell falls by s*sum(mu_i). Neither is d/dmu, which carries a -T of its own
    and therefore falls by s per entry. What *is* invariant is everything that
    sees only differences of times: the excitation part of the likelihood and
    the whole of dalpha and dbeta. Those are asserted exactly.

    A shift performed in float64 can also merge two distinct timestamps into
    one when their gap is below the resolution of the shifted values. That
    changes the mathematical input, so such examples are skipped rather than
    counted as failures.
    """
    m, mu, alpha, beta = params
    n = data.draw(st.integers(min_value=1, max_value=25))
    times = np.sort(
        np.array(
            data.draw(
                st.lists(
                    st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),
                    min_size=n,
                    max_size=n,
                )
            ),
            dtype=np.float64,
        )
    )
    types = np.array(
        data.draw(st.lists(st.integers(min_value=0, max_value=m - 1), min_size=n, max_size=n)),
        dtype=np.uint8,
    )
    T = float(times[-1] + 1.0)

    base = _call(times, types, mu, alpha, beta, T, grad=True)
    for shift in (1.0, 137.5):
        moved_times = times + shift
        # A shift that merges distinct timestamps has changed the input.
        assume(len(np.unique(moved_times)) == len(np.unique(times)))

        moved = _call(moved_times, types, mu, alpha, beta, T + shift, grad=True)
        expected = base["value"] - shift * float(np.sum(mu))
        assert _rel(moved["value"], expected) <= 1e-11, (
            f"shift={shift}: moved={moved['value']!r} expected={expected!r} "
            f"base={base['value']!r}"
        )
        # -T in d/dmu moves with the window; the excitation part does not.
        np.testing.assert_allclose(moved["dmu"], base["dmu"] - shift, rtol=1e-10, atol=1e-12)
        # dalpha and dbeta see only differences of times, so they are invariant.
        np.testing.assert_allclose(moved["dalpha"], base["dalpha"], rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(moved["dbeta"], base["dbeta"], rtol=1e-10, atol=1e-12)


@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    m=st.integers(min_value=2, max_value=4),
    n=st.integers(min_value=5, max_value=40),
)
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_permutation_invariance(seed, m, n):
    """Relabelling the dimensions and permuting the parameters leaves ell fixed."""
    rng = np.random.default_rng(seed)
    mu = rng.uniform(0.2, 1.5, m)
    alpha = rng.uniform(0.0, 0.25, (m, m))
    beta = rng.uniform(0.9, 3.0, (m, m))
    times = np.sort(rng.uniform(0.0, 30.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = float(times[-1] + 2.0)

    perm = rng.permutation(m)
    inverse = np.argsort(perm)
    permuted = _call(
        times,
        inverse[types],
        mu[perm],
        alpha[np.ix_(perm, perm)],
        beta[np.ix_(perm, perm)],
        T,
        grad=True,
    )
    original = _call(times, types, mu, alpha, beta, T, grad=True)

    assert _rel(permuted["value"], original["value"]) <= 1e-12
    # Undo the relabelling before comparing blocks.
    np.testing.assert_allclose(permuted["dmu"][inverse], original["dmu"], rtol=1e-10, atol=1e-12)


@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    n=st.integers(min_value=3, max_value=40),
)
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_mu_derivative_without_excitation(seed, n):
    """With alpha = 0 the gradient in mu is exactly n_i / mu_i - T.

    The likelihood is *not* monotone in mu: the derivative is positive whenever
    a type has more events than its baseline explains over the window. The
    exact derivative is the statement that holds, so that is what is pinned
    here rather than a monotonicity that is simply false.
    """
    rng = np.random.default_rng(seed)
    m = 3
    mu = rng.uniform(0.3, 1.0, m)
    beta = rng.uniform(1.0, 2.0, (m, m))
    times = np.sort(rng.uniform(0.0, 20.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = float(times[-1] + 1.0)
    zero = np.zeros((m, m))

    out = _call(times, types, mu, zero, beta, T, grad=True)
    counts = np.bincount(types, minlength=m).astype(np.float64)
    expected = counts / mu - T
    np.testing.assert_allclose(out["dmu"], expected, rtol=1e-12, atol=1e-12)

    # dalpha is not zero even with alpha = 0. Two contributions survive: the
    # event term, because S_ij is nonzero whether or not alpha_ij is (events
    # excite the state regardless), and the compensator, which differentiates
    # to -C_ij/beta_ij. With alpha = 0 the intensity at every event is exactly
    # mu_i, so both pieces are elementary.
    u = T - times
    expected_alpha = np.zeros((m, m))
    for i in range(m):
        for j in range(m):
            event_term = 0.0
            for k in np.flatnonzero(types == i):
                s = np.sum(
                    np.exp(-beta[i, j] * (times[k] - times[(types == j) & (times < times[k])]))
                )
                event_term += s / mu[i]
            comp = np.sum(-np.expm1(-beta[i, j] * u[types == j])) / beta[i, j]
            expected_alpha[i, j] = event_term - comp
    np.testing.assert_allclose(out["dalpha"], expected_alpha, rtol=1e-12, atol=1e-13)

    # dbeta does vanish: the compensator term is (alpha/beta)*C, and alpha = 0
    # makes every entry of that block zero whatever C is.
    np.testing.assert_allclose(out["dbeta"], 0.0, atol=1e-15)


def test_shared_decay_matches_pair_for_every_row_identical_block():
    """The fast path is an exact restatement, checked outside the oracle tests."""
    rng = np.random.default_rng(404)
    m, n = 5, 120
    mu = rng.uniform(0.2, 1.2, m)
    alpha = rng.uniform(0.0, 0.2, (m, m))
    beta = rng.uniform(0.7, 2.5, m)
    times = np.sort(rng.uniform(0.0, 60.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)

    a = _call(times, types, mu, alpha, beta, 70.0, shared=True)["value"]
    b = _call(times, types, mu, alpha, np.tile(beta, (m, 1)), 70.0)["value"]
    assert _rel(a, b) <= 1e-13


@pytest.mark.parametrize(
    "bad, message",
    [
        (lambda: _call([1.0], [0], [1.0], [[0.1]], [[1.0]], 2.0, shared=True), "shape"),
    ],
)
def test_shape_errors_are_value_errors(bad, message):
    with pytest.raises(ValueError, match=message):
        bad()


def test_unsorted_times_raise():
    # pybind11 maps std::invalid_argument to ValueError, so the boundary error
    # is a normal Python one rather than a RuntimeError from the C++ layer.
    with pytest.raises(ValueError, match="non-decreasing"):
        _call([2.0, 1.0], [0, 0], [1.0], [[0.1]], [[1.0]], 3.0)


def test_type_index_out_of_range_raises():
    with pytest.raises(ValueError, match="not less than M"):
        _call([1.0], [2], [0.5, 0.5], [[0.1, 0.0], [0.0, 0.1]], [[1.0, 1.0], [1.0, 1.0]], 2.0)


def test_float32_times_are_rejected_or_cast_explicitly():
    # The wrapper casts to float64 on purpose; the compiled layer must not
    # receive float32, because the 1e-12 agreement claim assumes binary64.
    out = hawkes_engine.loglik(
        np.array([1.0], dtype=np.float32),
        np.array([0], dtype=np.uint8),
        np.array([0.5]),
        np.array([[0.1]]),
        np.array([[1.0]]),
        2.0,
    )
    assert np.isfinite(out["value"])
