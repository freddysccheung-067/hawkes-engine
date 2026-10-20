"""The H6 estimands against a fixture computed by hand.

There is no oracle for a Monte Carlo analysis: a wrong estimand produces a number
that looks exactly like a right one. Every expected value below is therefore a
literal, derived by hand from the fixture with the arithmetic in a comment, so a
transcription error in a formula in ``studies/analyze.py`` fails here instead of
reaching a hypothesis verdict.

The fixture is one synthetic M = 2 cell of six replications. Coordinates are in
the ``theta_hat`` order of ``studies/run_cell.py``: mu(2), alpha(4, row-major),
beta(4, row-major).

    theta_0 = mu (1, 2) | alpha (0.2, 0.4, 0.6, 0.8) | beta (1, 2, 3, 4)
    mean|theta_0| per block: mu 1.5, alpha 0.5, beta 2.5;  10 * max beta_0 = 40

Most coordinates are ``theta_0 + b + s * e`` with the pattern
``e = (-2, -1, 0, 0, 1, 2)``, which has mean 0 and mean square 10/6:

    coord     b      s     se    estimates over reps 1..6
    mu0       0      0.1   0.1   0.8  0.9  1.0  1.0  1.1  1.2
    mu1       0.2    0.1   0.1   2.0  2.1  2.2  2.2  2.3  2.4
    a00       0.1    0.05  0.1   0.2  0.25 0.3  0.3  0.35 0.4
    a01       0      0.1   0.1   0.2  0.3  0.4  0.4  0.5  0.6
    a10       0.05   0.05  0.1   0.55 0.6  0.65 0.65 0.7  0.75
    a11      -0.05   0.05  0.1   0.65 0.7  0.75 0.75 0.8  0.85
    b00       0      0.1   0.1   0.8  0.9  1.0  1.0  1.1  1.2
    b01   (outlier)        0.5   1.8  1.9  2.0  2.0  2.1  100
    b10       0.3    0.1   0.2   3.1  3.2  3.3  3.3  3.4  3.5
    b11       0      0.2   0.2   3.6  3.8  4.0  4.0  4.2  4.4

    rep           1         2         3         4           5            6
    converged     1         1         1         0           1            1
    se            yes       yes       yes       yes         None         yes
    verdict       reliable  reliable  marginal  unreliable  unreliable   reliable

Coverage indicators ``|theta_hat - theta_0| <= 1.959964 se`` (rep 5 has no se, so
every coordinate is a miss there; rows are coordinates, columns reps 1..6):

    mu0  0 1 1 1 0 0   (|d| = 0.2 > 0.196 at reps 1 and 6)
    mu1  1 1 0 0 0 0   (d = 0, 0.1, 0.2, 0.2, -, 0.4)
    a00  1 1 1 1 0 0   (d = 0.2 at rep 6)
    a01  0 1 1 1 0 0
    a10  1 1 1 1 0 1   (largest |d| = 0.15)
    a11  1 1 1 1 0 1
    b00  0 1 1 1 0 0
    b01  1 1 1 1 0 0   (d = 98 at rep 6, against 0.98)
    b10  1 1 1 1 0 0   (d = 0.5 at rep 6, against 0.392)
    b11  0 1 1 1 0 0   (|d| = 0.4 > 0.392 at reps 1 and 6)
"""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pytest

from studies import analyze
from studies.grid import splitmix64

REL = 1e-12

THETA0 = [1.0, 2.0, 0.2, 0.4, 0.6, 0.8, 1.0, 2.0, 3.0, 4.0]
ESTIMATES = [
    # mu0  mu1  a00   a01  a10   a11   b00  b01    b10  b11
    [0.8, 2.0, 0.20, 0.2, 0.55, 0.65, 0.8, 1.8, 3.1, 3.6],
    [0.9, 2.1, 0.25, 0.3, 0.60, 0.70, 0.9, 1.9, 3.2, 3.8],
    [1.0, 2.2, 0.30, 0.4, 0.65, 0.75, 1.0, 2.0, 3.3, 4.0],
    [1.0, 2.2, 0.30, 0.4, 0.65, 0.75, 1.0, 2.0, 3.3, 4.0],
    [1.1, 2.3, 0.35, 0.5, 0.70, 0.80, 1.1, 2.1, 3.4, 4.2],
    [1.2, 2.4, 0.40, 0.6, 0.75, 0.85, 1.2, 100.0, 3.5, 4.4],
]
SE = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.5, 0.2, 0.2]
CONVERGED = [1, 1, 1, 0, 1, 1]
HAS_SE = [1, 1, 1, 1, 0, 1]
VERDICT = ["reliable", "reliable", "marginal", "unreliable", "unreliable", "reliable"]


def _rows() -> list[dict[str, str]]:
    """The fixture as the CSV rows ``run_cell`` writes, so parsing is tested too."""
    rows = []
    for i in range(6):
        has_se = HAS_SE[i] == 1
        failure = [] if has_se else ["se:none"]
        if not CONVERGED[i]:
            failure.append("not_converged")
        rows.append(
            {
                "cell_key": "FIXTURE",
                "rep_index": str(i),
                "theta0": json.dumps(THETA0),
                "theta_hat": json.dumps(ESTIMATES[i]),
                "converged": str(CONVERGED[i]),
                "nit": str(10 + i),
                "verdict": VERDICT[i],
                "bound_hit": "1" if i == 5 else "0",
                "failure": ";".join(failure),
                "se_mu": json.dumps(SE[0:2]) if has_se else "",
                "se_alpha": json.dumps([SE[2:4], SE[4:6]]) if has_se else "",
                "se_beta": json.dumps([SE[6:8], SE[8:10]]) if has_se else "",
                "n_events": "100",
            }
        )
    return rows


@pytest.fixture(scope="module")
def cell() -> analyze.CellData:
    return analyze.parse_rows(
        _rows(),
        key="FIXTURE",
        M=2,
        theta0=np.array(THETA0),
        axes={"N": 0, "rho": 0.5, "r": 0.0, "c": 1.0, "satellite": False, "T": 1.0},
    )


@pytest.fixture(scope="module")
def est(cell) -> dict:
    return analyze.cell_estimands(cell)


def test_parse_keeps_coordinate_order_and_marks_the_missing_se(cell):
    assert cell.R == 6
    assert cell.theta_hat[5, 7] == 100.0  # beta[0,1] of rep 6
    assert cell.theta_hat[0, 2] == 0.20  # alpha[0,0] of rep 1
    assert np.isnan(cell.se[4]).all()
    assert cell.se[0, 7] == 0.5
    assert list(cell.has_se) == [True, True, True, True, False, True]
    assert list(cell.converged) == [True, True, True, False, True, True]


# ---------------------------------------------------------------- E3.1, E3.2


def test_e31_e32_bias_and_relative_bias(est):
    b = est["blocks"]
    # mu: column means of d are 0 (mu0) and 0.2 (mu1): bias = 0.2 / 2 = 0.1;
    # rel = 0.1 / 1.5.
    assert b["mu"]["bias"] == pytest.approx(0.1, rel=REL)
    assert b["mu"]["rel"] == pytest.approx(0.066666666666666667, rel=REL)
    # alpha: column means 0.1, 0, 0.05, -0.05: bias = 0.1 / 4 = 0.025; rel = 0.025 / 0.5.
    assert b["alpha"]["bias"] == pytest.approx(0.025, rel=REL)
    assert b["alpha"]["rel"] == pytest.approx(0.05, rel=REL)
    # beta: b01 deviations -0.2 -0.1 0 0 0.1 98 have mean 97.8 / 6 = 16.3; with
    # b00 0 and b10 0.3 and b11 0 the block bias is 16.6 / 4 = 4.15; rel = 4.15 / 2.5.
    assert b["beta"]["bias"] == pytest.approx(4.15, rel=REL)
    assert b["beta"]["rel"] == pytest.approx(1.66, rel=REL)


def test_e32_per_coordinate(est):
    coord = {c["name"]: c for c in est["coordinates"]}
    # beta[0,1]: bias 16.3, rel = 16.3 / |2| = 8.15.
    assert coord["beta[0,1]"]["bias"] == pytest.approx(16.3, rel=REL)
    assert coord["beta[0,1]"]["rel"] == pytest.approx(8.15, rel=REL)
    # mu[1]: bias 0.2, rel 0.2 / 2 = 0.1.
    assert coord["mu[1]"]["rel"] == pytest.approx(0.1, rel=REL)


# ---------------------------------------------------------------------- E3.3


def test_e33_spread_is_the_empirical_sd_not_the_mean_se(est):
    b = est["blocks"]
    # mu: each coordinate has variance 0.1^2 * 10/6 = 1/60 (divisor R = 6, as
    # section 3 writes mean_r); sd = sqrt(1/60) = 0.129099444873580...
    assert b["mu"]["sd"] == pytest.approx(0.12909944487358056, rel=REL)
    # alpha: variances 0.025/6, 0.1/6, 0.025/6, 0.025/6; mean 0.175/24;
    # sd = sqrt(0.0072916666...) = 0.0853912563829966...
    assert b["alpha"]["sd"] == pytest.approx(0.08539125638299665, rel=REL)
    # beta: b01 has mean 109.8/6 = 18.3, squared deviations 272.25 268.96 265.69
    # 265.69 262.44 6674.89, sum 8009.92, variance 1334.98666...; b00 and b10
    # 0.1/6 each, b11 0.4/6. Mean = (0.1 + 1334.98666...)/4 = 333.771666...;
    # sd = 18.2694188...
    assert b["beta"]["sd"] == pytest.approx(18.269418892418738, rel=REL)
    # MC SE of the bias: sd / sqrt(R).
    assert b["mu"]["se_bias"] == pytest.approx(0.12909944487358056 / math.sqrt(6), rel=REL)
    assert b["alpha"]["se_rel"] == pytest.approx(0.08539125638299665 / math.sqrt(6) / 0.5, rel=REL)


# ---------------------------------------------------------------- E3.4, E3.6


def test_e34_mean_se_over_replications_that_have_one(est):
    b = est["blocks"]
    # The se is constant across the five reps that have one.
    assert b["mu"]["mse"] == pytest.approx(0.1, rel=REL)
    assert b["alpha"]["mse"] == pytest.approx(0.1, rel=REL)
    # beta: (0.1 + 0.5 + 0.2 + 0.2) / 4 = 0.25.
    assert b["beta"]["mse"] == pytest.approx(0.25, rel=REL)
    assert b["mu"]["n_se"] == 5


def test_e36_q_is_mean_se_over_sd(est):
    """q < 1: the library understates uncertainty; q > 1: it overstates it."""
    b = est["blocks"]
    # mu: 0.1 / sqrt(1/60) = sqrt(0.6) = 0.774596669... < 1, understated.
    assert b["mu"]["q"] == pytest.approx(0.7745966692414834, rel=REL)
    # alpha: 0.1 / 0.0853912... = sqrt(0.24 / 0.175) = 1.171080... > 1, overstated.
    assert b["alpha"]["q"] == pytest.approx(1.1710800875382399, rel=REL)
    # beta: 0.25 / 18.2694... = 0.0136840..., the outlier inflates sd.
    assert b["beta"]["q"] == pytest.approx(0.013684069617766689, rel=REL)
    # Delta-method SE: q * sqrt((SE(mse)/mse)^2 + 1/(2(R-1))). SE(mse) is 0 because
    # se is constant, so SE(q) = q / sqrt(10); for mu that is sqrt(0.06).
    assert b["mu"]["se_q_delta"] == pytest.approx(0.2449489742783178, rel=REL)


def test_e36_matched_set_sensitivity(est):
    # Sensitivity reading: sd over the five reps that have an se. mu0 over reps
    # 1,2,3,4,6 is 0.8 0.9 1.0 1.0 1.2, mean 0.98, squared deviations 0.0324
    # 0.0064 0.0004 0.0004 0.0484, sum 0.088, variance 0.0176; mu1 identical.
    # q = 0.1 / sqrt(0.0176) = 0.753778361...
    assert est["blocks"]["mu"]["q_matched"] == pytest.approx(0.7537783614444091, rel=REL)


def test_sensitivity_population_converged_only():
    est = analyze.cell_estimands(
        analyze.parse_rows(
            _rows(),
            key="FIXTURE",
            M=2,
            theta0=np.array(THETA0),
            axes={"N": 0, "rho": 0.5, "r": 0.0, "c": 1.0, "satellite": False, "T": 1.0},
        ),
        population="converged",
    )
    # Without rep 4: b01 deviations -0.2 -0.1 0 0.1 98 mean 97.8/5 = 19.56;
    # b00 0, b10 0.3, b11 0; bias_beta = 19.86 / 4 = 4.965.
    assert est["blocks"]["beta"]["bias"] == pytest.approx(4.965, rel=REL)


# ---------------------------------------------------------------------- E3.5


def test_e35_coverage_counts_a_missing_se_as_a_miss(est):
    b = est["blocks"]
    # Over all six replications (hits from the table in the module docstring):
    # mu 3 + 2 = 5 of 12; alpha 4 + 3 + 5 + 5 = 17 of 24; beta 3 + 4 + 4 + 3 = 14
    # of 24; all 36 of 60.
    assert b["mu"]["cov_all"] == pytest.approx(5 / 12, rel=REL)
    assert b["alpha"]["cov_all"] == pytest.approx(17 / 24, rel=REL)
    assert b["beta"]["cov_all"] == pytest.approx(14 / 24, rel=REL)
    assert b["all"]["cov_all"] == pytest.approx(0.6, rel=REL)
    # MC SE sqrt(cov (1 - cov) / R), R = 6.
    assert b["mu"]["se_cov_all"] == pytest.approx(math.sqrt(35 / 144 / 6), rel=REL)
    assert b["all"]["n_cov_all"] == 6


def test_e35_coverage_conditioned_on_convergence(est):
    b = est["blocks"]
    # Rep 4 (not converged) leaves; it was a hit everywhere except mu1.
    # mu 4 of 10; alpha 13 of 20; beta 10 of 20; all 27 of 50.
    assert b["mu"]["cov_cond"] == pytest.approx(0.4, rel=REL)
    assert b["alpha"]["cov_cond"] == pytest.approx(0.65, rel=REL)
    assert b["beta"]["cov_cond"] == pytest.approx(0.5, rel=REL)
    assert b["all"]["cov_cond"] == pytest.approx(0.54, rel=REL)
    assert b["all"]["se_cov_cond"] == pytest.approx(math.sqrt(0.54 * 0.46 / 5), rel=REL)
    assert b["all"]["n_cov_cond"] == 5


def test_rates(est):
    m = est["meta"]
    assert m["no_se_rate"] == pytest.approx(1 / 6, rel=REL)
    assert m["convergence_rate"] == pytest.approx(5 / 6, rel=REL)
    assert m["bound_hit_rate"] == pytest.approx(1 / 6, rel=REL)
    # nit = 10..15, mean 12.5.
    assert m["mean_nit"] == pytest.approx(12.5, rel=REL)


# ---------------------------------------------------------------------- E3.7


def test_e37_verdict_accuracy(est):
    v = est["blocks"]["all"]["verdict_all"]
    # Per-rep coverage over all 10 coordinates: 0.6, 1.0, 0.9, 0.9, 0.0, 0.2.
    # reliable {1,2,6}: (0.6 + 1.0 + 0.2) / 3 = 0.6
    # unreliable {4,5}: (0.9 + 0.0) / 2 = 0.45
    # marginal {3}: 0.9, reported separately and outside Delta
    assert v["reliable"]["cov"] == pytest.approx(0.6, rel=REL)
    assert v["unreliable"]["cov"] == pytest.approx(0.45, rel=REL)
    assert v["marginal"]["cov"] == pytest.approx(0.9, rel=REL)
    assert v["reliable"]["n"] == 3 and v["unreliable"]["n"] == 2
    # Delta = 0.15; delta-method SE sqrt(0.6*0.4/3 + 0.45*0.55/2) = sqrt(0.20375).
    assert v["delta"] == pytest.approx(0.15, rel=REL)
    assert v["se_delta"] == pytest.approx(0.45138675213169484, rel=REL)
    # Per block, mu: reliable reps cover 0.5, 1, 0 -> 0.5; unreliable 0.5, 0 -> 0.25.
    vm = est["blocks"]["mu"]["verdict_all"]
    assert vm["delta"] == pytest.approx(0.25, rel=REL)
    # Conditioned on convergence the only unreliable rep left is rep 5, coverage 0.
    vc = est["blocks"]["all"]["verdict_cond"]
    assert vc["unreliable"]["cov"] == pytest.approx(0.0, abs=1e-15)
    assert vc["delta"] == pytest.approx(0.6, rel=REL)


# ------------------------------------------------------------- E4.1 to E4.4


def test_e41_median_bias(est):
    c = est["companions"]
    # Medians over six reps average the 3rd and 4th order statistics.
    # mu: medians 1.0 and 2.2 -> deviations 0, 0.2 -> 0.1; medrel 0.1 / 1.5.
    assert c["mu"]["medbias"] == pytest.approx(0.1, rel=REL)
    assert c["mu"]["medrel"] == pytest.approx(0.066666666666666667, rel=REL)
    # beta: b01 sorted 1.8 1.9 2.0 2.0 2.1 100 has median 2.0, so the outlier
    # contributes 0; with b10 0.3 the block is 0.3 / 4 = 0.075; medrel 0.03.
    assert c["beta"]["medbias"] == pytest.approx(0.075, rel=REL)
    assert c["beta"]["medrel"] == pytest.approx(0.03, rel=REL)
    assert c["alpha"]["medbias"] == pytest.approx(0.025, rel=REL)


def test_e42_mad(est):
    c = est["companions"]
    # Pattern coordinates: |s e| sorted s * (0, 0, 1, 1, 2, 2), median s, MAD 1.4826 s.
    # mu: 1.4826 * 0.1.  alpha: 1.4826 * (0.05 + 0.1 + 0.05 + 0.05) / 4 = 0.0926625.
    # beta: b01 |x - 2| sorted 0 0 0.1 0.1 0.2 98, median 0.1, so 1.4826 * 0.1;
    # block = 1.4826 * (0.1 + 0.1 + 0.1 + 0.2) / 4 = 0.185325.
    assert c["mu"]["mad"] == pytest.approx(0.14826, rel=REL)
    assert c["alpha"]["mad"] == pytest.approx(0.0926625, rel=REL)
    assert c["beta"]["mad"] == pytest.approx(0.185325, rel=REL)


def test_e43_robust_q_over_replications_with_an_se(est):
    c = est["companions"]
    # Over reps 1,2,3,4,6 (five values, the median is the 3rd). median se = se.
    # mu0 0.8 0.9 1.0 1.0 1.2: median 1.0, |dev| sorted 0 0 0.1 0.2 0.2 -> 0.1.
    #   q_j = 0.1 / (1.4826 * 0.1) = 1 / 1.4826; mu1 likewise.
    assert c["mu"]["qrob"] == pytest.approx(0.6744907594765952, rel=REL)
    # alpha: a00 |dev| 0.1 0.05 0 0 0.1 -> 0.05, q = 2/1.4826; a01 -> 1/1.4826;
    #   a10, a11 -> 2/1.4826. Mean (2 + 1 + 2 + 2) / 4 / 1.4826 = 1.75 / 1.4826.
    assert c["alpha"]["qrob"] == pytest.approx(1.1803588290840416, rel=REL)
    # beta: b00 1/1.4826; b01 0.5/(1.4826 * 0.1) = 5/1.4826 (the outlier rep 6 is
    #   in, and moves nothing); b10 0.2/(1.4826*0.1) = 2/1.4826; b11 0.2/(1.4826*0.2).
    #   Mean (1 + 5 + 2 + 1) / 4 / 1.4826 = 2.25 / 1.4826.
    assert c["beta"]["qrob"] == pytest.approx(1.5176042088223391, rel=REL)


def test_e44_tail_share_over_converged_replications(est):
    # Converged reps 1,2,3,5,6; only rep 6 has a beta (100) above 10 * 4 = 40.
    assert est["companions"]["tail"] == pytest.approx(0.2, rel=REL)
    assert est["companions"]["n_tail"] == 5


# --------------------------------------------------------------- bootstrap


def test_boot_seed_is_the_section_10_construction():
    key = "M2_N2000_rho0.3028_r0.0_c1.0"
    digest = hashlib.sha256(f"h6-v1-boot|{key}".encode()).digest()
    assert analyze.boot_seed(key) == splitmix64(int.from_bytes(digest[:16], "big"))[1]
    # Pinned once, so a change of message format cannot pass silently.
    assert analyze.boot_seed(key) == 539176524293729413


def test_bootstrap_is_deterministic(cell):
    a = analyze.bootstrap_cell(cell, resamples=50)
    b = analyze.bootstrap_cell(cell, resamples=50)
    for block in ("mu", "alpha", "beta"):
        for name in ("medbias", "mad", "qrob", "q"):
            np.testing.assert_array_equal(a[block][name], b[block][name])
    np.testing.assert_array_equal(a["tail"], b["tail"])
    # The point estimate is the identity resample.
    assert analyze.BOOT_RESAMPLES == 1000


def test_bootstrap_identity_resample_reproduces_the_point_estimate(cell, est):
    ident = analyze.e4_statistics(cell, np.arange(cell.R)[None, :])
    assert ident["beta"]["qrob"][0] == pytest.approx(est["companions"]["beta"]["qrob"], rel=REL)
    assert ident["mu"]["q"][0] == pytest.approx(est["blocks"]["mu"]["q"], rel=REL)


# ------------------------------------------------------------------ H6.5 pooling


def _summary(M, N, rho, r, c, sat, q, mse=None, sd=None):
    blocks = {}
    for name, value in zip(("mu", "alpha", "beta"), q, strict=True):
        blocks[name] = {
            "q": value,
            "mse": value if mse is None else mse[name],
            "sd": 1.0 if sd is None else sd[name],
        }
    return {
        "meta": {"M": M, "N": N, "rho": rho, "r": r, "c": c, "satellite": sat},
        "blocks": blocks,
    }


def test_h65_pooled_q_uses_the_12_m2_cells_only():
    cells = {}
    rhos = (0.3028, 0.6, 0.85, 0.95)
    for i, (N, rho) in enumerate((N, rho) for N in (2000, 10000, 50000) for rho in rhos):
        if i < 6:
            # q (0.5, 1, 1.5) from mse (1, 2, 3) over sd 2: coordinate-weighted cell
            # q = (2*0.5 + 4*1 + 4*1.5) / 10 = 1.1.
            mse = {"mu": 1.0, "alpha": 2.0, "beta": 3.0}
            sd = {"mu": 2.0, "alpha": 2.0, "beta": 2.0}
            cells[f"A{i}"] = _summary(2, N, rho, 0.0, 1.0, False, (0.5, 1.0, 1.5), mse, sd)
        else:
            cells[f"B{i}"] = _summary(2, N, rho, 0.0, 1.0, False, (1.0, 1.0, 1.0))
    # Distractors that would move the answer if they entered: the satellite, a
    # smaller N, a quantised cell, the slow-decay half.
    cells["sat"] = _summary(4, 2000, 0.3028, 0.0, 1.0, True, (10.0, 10.0, 10.0))
    cells["n1000"] = _summary(2, 1000, 0.3028, 0.0, 1.0, False, (10.0, 10.0, 10.0))
    cells["r01"] = _summary(2, 2000, 0.3028, 0.1, 1.0, False, (10.0, 10.0, 10.0))
    cells["slow"] = _summary(2, 2000, 0.3028, 0.0, 0.001, False, (10.0, 10.0, 10.0))
    keys = analyze.h65_cells(cells)
    assert sorted(keys) == sorted(k for k in cells if k[0] in "AB")
    pooled = analyze.pooled_q(cells, keys)
    # (6 * 1.1 + 6 * 1.0) / 12 = 1.05.
    assert pooled["q"] == pytest.approx(1.05, rel=REL)
    # Ratio form: sum w mse / sum w sd = (6*(2+8+12) + 6*10) / (6*20 + 6*10) = 192/180.
    assert pooled["q_ratio"] == pytest.approx(1.0666666666666667, rel=REL)
    assert analyze.h65_satellite_cells(cells) == ["sat"]


# ------------------------------------------------------------------- Holm


def test_holm_thresholds():
    assert analyze.HOLM_THRESHOLDS == pytest.approx((0.0125, 0.05 / 3, 0.025, 0.05), rel=REL)


def test_holm_stops_at_the_first_failure_and_needs_both_bars():
    # Section 4's bar z > 2 is p < 1 - Phi(2) = 0.0227501.
    #   H6.6 p 0.001 (z 3.09): step 1, 0.001 <= 0.0125 pass        -> confirmed
    #   H6.3 p 0.020 (z 2.05): step 2, 0.020 >  0.01667 FAIL, stop -> confirmed
    #        before correction only (section 4 passes, Holm does not)
    #   H6.4 p 0.021 (z 2.03): step 3, would pass 0.025 alone, but Holm has
    #        stopped                                               -> before correction only
    #   H6.5 p 0.040 (z 1.75): section 4 inconclusive (within 2 SE) -> inconclusive
    p = {"H6.3": 0.020, "H6.4": 0.021, "H6.5": 0.040, "H6.6": 0.001}
    s4 = {k: analyze.section4_verdict(analyze.z_from_p(v)) for k, v in p.items()}
    assert s4 == {
        "H6.3": "confirmed",
        "H6.4": "confirmed",
        "H6.5": "inconclusive",
        "H6.6": "confirmed",
    }
    holm = analyze.holm(p)
    assert [holm[k]["step"] for k in ("H6.6", "H6.3", "H6.4", "H6.5")] == [1, 2, 3, 4]
    assert holm["H6.6"]["passed"] and not holm["H6.3"]["passed"]
    assert not holm["H6.4"]["passed"] and not holm["H6.5"]["passed"]
    labels = {k: analyze.final_label(s4[k], holm[k]["passed"]) for k in p}
    assert labels == {
        "H6.3": "confirmed before correction only",
        "H6.4": "confirmed before correction only",
        "H6.5": "inconclusive",
        "H6.6": "confirmed",
    }


def test_a_failed_section_4_rule_is_not_rescued_by_holm():
    #   H6.3 p 0.0001, but its monotonicity clause failed, so section 4 says
    #        refuted. Holm step 1 passes (0.0001 <= 0.0125)        -> not confirmed
    #   H6.5 p 0.003 (z 2.75): step 2, 0.003 <= 0.01667 pass       -> confirmed
    #   H6.4 p 0.5 (z 0): step 3, 0.5 > 0.025 FAIL, stop           -> inconclusive
    #   H6.6 p 0.99 (z -2.33): refuted                             -> not confirmed
    p = {"H6.3": 0.0001, "H6.4": 0.5, "H6.5": 0.003, "H6.6": 0.99}
    s4 = {k: analyze.section4_verdict(analyze.z_from_p(v)) for k, v in p.items()}
    s4["H6.3"] = "refuted"
    holm = analyze.holm(p)
    assert holm["H6.3"]["passed"] and holm["H6.5"]["passed"]
    assert not holm["H6.4"]["passed"] and not holm["H6.6"]["passed"]
    labels = {k: analyze.final_label(s4[k], holm[k]["passed"]) for k in p}
    assert labels == {
        "H6.3": "not confirmed",
        "H6.4": "inconclusive",
        "H6.5": "confirmed",
        "H6.6": "not confirmed",
    }


def test_section4_band():
    # Confirmation is strict (T - 2 SE > tau); every falsifier in section 4 is
    # non-strict (e.g. H6.1 "rel + 2 SE <= 0.05", H6.5 "q - 2 SE >= 1").
    assert analyze.section4_verdict(2.0001) == "confirmed"
    assert analyze.section4_verdict(2.0) == "inconclusive"
    assert analyze.section4_verdict(-1.9999) == "inconclusive"
    assert analyze.section4_verdict(-2.0) == "refuted"


# ---------------------------------------------- combinations Amendment 5 leaves open


def test_h64_combines_cell_differences_two_ways():
    # Two cells: D = 0.02, 0.05 with SE(D) = 0.003, 0.004.
    #   T = 0.035.
    #   independent cells: SE = sqrt(0.003^2 + 0.004^2) / 2 = 0.005 / 2 = 0.0025,
    #     z = (0.035 - 0.01) / 0.0025 = 10.
    #   between cells: SE = sd(0.02, 0.05; ddof 1) / sqrt(2) = 0.0212132 / 1.41421
    #     = 0.015, z = 0.025 / 0.015 = 1.6667.
    out = analyze.mean_of_differences(np.array([0.02, 0.05]), np.array([0.003, 0.004]))
    assert out["T"] == pytest.approx(0.035, rel=REL)
    assert out["se_independent"] == pytest.approx(0.0025, rel=REL)
    assert out["se_between"] == pytest.approx(0.015, rel=REL)


# ------------------------------------------- a second fixture for four edges
#
# The six-replication fixture cannot tell apart four transcription errors: its
# theta_0 is all positive (mean|theta_0| = mean theta_0), no deviation lies
# between 1.959964 se and 1.96 se, its non-converged replication has no wild
# beta, and dropping its se-less replication leaves every median unchanged. This
# fixture is M = 1 (one mu, one alpha, one beta), R = 4, built to separate them.
#
#   theta_0 = (1.0, -0.5, 2.0)   (a negative alpha is not a Hawkes value; it is
#                                 here only so that |theta_0| differs from theta_0)
#   rep  mu        alpha  beta  se (all)  converged
#   1    1.0       -0.5   2.0   0.1       1
#   2    1.195998  -0.3   2.0   0.1       1
#   3    1.0       -0.6   50.0  0.1       0
#   4    1.0       -0.9   2.0   None      1


def _edge_cell() -> analyze.CellData:
    est = [[1.0, -0.5, 2.0], [1.195998, -0.3, 2.0], [1.0, -0.6, 50.0], [1.0, -0.9, 2.0]]
    rows = []
    for i, e in enumerate(est):
        has_se = i != 3
        rows.append(
            {
                "rep_index": str(i),
                "theta_hat": json.dumps(e),
                "converged": "0" if i == 2 else "1",
                "verdict": "reliable",
                "failure": "" if has_se else "se:none",
                "se_mu": "[0.1]" if has_se else "",
                "se_alpha": "[[0.1]]" if has_se else "",
                "se_beta": "[[0.1]]" if has_se else "",
            }
        )
    return analyze.parse_rows(
        rows,
        key="EDGE",
        M=1,
        theta0=np.array([1.0, -0.5, 2.0]),
        axes={"N": 0, "rho": 0.5, "r": 0.0, "c": 1.0, "satellite": False, "T": 1.0},
    )


def test_edge_the_coverage_constant_is_1_959964():
    b = analyze.cell_estimands(_edge_cell())["blocks"]
    # mu: rep 2 deviates 0.195998 > 1.959964 * 0.1 = 0.1959964, a miss (it would
    # be a hit at 1.96). Hits: rep 1 (d 0), rep 3 (d 0); rep 4 has no se.
    # cov_all = 2 / 4; conditioned on convergence (reps 1, 2, 4) = 1 / 3.
    assert b["mu"]["cov_all"] == pytest.approx(0.5, rel=REL)
    assert b["mu"]["cov_cond"] == pytest.approx(1 / 3, rel=REL)


def test_edge_relative_bias_divides_by_mean_absolute_theta0():
    b = analyze.cell_estimands(_edge_cell())["blocks"]
    # alpha: mean estimate (-0.5 - 0.3 - 0.6 - 0.9) / 4 = -0.575; bias = -0.075.
    # rel = -0.075 / |-0.5| = -0.15 (dividing by theta_0 itself would give +0.15).
    assert b["alpha"]["bias"] == pytest.approx(-0.075, rel=REL)
    assert b["alpha"]["rel"] == pytest.approx(-0.15, rel=REL)


def test_edge_tail_share_counts_converged_replications_only():
    c = analyze.cell_estimands(_edge_cell())["companions"]
    # Cap 10 * 2 = 20. Rep 3 has beta 50 but did not converge, so it is in neither
    # numerator nor denominator: 0 of 3.
    assert c["tail"] == pytest.approx(0.0, abs=1e-15)
    assert c["n_tail"] == 3


def test_edge_robust_q_uses_replications_with_an_se_for_the_mad():
    c = analyze.cell_estimands(_edge_cell())["companions"]
    # alpha over reps 1, 2, 3 (rep 4 has no se): -0.5 -0.3 -0.6, median -0.5,
    # |dev| 0 0.2 0.1, median 0.1, MAD 0.14826; median se 0.1; qrob = 1 / 1.4826.
    # Over all four reps the median is -0.55, |dev| 0.05 0.25 0.05 0.35, MAD
    # 1.4826 * 0.15, which would give 0.449660...
    assert c["alpha"]["qrob"] == pytest.approx(0.6744907594765952, rel=REL)
    # E4.2 itself is over all replications: 1.4826 * 0.15 = 0.22239.
    assert c["alpha"]["mad"] == pytest.approx(0.22239, rel=REL)
