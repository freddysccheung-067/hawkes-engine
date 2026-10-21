"""Time-rescaling diagnostic: passes under the true model, fails under a wrong one.

The negative control scales the baseline by 1.5, as tests/test_simulators.py
does. A diagnostic that cannot fail would say nothing when it passes.
Deterministic and fast.
"""

import hawkes_engine as he
import numpy as np
from hawkes_engine.diagnostics import ljung_box

mu = np.array([0.6, 0.9])
alpha = np.array([[0.10, 0.35], [0.20, 0.05]])
beta = np.array([[1.30, 1.70], [1.30, 1.70]])
times, types = he.simulate(mu, alpha, beta, T=4000.0, seed=3)


def check(label, m, a, b):
    gaps = he.time_rescale(times, types, m, a, b)
    ks, lb = he.ks_test(gaps).pvalue, ljung_box(gaps).pvalue
    print(f"{label:<28} KS p = {np.round(ks, 4)}  Ljung-Box p = {np.round(lb, 4)}")
    return min(ks.min(), lb.min())


p_true = check("true parameters", mu, alpha, beta)
p_bad = check("baseline scaled by 1.5", 1.5 * mu, alpha, beta)
fit = he.fit(times, types, M=2, T=4000.0, seed=3)
p_fit = check("fitted parameters", fit.mu, fit.alpha, fit.beta)

print(f"\nsmallest p: true {p_true:.4f}, wrong {p_bad:.2e}, fitted {p_fit:.4f}")
assert p_true > 0.05 and p_bad < 0.05
print("diagnostic passes under the truth and rejects the wrong model")
