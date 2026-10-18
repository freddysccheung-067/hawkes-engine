"""Test oracle gradient vs finite differences."""

import numpy as np
import sys
from pathlib import Path

# Add oracle directory to path so we can import hawkes_oracle
sys.path.insert(0, str(Path(__file__).parent))

from hawkes_oracle import loglik_oracle, grad_oracle


def test_gradient_vs_findiff():
    """
    Test analytic gradient vs central finite differences.

    For 200 random parameter sets:
    - Compute analytic grad = grad_oracle(...)
    - Compute numeric grad via (ℓ(θ+h) - ℓ(θ-h)) / 2h
    - Check relative error < 1e-6
    """
    np.random.seed(42)
    h = 1e-5  # Finite diff step

    n_tests = 200
    failures = []

    for test_idx in range(n_tests):
        # Generate random test case
        M = np.random.choice([2, 3, 4])
        N = np.random.randint(50, 200)

        mu = np.random.exponential(1.0, M)
        alpha = np.random.exponential(0.5, (M, M))
        beta = np.random.exponential(2.0, (M, M))

        times = np.sort(np.random.uniform(0, 100, N))
        types = np.random.randint(0, M, N, dtype=np.uint8)
        T = times[-1] + np.random.uniform(1, 10)

        # Compute analytic gradient
        grad_mu_a, grad_alpha_a, grad_beta_a = grad_oracle(
            times, types, mu, alpha, beta, T
        )

        # Check not NaN
        if np.any(np.isnan(grad_mu_a)):
            failures.append(f"Test {test_idx}: gradient is NaN (likely λ≤0)")
            continue

        # Compute numeric gradient for μ
        grad_mu_n = np.zeros_like(mu)
        for i in range(M):
            mu_plus = mu.copy()
            mu_plus[i] += h
            ell_plus = loglik_oracle(times, types, mu_plus, alpha, beta, T)

            mu_minus = mu.copy()
            mu_minus[i] -= h
            ell_minus = loglik_oracle(times, types, mu_minus, alpha, beta, T)

            grad_mu_n[i] = (ell_plus - ell_minus) / (2 * h)

        # Check μ gradient
        abs_err_mu = np.abs(grad_mu_a - grad_mu_n)
        rel_err_mu = abs_err_mu / (np.abs(grad_mu_n) + 1e-10)
        # Fail only if both relative error > 1e-5 AND absolute error > 1e-6.
        # The absolute backstop handles near-zero gradients where relative error
        # blows up from catastrophic cancellation in the finite difference.
        if np.max(rel_err_mu) > 1e-5 and np.max(abs_err_mu) > 1e-6:
            failures.append(
                f"Test {test_idx}: mu gradient error {np.max(rel_err_mu):.2e} "
                f"(abs err {np.max(abs_err_mu):.2e})"
            )

        # Compute numeric gradient for α (spot check, not all M²)
        for i in range(min(2, M)):
            for j in range(min(2, M)):
                alpha_plus = alpha.copy()
                alpha_plus[i, j] += h
                ell_plus = loglik_oracle(times, types, mu, alpha_plus, beta, T)

                alpha_minus = alpha.copy()
                alpha_minus[i, j] -= h
                ell_minus = loglik_oracle(times, types, mu, alpha_minus, beta, T)

                grad_alpha_n = (ell_plus - ell_minus) / (2 * h)
                abs_err = np.abs(grad_alpha_a[i, j] - grad_alpha_n)
                rel_err = abs_err / (np.abs(grad_alpha_n) + 1e-10)

                if rel_err > 1e-5 and abs_err > 1e-6:
                    failures.append(
                        f"Test {test_idx}: alpha[{i},{j}] gradient error {rel_err:.2e} "
                        f"(abs err {abs_err:.2e})"
                    )

        # Similar for β (spot check)
        for i in range(min(2, M)):
            for j in range(min(2, M)):
                beta_plus = beta.copy()
                beta_plus[i, j] += h
                ell_plus = loglik_oracle(times, types, mu, alpha, beta_plus, T)

                beta_minus = beta.copy()
                beta_minus[i, j] -= h
                ell_minus = loglik_oracle(times, types, mu, alpha, beta_minus, T)

                grad_beta_n = (ell_plus - ell_minus) / (2 * h)
                abs_err = np.abs(grad_beta_a[i, j] - grad_beta_n)
                rel_err = abs_err / (np.abs(grad_beta_n) + 1e-10)

                if rel_err > 1e-5 and abs_err > 1e-6:
                    failures.append(
                        f"Test {test_idx}: beta[{i},{j}] gradient error {rel_err:.2e} "
                        f"(abs err {abs_err:.2e})"
                    )

    # Report
    if failures:
        print(f"\n[FAIL] {len(failures)} failures out of {n_tests} tests:")
        for f in failures[:10]:  # Show first 10
            print(f"  {f}")
        raise AssertionError(f"{len(failures)}/{n_tests} gradient tests failed")
    else:
        print(
            f"[PASS] All {n_tests} gradient tests passed "
            f"(rel err < 1e-5, with abs err < 1e-6 backstop)"
        )


if __name__ == "__main__":
    test_gradient_vs_findiff()
