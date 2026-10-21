"""A small reproduction of the SE-understatement finding. An illustration, not the study.

Fits 50 replicates at one cell of the H6 grid (N = 2000, rho = 0.3028, c = 1) and
reports q = mean reported SE / empirical SD per block. q < 1 means the reported
standard errors are smaller than the spread of the estimates. 50 replicates is far
too few to decide anything. Here the mu and beta blocks come out below 1 and the
alpha block above it, and the beta block does not reach the heavy tail of beta_hat
that dominates the study's q for that block; a different seed range moves each
block by several tenths. The study's values for the same cell are printed below.
This script therefore does not reproduce the finding at one cell; the pooled
result over 12 cells and 24 000 fits is what supports it (q = 0.779 +/- 0.011, see
docs/limits.md); the study's numbers are in studies/results/analysis/. Runs in a few
seconds.
"""

import csv
import json
from pathlib import Path

import hawkes_engine as he
import numpy as np

cells = json.loads((Path(__file__).parents[1] / "studies" / "theta0.json").read_text())["cells"]
cell = next(
    c for c in cells if (c["N_target"], c["rho"], c["r"], c["c"]) == (2000, 0.3028, 0.0, 1.0)
)
mu, alpha, beta, T = (np.array(cell[k]) for k in ("mu", "alpha", "beta", "T"))

burn_in = 10.0 / (beta.min() * (1.0 - 0.3028))  # the study's rule: ten relaxation times
R = 50
est, se, no_se = [], [], 0
for k in range(R):
    times, types = he.simulate(mu, alpha, beta, T=float(T), seed=1000 + k, burn_in=burn_in)
    fit = he.fit(times, types, M=2, T=float(T), seed=k)
    if fit.se is None:
        no_se += 1
        continue
    est.append(np.concatenate([fit.mu, fit.alpha.ravel(), fit.beta.ravel()]))
    se.append(np.concatenate([fit.se["mu"], fit.se["alpha"].ravel(), fit.se["beta"].ravel()]))

est, se = np.array(est), np.array(se)
sd = est.std(axis=0)
q = se.mean(axis=0) / sd
print(f"{R} replicates, {R - no_se} with standard errors")
for name, sl in (("mu", slice(0, 2)), ("alpha", slice(2, 6)), ("beta", slice(6, 10))):
    print(f"  q[{name}] = {q[sl].mean():.3f}   (per coordinate {np.round(q[sl], 3).tolist()})")
study = Path(__file__).parents[1] / "data" / "trust" / "v1_excitation_only.csv"
row = next(r for r in csv.DictReader(study.open()) if r["cell"] == "M2_N2000_rho0.3028_r0.0_c1.0")
print(
    "study, same cell, 2000 replicates: "
    + ", ".join(f"q[{b}] = {float(row[b + '_q']):.3f}" for b in ("mu", "alpha", "beta"))
)
