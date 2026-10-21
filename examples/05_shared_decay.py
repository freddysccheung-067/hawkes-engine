"""Pair decay and shared decay: the same likelihood where they coincide.

With beta[i, j] = b[j] the pair-decay likelihood equals the shared-decay one. The
speed ratio printed at the end is read from the committed capability table; it is
a likelihood-call ratio on one machine, not a measurement made by this script, and
a fit-level speed-up for shared decay was not measured. Shared decay is a different
model (M decay rates, not M^2). Deterministic and instant.
"""

import re
from pathlib import Path

import hawkes_engine as he
import numpy as np

mu = np.array([0.4, 0.5, 0.3])
alpha = np.array([[0.10, 0.20, 0.05], [0.15, 0.10, 0.10], [0.05, 0.10, 0.20]])
b = np.array([1.0, 1.5, 2.0])
beta_pair = np.tile(b, (3, 1))  # beta[i, j] = b[j]: the decay belongs to the source

times, types = he.simulate(mu, alpha, beta_pair, T=500.0, seed=5)
pair = he.loglik(times, types, mu, alpha, beta_pair, T=500.0)["value"]
shared = he.loglik(times, types, mu, alpha, b, T=500.0, shared_decay=True)["value"]
print(f"{len(times)} events")
print(f"pair decay   loglik = {pair:.10f}")
print(f"shared decay loglik = {shared:.10f}")
print(f"absolute difference = {abs(pair - shared):.2e}")
assert abs(pair - shared) < 1e-8 * abs(pair)

table = Path(__file__).parents[1] / "benchmarks" / "results" / "capability_2026-10-21.md"
row = re.search(
    r"^\| 6 \| 1,000,000 \| value\+grad \| (\S+ ms) \| (\S+ ms) \| (\S+) \|",
    table.read_text(),
    re.M,
)
print("capability table, M=6, N=1,000,000, value+grad:")
print(f"  pair {row[1]}, shared {row[2]}, ratio {row[3]}")
