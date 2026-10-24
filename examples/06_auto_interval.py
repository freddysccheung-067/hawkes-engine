"""What `se_method="auto"` decides, and what the result says about it.

Three fits of simulated streams, each showing the decision record: inside the
measured box at 2000 events, where the map says the Hessian interval is too narrow
and the bootstrap is used; outside the box, where the map has nothing to say; and a
case where the bootstrap is indicated but refused by `auto_max_seconds`.

The bootstrap runs in this process (`bootstrap_workers=1`) so the script needs no
`if __name__ == "__main__":` guard and finishes in seconds. In a program that fits
once, leave `bootstrap_workers` at its default and use the guard.
"""

import hawkes_engine as he
import numpy as np

MU = np.array([0.6, 0.9])
ALPHA = np.array([[0.10, 0.35], [0.20, 0.05]])
BETA = np.array([[1.30, 1.70], [1.30, 1.70]])


def report(label, fit):
    decision = fit.auto
    distance = "n/a" if decision.distance is None else f"{decision.distance:.3f}"
    cell = decision.cell or "none"
    print(f"{label}")
    print(f"  se_source: {fit.se_source}")
    print(f"  action: {decision.action}")
    print(f"  map cell: {cell}, distance {distance} grid steps")
    print(f"  threshold on q: {decision.threshold:g} Monte Carlo standard errors")
    print(f"  reason: {fit.se_note}")
    print(f"  interval reported: {fit.se is not None}\n")


times, types = he.simulate(MU, ALPHA, BETA, T=2000.0, seed=11)

# Inside the box at 2000 events: every block's q is measurably below 1, so the
# bootstrap replaces the Hessian interval.
mapped = he.fit(
    times,
    types,
    M=2,
    T=2000.0,
    seed=1,
    se_method="auto",
    n_bootstrap=50,
    bootstrap_workers=1,
)
report("inside the measured box, narrow interval measured", mapped)

# The same data with the cost ceiling turned down: the switch is indicated and
# refused, and the result says so rather than spending the time.
refused = he.fit(
    times,
    types,
    M=2,
    T=2000.0,
    seed=1,
    se_method="auto",
    auto_max_seconds=1e-9,
    bootstrap_workers=1,
)
report("bootstrap indicated but over auto_max_seconds", refused)

# A window holding too few events is outside the measured box, so the map does
# not answer from it: the Hessian interval is kept and labelled uncalibrated.
short = he.simulate(MU, ALPHA, BETA, T=2.0, seed=5)
few = he.fit(short[0], short[1], M=2, T=2.0, seed=1, se_method="auto", bootstrap_workers=1)
report("outside the measured box", few)

print("the result says which method produced the interval: True")
