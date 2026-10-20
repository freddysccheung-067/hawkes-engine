"""The H6 harness: grid, seeds, resumability, determinism, failures, collection.

These tests prove properties of the *harness*. They measure no estimand and
touch no H6 result: every cell here runs a handful of replications into a
temporary directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from hawkes_engine import _core

from studies import collect, grid, run_cell

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "M2_N200_rho0.3028_r0.0_c1.0"
FAST_CELL = "M2_N200_rho0.3028_r0.0_c1.0"

# Committed golden values for section 10. They were produced by grid.py once and
# are literals here, so a change to the formatting rules or the SplitMix64 step
# breaks this file instead of silently moving every seed in the study.
GOLDEN = {
    "anchor_cell": (2, 2000, 0.3028, 0.0, 1.0, 4711469738829716385),
    "quantised_cell": (2, 200, 0.95, 0.1, 1.0, 17016152091388041090),
    "slowdecay_cell": (2, 200, 0.3028, 0.0, 1e-3, 13417931643152584232),
    "satellite_cell": (4, 20000, 0.85, 0.1, 1.0, 10324202119113677680),
}
GOLDEN_ANCHOR_REPS = {0: 11314197227357204596, 1: 8138034785835338435}


@pytest.fixture(scope="module")
def cells():
    return {c.key: c for c in grid.load_cells()}


# ------------------------------------------------------------------ the grid


def test_grid_reproduces_128_keys_and_the_digest(cells):
    assert len(cells) == 128
    assert sum(c.satellite for c in cells.values()) == 8
    assert grid.canonical_digest() == grid.EXPECTED_DIGEST
    prereg = (REPO / "docs" / "preregistration.md").read_text(encoding="utf-8")
    assert grid.EXPECTED_DIGEST in prereg


def test_a_changed_grid_is_refused(tmp_path):
    payload = json.loads(grid.THETA0_PATH.read_text(encoding="utf-8"))
    payload["cells"][0]["rho"] = 0.31
    altered = tmp_path / "theta0.json"
    altered.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="refusing to measure"):
        grid.load_cells(altered)


def test_keys_encode_their_coordinates(cells):
    assert grid.cell_key(2, 200, 0.3028, 0.0, 1.0, False) == ANCHOR
    assert grid.cell_key(4, 20000, 0.85, 0.1, 1.0, True) == "M4_N20000_rho0.85_r0.1_c1.0_sat"
    assert ANCHOR in cells


# ---------------------------------------------------------------------- seeds


def test_splitmix64_reproduces_the_compiled_golden_words():
    _, first = grid.splitmix64(0)
    state, _ = grid.splitmix64(0)
    _, second = grid.splitmix64(state)
    assert (first, second) == (0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4)


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_cell_seed_matches_the_committed_golden_value(name):
    M, N, rho, r, c, expected = GOLDEN[name]
    assert grid.cell_seed(M, N, rho, r, c) == expected


def test_cell_seed_follows_section_10_computed_independently():
    """Recompute the formula here with hashlib, not through grid.cell_seed."""
    message = "h6-v1|2|2000|0.3028|0.0|1.0"
    assert grid.seed_message(2, 2000, 0.3028, 0.0, 1.0) == message
    word = int.from_bytes(hashlib.sha256(message.encode()).digest()[:16], "big")
    mask = (1 << 64) - 1
    z = (word + 0x9E3779B97F4A7C15) & mask
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & mask
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & mask
    assert grid.cell_seed(2, 2000, 0.3028, 0.0, 1.0) == z ^ (z >> 31)


def test_replication_seeds_are_golden_and_independent_of_R(cells):
    anchor = cells["M2_N2000_rho0.3028_r0.0_c1.0"]
    for index, expected in GOLDEN_ANCHOR_REPS.items():
        assert grid.rep_seed(anchor, index) == expected
        assert grid.rep_seed(anchor, index) == int(_core.seed_stream(anchor.seed, index))


def test_all_cell_seeds_are_distinct(cells):
    assert len({c.seed for c in cells.values()}) == 128


# ------------------------------------------------- running, resuming, forcing


def test_a_cell_runs_five_rows_writes_done_and_the_second_call_is_a_no_op(cells, tmp_path):
    cell = cells[FAST_CELL]
    first = run_cell.run_cell(cell, 5, tmp_path)
    assert (first.completed, first.skipped) == (5, False)
    assert len(run_cell.read_rows(first.rows_path)) == 5

    done = json.loads(first.done_path.read_text(encoding="utf-8"))
    for field in (
        "reps_requested",
        "reps_completed",
        "wall_seconds",
        "worker",
        "checksum",
        "git_sha",
    ):
        assert field in done
    assert (done["reps_requested"], done["reps_completed"]) == (5, 5)

    before = first.rows_path.read_bytes()
    second = run_cell.run_cell(cell, 5, tmp_path)
    assert second.skipped is True
    assert first.rows_path.read_bytes() == before


def test_force_rerun_reproduces_identical_rows(cells, tmp_path):
    cell = cells["M2_N1000_rho0.6_r0.0_c1.0"]
    a = run_cell.run_cell(cell, 5, tmp_path / "a")
    b = run_cell.run_cell(cell, 5, tmp_path / "b", force=True)
    assert a.checksum == b.checksum

    def numeric(path):
        rows = run_cell.read_rows(path)
        return hashlib.sha256(
            "|".join(f"{r['theta_hat']}{r['loglik']}{r['se_alpha']}" for r in rows).encode()
        ).hexdigest()

    assert numeric(a.rows_path) == numeric(b.rows_path)
    again = run_cell.run_cell(cell, 5, tmp_path / "a", force=True)
    assert again.checksum == a.checksum


def test_a_crash_loses_at_most_the_row_in_flight(cells, tmp_path):
    cell = cells[FAST_CELL]
    full = run_cell.run_cell(cell, 5, tmp_path)
    rows = run_cell.read_rows(full.rows_path)
    with full.rows_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[:3])
    full.done_path.unlink()

    resumed = run_cell.run_cell(cell, 5, tmp_path)
    assert resumed.skipped is False and resumed.completed == 5
    assert resumed.checksum == full.checksum


def test_a_tampered_done_does_not_count_as_complete(cells, tmp_path):
    cell = cells[FAST_CELL]
    result = run_cell.run_cell(cell, 5, tmp_path)
    rows = run_cell.read_rows(result.rows_path)
    rows[0]["n_events"] = "999999"
    with result.rows_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    complete, reason = run_cell.is_complete(cell, tmp_path)
    assert not complete and "checksum" in reason


# ------------------------------------------------------------------- failures


def test_a_fit_that_raises_is_a_row_and_counts_toward_R(cells, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("injected")

    monkeypatch.setattr(run_cell, "fit_fn", boom)
    result = run_cell.run_cell(cells[FAST_CELL], 5, tmp_path)
    rows = run_cell.read_rows(result.rows_path)
    assert result.completed == 5 and len(rows) == 5
    assert all(r["failure"].startswith("fit:RuntimeError") for r in rows)
    assert all(r["theta_hat"] == "" for r in rows)


def test_a_degenerate_theta0_is_a_row_with_a_reason(cells, tmp_path):
    bad = replace(
        cells[FAST_CELL],
        key="degenerate",
        alpha=((5.0, 5.0), (5.0, 5.0)),
    )
    result = run_cell.run_cell(bad, 5, tmp_path)
    rows = run_cell.read_rows(result.rows_path)
    assert result.completed == 5
    assert all(r["failure"].startswith("simulate:ValueError") for r in rows)


def test_an_empty_event_array_is_recorded_not_skipped(cells, tmp_path):
    empty = replace(cells[FAST_CELL], key="empty", T=1e-9)
    result = run_cell.run_cell(empty, 5, tmp_path)
    rows = run_cell.read_rows(result.rows_path)
    assert len(rows) == 5
    assert all(r["n_events"] == "0" for r in rows)
    assert all(r["verdict"] == "unreliable" or r["failure"] for r in rows)


# --------------------------------------------------------------- quantisation


def test_quantised_times_are_exact_multiples_of_delta_and_exact_times_are_not(cells):
    from hawkes_engine import simulate

    coarse = cells["M2_N1000_rho0.6_r0.1_c1.0"]
    exact = cells["M2_N1000_rho0.6_r0.0_c1.0"]
    for cell in (coarse, exact):
        t, _ = simulate(
            np.asarray(cell.mu),
            np.asarray(cell.alpha),
            np.asarray(cell.beta),
            cell.T,
            method="thinning",
            seed=3,
            burn_in=10 * cell.relaxation,
        )
        if cell is coarse:
            q = run_cell.quantise(t, cell.delta, cell.T)
            assert cell.delta == pytest.approx(0.1)
            assert np.array_equal(q, np.round(np.round(q / cell.delta) * cell.delta, 12))
            assert np.allclose(q / cell.delta, np.round(q / cell.delta), atol=1e-9, rtol=0)
            assert q.max() < cell.T and np.all(np.diff(q) >= 0)
        else:
            assert not np.allclose(t / 0.1, np.round(t / 0.1), atol=1e-9, rtol=0)


def test_quantisation_never_leaves_the_window_even_when_delta_exceeds_T(cells):
    slow = cells["M2_N200_rho0.3028_r0.1_c0.001"]
    assert slow.delta > slow.T / 2
    t = np.linspace(0.0, slow.T * 0.999, 50)
    q = run_cell.quantise(t, slow.delta, slow.T)
    assert q.min() >= 0.0 and q.max() < slow.T


# ----------------------------------------------------------------- collection


def test_collect_names_the_cell_whose_done_is_missing(cells, tmp_path):
    run_cell.run_cell(cells[FAST_CELL], 5, tmp_path)
    report = collect.collect(tmp_path)
    assert report["complete"] == 1 and report["expected"] == 128
    missing = dict(report["missing"])
    assert FAST_CELL not in missing
    assert "M2_N1000_rho0.6_r0.0_c1.0" in missing

    (tmp_path / f"{FAST_CELL}.done").unlink()
    report = collect.collect(tmp_path)
    assert dict(report["missing"])[FAST_CELL] == "no .done marker"


# ---------------------------------------------------------------------- pilot


def test_pilot_quick_runs_in_under_three_minutes_and_emits_parseable_json(tmp_path):
    out = tmp_path / "pilot.json"
    done = subprocess.run(
        [sys.executable, "-m", "studies.pilot", "--quick", "--reps", "5", "--out", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stderr[-800:]
    payload = json.loads(out.read_text(encoding="utf-8"))
    measured = payload["measurements"][0]
    assert measured["cell_key"] == ANCHOR and measured["reps"] == 5
    assert measured["ms_median"] > 0 and measured["peak_rss_after"] > 0
    assert payload["recommendation"]["workers"] >= 1
