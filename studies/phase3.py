"""Phase 3 sanity checks on the H6 analysis output, before any verdict is believed.

Reads the raw cell CSVs and ``studies/results/analysis/``; writes
``studies/results/analysis/phase3_report.txt``. Four checks:

1. The H3 anchor: bias, ``bias / sd``, ``z`` and coverage per coordinate at
   ``M2_N2000_rho0.3028_r0.0_c1.0``, against ``studies/PRIOR_EVIDENCE.md`` section 2.
2. Every cell-block with coverage exactly 0 or 1, or ``q`` outside [0.2, 5], with
   the quantities that explain it.
3. Rows entering each estimand against rows minus documented exclusions, cell by
   cell, the exclusions recounted from the raw ``failure`` strings.
4. A diagnostic of H6.6 computed **after** the verdicts were seen: how much of
   ``Delta`` comes from replications that have no standard error. It is labelled
   post hoc in the report and decides nothing.

    python -m studies.phase3
"""

from __future__ import annotations

import csv
import io
import math
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

from studies import analyze
from studies.grid import load_cells

ANALYSIS = analyze.OUT_DIR
ANCHOR = "M2_N2000_rho0.3028_r0.0_c1.0"

# PRIOR_EVIDENCE.md section 2, the 2000-event row, and its text.
H3 = {
    "R": 100,
    "worst_abs_z": 4.63,
    "mean_abs_z": 0.90,
    "worst_bias_over_sd": 0.46,
    "alpha01_bias_over_sd": 0.46,
    "beta01_bias_over_sd": 0.40,
    "coverage_range": (0.90, 0.95),
    "beta01_p95": 8.6,
}


def _read(name: str) -> list[dict[str, str]]:
    with (ANALYSIS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def anchor() -> None:
    print("=" * 78)
    print("1. The H3 anchor, M2_N2000_rho0.3028_r0.0_c1.0")
    print("=" * 78)
    cell = {c.key: c for c in load_cells()}[ANCHOR]
    data = analyze.load_cell(cell)
    names = analyze.coordinate_names(2)
    hits = analyze.coverage_hits(data)
    for label, n in (("all 2000 replications", data.R), ("first 100 replications", 100)):
        X = data.theta_hat[:n]
        d = X - data.theta0
        bias = d.mean(axis=0)
        sd = X.std(axis=0)
        z = bias / (sd / math.sqrt(n))
        cov = hits[:n].mean(axis=0)
        print(f"\n{label}:")
        print(
            f"  {'coordinate':<11} {'theta0':>8} {'mean':>10} {'median':>8} {'bias':>10} "
            f"{'bias/sd':>8} {'z':>7} {'coverage':>9}"
        )
        for j, name in enumerate(names):
            print(
                f"  {name:<11} {data.theta0[j]:8.4f} {X[:, j].mean():10.4f} "
                f"{np.median(X[:, j]):8.4f} {bias[j]:+10.4f} {bias[j] / sd[j]:+8.3f} "
                f"{z[j]:+7.2f} {cov[j]:9.4f}"
            )
        exc = slice(2, 10)
        print(
            f"  excitation entries: worst |z| {np.abs(z[exc]).max():.2f}, mean |z| "
            f"{np.abs(z[exc]).mean():.2f}, worst bias/sd {np.abs(bias / sd)[exc].max():.3f}"
        )
        print(f"  coverage range over the 10 coordinates: {cov.min():.4f} to {cov.max():.4f}")
    b01 = data.theta_hat[:, 7]
    print(
        f"\n  beta[0,1]: median {np.median(b01):.3f}, mean {b01.mean():.2f}, "
        f"p95 {np.percentile(b01, 95):.2f}, p99 {np.percentile(b01, 99):.1f}, "
        f"max {b01.max():.0f} (truth 1.2)"
    )
    est = analyze.cell_estimands(data)
    print("\n  block estimands (all 2000):")
    for b in analyze.BLOCKS:
        x = est["blocks"][b]
        c = est["companions"][b]
        print(
            f"    {b:<6} rel {x['rel']:+.4f} +/- {x['se_rel']:.4f}   cov {x['cov_all']:.4f} "
            f"+/- {x['se_cov_all']:.4f}   q {x['q']:.4f}   medrel {c['medrel']:+.4f}   "
            f"qrob {c['qrob']:.4f}"
        )
    print(
        "\n  H3 recorded (R = 100, PRIOR_EVIDENCE.md section 2): worst |z| 4.63, mean |z| "
        "0.90, worst bias/sd 0.46 (alpha[0,1]) and 0.40 (beta[0,1]), coverage 0.90 to "
        "0.95, beta[0,1] p95 8.6. H3 never formed q."
    )


def extremes() -> None:
    print()
    print("=" * 78)
    print("2. Cell-blocks with coverage exactly 0 or 1, or q outside [0.2, 5]")
    print("=" * 78)
    cells = {r["cell"]: r for r in _read("cells.csv")}
    rows = [r for r in _read("blocks.csv") if r["block"] != "all"]
    flagged = []
    for r in rows:
        cov = float(r["cov_all"])
        q = float(r["q"]) if r["q"] not in ("", "inf") else math.inf
        reasons = []
        if cov in (0.0, 1.0):
            reasons.append(f"coverage {cov:g}")
        if not 0.2 <= q <= 5.0:
            reasons.append(f"q {q:.3g}")
        if reasons:
            flagged.append((r, reasons))
    print(f"{len(flagged)} of {len(rows)} cell-blocks flagged.\n")
    groups: dict[str, list[str]] = {}
    for r, reasons in flagged:
        m = cells[r["cell"]]
        no_se = float(m["no_se_rate"])
        undefined = m["estimator_undefined"] == "1"
        if undefined:
            cause = "estimator undefined (unresolved ticks or no SE in most replications)"
        elif float(r["sd"]) > 10 * float(r["mse"]) if r["mse"] else False:
            cause = "sd inflated by a heavy right tail (sd > 10 x mean SE)"
        elif no_se > 0.2:
            cause = "more than 20 percent of replications return no SE"
        else:
            cause = "other"
        groups.setdefault(cause, []).append(
            f"  {r['cell']:<36} {r['block']:<6} {', '.join(reasons):<24} "
            f"no_se {no_se:.3f} conv {float(m['convergence_rate']):.3f} "
            f"sd {float(r['sd']):.4g} mean_se {float(r['mse']) if r['mse'] else math.nan:.4g}"
        )
    for cause, lines in groups.items():
        print(f"{cause}: {len(lines)}")
        for line in lines:
            print(line)
        print()
    other = groups.get("other", [])
    print(f"Unexplained by the three causes above: {len(other)}")


def _failures(path: Path) -> tuple[int, int, int, int]:
    rows = no_se = not_conv = 0
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows += 1
            parts = set(filter(None, row["failure"].split(";")))
            no_se += "se:none" in parts
            not_conv += "not_converged" in parts
    return rows, no_se, not_conv, rows - not_conv


def row_counts() -> None:
    print("=" * 78)
    print("3. Rows entering each estimand = rows minus documented exclusions")
    print("=" * 78)
    counts = {r["cell"]: r for r in _read("row_counts.csv")}
    bad = []
    for cell in load_cells():
        rows, no_se, not_conv, conv = _failures(analyze.CELLS_DIR / f"{cell.key}.csv")
        c = counts[cell.key]
        expect = {
            "rows": rows,
            "n_bias": rows,  # E3.1 to E3.3: no exclusion (R1)
            "n_mse": rows - no_se,  # E3.4: excludes se:none
            "n_cov_all": rows,  # E3.5 unconditional: se:none is a miss, not an exclusion
            "n_cov_cond": rows - not_conv,  # E3.5 conditional: excludes not_converged
            "n_tail": conv,  # E4.4: converged only
        }
        for k, v in expect.items():
            if int(c[k]) != v:
                bad.append(f"  {cell.key} {k}: analysis {c[k]}, expected {v}")
    print(f"checked 128 cells x 6 counts; mismatches: {len(bad)}")
    for line in bad:
        print(line)
    print(
        "Exclusions are recounted here from the raw failure strings, not taken from "
        "analyze.py: se:none for E3.4, not_converged for conditional coverage and E4.4."
    )


def h66_diagnostic() -> None:
    print()
    print("=" * 78)
    print("4. H6.6 diagnostic: POST HOC, computed after the verdicts were seen")
    print("=" * 78)
    print(
        "E3.5 counts a replication without a standard error as a miss, and trust.report\n"
        "returns 'unreliable' whenever the information matrix could not be inverted. So\n"
        "an 'unreliable' replication without an SE has coverage 0 by definition. This\n"
        "splits each class by whether it carries an SE. It is not a sensitivity value\n"
        "named in ANALYSIS_NOTES.md before the run, and it decides nothing.\n"
    )
    cells = {c.key: c for c in load_cells()}
    region = [k for k, c in cells.items() if c.c == 1.0 and c.r == 0.0]
    deltas = []
    tot = {"rel_se": [0, 0.0], "unrel_se": [0, 0.0], "unrel_nose": 0, "rel_nose": 0}
    print(
        f"  {'cell':<36} {'unrel':>5} {'no SE':>5} {'cov_rel|SE':>10} "
        f"{'cov_unrel|SE':>12} {'Delta|SE':>9}"
    )
    for k in sorted(region):
        d = analyze.load_cell(cells[k])
        share = analyze.coverage_hits(d).mean(axis=1)
        rel = d.verdict == "reliable"
        unrel = d.verdict == "unreliable"
        tot["unrel_nose"] += int((unrel & ~d.has_se).sum())
        tot["rel_nose"] += int((rel & ~d.has_se).sum())
        a = share[rel & d.has_se]
        b = share[unrel & d.has_se]
        tot["rel_se"][0] += a.size
        tot["rel_se"][1] += float(a.sum())
        tot["unrel_se"][0] += b.size
        tot["unrel_se"][1] += float(b.sum())
        if unrel.sum() == 0:
            continue
        line = f"  {k:<36} {int(unrel.sum()):5d} {int((unrel & ~d.has_se).sum()):5d} "
        if a.size and b.size:
            se = math.sqrt(a.mean() * (1 - a.mean()) / a.size + b.mean() * (1 - b.mean()) / b.size)
            deltas.append((a.mean() - b.mean(), se))
            line += f"{a.mean():10.4f} {b.mean():12.4f} {a.mean() - b.mean():+9.4f}"
        else:
            line += f"{a.mean() if a.size else math.nan:10.4f} {'(none)':>12}"
        print(line)
    n_unrel = tot["unrel_nose"] + tot["unrel_se"][0]
    print(
        f"\n  region: {n_unrel} 'unreliable' replications, {tot['unrel_nose']} of them "
        f"without an SE ({tot['unrel_nose'] / n_unrel:.3f}); {tot['rel_nose']} 'reliable' "
        "replications without an SE."
    )
    if deltas:
        D = np.array([x for x, _ in deltas])
        S = np.array([s for _, s in deltas])
        agg = analyze.mean_of_differences(D, S)
        print(
            f"  Delta among replications that carry an SE, mean over the {agg['K']} cells "
            f"with both classes: {agg['T']:+.4f} +/- {agg['se_independent']:.4f} "
            f"(independent cells) or +/- {agg['se_between']:.4f} (between-cell spread)."
        )
    rp, up = tot["rel_se"], tot["unrel_se"]
    if rp[0] and up[0]:
        print(
            f"  Pooled over replications with an SE (confounded with N): reliable "
            f"{rp[1] / rp[0]:.4f} (n {rp[0]}), unreliable {up[1] / up[0]:.4f} (n {up[0]})."
        )


def main() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        anchor()
        extremes()
        row_counts()
        h66_diagnostic()
    text = buf.getvalue()
    print(text)
    (ANALYSIS / "phase3_report.txt").write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
