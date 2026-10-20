"""The shipped H6 map and its lookup.

The map is ``data/trust/v1_excitation_only.csv``, built by ``studies/build_map.py``
from ``studies/results/analysis/``. These tests pin its provenance and the three
answers the lookup can give: a measured cell, ``"unknown"`` outside the box, and
``"estimator undefined in this regime"`` with no coverage number.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest
from hawkes_engine import trust_map

REPO = Path(__file__).resolve().parent.parent
ANALYSIS = REPO / "studies" / "results" / "analysis"


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    return trust_map.load_map()


def _row(rows, key):
    return next(r for r in rows if r["cell"] == key)


def test_the_map_has_every_cell_and_the_study_provenance(rows):
    assert len(rows) == 128
    assert len({r["cell"] for r in rows}) == 128
    provenance = json.loads((ANALYSIS / "provenance.json").read_text(encoding="utf-8"))
    assert {r["study_id"] for r in rows} == {trust_map.STUDY_ID} == {provenance["study_id"]}
    assert {r["preregistration_tag"] for r in rows} == {"H6-preregistration"}
    assert {r["analysis_commit"] for r in rows} == {provenance["analysis_commit"]}


def test_a_wrong_study_id_is_refused(tmp_path, rows):
    path = tmp_path / "map.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerow({**rows[0], "study_id": "h6-v0"})
    with pytest.raises(ValueError, match="study_id"):
        trust_map.load_map(path)


def test_the_map_copies_the_analysis_numbers_exactly(rows):
    with (ANALYSIS / "blocks.csv").open(newline="", encoding="utf-8") as fh:
        blocks = {(r["cell"], r["block"]): r for r in csv.DictReader(fh)}
    for r in rows:
        for b in ("mu", "alpha", "beta", "all"):
            assert r[f"{b}_cov_all"] == blocks[(r["cell"], b)]["cov_all"]
            assert r[f"{b}_q"] == blocks[(r["cell"], b)]["q"]


def test_a_grid_point_returns_its_own_cell_exactly(rows):
    key = "M2_N2000_rho0.3028_r0.0_c1.0"
    row = _row(rows, key)
    beta_min = 1.0  # min(beta_0) at c = 1
    ans = trust_map.lookup(2000, 0.3028, beta_min, float(row["T"]), rows=rows)
    assert ans.status == "measured"
    assert ans.cell == key
    assert ans.distance == pytest.approx(0.0, abs=1e-12)
    assert ans.coverage["all"] == (float(row["all_cov_all"]), float(row["all_se_cov_all"]))
    assert ans.q["beta"] == (float(row["beta_q"]), float(row["beta_se_q_boot"]))


def test_every_defined_grid_point_returns_itself(rows):
    for row in rows:
        beta_min = float(row["beta_min_T"]) / float(row["T"])
        ans = trust_map.lookup(
            float(row["N"]),
            float(row["rho"]),
            beta_min,
            float(row["T"]),
            float(row["delta"]),
            M=int(row["M"]),
            rows=rows,
        )
        assert ans.cell == row["cell"], row["cell"]
        assert ans.distance == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"N": 100_000, "rho_hat": 0.6, "beta": 1.0, "T": 50_000.0}, "N"),
        ({"N": 100, "rho_hat": 0.6, "beta": 1.0, "T": 100.0}, "N"),
        ({"N": 2000, "rho_hat": 0.97, "beta": 1.0, "T": 1000.0}, "rho"),
        ({"N": 2000, "rho_hat": 0.6, "beta": 1.0, "T": 1000.0, "M": 3}, "M = 3"),
        ({"N": 2000, "rho_hat": 0.6, "beta": 1.0, "T": 1000.0, "resolution": 0.5}, "delta"),
        ({"N": 2000, "rho_hat": 0.6, "beta": 1e-6, "T": 1000.0}, "beta * T"),
        ({"N": 2000, "rho_hat": 0.6, "beta": 100.0, "T": 1000.0}, "beta * T"),
    ],
)
def test_outside_the_measured_box_is_unknown(rows, kwargs, reason):
    ans = trust_map.lookup(rows=rows, **kwargs)
    assert ans.status == "unknown"
    assert ans.coverage is None and ans.q is None and ans.distance is None
    assert reason in ans.note


def test_an_undefined_regime_returns_no_coverage(rows):
    # c = 1e-3, N = 2000, rho = 0.6: beta_min = 1e-3, T as in the grid.
    row = _row(rows, "M2_N2000_rho0.6_r0.0_c0.001")
    assert row["estimator_undefined"] == "1"
    ans = trust_map.lookup(2000, 0.6, 1e-3, float(row["T"]), rows=rows)
    assert ans.status == "estimator undefined in this regime"
    assert ans.cell == row["cell"]
    assert ans.coverage is None and ans.q is None
    assert math.isfinite(ans.distance)


def test_the_distance_grows_off_the_grid(rows):
    near = trust_map.lookup(2000, 0.3028, 1.0, 1722.6, rows=rows)
    far = trust_map.lookup(3000, 0.45, 1.0, 1722.6, rows=rows)
    assert near.distance < far.distance
