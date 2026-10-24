"""``se_method="auto"``: the policy, the record, and the four outcomes.

The policy is a pure function of a fitted regime and the shipped map, so most of
it is tested without a fit. Three tests do run a real fit -- one that takes the
bootstrap path, one that is refused by the time limit, and one for ``shared_decay``
-- because the wiring between the decision and the estimator is where a policy
that is right on paper can still be wrong in the result object.

Every test that would run a 200-replication bootstrap monkeypatches
``n_bootstrap`` down. The projection tests use the capability table's measured
rows directly, so the cost model is checked against measurements rather than
against itself.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from hawkes_engine import se_policy, trust_map
from hawkes_engine.fit import fit
from hawkes_engine.model import FitResult
from hawkes_engine.simulation import simulate

PAIR_MU = np.array([0.6, 0.9])
PAIR_ALPHA = np.array([[0.10, 0.35], [0.20, 0.05]])
PAIR_BETA = np.array([[1.30, 1.70], [1.30, 1.70]])


# --------------------------------------------------------------- map fixtures


def _row(**over):
    """A map row with every field the lookup reads, settable per test."""
    base = {
        "study_id": trust_map.STUDY_ID,
        "preregistration_tag": "H6-preregistration",
        "analysis_commit": "0" * 40,
        "cell": "M2_TEST",
        "M": "2",
        "N": "2000",
        "rho": "0.3028",
        "r": "0.0",
        "c": "1.0",
        "satellite": "0",
        "T": "1722.6",
        "delta": "0.0",
        "beta_min_T": "1722.6",
        "convergence_rate": "0.99",
        "no_se_rate": "0.01",
        "resolved": "1",
        "estimator_undefined": "0",
    }
    for block in ("mu", "alpha", "beta", "all"):
        base[f"{block}_cov_all"] = "0.94"
        base[f"{block}_se_cov_all"] = "0.005"
        base[f"{block}_q"] = "1.0"
        base[f"{block}_se_q_boot"] = "0.02"
    base.update(over)
    return base


# A cell where every block's interval is too narrow by more than its own error.
NARROW = [_row(mu_q="0.70", alpha_q="0.60", beta_q="0.50")]
# A cell where every block is indistinguishable from correctly calibrated.
CALIBRATED = [_row()]
# A cell where the interval is too wide, which is also a resolved miscalibration.
WIDE = [_row(mu_q="1.30", alpha_q="1.25", beta_q="1.40")]
# A cell whose estimator is undefined.
UNDEFINED = [_row(cell="M2_UNDEF", estimator_undefined="1", no_se_rate="0.75")]


def _decide(rows, **over):
    kwargs = dict(N=2000, rho_hat=0.3028, beta_min=1.0, T=1722.6, rows=rows)
    kwargs.update(over)
    return se_policy.decide(**kwargs)


# ------------------------------------------------------------------- the rule


def test_a_narrow_block_chooses_the_bootstrap():
    decision = _decide(NARROW, beta_min=1.0)
    assert decision.action == "bootstrap"
    assert decision.se_source == "bootstrap"
    assert {block for block, _ in decision.firing_blocks} == {"mu", "alpha", "beta"}
    assert all(direction == "narrow" for _, direction in decision.firing_blocks)


def test_a_calibrated_cell_keeps_the_hessian():
    decision = _decide(CALIBRATED)
    assert decision.action == "hessian_calibrated"
    assert decision.se_source == "hessian"
    assert decision.firing_blocks == ()


def test_a_wide_block_is_also_a_resolved_miscalibration():
    """Over-coverage is miscalibration in the other direction, and the rule sees it."""
    decision = _decide(WIDE)
    assert decision.action == "bootstrap"
    assert {direction for _, direction in decision.firing_blocks} == {"wide"}


def test_an_undefined_cell_returns_no_number_and_names_the_axis():
    decision = _decide(UNDEFINED, N=2000, rho_hat=0.3028, beta_min=1.0)
    assert decision.action == "none"
    assert decision.se_source == "none"
    assert decision.q == {} and decision.se_q == {}
    assert decision.projected_seconds is None
    # The rate is above 0.5 here, so the failing axis is the missing-interval
    # rate rather than the decay-window axis.
    assert "no_se_rate" in decision.note
    assert "no interval is reported" in decision.note


def test_a_small_decay_window_names_beta_t_as_the_failing_axis():
    rows = [_row(cell="M2_TINY", estimator_undefined="1", no_se_rate="0.25")]
    decision = _decide(rows)
    assert decision.action == "none"
    assert "beta_min*T" in decision.note


def test_outside_the_box_the_hessian_is_used_and_labelled_uncalibrated():
    decision = se_policy.decide(N=100_000, rho_hat=0.6, beta_min=1.0, T=50_000.0, rows=CALIBRATED)
    assert decision.action == "hessian_unmapped"
    assert decision.se_source == "hessian"
    assert decision.status == "unknown"
    assert "uncalibrated" in decision.note
    assert "no bootstrap was run" in decision.note


def test_a_fixed_block_is_not_tested():
    """A block held constant has no standard error and says nothing about the method."""
    rows = [_row(mu_q="0.10", alpha_q="1.0", beta_q="1.0")]
    tested = _decide(rows)
    assert tested.action == "bootstrap"
    untested = _decide(rows, free={"mu": False, "alpha": True, "beta": True})
    assert untested.action == "hessian_calibrated"


# ---------------------------------------------------------------- the cost rule


def test_projection_reproduces_every_measured_row():
    """The projection is fitted to the capability table; it must still match it."""
    for M, N, measured in se_policy._MEASURED_ROWS:
        projected = se_policy.project_seconds(200, M, N, workers=1)
        assert projected == pytest.approx(measured, rel=0.03), (M, N, measured, projected)


def test_projection_uses_measured_pool_efficiency_not_the_worker_count():
    """Dividing by workers would project 86 s as 21 s; the table measured 5.9x, not 24x."""
    one = se_policy.project_seconds(200, 4, 100_000, workers=1)
    four = se_policy.project_seconds(200, 4, 100_000, workers=4)
    pool = se_policy.project_seconds(200, 4, 100_000, workers=None)
    # Measured 3.6x at M = 4, N = 1e5: four workers must beat one, and must not
    # achieve anything near the 24x a linear split would give.
    assert four < one < 4.0 * four
    assert pool < four
    assert 70.0 < pool < 100.0, pool


def test_a_projection_above_the_limit_keeps_the_hessian_and_warns():
    decision = _decide(NARROW, auto_max_seconds=0.001)
    assert decision.action == "hessian_after_limit"
    assert decision.se_source == "hessian"
    assert decision.projected_seconds is not None
    assert decision.max_seconds == pytest.approx(0.001)
    assert "auto_max_seconds" in decision.note
    assert len(decision.firing_blocks) == 3


def test_no_limit_means_no_refusal():
    decision = _decide(NARROW, auto_max_seconds=None)
    assert decision.action == "bootstrap"


def test_the_default_limit_admits_the_measured_pool_run_and_refuses_one_worker():
    """The default is chosen against the table, not picked for roundness."""
    pool = se_policy.project_seconds(200, 4, 100_000, workers=None)
    single = se_policy.project_seconds(200, 4, 100_000, workers=1)
    assert pool <= se_policy.AUTO_MAX_SECONDS
    assert single > se_policy.AUTO_MAX_SECONDS


# --------------------------------------------------------------- the record


def test_the_record_carries_the_evidence_it_read():
    decision = _decide(NARROW)
    record = decision.to_dict()
    assert record["status"] == "measured"
    assert record["cell"] == "M2_TEST"
    assert record["distance"] == pytest.approx(0.0, abs=1e-9)
    assert record["q"]["beta"] == pytest.approx(0.50)
    assert record["se_q"]["beta"] == pytest.approx(0.02)
    assert record["threshold"] == pytest.approx(se_policy.CALIBRATION_Z)
    assert ["beta", "narrow"] in record["firing_blocks"]


def test_the_record_round_trips_through_json():
    decision = _decide(NARROW)
    text = json.dumps(decision.to_dict())
    rebuilt = se_policy.AutoDecision.from_dict(json.loads(text))
    assert rebuilt == decision


def test_the_record_round_trips_for_every_action():
    decisions = [
        _decide(NARROW),
        _decide(CALIBRATED),
        _decide(UNDEFINED, N=2000, rho_hat=0.3028, beta_min=1.0),
        _decide(NARROW, auto_max_seconds=0.001),
        se_policy.decide(N=100_000, rho_hat=0.6, beta_min=1.0, T=50_000.0, rows=CALIBRATED),
    ]
    for decision in decisions:
        rebuilt = se_policy.AutoDecision.from_dict(json.loads(json.dumps(decision.to_dict())))
        assert rebuilt == decision


# ------------------------------------------------------------------ the fit


@pytest.fixture(scope="module")
def fitted_data():
    times, types = simulate(PAIR_MU, PAIR_ALPHA, PAIR_BETA, 2000.0, method="thinning", seed=41)
    return times, types


def test_auto_on_real_data_chooses_the_bootstrap_and_records_why(fitted_data):
    times, types = fitted_data
    dense = len(times) / times[-1]
    assert dense > 1.0
    result = fit(times, types, M=2, T=2000.0, seed=1, se_method="auto", n_bootstrap=20)
    assert result.se_source == "bootstrap"
    assert result.auto is not None
    assert result.auto.action == "bootstrap"
    assert result.se is not None
    assert result.auto.cell is not None
    assert "bootstrap" in result.se_note
    assert result.se_note in result.notes


def test_the_time_limit_is_honoured_by_the_fit_itself(fitted_data):
    times, types = fitted_data
    result = fit(times, types, M=2, T=2000.0, seed=1, se_method="auto", auto_max_seconds=1e-9)
    assert result.se_source == "hessian"
    assert result.auto.action == "hessian_after_limit"
    assert result.se is not None
    assert any("auto_max_seconds" in note for note in result.notes)


def test_the_limit_warns_once(fitted_data):
    times, types = fitted_data
    with pytest.warns(RuntimeWarning, match="auto_max_seconds"):
        fit(times, types, M=2, T=2000.0, seed=1, se_method="auto", auto_max_seconds=1e-9)


def test_shared_decay_is_outside_the_map_and_says_so(fitted_data):
    times, types = fitted_data
    result = fit(times, types, M=2, T=2000.0, seed=1, se_method="auto", shared_decay=True)
    assert result.se_source == "hessian"
    assert result.auto.action == "hessian_unmapped"
    assert result.auto.status == "unknown"
    assert "different model" in result.se_note


def test_the_result_round_trips_with_its_auto_record(fitted_data):
    times, types = fitted_data
    original = fit(times, types, M=2, T=2000.0, seed=1, se_method="auto", auto_max_seconds=1e-9)
    rebuilt = FitResult.from_dict(json.loads(json.dumps(original.to_dict())))
    assert rebuilt.se_source == original.se_source
    assert rebuilt.se_note == original.se_note
    assert rebuilt.auto == original.auto


def test_explicit_methods_still_report_their_source(fitted_data):
    times, types = fitted_data
    hessian = fit(times, types, M=2, T=2000.0, seed=1)
    assert hessian.se_source == "hessian"
    assert hessian.se_note == ""
    assert hessian.auto is None
    none = fit(times, types, M=2, T=2000.0, seed=1, se_method=None)
    assert none.se_source == "none"
    assert none.se is None


def test_a_bootstrap_count_below_ten_is_refused(fitted_data):
    """Below ten the bootstrap always declines; that is a configuration error, not a result."""
    times, types = fitted_data
    with pytest.raises(ValueError, match="n_bootstrap"):
        fit(times, types, M=2, T=2000.0, se_method="auto", n_bootstrap=5)
    with pytest.raises(ValueError, match="n_bootstrap"):
        fit(times, types, M=2, T=2000.0, se_method="bootstrap", n_bootstrap=9)


def test_an_unknown_method_is_refused(fitted_data):
    times, types = fitted_data
    with pytest.raises(ValueError, match="se_method"):
        fit(times, types, M=2, T=2000.0, se_method="bayes")


def test_a_schema_one_document_still_reads(fitted_data):
    """A 0.1.0 result has no se_source; it reads as hessian with an empty note."""
    times, types = fitted_data
    result = fit(times, types, M=2, T=2000.0, seed=1)
    payload = result.to_dict()
    payload["schema"] = 1
    del payload["se_source"]
    del payload["se_note"]
    del payload["auto"]
    rebuilt = FitResult.from_dict(payload)
    assert rebuilt.se_source == "hessian"
    assert rebuilt.se_note == ""
    assert rebuilt.auto is None


def test_a_future_schema_is_refused(fitted_data):
    times, types = fitted_data
    payload = fit(times, types, M=2, T=2000.0, seed=1).to_dict()
    payload["schema"] = 99
    with pytest.raises(ValueError, match="schema"):
        FitResult.from_dict(payload)
