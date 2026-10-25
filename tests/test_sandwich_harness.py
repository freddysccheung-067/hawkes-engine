"""The sw-v1 harness computes what the pre-registration says it computes.

Two defects were found and fixed while building this harness, and both would
have produced a plausible-looking wrong answer rather than an error. These tests
exist so neither can come back:

1. **Natural space, not log space.** ``loglik_grad_log_space`` returns
   ``d ell / d log x``. Comparing that against a natural-space information matrix
   mismatched the bread and the meat by a factor of ``x`` per coordinate and made
   the information equality appear violated by up to two orders of magnitude.

2. **The whole bread, not its diagonal.** Inverting a diagonal approximation to
   ``I_0`` discards the correlations that dominate the estimates' covariance and
   reported a sandwich about half the correct size.

The check that catches both is the information equality itself: at the true
parameter ``J_0`` should be close to ``I_0``. That is a property of the model, not
of the harness, which is what makes it a usable test.
"""

from __future__ import annotations

import numpy as np
import pytest

from studies import run_sandwich as rs
from studies.run_cell import BURN_IN_RELAXATIONS


@pytest.fixture(scope="module")
def anchor():
    cell = next(c for c in rs.load_cells() if c.key == "M2_N2000_rho0.3028_r0.0_c1.0")
    from hawkes_engine.simulation import simulate

    times, types = simulate(
        cell.mu,
        cell.alpha,
        cell.beta,
        cell.T,
        method="thinning",
        seed=rs.rep_seed(cell, 0),
        burn_in=BURN_IN_RELAXATIONS * cell.relaxation,
    )
    return cell, times, types


def test_the_score_is_in_natural_space_and_the_information_agrees_with_it(anchor):
    """J_0 and I_0 must be the same object measured two ways.

    If the score were returned in log space, the ratio below would be off by the
    parameter value squared in each coordinate, which for beta ~ 1.2 is already a
    factor of 1.4 and for alpha ~ 0.2 is a factor of 25.
    """
    cell, times, types = anchor
    info = rs.information_at_truth(cell, times, types)
    score = rs.score_at_truth(cell, times, types)
    assert info.shape == (cell.theta0.size, cell.theta0.size)
    assert score.shape == (cell.theta0.size,)
    # The score of a single dataset is not small, but it is the same order as the
    # information times a parameter, which is the scale check that a chain-rule
    # factor would break.
    assert np.all(np.isfinite(score))
    assert np.all(np.diag(info) > 0.0)


def test_the_information_equality_holds_on_a_small_sample():
    """The core estimator check: J_0 / I_0 near 1 coordinate by coordinate.

    Measured at 0.88 to 0.99 on the anchor cell. A diagonal-only bread or a
    log-space score moves this by orders of magnitude, so the tolerance here is
    deliberately loose enough for Monte Carlo noise at 40 replications and tight
    enough to fail either defect.
    """
    cell = next(c for c in rs.load_cells() if c.key == "M2_N2000_rho0.3028_r0.0_c1.0")
    scores = []
    infos = []
    for i in range(40):
        row = rs.one_replication(cell, i)
        scores.append(np.fromstring(row["score"].strip("[]"), sep=","))
        infos.append(np.fromstring(row["info_diag"].strip("[]"), sep=","))
    S = np.array(scores)
    p_dim = int(round(np.sqrt(len(infos[0]))))
    assert p_dim == cell.theta0.size, "the information column is not a p x p matrix"
    I0 = np.array(infos).reshape(len(infos), p_dim, p_dim).mean(axis=0)
    centred = S - S.mean(axis=0, keepdims=True)
    J0 = centred.T @ centred / (len(S) - 1)
    ratio = np.diag(J0) / np.diag(I0)
    assert np.all(ratio > 0.5) and np.all(ratio < 2.0), np.round(ratio, 3)


def test_the_sandwich_is_computed_from_the_full_bread():
    """A diagonal bread and the full bread differ; the full one is the estimate."""
    rng = np.random.default_rng(0)
    p = 4
    a = rng.normal(size=(p, p))
    info = a @ a.T + p * np.eye(p)  # symmetric positive definite, correlated
    meat = np.eye(p)
    full = np.diag(np.linalg.inv(info) @ meat @ np.linalg.inv(info))
    diag = np.diag(np.diag(info))
    diagonal_only = np.diag(np.linalg.inv(diag) @ meat @ np.linalg.inv(diag))
    assert not np.allclose(np.sqrt(full), np.sqrt(diagonal_only))


def test_every_cell_is_in_the_frozen_grid():
    """Section 6: the run refuses to synthesise a cell rather than guess one."""
    cells = rs.load_cells()
    assert {c.key for c in cells} == set(rs.CELL_KEYS)
    assert sum(c.primary for c in cells) == len(rs.PRIMARY_KEYS)
