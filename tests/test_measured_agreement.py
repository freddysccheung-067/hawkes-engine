"""Reports the measured worst-case agreement between the core and the reference.

The other agreement tests assert a bound. This one measures it, over a grid
wider than the assertions cover, and fails only if the measured number exceeds
the published claim. The numbers it prints are the ones recorded in
docs/STATE.md, so a regression in either implementation shows up as a changed
measurement rather than as a test that merely still passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "oracle"))

import hawkes_engine  # noqa: E402
from hawkes_oracle import grad_oracle, loglik_oracle  # noqa: E402


def _core(*args, **kwargs):
    return hawkes_engine.loglik(*args, **kwargs)


def _rel(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-300)


def _entry_rel(actual: np.ndarray, expected: np.ndarray) -> float:
    floor = 1e-12 * max(float(np.max(np.abs(expected))), 1e-300)
    err = np.abs(actual - expected) / np.maximum(np.abs(expected), floor)
    return float(np.nanmax(np.nan_to_num(err, nan=np.inf)))


def test_measured_agreement_grid(capsys):
    worst_value = 0.0
    worst_grad = 0.0
    value_at = ("", 0, 0)
    grad_at = ("", 0, 0)

    for m in (1, 2, 3, 4, 6):
        for n in (1, 2, 10, 50, 200, 1000):
            rng = np.random.default_rng(90_000 + 131 * m + n)
            mu = rng.uniform(0.2, 1.5, m)
            alpha = rng.uniform(0.0, 0.4, (m, m))
            beta = rng.uniform(0.8, 3.0, (m, m))
            times = np.sort(rng.uniform(0.0, 50.0, n))
            types = rng.integers(0, m, n).astype(np.uint8)
            T = float(times[-1] + 2.0)

            expected = loglik_oracle(times, types, mu, alpha, beta, T)
            out = hawkes_engine.loglik(
                np.ascontiguousarray(times, np.float64),
                np.ascontiguousarray(types, np.uint8),
                np.ascontiguousarray(mu, np.float64),
                np.ascontiguousarray(alpha, np.float64),
                np.ascontiguousarray(beta, np.float64),
                T,
                grad=True,
            )
            value_rel = _rel(out["value"], expected)
            if value_rel > worst_value:
                worst_value = value_rel
                value_at = ("value", m, n)

            o_mu, o_alpha, o_beta = grad_oracle(times, types, mu, alpha, beta, T)
            for block, actual, exp in (
                ("dmu", out["dmu"], o_mu),
                ("dalpha", out["dalpha"], o_alpha),
                ("dbeta", out["dbeta"], o_beta),
            ):
                rel = _entry_rel(np.asarray(actual), np.asarray(exp))
                if rel > worst_grad:
                    worst_grad = rel
                    grad_at = (block, m, n)

    with capsys.disabled():
        print(
            f"\nworst value relative error : {worst_value:.3e}  (M={value_at[1]}, N={value_at[2]})"
        )
        print(
            f"worst gradient entry error : {worst_grad:.3e}  "
            f"({grad_at[0]}, M={grad_at[1]}, N={grad_at[2]})"
        )

    # Published claim: 1e-12 for the value, 1e-10 for the gradient, both over
    # every entry of every block.
    assert worst_value <= 1e-12
    assert worst_grad <= 1e-10


def test_measured_n1000_is_the_summation_order():
    """At N = 1000 the value bound is set by summation order, not by algebra."""
    rng = np.random.default_rng(4)
    m, n = 4, 1000
    mu = rng.uniform(0.2, 1.5, m)
    alpha = rng.uniform(0.0, 0.3, (m, m))
    beta = rng.uniform(0.8, 3.0, (m, m))
    times = np.sort(rng.uniform(0.0, 50.0, n))
    types = rng.integers(0, m, n).astype(np.uint8)
    T = float(times[-1] + 2.0)

    expected = loglik_oracle(times, types, mu, alpha, beta, T)
    got = _core(times, types, mu, alpha, beta, T)["value"]
    rel = _rel(got, expected)
    # The recursion sums N terms forward; the oracle sums each type's events in
    # the same forward order but through a different expression. A few ulp of
    # difference in the last bits is expected and is what bounds this case.
    assert rel <= 1e-12
