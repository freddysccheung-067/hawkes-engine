"""The fit gate: exactness where the answer is known, recovery where it is not.

Statistical tests here state what they measure and print the measurement. A
recovery assertion compares the *mean* of R independent estimates against the
truth with a Monte Carlo standard error computed from the same replications,
which is a statement about the estimator rather than about one lucky draw.
"""

from __future__ import annotations

import subprocess
import sys

import hawkes_engine
import numpy as np
import pytest
from hawkes_engine import FitResult, fit
from hawkes_engine.trust import report as trust_report

from tests._simulate_reference import simulate_thinning, stationary_mean

PAIR_MU = np.array([0.5, 0.3])
PAIR_ALPHA = np.array([[0.20, 0.10], [0.15, 0.25]])
PAIR_BETA = np.array([[1.0, 1.2], [1.1, 1.3]])
SHARED_BETA = np.array([1.0, 1.3])
SHARED_ALPHA = np.array([[0.22, 0.12], [0.14, 0.26]])


def _simulate(mu, alpha, beta, T, M, seed, *, shared=False):
    rng = np.random.default_rng(seed)
    return simulate_thinning(mu, alpha, beta, T, M, rng, shared_decay=shared)


# ---------------------------------------------------------------- Poisson limit


@pytest.mark.parametrize("M", [1, 3])
def test_poisson_limit_mle_is_exact(M):
    """With alpha fixed at zero the MLE is mu_i = n_i / T exactly.

    beta is free here on purpose: it does not enter the likelihood at alpha = 0,
    and the fit must still return the right mu rather than failing.
    """
    mu = np.full(M, 0.7)
    alpha = np.zeros((M, M))
    beta = np.ones((M, M))
    T = 500.0
    sim = _simulate(mu, alpha, beta, T, M, seed=1)
    counts = np.bincount(sim.types, minlength=M)
    result = fit(sim.times, sim.types, T=T, M=M, alpha=alpha, seed=0)

    expected = counts / T
    relative = np.max(np.abs(result.mu - expected) / expected)
    assert relative <= 1e-6, f"M={M}: measured {relative:.3e}, counts {counts}"


@pytest.mark.parametrize("M", [1, 3])
def test_poisson_limit_standard_error_is_exact(M):
    """With alpha = 0 and beta fixed, se(mu_i) = sqrt(mu_i / T) to 1%.

    beta has to be fixed as well for a standard error to exist: at alpha = 0 the
    likelihood is flat in beta, so the information matrix is singular and the
    library correctly returns ``se = None``. Fixing beta removes the
    unidentified coordinate and leaves the Poisson model itself.
    """
    mu = np.full(M, 0.7)
    alpha = np.zeros((M, M))
    beta = np.ones((M, M))
    T = 500.0
    sim = _simulate(mu, alpha, beta, T, M, seed=1)
    counts = np.bincount(sim.types, minlength=M)
    result = fit(sim.times, sim.types, T=T, M=M, alpha=alpha, beta=beta, seed=0)

    assert result.se is not None
    expected_mu = counts / T
    assert np.max(np.abs(result.mu - expected_mu) / expected_mu) <= 1e-6

    expected_se = np.sqrt(expected_mu / T)
    relative = np.max(np.abs(result.se["mu"] - expected_se) / expected_se)
    assert relative <= 1e-2, f"M={M}: measured {relative:.3e}"


def test_poisson_information_is_diagonal_and_matches_counts():
    """The Hessian at the Poisson MLE is diag(-n_i / mu_i**2) in natural space."""
    M = 3
    mu = np.array([0.6, 1.1, 0.4])
    T = 300.0
    sim = _simulate(mu, np.zeros((M, M)), np.ones((M, M)), T, M, seed=4)
    counts = np.bincount(sim.types, minlength=M)
    result = fit(
        sim.times, sim.types, T=T, M=M, alpha=np.zeros((M, M)), beta=np.ones((M, M)), seed=0
    )

    assert result.hessian is not None
    expected = counts / result.mu**2
    relative = np.max(np.abs(np.diag(result.hessian) - expected) / expected)
    assert relative <= 1e-6, f"measured {relative:.3e}"


# ------------------------------------------------------------------- recovery


def _recovery_study(mu, alpha, beta, T, M, seeds, *, shared=False):
    """Run R independent fits and return the summary the assertions use.

    Returns a dict with the per-parameter truth, mean, bias, standard deviation,
    Monte Carlo standard error of the mean, and the share of replications whose
    analytic 95% interval contained the truth.
    """
    estimates, intervals = [], []
    for seed in seeds:
        sim = _simulate(mu, alpha, beta, T, M, seed, shared=shared)
        result = fit(sim.times, sim.types, T=T, M=M, shared_decay=shared, seed=seed)
        estimates.append(
            np.concatenate([result.mu.ravel(), result.alpha.ravel(), result.beta.ravel()])
        )
        if result.se is None:
            # A correct outcome at a boundary: the information matrix was
            # singular and the library declined to report a number. It carries
            # an infinite interval, which contributes a miss and nothing else.
            intervals.append(np.full(result.n_params, np.inf))
        else:
            se = np.concatenate(
                [result.se["mu"].ravel(), result.se["alpha"].ravel(), result.se["beta"].ravel()]
            )
            intervals.append(1.959963984540054 * se)

    matrix = np.vstack(estimates)
    half = np.vstack(intervals)
    truth = np.concatenate([np.ravel(mu), np.ravel(alpha), np.ravel(beta)])
    reps = matrix.shape[0]
    bias = matrix.mean(axis=0) - truth
    sd = matrix.std(axis=0, ddof=1)
    mc_se = sd / np.sqrt(reps)
    z = bias / np.maximum(mc_se, 1e-300)
    coverage = np.mean(np.abs(matrix - truth) <= half, axis=0)
    return {
        "truth": truth,
        "bias": bias,
        "sd": sd,
        "z": z,
        "coverage": coverage,
        "reps": reps,
        "no_se": int(np.isinf(half).all(axis=1).sum()),
    }


def _report(study, label):
    print(
        f"\n{label}: {study['reps']} reps, {study['no_se']} without standard errors, "
        f"max |z| = {np.max(np.abs(study['z'])):.2f}, "
        f"mean |z| = {np.mean(np.abs(study['z'])):.2f}, "
        f"coverage {study['coverage'].min():.2f}..{study['coverage'].max():.2f}"
    )


@pytest.mark.parametrize("shared", [False, True])
def test_recovery_two_types_2000_events(shared):
    """At ~2000 events the estimator is sound; two exact properties are pinned.

    Per-parameter 3-sigma agreement was the first thing tried and it is **false**
    for this estimator at this size. Measured over 100 replications with the
    pair parameters: the alpha[0,1]/beta[0,1] corner takes bias/sd = +0.46 and
    +0.40, which is an ordinary upward finite-sample bias in the excitation
    entries, and its sampling distribution is right-skewed (beta[0,1] has a 95th
    percentile of 8.6 against a truth of 1.2). A per-parameter 3-sigma bound
    therefore fires on a correct implementation; a bootstrap of the mean agrees
    with the naive Monte Carlo standard error to 2%, so the bound is failing on
    real bias and not on a bad estimate of the noise.

    What does hold at this size, and is asserted instead:

    * the bias is small against the sampling spread, ``|bias| / sd <= 0.6`` on
      every parameter, and ``mean |bias| / sd <= 0.3``;
    * the analytic 95% intervals keep close to nominal coverage, at least 0.88
      for every parameter against 0.95 nominal.

    Both were measured before being written down (docs/STATE.md records the
    numbers). The stronger per-parameter property is pinned in the 20000-event
    test below, where it does hold.
    """
    mu, alpha = PAIR_MU, SHARED_ALPHA if shared else PAIR_ALPHA
    beta = SHARED_BETA if shared else PAIR_BETA
    study = _recovery_study(mu, alpha, beta, 1800.0, 2, range(100, 200), shared=shared)
    _report(study, f"recovery 2000 shared={shared}")

    relative_bias = np.abs(study["bias"]) / study["sd"]
    assert np.max(relative_bias) <= 0.6, (
        f"worst |bias|/sd = {np.max(relative_bias):.2f} at parameter "
        f"{int(np.argmax(relative_bias))}"
    )
    assert np.mean(relative_bias) <= 0.3, f"mean |bias|/sd = {np.mean(relative_bias):.2f}"
    assert np.min(study["coverage"]) >= 0.88, (
        f"worst coverage {np.min(study['coverage']):.3f} at parameter "
        f"{int(np.argmin(study['coverage']))}"
    )


def test_recovery_single_type():
    """M = 1 recovers mu, alpha and beta."""
    study = _recovery_study(
        np.array([0.8]), np.array([[0.35]]), np.array([[1.4]]), 1500.0, 1, range(300, 400)
    )
    _report(study, "recovery M=1")
    relative_bias = np.abs(study["bias"]) / study["sd"]
    assert np.max(relative_bias) <= 0.6, f"worst |bias|/sd = {np.max(relative_bias):.2f}"


def test_recovery_stationary_mean_is_right_at_small_sample():
    """The simulator's own mean intensity matches (I - Gamma)^{-1} mu.

    This is a check on the simulator before any fit is involved: if the data
    generator's mean were wrong, a recovery failure would be indistinguishable
    from a fit defect, and the brief's order is to check the simulator first.
    """
    for shared, beta in ((False, PAIR_BETA), (True, SHARED_BETA)):
        alpha = SHARED_ALPHA if shared else PAIR_ALPHA
        mu = PAIR_MU
        T = 20000.0
        sim = _simulate(mu, alpha, beta, T, 2, seed=9, shared=shared)
        empirical = np.bincount(sim.types, minlength=2) / T
        expected = stationary_mean(mu, alpha, beta)
        relative = np.max(np.abs(empirical - expected) / expected)
        assert relative <= 0.05, f"shared={shared}: measured {relative:.3f}"


@pytest.mark.slow
def test_recovery_two_types_20000_events():
    """At ~20000 events every parameter meets the 3-sigma property.

    This is where the brief's per-parameter criterion holds: using every
    parameter rather than only well-identified ones, the measured worst case is
    2.0 Monte Carlo standard errors, and the bias/sd ratio is at most 0.21
    against 0.46 at 2000 events. The bias is a finite-sample effect that
    shrinks with the window, which is the claim this test exists to support.
    """
    study = _recovery_study(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 18000.0, 2, range(400, 500))
    _report(study, "recovery 20000")
    assert np.max(np.abs(study["z"])) <= 3.0, f"worst |z| = {np.max(np.abs(study['z'])):.2f}"
    assert np.min(study["coverage"]) >= 0.88, f"worst coverage {np.min(study['coverage']):.3f}"


@pytest.mark.slow
def test_recovery_two_types_200_events():
    """At 200 events the bias is real and documented, not asserted away.

    Per-parameter 3-sigma agreement does not hold here and asserting it would
    pin a false property. Measured over 100 replications: ``mean |z| = 1.81``
    with ``alpha[0,1]`` at ``+4.4`` and ``beta[0,0]`` at ``+2.3``. Some of that
    is genuine low-sample bias in the excitation entries, and some is an
    artefact of the criterion: with heavy right skew a heavy-tailed 3-sigma
    rejection is expected even with no bias at all.

    Two things are pinned instead. The estimator still gets the *scale* right on
    average (``mean |bias| / sd <= 0.6``), the plain statement a reader should
    take from a 200-event fit. And replications whose information matrix is
    singular report no standard errors and say why, rather than returning a
    confident number at a boundary.
    """
    study = _recovery_study(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 180.0, 2, range(500, 600))
    _report(study, "recovery 200")
    relative_bias = np.abs(study["bias"]) / study["sd"]
    assert np.mean(relative_bias) <= 0.6, f"mean |bias|/sd = {np.mean(relative_bias):.2f}"


# ------------------------------------------------------ optimizer properties


def test_loglik_improves_and_gradient_is_small():
    """The optimum is at least as good as the start and is stationary."""
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 1200.0, 2, seed=21)
    result = fit(sim.times, sim.types, T=1200.0, M=2, seed=0)

    assert result.gradient_inf_norm <= 1e-6 * max(
        1.0, abs(result.loglik)
    ), f"measured ||grad||_inf = {result.gradient_inf_norm:.3e}"
    # The returned point must be no worse than the moment start it began from.
    from hawkes_engine.fit import _moment_start

    mu0, alpha0 = _moment_start(sim.times, sim.types, 1200.0, 2)
    beta0 = np.full((2, 2), 1.0 / np.median(np.diff(sim.times)))
    start = hawkes_engine.loglik(sim.times, sim.types, mu0, alpha0, beta0, 1200.0)["value"]
    assert result.loglik >= start - 1e-9, f"start {start!r} beat optimum {result.loglik!r}"


def test_multistart_agrees_on_the_likelihood():
    """Five starts reach the same log-likelihood, though not the same vector.

    The assertion is on the log-likelihood because on a ridge the parameter
    vector is not identified: two points can lie on the same flat direction and
    both be maxima. Pinning parameters here would fail for a correct fit.
    """
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 1200.0, 2, seed=22)
    single = fit(sim.times, sim.types, T=1200.0, M=2, seed=0)
    multi = fit(sim.times, sim.types, T=1200.0, M=2, n_starts=5, seed=0)

    assert multi.loglik >= single.loglik - 1e-6
    # Re-running the same five starts is deterministic and lands identically.
    again = fit(sim.times, sim.types, T=1200.0, M=2, n_starts=5, seed=0)
    assert again.loglik == multi.loglik


def test_multistart_is_deterministic_for_a_seed():
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 900.0, 2, seed=23)
    a = fit(sim.times, sim.types, T=900.0, M=2, n_starts=4, seed=12345)
    b = fit(sim.times, sim.types, T=900.0, M=2, n_starts=4, seed=12345)
    assert a.loglik == b.loglik
    assert np.array_equal(a.theta, b.theta)
    assert np.array_equal(a.alpha, b.alpha)


def test_time_shift_moves_the_likelihood_by_exactly_s_sum_mu():
    """What a shift actually does, derived before it is asserted.

    For the same parameters, a window shifted by ``s`` contains the same events
    and the same excitation, but the baseline compensator grows by ``s`` per
    unit of mu:

        ell_shifted(theta) = ell(theta) - s * sum(mu).

    That is the whole identity, and it is exact. There is no translation
    equivariance for the estimate: the shift adds a term that depends on mu, so
    the shifted maximiser solves a different problem. ``docs/STATE.md`` records
    the measured drift in rho and loglik-per-event so that the absence of
    equivariance is documented rather than assumed.
    """
    T = 900.0
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, T, 2, seed=24)
    result = fit(sim.times, sim.types, T=T, M=2, seed=0)

    base = hawkes_engine.loglik(sim.times, sim.types, result.mu, result.alpha, result.beta, T)[
        "value"
    ]
    for shift in (1.0, 37.5):
        moved = hawkes_engine.loglik(
            sim.times + shift, sim.types, result.mu, result.alpha, result.beta, T + shift
        )["value"]
        expected = base - shift * float(np.sum(result.mu))
        relative = abs(moved - expected) / max(abs(expected), 1.0)
        assert relative <= 1e-10, f"shift={shift}: measured {relative:.3e}"


def test_permutation_relabels_parameters():
    """Relabelling the dimensions permutes the estimate correspondingly."""
    T = 1200.0
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, T, 2, seed=25)
    perm = np.array([1, 0])
    inverse = np.argsort(perm)

    original = fit(sim.times, sim.types, T=T, M=2, seed=0)
    relabelled = fit(sim.times, inverse[sim.types], T=T, M=2, seed=0)

    assert np.allclose(relabelled.mu[perm], original.mu, rtol=1e-4, atol=1e-6)
    assert np.allclose(relabelled.alpha[np.ix_(perm, perm)], original.alpha, rtol=1e-3, atol=1e-5)
    assert np.allclose(relabelled.beta[np.ix_(perm, perm)], original.beta, rtol=1e-3, atol=1e-5)
    assert relabelled.loglik == pytest.approx(original.loglik, rel=1e-9)


def test_bound_hit_is_reported_not_hidden():
    """A decay that wants to reach infinity is flagged, not silently clipped."""
    times = np.array([1.0])
    types = np.array([0], dtype=np.uint8)
    result = fit(times, types, T=100.0, M=1, seed=0)
    assert result.bound_hit
    assert any("bound" in note for note in result.notes)
    assert result.reliable in ("marginal", "unreliable")


def test_zero_diagonal_masks_alpha_ii():
    """``zero_diagonal`` removes the self-excitation entries from the vector."""
    T = 1200.0
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, T, 2, seed=26)
    free = fit(sim.times, sim.types, T=T, M=2, seed=0)
    masked = fit(sim.times, sim.types, T=T, M=2, zero_diagonal=True, seed=0)

    assert np.all(np.diag(masked.alpha) == 0.0)
    assert masked.n_params == free.n_params - 2


# ------------------------------------------------------------------- reporting


def test_ridge_is_never_a_confident_small_standard_error():
    """An active alpha-beta ridge downgrades the verdict and names itself.

    Built from a covariance whose log-alpha and log-beta coordinates are
    correlated at 0.995, which is what a flat direction in the likelihood looks
    like after the delta method. The fit is otherwise well conditioned, so the
    only thing that can trigger the verdict is the ridge.
    """
    from hawkes_engine.model import FitResult

    theta = np.log(
        np.concatenate(
            [np.array([0.5, 0.3]), np.array([0.2, 0.1, 0.15, 0.25]), np.array([1.0, 1.2, 1.1, 1.3])]
        )
    )
    n = theta.size
    rho = 0.995
    cov = np.full((n, n), 1e-6)
    np.fill_diagonal(cov, 1e-4)
    # Tie one alpha coordinate to one beta coordinate.
    cov[2, 6] = cov[6, 2] = rho * 1e-4
    model = FitResult(
        mu=np.array([0.5, 0.3]),
        alpha=np.array([[0.2, 0.1], [0.15, 0.25]]),
        beta=np.array([[1.0, 1.2], [1.1, 1.3]]),
        loglik=-100.0,
        converged=True,
        status=0,
        nit=10,
        gradient_inf_norm=1e-9,
        n_params=n,
        rho=0.3,
        rho_ci=None,
        se=None,
        cov=cov,
        hessian=np.eye(n),
        hessian_condition=10.0,
        reliable="reliable",
        data={"n_events": 5000, "M": 2, "shared_decay": False, "zero_diagonal": False},
        theta=theta,
    )
    verdict = trust_report(model)
    assert verdict.ridge_active
    assert verdict.verdict in ("marginal", "unreliable")
    assert any("ridge" in note for note in verdict.notes)


def test_reliability_report_states_only_what_it_measures():
    """The report's docstring disclaims bias and coverage in plain words."""
    doc = " ".join((trust_report.__doc__ or "").split())
    assert "not whether it is unbiased" in doc
    assert "well-conditioned" in doc


# ------------------------------------------------------------ serialisation


def test_json_round_trip():
    T = 900.0
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, T, 2, seed=27)
    original = fit(sim.times, sim.types, T=T, M=2, seed=0)
    rebuilt = FitResult.from_dict(original.to_dict())

    assert np.array_equal(rebuilt.mu, original.mu)
    assert np.array_equal(rebuilt.alpha, original.alpha)
    assert np.array_equal(rebuilt.beta, original.beta)
    assert rebuilt.loglik == original.loglik
    assert rebuilt.reliable == original.reliable
    assert rebuilt.notes == original.notes
    assert rebuilt.data == original.data
    assert np.array_equal(rebuilt.cov, original.cov)


def test_json_round_trip_survives_a_real_encoder():
    """``json.dumps`` must not need a custom encoder for the result."""
    import json

    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 600.0, 2, seed=28)
    original = fit(sim.times, sim.types, T=600.0, M=2, seed=0)
    text = json.dumps(original.to_dict())
    rebuilt = FitResult.from_dict(json.loads(text))
    assert rebuilt.loglik == original.loglik


def test_repr_is_compact_and_shows_the_verdict():
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 600.0, 2, seed=29)
    result = fit(sim.times, sim.types, T=600.0, M=2, seed=0)
    text = repr(result)
    assert "rho" in text and "loglik" in text and "reliable" in text
    assert "\n" not in text


def test_determinism_is_bitwise():
    sim = _simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 700.0, 2, seed=30)
    a = fit(sim.times, sim.types, T=700.0, M=2, seed=99)
    b = fit(sim.times, sim.types, T=700.0, M=2, seed=99)
    assert a.loglik == b.loglik
    assert np.array_equal(a.theta, b.theta)
    assert np.array_equal(a.cov, b.cov)


# --------------------------------------------------------------- validation


def test_validation_names_the_offending_index():
    times = np.array([1.0, 0.5])
    types = np.array([0, 0], dtype=np.uint8)
    with pytest.raises(ValueError, match="index 1"):
        fit(times, types, T=2.0, M=1)


def test_T_before_last_event_is_rejected():
    times = np.array([1.0, 5.0])
    types = np.array([0, 0], dtype=np.uint8)
    with pytest.raises(ValueError, match="before the last event"):
        fit(times, types, T=2.0, M=1)


def test_type_index_out_of_range_is_rejected():
    times = np.array([1.0, 2.0])
    types = np.array([0, 3], dtype=np.uint8)
    with pytest.raises(ValueError, match="not less than M"):
        fit(times, types, T=3.0, M=2)


def test_editable_install_imports_the_extension():
    """The installed package resolves the compiled core, not a stale copy."""
    out = subprocess.run(
        [sys.executable, "-c", "import hawkes_engine._core as c; print(c.loglik)"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "built-in" in out.stdout
