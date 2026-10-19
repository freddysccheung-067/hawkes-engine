"""The H4 gate: both simulators sample the same law, and it is the right one.

Every statistical test here is deterministic (fixed seeds) and is a level-1e-3
test, calibrated offline by ``benchmarks/calibrate_tests.py``. The checks live
in ``tests/_stat_checks.py`` so that the calibration runs identical code. Where
a test asserts something that is merely likely, such as overdispersion, the
margin is stated beside it.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import hawkes_engine
import numpy as np
import pytest
from hawkes_engine import _core as core

from tests import _stat_checks as chk

METHODS = chk.METHODS
CASES = [(M, rho) for M in (1, 2, 3) for rho in (0.3, 0.6, 0.85)]


# ------------------------------------------------------------ stationary mean


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("M", "rho"), CASES)
def test_stationary_mean(method, M, rho):
    worst, z = chk.stationary_mean_z(method, M, rho, seed=101)
    print(f"stationary mean {method} M={M} rho={rho}: z = {np.round(z, 2)}")
    assert worst < chk.MEAN_Z_LIMIT, f"worst |z| = {worst:.2f}, z = {z}"


# --------------------------------------------------------- count distribution


def test_counts_come_from_one_distribution():
    p = chk.count_distribution_p(seed=102)
    print(f"count distribution, Bonferroni over Mann-Whitney and KS: p = {p:.3g}")
    assert p > chk.ALPHA


@pytest.mark.parametrize("rho", [0.6, 0.85])
def test_counts_are_overdispersed(rho):
    """Hawkes counts have variance well above the Poisson value of the mean.

    At rho = 0.6 the ratio is about 3.5; at rho = 0.3 it is about 1.5. The bound
    of 1.2 is a margin below the smaller, not a fitted number.
    """
    for method, ratio in chk.overdispersion(103, rho).items():
        assert np.all(ratio > 1.2), f"{method}: var/mean = {ratio}"


# ----------------------------------------------------------- gap distribution


def test_gap_distributions_agree_pairwise():
    p = chk.gap_distribution_p(seed=104)
    print(f"gap distribution, thinning vs cluster vs NumPy reference: p = {p:.3g}")
    assert p > chk.ALPHA


# ------------------------------------------------------------ time rescaling


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("M", "rho"), [(1, 0.3), (2, 0.6), (3, 0.85), (2, 0.3), (3, 0.6)])
def test_rescaling_under_the_truth_passes(method, M, rho):
    p = chk.rescaling_p(method, M, rho, seed=105)
    print(f"rescaling {method} M={M} rho={rho}: KS and Ljung-Box p = {p:.3g}")
    assert p > chk.ALPHA


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(("M", "rho"), [(1, 0.3), (2, 0.6), (3, 0.85)])
def test_rescaling_negative_control_rejects(method, M, rho):
    """A wrong baseline must fail, so the test above cannot be vacuous."""
    p = chk.rescaling_p(method, M, rho, seed=105, scale_mu=1.5)
    print(f"negative control {method} M={M} rho={rho}: p = {p:.3g}")
    assert p < chk.ALPHA


# -------------------------------------------------------------- Poisson limit


@pytest.mark.parametrize("method", METHODS)
def test_poisson_limit(method):
    p = chk.poisson_limit_p(method, seed=106)
    print(f"Poisson limit {method}: p = {p:.3g}")
    assert p > chk.ALPHA


# ------------------------------------------------------------- cluster size


@pytest.mark.parametrize("rho", [0.3, 0.6])
def test_mean_cluster_size(rho):
    """E[size] = 1/(1-rho) in the limit; at finite T the truncated value is exact."""
    est, se, exact, limit = chk.cluster_size(rho, seed=107)
    print(f"cluster size rho={rho}: {est:.4f} +- {se:.4f}, truncated {exact:.4f}, {limit=:.4f}")
    assert abs(est - exact) < 4 * se
    assert abs(exact - limit) / limit < 0.01


# ------------------------------------------------------ determinism, threads


def test_same_seed_same_output_and_different_seeds_differ():
    mu, alpha, beta = chk.make_params(2, 0.6)
    for method in METHODS:
        a = hawkes_engine.simulate(mu, alpha, beta, 50.0, method=method, seed=7)
        b = hawkes_engine.simulate(mu, alpha, beta, 50.0, method=method, seed=7)
        c = hawkes_engine.simulate(mu, alpha, beta, 50.0, method=method, seed=8)
        assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
        assert a[0].shape != c[0].shape or not np.array_equal(a[0], c[0])


def test_simulate_many_is_repeatable_and_thread_count_free():
    mu, alpha, beta = chk.make_params(2, 0.6)
    kw = {"method": "thinning", "seed": 11}
    first = hawkes_engine.simulate_many(mu, alpha, beta, 30.0, n_paths=24, **kw)
    again = hawkes_engine.simulate_many(mu, alpha, beta, 30.0, n_paths=24, **kw)

    def one(k):
        return hawkes_engine.simulate(
            mu, alpha, beta, 30.0, method="thinning", seed=core.seed_stream(11, k)
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        threaded = list(pool.map(one, range(24)))
    for x, y, z in zip(first, again, threaded, strict=True):
        assert np.array_equal(x[0], y[0]) and np.array_equal(x[0], z[0])
        assert np.array_equal(x[1], y[1]) and np.array_equal(x[1], z[1])


def test_paths_of_simulate_many_are_distinct():
    mu, alpha, beta = chk.make_params(1, 0.5)
    paths = hawkes_engine.simulate_many(mu, alpha, beta, 40.0, n_paths=50, seed=3)
    assert len({p[0].tobytes() for p in paths}) == 50


# ------------------------------------------------------------- output contract


@pytest.mark.parametrize("method", METHODS)
def test_output_is_sorted_typed_and_in_window(method):
    mu, alpha, beta = chk.make_params(3, 0.85)
    t, k = hawkes_engine.simulate(mu, alpha, beta, 200.0, method=method, seed=5, t0=-10.0)
    assert t.dtype == np.float64 and k.dtype == np.uint8
    assert t.size > 100 and t.size == k.size
    assert np.all(np.diff(t) >= 0.0)
    assert t[0] >= -10.0 and t[-1] < 200.0
    assert k.max() < 3
    for i in range(3):
        assert np.all(np.diff(t[k == i]) > 0.0), "equal times within one type"


@pytest.mark.parametrize("method", METHODS)
def test_rho_at_or_above_one_raises_and_names_the_radius(method):
    mu, beta = np.array([0.5]), np.array([[1.0]])
    for a, expected in ((1.0, "1"), (1.5, "1.5")):
        with pytest.raises(ValueError, match=r"spectral radius.*" + expected):
            hawkes_engine.simulate(mu, np.array([[a]]), beta, 10.0, method=method, seed=1)


@pytest.mark.parametrize("method", METHODS)
def test_malformed_arguments_raise(method):
    mu, alpha, beta = chk.make_params(1, 0.5)
    for T in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            hawkes_engine.simulate(mu, alpha, beta, T, method=method, seed=1)
    with pytest.raises(ValueError):
        hawkes_engine.simulate(mu, alpha, beta, 10.0, method=method, seed=1, t0=10.0)
    with pytest.raises(ValueError):
        hawkes_engine.simulate(mu, alpha, beta, 10.0, method=method, seed=1, burn_in=-1.0)
    with pytest.raises(ValueError):
        hawkes_engine.simulate(mu, alpha, beta, 10.0, method="nope", seed=1)
    with pytest.raises(ValueError):
        hawkes_engine.simulate(mu, alpha, beta, 10.0, method=method, seed=-1)
    with pytest.raises(TypeError):
        hawkes_engine.simulate(mu, alpha, beta, 10.0, method=method, seed=1.5)


@pytest.mark.parametrize("method", METHODS)
def test_empty_output_has_the_right_dtypes(method):
    t, k = hawkes_engine.simulate(
        np.array([1e-9]), np.array([[0.1]]), np.array([[1.0]]), 1.0, method=method, seed=1
    )
    assert t.shape == (0,) and k.shape == (0,)
    assert t.dtype == np.float64 and k.dtype == np.uint8
    t, k = hawkes_engine.simulate(
        np.zeros(2), np.zeros((2, 2)), np.ones((2, 2)), 5.0, method=method, seed=1
    )
    assert t.size == 0 and k.dtype == np.uint8


@pytest.mark.parametrize("method", METHODS)
def test_burn_in_removes_the_empty_start(method):
    """From an empty history the early rate is below stationary; burn-in fixes it."""
    mu, alpha, beta = chk.make_params(1, 0.85)
    target = float(core.stationary_mean(mu, alpha, beta)[0])
    early = {0.0: [], 60.0: []}
    for burn_in in early:
        for s in range(400):
            t, _ = hawkes_engine.simulate(
                mu, alpha, beta, 1.0, method=method, seed=s, burn_in=burn_in
            )
            early[burn_in].append(t.size)
    cold, warm = np.array(early[0.0]), np.array(early[60.0])
    se = warm.std(ddof=1) / np.sqrt(warm.size)
    print(
        f"{method}: first unit of time, cold {cold.mean():.3f}, warm {warm.mean():.3f}, "
        f"stationary {target:.3f}"
    )
    assert cold.mean() < 0.8 * target
    assert abs(warm.mean() - target) < 4 * se


# ------------------------------------------------------------ likelihood tie


def test_simulator_and_likelihood_are_consistent():
    gain, z, worst = chk.loglik_consistency(seed=108)
    print(
        f"true vs perturbed: mean gain {gain:.5f} per event, z = {z:.1f}; "
        f"core vs oracle worst relative difference {worst:.2e}"
    )
    assert gain > 0.0 and z > 4.0
    assert worst <= 1e-12


# ------------------------------------------------------------- independence


def test_the_two_simulators_share_no_source():
    """A reviewer's grep, kept as a test: neither simulator includes the other."""
    src = Path(__file__).parent.parent / "cpp" / "src"
    for mine, other in (("simulate_thin", "cluster"), ("simulate_cluster", "thin")):
        text = (src / f"{mine}.cpp").read_text(encoding="utf-8")
        includes = re.findall(r'#include\s+"hawkes/([^"]+)"', text)
        assert not any(other in name for name in includes), includes
        assert set(includes) <= {
            f"{mine}.hpp",
            "diagnostics.hpp",
            "rng.hpp",
            "validation.hpp",
        }
