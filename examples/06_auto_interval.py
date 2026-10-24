"""What `se_method="auto"` decides, and what the result says about it.

Three fits of the same stream: inside the measured box, where the map says the
Hessian interval is too narrow and the bootstrap is used; with the cost ceiling
turned down, where the switch is indicated and refused; and outside the box.

The bootstrap runs in this process (`bootstrap_workers=1`), so no `__main__` guard
is needed and the script finishes in seconds.
"""

import hawkes_engine as he
import numpy as np

MU = np.array([0.6, 0.9])
ALPHA = np.array([[0.10, 0.35], [0.20, 0.05]])
BETA = np.array([[1.30, 1.70], [1.30, 1.70]])
BASE = {"M": 2, "seed": 1, "se_method": "auto", "bootstrap_workers": 1}


def report(label, fit):
    d = fit.auto
    print(f"{label}\n  se_source: {fit.se_source}\n  action: {d.action}")
    print(f"  cell: {d.cell or 'none'}\n  reason: {fit.se_note}")
    print(f"  interval reported: {fit.se is not None}\n")


times, types = he.simulate(MU, ALPHA, BETA, T=2000.0, seed=11)

report("inside the measured box", he.fit(times, types, T=2000.0, **BASE, n_bootstrap=50))
report("over auto_max_seconds", he.fit(times, types, T=2000.0, **BASE, auto_max_seconds=1e-9))

t2, k2 = he.simulate(MU, ALPHA, BETA, T=2.0, seed=5)
report("outside the measured box", he.fit(t2, k2, T=2.0, **BASE))
