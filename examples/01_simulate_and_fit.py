"""Simulate from known parameters, fit, and compare the estimate with the truth.

Runs in about a second. Deterministic: every random draw is seeded.

The second half refits a short window of the same process. At T = 2000 the fit
below returns beta[1, 1] of about 452 where the truth is 1.7, converged, and labelled
"reliable". That is the small-sample heavy tail documented in docs/limits.md.
"""

import hawkes_engine as he
import numpy as np

mu = np.array([0.6, 0.9])
alpha = np.array([[0.10, 0.35], [0.20, 0.05]])  # row = target, column = source
beta = np.array([[1.30, 1.70], [1.30, 1.70]])
print(f"true branching ratio rho = {he.spectral_radius(mu, alpha, beta):.4f}")

for T in (20000.0, 2000.0):
    times, types = he.simulate(mu, alpha, beta, T=T, seed=1)
    fit = he.fit(times, types, M=2, T=T, seed=1)
    print(f"\nT = {T:.0f}, {len(times)} events")
    print(fit)
    print("mu_hat   ", np.round(fit.mu, 3), " se", np.round(fit.se["mu"], 3))
    print("alpha_hat", np.round(fit.alpha, 3).tolist(), " truth", alpha.tolist())
    print("beta_hat ", np.round(fit.beta, 2).tolist(), " truth", beta.tolist())
    print(f"rho_hat = {fit.rho:.4f}, 95% interval {np.round(fit.rho_ci, 4).tolist()}")
    print(f"converged={fit.converged} bound_hit={fit.bound_hit} reliable={fit.reliable!r}")
