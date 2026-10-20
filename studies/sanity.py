"""Sanity pass over the raw H6 rows. Counts only: no bias, coverage or hypothesis test.

Run after the full grid and before ``analyze.py``. It exists so that the shape of
the data (how many fits failed, where the estimator hit a boundary, which verdicts
were issued) is on record independently of any estimand, and so a harness fault
would be visible before it became a hypothesis verdict.

    python -m studies.sanity
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

csv.field_size_limit(2**30)

STUDIES = Path(__file__).resolve().parent
CELLS_DIR = STUDIES / "results" / "cells"
THETA0 = STUDIES / "theta0.json"

BETA_OFFSET = 6  # theta_hat layout at M = 2: mu(2), alpha(4), beta(4)


def _cells() -> dict[str, dict]:
    doc = json.loads(THETA0.read_text(encoding="utf-8"))
    out = {}
    for c in doc["cells"]:
        key = f"M{c['M']}_N{c['N_target']}_rho{c['rho']}_r{c['r']}_c{c['c']}"
        out[key + ("_sat" if c["satellite"] else "")] = c
    return out


def _rows(key: str):
    with (CELLS_DIR / f"{key}.csv").open(newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def failure_profile() -> None:
    reasons: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    total = 0
    low_convergence = []
    for key in _cells():
        n = conv = 0
        for row in _rows(key):
            n += 1
            conv += row["converged"] == "1"
            verdicts[row["verdict"] or "(none)"] += 1
            for part in filter(None, row["failure"].split(";")):
                reasons[part] += 1
        total += n
        if conv / n < 0.5:
            low_convergence.append((key, conv / n))
    print(f"rows read: {total}")
    print("failure reasons:", dict(reasons))
    print("verdicts:", dict(verdicts))
    print("cells with convergence below 0.50:", low_convergence or "none")


def identifiability() -> None:
    """beta_min * T: how many slowest decay times the window holds."""
    print("\nbeta_min * T for r = 0 cells (M = 2)")
    cells = [c for c in _cells().values() if not c["satellite"] and c["r"] == 0.0]
    for cc in (1.0, 0.001):
        print(f" c = {cc}")
        for n in (200, 1000, 2000, 10000, 50000):
            cols = []
            for rho in (0.3028, 0.6, 0.85, 0.95):
                c = next(
                    x for x in cells if x["c"] == cc and x["N_target"] == n and x["rho"] == rho
                )
                cols.append(f"rho {rho}: {float(np.min(c['beta'])) * c['T']:9.2f}")
            print(f"  N={n:>6}  " + "  ".join(cols))


def implausible_beta() -> None:
    """Converged fits with some beta_hat above 10x the largest true beta, by verdict."""
    print("\nc = 1, r = 0: converged fits with a beta_hat above 10x the largest true beta")
    cells = [c for c in _cells().values() if not c["satellite"] and c["c"] == 1.0 and c["r"] == 0.0]
    tot_wild = tot_rel = 0
    for n in (200, 1000, 2000, 10000, 50000):
        for rho in (0.3028, 0.6, 0.85, 0.95):
            c = next(x for x in cells if x["N_target"] == n and x["rho"] == rho)
            cap = 10.0 * float(np.max(c["beta"]))
            conv = wild = rel = 0
            for row in _rows(f"M2_N{n}_rho{rho}_r0.0_c1.0"):
                if row["converged"] != "1" or not row["theta_hat"]:
                    continue
                conv += 1
                if max(json.loads(row["theta_hat"])[BETA_OFFSET : BETA_OFFSET + 4]) > cap:
                    wild += 1
                    rel += row["verdict"] == "reliable"
            tot_wild += wild
            tot_rel += rel
            pct = 100 * wild / conv
            print(
                f"  N={n:>6} rho={rho:<6} converged={conv:>5} "
                f"wild={wild:>5} ({pct:5.1f}%) reliable={rel:>4}"
            )
    print(f"  total wild {tot_wild}, of which verdict 'reliable' {tot_rel}")


def convergence_by_regime() -> None:
    groups: dict[tuple[str, str], list[tuple[float, float, float]]] = defaultdict(list)
    for key in _cells():
        if key.endswith("_sat"):
            continue
        c = "c=0.001" if "c0.001" in key else "c=1"
        r = next(t for t in key.split("_") if t.startswith("r") and t[1:2].isdigit())
        n = conv = nose = bound = 0
        for row in _rows(key):
            n += 1
            conv += row["converged"] == "1"
            nose += "se:none" in row["failure"]
            bound += row["bound_hit"] == "1"
        groups[(c, r)].append((conv / n, nose / n, bound / n))
    print("\nmean per-cell rates by regime (M = 2)")
    for (c, r), vals in sorted(groups.items()):
        a = np.array(vals).mean(axis=0)
        print(
            f"  {c:<8} {r:<6} cells={len(vals):>2}  converged={a[0]:.3f}  "
            f"no-SE={a[1]:.3f}  bound-hit={a[2]:.3f}"
        )


def main() -> None:
    failure_profile()
    identifiability()
    convergence_by_regime()
    implausible_beta()


if __name__ == "__main__":
    main()
