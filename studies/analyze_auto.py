"""Analyse the ``auto-v1`` study and test H-A1, H-A2 and H-A3.

    python -m studies.analyze_auto

Writes ``studies/results/auto/analysis/``:

* ``cells.csv``    per cell and block: coverage, q, delta, over, with SEs;
* ``delta.csv``    the paired difference that H-A1 is decided on;
* ``decisions.csv`` how often each map action was taken;
* ``hypotheses.json`` the verdicts and the numbers that produced them;
* ``report.txt``   the human-readable summary the paper and the docs quote.

Every number is computed from the rows and nothing is read from a stored
estimate. The hypotheses are the ones frozen in ``docs/preregistration_auto.md``:

H-A1  delta(beta) < 0 by more than two paired standard errors at each cell, and
      the same sign on the pooled block.
H-A2  cov_auto <= 1.05 * 0.95 at every cell and block.
H-A3  (exploratory) the improvement is larger at rho = 0.95 than at 0.3028.

The paired SE is the standard error of the per-replication difference between the
two arms' coverage indicators, which is legitimate because both arms saw the same
event stream.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

STUDIES = Path(__file__).resolve().parent
RESULTS = STUDIES / "results" / "auto"
OUT = RESULTS / "analysis"

NOMINAL = 0.95
Z = 1.959963984540054
BLOCKS = ("mu", "alpha", "beta", "all")
CELLS = (
    "M2_N2000_rho0.3028_r0.0_c1.0",
    "M2_N2000_rho0.85_r0.0_c1.0",
    "M2_N2000_rho0.95_r0.0_c1.0",
)


def _rows(key: str) -> list[dict[str, str]]:
    path = RESULTS / f"{key}.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(value: str) -> float:
    return float(value) if value not in ("", None) else float("nan")


def _mean_se(values: np.ndarray) -> tuple[float, float]:
    """A mean and its Monte Carlo standard error."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), float("nan")
    return float(finite.mean()), float(finite.std(ddof=1) / np.sqrt(finite.size))


def analyse_cell(key: str) -> dict[str, Any]:
    rows = _rows(key)
    valid = [r for r in rows if not r["failure"]]
    n = len(valid)
    out: dict[str, Any] = {"cell": key, "rows": len(rows), "failures": len(rows) - n, "blocks": {}}

    for block in BLOCKS:
        h = np.array([_f(r[f"h_cov_{block}"]) for r in valid], dtype=float)
        a = np.array([_f(r[f"a_cov_{block}"]) for r in valid], dtype=float)
        h_mean, h_se = _mean_se(h)
        a_mean, a_se = _mean_se(a)
        d = np.abs(a - NOMINAL) - np.abs(h - NOMINAL)
        d_mean, d_se = _mean_se(d)
        # Paired SE of the difference in coverage itself, for the overshoot test.
        diff = a - h
        diff_mean, diff_se = _mean_se(diff)
        out["blocks"][block] = {
            "n": n,
            "cov_hessian": h_mean,
            "cov_hessian_se": h_se,
            "cov_auto": a_mean,
            "cov_auto_se": a_se,
            "delta": d_mean,
            "delta_se": d_se,
            "delta_z": d_mean / d_se if d_se and np.isfinite(d_se) and d_se > 0 else float("nan"),
            "coverage_difference": diff_mean,
            "coverage_difference_se": diff_se,
            "over": a_mean - NOMINAL,
        }

    # The reported SEs, to show what changed in the interval rather than only its
    # coverage.
    for arm in ("h", "a"):
        for block in ("mu", "alpha", "beta"):
            values = np.array([_f(r[f"{arm}_se_{block}"]) for r in valid], dtype=float)
            mean, se = _mean_se(values)
            out["blocks"][block][f"mean_se_{'hessian' if arm == 'h' else 'auto'}"] = mean

    actions: dict[str, int] = {}
    for r in valid:
        actions[r["a_action"]] = actions.get(r["a_action"], 0) + 1
    out["actions"] = actions
    out["sources_hessian"] = {r["h_source"] for r in valid}
    out["sources_auto"] = {r["a_source"] for r in valid}
    distances = np.array([_f(r["a_distance"]) for r in valid], dtype=float)
    mean_d, se_d = _mean_se(distances)
    out["distance_mean"] = mean_d
    out["distance_se"] = se_d
    return out


def decide_hypotheses(cells: list[dict[str, Any]]) -> dict[str, Any]:
    hypotheses: dict[str, Any] = {}

    # H-A1: delta(beta) < -2 SE at every cell, and pooled delta < 0 too.
    per_cell = {
        c["cell"]: {
            "delta_beta": c["blocks"]["beta"]["delta"],
            "delta_beta_se": c["blocks"]["beta"]["delta_se"],
            "z": c["blocks"]["beta"]["delta_z"],
            "delta_all": c["blocks"]["all"]["delta"],
            "delta_all_se": c["blocks"]["all"]["delta_se"],
        }
        for c in cells
    }
    beta_ok = all(
        v["delta_beta"] < 0 and v["delta_beta"] < -2.0 * v["delta_beta_se"]
        for v in per_cell.values()
    )
    pool_ok = all(v["delta_all"] < 0 for v in per_cell.values())
    hypotheses["H-A1"] = {
        "label": "confirmed" if (beta_ok and pool_ok) else "not confirmed",
        "beta_block_below_neg_2se_every_cell": bool(beta_ok),
        "pooled_block_negative_every_cell": bool(pool_ok),
        "per_cell": per_cell,
    }

    # H-A2: no block in any cell exceeds 1.05 * nominal.
    ceiling = NOMINAL * 1.05
    over = {
        c["cell"]: {
            b: {
                "cov_auto": c["blocks"][b]["cov_auto"],
                "ceiling": ceiling,
                "ok": c["blocks"][b]["cov_auto"] <= ceiling,
            }
            for b in BLOCKS
        }
        for c in cells
    }
    worst = max(
        c["blocks"][b]["cov_auto"]
        for c in cells
        for b in BLOCKS
        if np.isfinite(c["blocks"][b]["cov_auto"])
    )
    hypotheses["H-A2"] = {
        "label": "confirmed" if worst <= ceiling else "not confirmed",
        "ceiling": ceiling,
        "worst_cov_auto": worst,
        "by_cell": over,
    }

    # H-A3 (exploratory): the improvement at rho = 0.95 exceeds that at 0.3028.
    low = per_cell["M2_N2000_rho0.3028_r0.0_c1.0"]
    high = per_cell["M2_N2000_rho0.95_r0.0_c1.0"]
    gain_low = -low["delta_all"]
    gain_high = -high["delta_all"]
    gain_diff = gain_high - gain_low
    gain_se = float(np.hypot(low["delta_all_se"], high["delta_all_se"]))
    hypotheses["H-A3"] = {
        "label": "confirmed (exploratory)" if gain_diff > 2.0 * gain_se else "not confirmed",
        "gain_at_low_rho": gain_low,
        "gain_at_high_rho": gain_high,
        "difference": gain_diff,
        "difference_se": gain_se,
        "note": "exploratory: the map's own pattern suggested the direction",
    }
    return hypotheses


def write_outputs(cells: list[dict[str, Any]], hypotheses: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    with (OUT / "cells.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "cell",
                "block",
                "n",
                "cov_hessian",
                "cov_hessian_se",
                "cov_auto",
                "cov_auto_se",
                "delta",
                "delta_se",
                "delta_z",
                "coverage_difference",
                "coverage_difference_se",
                "over",
                "mean_se_hessian",
                "mean_se_auto",
            ]
        )
        for c in cells:
            for b in BLOCKS:
                v = c["blocks"][b]
                w.writerow(
                    [
                        c["cell"],
                        b,
                        v["n"],
                        f"{v['cov_hessian']:.6f}",
                        f"{v['cov_hessian_se']:.6f}",
                        f"{v['cov_auto']:.6f}",
                        f"{v['cov_auto_se']:.6f}",
                        f"{v['delta']:.6f}",
                        f"{v['delta_se']:.6f}",
                        f"{v['delta_z']:.4f}",
                        f"{v['coverage_difference']:.6f}",
                        f"{v['coverage_difference_se']:.6f}",
                        f"{v['over']:.6f}",
                        f"{v.get('mean_se_hessian', float('nan')):.6f}",
                        f"{v.get('mean_se_auto', float('nan')):.6f}",
                    ]
                )

    with (OUT / "decisions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell", "action", "count", "rows", "failures", "distance_mean", "distance_se"])
        for c in cells:
            for action, count in sorted(c["actions"].items()):
                w.writerow(
                    [
                        c["cell"],
                        action,
                        count,
                        c["rows"],
                        c["failures"],
                        f"{c['distance_mean']:.4f}",
                        f"{c['distance_se']:.4f}",
                    ]
                )

    payload = {
        "study_id": "auto-v1",
        "preregistration": "docs/preregistration_auto.md",
        "cells": cells,
        "hypotheses": hypotheses,
    }
    (OUT / "hypotheses.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def report(cells: list[dict[str, Any]], hypotheses: dict[str, Any]) -> str:
    lines = [
        "auto-v1: does the auto interval land closer to nominal than the Hessian's?",
        "",
    ]
    for c in cells:
        lines.append(f"{c['cell']}  ({c['rows']} rows, {c['failures']} failures)")
        lines.append(
            f"  {'block':6s} {'cov hessian':>18s} {'cov auto':>18s} {'delta':>18s} "
            f"{'mean SE h':>11s} {'mean SE a':>11s}"
        )
        for b in BLOCKS:
            v = c["blocks"][b]
            lines.append(
                f"  {b:6s} {v['cov_hessian']:9.4f} +/- {v['cov_hessian_se']:.4f} "
                f"{v['cov_auto']:9.4f} +/- {v['cov_auto_se']:.4f} "
                f"{v['delta']:9.4f} +/- {v['delta_se']:.4f} "
                f"{v.get('mean_se_hessian', float('nan')):11.4f} "
                f"{v.get('mean_se_auto', float('nan')):11.4f}"
            )
        actions = ", ".join(f"{k}: {v}" for k, v in sorted(c["actions"].items()))
        lines.append(f"  map actions: {actions}")
        lines.append("")
    lines.append("Hypotheses")
    for name in ("H-A1", "H-A2", "H-A3"):
        h = hypotheses[name]
        lines.append(f"  {name}: {h['label']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    missing = [k for k in CELLS if not (RESULTS / f"{k}.csv").exists()]
    if missing:
        print(f"missing cells: {missing}; run python -m studies.run_auto first")
        return 1
    cells = [analyse_cell(k) for k in CELLS]
    hypotheses = decide_hypotheses(cells)
    write_outputs(cells, hypotheses)
    text = report(cells, hypotheses)
    (OUT / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
