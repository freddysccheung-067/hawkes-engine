"""Phase 3 sanity: an independent recomputation, sharing no code with analyze.py.

Pure Python (csv, json, math): no numpy, no import from ``studies``. It re-reads
three cells, rebuilds theta_0 from ``studies/theta0.json`` by its own key rule,
and recomputes coverage (E3.5, over all replications and conditioned on
convergence), bias and q for every block. It then compares with
``studies/results/analysis/blocks.csv`` and fails if any value differs by more
than 1e-12.

    python studies/sanity_independent.py
"""

import csv
import json
import math
import sys
from pathlib import Path

csv.field_size_limit(2**30)

HERE = Path(__file__).resolve().parent
CELLS = [
    "M2_N2000_rho0.3028_r0.0_c1.0",  # the anchor
    "M2_N200_rho0.95_r0.1_c1.0",  # small N, near-critical, quantised
    "M4_N20000_rho0.85_r0.0_c1.0_sat",  # the M = 4 satellite
]
TOL = 1e-12


def truth(key):
    doc = json.loads((HERE / "theta0.json").read_text(encoding="utf-8"))
    for c in doc["cells"]:
        k = f"M{c['M']}_N{c['N_target']}_rho{c['rho']!r}_r{c['r']!r}_c{c['c']!r}"
        if c["satellite"]:
            k += "_sat"
        if k == key:
            t = list(c["mu"])
            for row in c["alpha"]:
                t.extend(row)
            for row in c["beta"]:
                t.extend(row)
            return c["M"], t
    raise KeyError(key)


def flatten(text):
    out = []
    for v in json.loads(text):
        if isinstance(v, list):
            out.extend(v)
        else:
            out.append(v)
    return out


def recompute(key):
    M, t0 = truth(key)
    blocks = {
        "mu": list(range(M)),
        "alpha": list(range(M, M + M * M)),
        "beta": list(range(M + M * M, M + 2 * M * M)),
    }
    blocks["all"] = list(range(M + 2 * M * M))
    reps = []
    with (HERE / "results" / "cells" / (key + ".csv")).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            est = flatten(row["theta_hat"])
            se = None
            if row["se_mu"] != "":
                se = flatten(row["se_mu"]) + flatten(row["se_alpha"]) + flatten(row["se_beta"])
            reps.append((est, se, row["converged"] == "1"))
    out = {}
    for name, J in blocks.items():
        shares_all = []
        shares_conv = []
        for est, se, conv in reps:
            hits = 0
            for j in J:
                if se is not None and abs(est[j] - t0[j]) <= 1.959964 * se[j]:
                    hits += 1
            shares_all.append(hits / len(J))
            if conv:
                shares_conv.append(hits / len(J))
        R = len(reps)
        bias_terms = [est[j] - t0[j] for est, _, _ in reps for j in J]
        var_sum = 0.0
        for j in J:
            m = sum(est[j] for est, _, _ in reps) / R
            var_sum += sum((est[j] - m) ** 2 for est, _, _ in reps) / R
        sd = math.sqrt(var_sum / len(J))
        se_vals = [se[j] for _, se, _ in reps if se is not None for j in J]
        mse = sum(se_vals) / len(se_vals) if se_vals else float("nan")
        out[name] = {
            "cov_all": sum(shares_all) / len(shares_all),
            "cov_cond": sum(shares_conv) / len(shares_conv),
            "bias": sum(bias_terms) / len(bias_terms),
            "sd": sd,
            "q": mse / sd,
        }
    return out


def recorded(key):
    out = {}
    with (HERE / "results" / "analysis" / "blocks.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["cell"] == key:
                out[row["block"]] = {
                    k: float(row[k]) for k in ("cov_all", "cov_cond", "bias", "sd", "q")
                }
    return out


def main():
    worst = 0.0
    ok = True
    for key in CELLS:
        mine = recompute(key)
        theirs = recorded(key)
        for block in ("mu", "alpha", "beta", "all"):
            for stat in ("cov_all", "cov_cond", "bias", "sd", "q"):
                a, b = mine[block][stat], theirs[block][stat]
                diff = abs(a - b) / max(1.0, abs(b))
                worst = max(worst, diff)
                flag = "PASS" if diff <= TOL else "FAIL"
                ok = ok and diff <= TOL
                print(
                    f"{flag}  {key:<34} {block:<5} {stat:<8} "
                    f"naive={a:.15g} analyze={b:.15g} diff={diff:.2e}"
                )
    print(f"worst relative difference {worst:.3e} (tolerance {TOL:.0e})")
    print("ALL AGREE" if ok else "DISAGREEMENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
