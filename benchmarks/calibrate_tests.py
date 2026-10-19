"""Offline calibration of the simulator tests' false-rejection rates.

Each statistical test in ``tests/test_simulators.py`` is a function of a seed.
Under the null (a correct simulator) it should reject at its nominal level,
1e-3. This script runs every check under 200 different seeds, once, and records
the observed number of rejections; with 200 trials and a true level of 1e-3 the
chance of three or more rejections is about 1e-3, so more than 2 is evidence
that the test or the simulator is wrong, not bad luck. Thresholds are never
widened to pass; a failing row is investigated.

Run:  python benchmarks/calibrate_tests.py [--seeds 200] > benchmarks/results/calibration.txt
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scipy import stats  # noqa: E402

from tests import _stat_checks as chk  # noqa: E402

RHOS = (0.3, 0.6, 0.85)
LIMIT = 2


def _cluster_rejects(rho: float, seed: int) -> bool:
    est, se, exact, _ = chk.cluster_size(rho, seed)
    return abs(est - exact) > 4 * se


def _cases():
    for method in chk.METHODS:
        for M in (1, 2, 3):
            for rho in RHOS:
                yield (
                    f"stationary_mean[{method},M={M},rho={rho}]",
                    lambda s, m=method, M=M, r=rho: (
                        chk.stationary_mean_z(m, M, r, s)[0] > chk.MEAN_Z_LIMIT
                    ),
                )
    yield "count_distribution", lambda s: chk.count_distribution_p(s) < chk.ALPHA
    yield "gap_distribution", lambda s: chk.gap_distribution_p(s) < chk.ALPHA
    for method in chk.METHODS:
        for M, rho in ((1, 0.3), (2, 0.6), (3, 0.85)):
            yield (
                f"rescaling[{method},M={M},rho={rho}]",
                lambda s, m=method, M=M, r=rho: chk.rescaling_p(m, M, r, s) < chk.ALPHA,
            )
        yield (
            f"poisson_limit[{method}]",
            lambda s, m=method: chk.poisson_limit_p(m, s) < chk.ALPHA,
        )
    for rho in (0.3, 0.6):
        yield (
            f"cluster_size[rho={rho}]",
            lambda s, r=rho: _cluster_rejects(r, s),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=200)
    args = parser.parse_args()

    failures = 0
    print(f"{'check':45s} {'rejections':>10s} {'of':>5s} {'P(>=k | level 1e-3)':>22s}")
    for name, reject in _cases():
        t = time.time()
        k = sum(bool(reject(10_000 + s)) for s in range(args.seeds))
        tail = stats.binom.sf(k - 1, args.seeds, chk.ALPHA) if k else 1.0
        flag = "" if k <= LIMIT else "  <-- INVESTIGATE"
        failures += k > LIMIT
        print(f"{name:45s} {k:10d} {args.seeds:5d} {tail:22.3g}{flag}  ({time.time() - t:.0f}s)")
        sys.stdout.flush()
    print(f"\nchecks over the limit of {LIMIT} rejections: {failures}")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
