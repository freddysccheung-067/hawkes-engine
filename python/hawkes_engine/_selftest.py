"""Self-test run against an installed wheel by cibuildwheel.

This is what ``CIBW_TEST_COMMAND`` executes, and it is deliberately not
``import hawkes_engine``. An import proves that the extension loads; it does not
prove that the compiled code runs, that the parameter blocks are reachable, or
that a simulated path comes back with the right dtype. A wheel that fails either
of those is broken for every user while importing cleanly.

The script is inside the package rather than in the test tree because a wheel
does not ship ``tests/``. Keep it dependency-free apart from NumPy, which the
library already requires, and keep it under a second.
"""

from __future__ import annotations

import sys

import numpy as np

from hawkes_engine import __version__, loglik, simulate, trust_lookup
from hawkes_engine._core import build_info
from hawkes_engine.trust_map import MAP_PATH


def _check_likelihood() -> float:
    times = np.array([0.4, 1.1, 1.9, 3.0, 4.2])
    types = np.array([0, 1, 0, 1, 0], dtype=np.uint8)
    mu = np.array([0.6, 0.9])
    alpha = np.array([[0.10, 0.35], [0.20, 0.05]])
    beta = np.array([[1.30, 1.70], [1.30, 1.70]])
    out = loglik(times, types, mu, alpha, beta, 6.0, grad=True)
    value = out["value"]
    if not np.isfinite(value):
        raise SystemExit(f"loglik returned {value!r}, expected a finite value")
    # The gradient must have the documented shapes, not merely exist.
    blocks = {"dmu": out["dmu"], "dalpha": out["dalpha"], "dbeta": out["dbeta"]}
    for key, shape in (("dmu", (2,)), ("dalpha", (2, 2)), ("dbeta", (2, 2))):
        if blocks[key].shape != shape:
            raise SystemExit(f"{key} has shape {blocks[key].shape}, expected {shape}")
    return float(value)


def _check_simulation() -> int:
    mu = np.array([0.6, 0.9])
    alpha = np.array([[0.10, 0.35], [0.20, 0.05]])
    beta = np.array([[1.30, 1.70], [1.30, 1.70]])
    for method in ("thinning", "cluster"):
        times, types = simulate(mu, alpha, beta, 200.0, method=method, seed=2026)
        if times.dtype != np.float64 or types.dtype != np.uint8:
            raise SystemExit(f"{method}: dtypes are {times.dtype}, {types.dtype}")
        if times.size == 0 or times.size != types.size:
            raise SystemExit(f"{method}: {times.size} times, {types.size} types")
        if np.any(np.diff(times) < 0):
            raise SystemExit(f"{method}: times are not sorted")
    return int(times.size)


def _check_trust_map() -> str:
    # The map is data, not code, so a wheel can import and compute and still
    # lack it. Without the installed copy MAP_PATH falls back to a path inside a
    # source checkout, which does not exist in site-packages, so is_file() fails
    # exactly when the wheel is missing it.
    if not MAP_PATH.is_file():
        raise SystemExit(f"the trust map is missing: {MAP_PATH}")
    measured = trust_lookup(N=2000, rho_hat=0.3028, beta=1.0, T=1722.6)
    outside = trust_lookup(N=500_000, rho_hat=0.3028, beta=1.0, T=1722.6)
    if measured.status != "measured" or measured.coverage is None:
        raise SystemExit(f"trust_lookup at the anchor cell answered {measured.status!r}")
    if outside.status != "unknown":
        raise SystemExit(f"trust_lookup outside the box answered {outside.status!r}")
    return measured.cell or ""


def main() -> int:
    info = build_info()
    value = _check_likelihood()
    n_events = _check_simulation()
    cell = _check_trust_map()
    print(
        f"hawkes-engine {__version__} on {sys.platform}, "
        f"built with {info['compiler']} {info['compiler_version']}, "
        f"pybind11 {info['pybind11_version']}: "
        f"loglik = {value:.6f}, simulated {n_events} events, "
        f"trust map answered for {cell}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
