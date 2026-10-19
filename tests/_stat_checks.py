"""Statistical checks for the simulators, as functions of a seed.

Each check returns a p-value (or, for the mean-intensity check, a worst z-score)
so that the tests in ``test_simulators.py`` and the offline calibration in
``benchmarks/calibrate_tests.py`` run exactly the same code. A test that has not
been run under many seeds has an unknown false-rejection rate; the calibration
script is what makes the nominal level of these checks a measured one.

Multiple comparisons inside one check (several dimensions, several tests) are
combined by Bonferroni, so every check is a level-``ALPHA`` test as a whole.
"""

from __future__ import annotations

import sys
from pathlib import Path

import hawkes_engine
import numpy as np
from hawkes_engine import _core as core
from hawkes_engine import ks_test, simulate, simulate_many, time_rescale
from hawkes_engine.diagnostics import ljung_box
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent / "oracle"))
from hawkes_oracle import loglik_oracle  # noqa: E402

from tests._simulate_reference import simulate_cluster as ref_cluster
from tests._simulate_reference import simulate_thinning as ref_thinning

ALPHA = 1e-3
MEAN_Z_LIMIT = 4.0
METHODS = ("thinning", "cluster")


def make_params(M: int, rho: float, seed: int = 0):
    """Parameters with ``rho(alpha / beta) = rho`` exactly, all entries nonzero."""
    rng = np.random.default_rng(1000 * M + seed)
    gamma = rng.uniform(0.3, 1.0, (M, M))
    beta = rng.uniform(0.8, 2.0, (M, M))
    mu = rng.uniform(0.3, 0.7, M)
    alpha_unscaled = gamma * beta
    radius = core.spectral_radius(mu, alpha_unscaled, beta)
    alpha = alpha_unscaled * (rho / radius)
    return mu, alpha, beta


def _bonferroni(pvalues) -> float:
    p = np.asarray(pvalues, dtype=float)
    return float(min(1.0, p.min() * p.size))


def stationary_mean_z(method: str, M: int, rho: float, seed: int, n_paths: int = 400):
    """Worst |z| of the empirical rate against ``(I - Gamma)^{-1} mu``.

    The standard error comes from the between-path variance of the per-path
    rates, not from an assumed Poisson variance, which would understate it by
    the overdispersion factor.
    """
    mu, alpha, beta = make_params(M, rho)
    T, burn_in = 100.0, 100.0
    paths = simulate_many(
        mu, alpha, beta, T, n_paths=n_paths, method=method, seed=seed, burn_in=burn_in
    )
    rates = np.array([np.bincount(k, minlength=M) / T for _, k in paths])
    expected = core.stationary_mean(mu, alpha, beta)
    se = rates.std(axis=0, ddof=1) / np.sqrt(n_paths)
    z = (rates.mean(axis=0) - expected) / se
    return float(np.max(np.abs(z))), z


def count_distribution_p(seed: int, n_paths: int = 2000) -> float:
    """Counts of the two simulators come from one distribution, per dimension."""
    mu, alpha, beta = make_params(2, 0.6)
    T = 50.0
    counts = {}
    for method in METHODS:
        paths = simulate_many(mu, alpha, beta, T, n_paths=n_paths, method=method, seed=seed)
        counts[method] = np.array([np.bincount(k, minlength=2) for _, k in paths])
    ps = []
    for i in range(2):
        a, b = counts["thinning"][:, i], counts["cluster"][:, i]
        ps.append(stats.mannwhitneyu(a, b).pvalue)
        ps.append(stats.ks_2samp(a, b).pvalue)
    return _bonferroni(ps)


def overdispersion(seed: int, rho: float, n_paths: int = 2000):
    """Variance-to-mean ratio of counts per dimension, one value per method."""
    mu, alpha, beta = make_params(2, rho)
    out = {}
    for method in METHODS:
        paths = simulate_many(mu, alpha, beta, 50.0, n_paths=n_paths, method=method, seed=seed)
        c = np.array([np.bincount(k, minlength=2) for _, k in paths])
        out[method] = c.var(axis=0, ddof=1) / c.mean(axis=0)
    return out


def _gaps(times: np.ndarray, stride: int) -> np.ndarray:
    return np.diff(times)[::stride]


def gap_distribution_p(seed: int, n_paths: int = 300, stride: int = 10) -> float:
    """Pairwise two-sample KS on inter-event gaps: thinning, cluster, NumPy reference.

    Gaps inside a path are dependent, so only every ``stride``-th is kept; the
    calibration run is what verifies that this restores the nominal level.
    """
    mu, alpha, beta = make_params(2, 0.6)
    T = 100.0
    samples = {}
    for method in METHODS:
        paths = simulate_many(mu, alpha, beta, T, n_paths=n_paths, method=method, seed=seed)
        samples[method] = np.concatenate([_gaps(t, stride) for t, _ in paths])
    parts = []
    for k in range(n_paths):
        rng = np.random.default_rng([seed, k])
        parts.append(_gaps(ref_thinning(mu, alpha, beta, T, 2, rng).times, stride))
    samples["reference"] = np.concatenate(parts)
    pairs = [("thinning", "cluster"), ("thinning", "reference"), ("cluster", "reference")]
    return _bonferroni([stats.ks_2samp(samples[a], samples[b]).pvalue for a, b in pairs])


def rescaling_p(method: str, M: int, rho: float, seed: int, scale_mu: float = 1.0) -> float:
    """KS and Ljung-Box on rescaled gaps, rescaling with ``mu * scale_mu``.

    ``scale_mu = 1`` is the null: the true parameters. Any other value is the
    negative control and should drive the p-value to zero. The window is sized
    for about 30000 events so that the control has power at high rho, where the
    baseline is a small share of the intensity.
    """
    mu, alpha, beta = make_params(M, rho)
    T = 30000.0 / float(core.stationary_mean(mu, alpha, beta).sum())
    times, types = simulate(mu, alpha, beta, T, method=method, seed=seed)
    gaps = time_rescale(times, types, mu * scale_mu, alpha, beta)
    ps = np.concatenate([ks_test(gaps).pvalue, ljung_box(gaps).pvalue])
    return _bonferroni(ps)


def poisson_limit_p(method: str, seed: int, M: int = 3, n_paths: int = 2000) -> float:
    """alpha = 0: counts are Poisson(mu_i T) and times are uniform given the count."""
    mu = np.array([0.4, 1.1, 2.0])[:M]
    alpha, beta = np.zeros((M, M)), np.ones((M, M))
    T = 10.0
    paths = simulate_many(mu, alpha, beta, T, n_paths=n_paths, method=method, seed=seed)
    counts = np.array([np.bincount(k, minlength=M) for _, k in paths])
    # Randomized probability integral transform: exactly uniform for a discrete
    # law, so the continuous KS applies without its usual conservatism.
    jitter = np.random.default_rng(seed).uniform(size=counts.shape)
    ps = []
    for i in range(M):
        cdf_hi = stats.poisson.cdf(counts[:, i], mu[i] * T)
        cdf_lo = stats.poisson.cdf(counts[:, i] - 1, mu[i] * T)
        ps.append(stats.kstest(cdf_lo + jitter[:, i] * (cdf_hi - cdf_lo), "uniform").pvalue)
    times = np.concatenate([t for t, _ in paths]) / T
    ps.append(stats.kstest(times, "uniform").pvalue)
    return _bonferroni(ps)


def cluster_size(rho: float, seed: int, n_paths: int = 20000):
    """Mean cluster size from one immigrant, estimated and exact, with its SE.

    Immigrants are Poisson with mean ``mu T = 1`` and each path's count is
    immigrants times cluster size, so ``E[N] / (mu T)`` estimates the mean
    cluster size without having to condition on a single immigrant. Truncation at
    ``T`` removes a known amount: for one immigrant uniform on ``[0, T]`` the
    expected size is ``1 / (1 - rho) - rho (1 - exp(-b T)) / (beta (1 - rho)^2 T)``
    with ``b = beta (1 - rho)``. As ``T`` grows that tends to ``1 / (1 - rho)``.
    """
    beta, T = 1.0, 400.0
    mu = np.array([1.0 / T])
    alpha = np.array([[rho * beta]])
    paths = simulate_many(
        mu, alpha, np.array([[beta]]), T, n_paths=n_paths, method="cluster", seed=seed
    )
    n = np.array([t.size for t, _ in paths], dtype=float)
    est = n.mean()
    se = n.std(ddof=1) / np.sqrt(n_paths)
    b = beta * (1.0 - rho)
    exact = 1.0 / (1.0 - rho) - rho * (1.0 - np.exp(-b * T)) / (beta * (1.0 - rho) ** 2 * T)
    return float(est), float(se), float(exact), 1.0 / (1.0 - rho)


def loglik_consistency(seed: int, n_paths: int = 200):
    """Per-event gain of the true parameters over perturbed ones, and the oracle gap.

    Returns the mean paired gain, its z-score, and the worst relative difference
    between the compiled and the reference log-likelihood over the paths.
    """
    mu, alpha, beta = make_params(2, 0.5)
    T = 40.0
    paths = simulate_many(mu, alpha, beta, T, n_paths=n_paths, method="thinning", seed=seed)
    gain, worst = [], 0.0
    for t, k in paths:
        if t.size == 0:
            continue
        true = hawkes_engine.loglik(t, k, mu, alpha, beta, T)["value"]
        off = hawkes_engine.loglik(t, k, mu * 1.3, alpha * 0.7, beta, T)["value"]
        ref = loglik_oracle(t, k, mu, alpha, beta, T)
        worst = max(worst, abs(true - ref) / abs(ref))
        gain.append((true - off) / t.size)
    g = np.asarray(gain)
    return float(g.mean()), float(g.mean() / (g.std(ddof=1) / np.sqrt(g.size))), worst


def reference_cluster_matches(seed: int):
    """Smoke hook so the cluster reference stays exercised by the checks."""
    mu, alpha, beta = make_params(2, 0.5)
    return ref_cluster(mu, alpha, beta, 20.0, 2, np.random.default_rng(seed)).times.size
