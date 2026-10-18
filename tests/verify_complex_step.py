"""
Independent high-precision verification of the oracle gradient.

Finite differences at h=1e-5 cannot distinguish a correct gradient from one
with ~1e-6 relative error. Complex-step differentiation has no subtractive
cancellation and reaches machine precision, so it settles the question.

Run once at H1 to confirm the oracle; not part of the locked test suite.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "oracle"))
from hawkes_oracle import loglik_oracle, grad_oracle


def complex_step_check(seed=7, n_cases=10, h=1e-20):
    rng = np.random.default_rng(seed)
    worst = 0.0
    for case in range(n_cases):
        M = int(rng.choice([2, 3]))
        N = int(rng.integers(20, 60))

        mu = rng.exponential(1.0, M)
        alpha = rng.exponential(0.5, (M, M))
        beta = rng.exponential(2.0, (M, M))
        times = np.sort(rng.uniform(0, 50, N))
        types = rng.integers(0, M, N).astype(np.uint8)
        T = times[-1] + rng.uniform(1, 5)

        g_mu, g_alpha, g_beta = grad_oracle(times, types, mu, alpha, beta, T)

        def cs_grad(param, idx=None, kind="mu"):
            def f(z):
                if kind == "mu":
                    m = mu.astype(complex).copy(); m[idx] = z
                    return loglik_oracle(times, types, m, alpha.astype(complex), beta.astype(complex), T)
                if kind == "alpha":
                    a = alpha.astype(complex).copy(); a[idx] = z
                    return loglik_oracle(times, types, mu.astype(complex), a, beta.astype(complex), T)
                b = beta.astype(complex).copy(); b[idx] = z
                return loglik_oracle(times, types, mu.astype(complex), alpha.astype(complex), b, T)

            base = param[idx] if idx is not None else None
            val = f(complex(base, h))
            return val.imag / h

        errs = []
        for i in range(M):
            errs.append(abs(cs_grad(mu, i, "mu") - g_mu[i]))
        for i in range(M):
            for j in range(M):
                errs.append(abs(cs_grad(alpha, (i, j), "alpha") - g_alpha[i, j]))
                errs.append(abs(cs_grad(beta, (i, j), "beta") - g_beta[i, j]))

        errs = np.array(errs)
        rel = errs / (np.abs(np.concatenate([
            g_mu, g_alpha.ravel(), g_beta.ravel()
        ])) + 1.0)
        worst = max(worst, rel.max())

    print(f"Complex-step check over {n_cases} cases: worst rel err = {worst:.3e}")
    assert worst < 1e-10, f"Complex-step disagrees: {worst:.3e}"
    print("[PASS] Oracle gradient confirmed to machine precision")


if __name__ == "__main__":
    complex_step_check()
