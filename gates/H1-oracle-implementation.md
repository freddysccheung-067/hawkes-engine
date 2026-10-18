# H1: ORACLE IMPLEMENTATION FROM SPEC

**Time**: 12 hours (Week 3–4)  
**Goal**: Oracle implemented by Claude from frozen spec, verified, locked  
**Models**: Sonnet 5.5 (default), Opus 5.5 (if debugging needed)

---

## PHILOSOPHY: SMOOTH VIBE CODING

This gate is **fully automated**. Claude reads the spec and implements everything:
- No manual math derivation needed from you
- No back-and-forth reviews
- Claude self-verifies with gradient tests
- You just review the final result and approve

**Your role**: Execute prompts, review final oracle for clarity

---

## H1.1: IMPLEMENT ORACLE FROM SPEC (5 hours, Sonnet 5.5)

**Prompt** (copy-paste into Claude Code):

```
ROLE: Numerical programmer implementing reference oracle

TASK: Write `oracle/hawkes_oracle.py` — a pure NumPy O(N²M²) reference implementation of Hawkes process likelihood and gradient, directly from the frozen mathematical specification.

CONTEXT: You are implementing the "oracle" — a simple, obviously correct reference that the fast C++ code will be tested against. Clarity and correctness matter infinitely more than speed.

SPEC TO READ:
1. Open and read: `D:\hawkes-engine-v2\docs\spec\mathematics.md`
2. Sections 3–5 contain the exact formulas

WHAT TO IMPLEMENT:

Create `D:\hawkes-engine-v2\repo-template\oracle\hawkes_oracle.py`:

```python
"""
Reference implementation of Hawkes process likelihood and gradient.
Pure NumPy, O(N²M²) complexity. Used as oracle for C++ tests.

This is the source of truth. The spec (docs/spec/mathematics.md) is frozen.
If this oracle disagrees with the spec, the oracle is wrong.
"""

import numpy as np
from typing import Tuple

def loglik_oracle(
    times: np.ndarray,  # (N,) float64, sorted
    types: np.ndarray,  # (N,) uint8, dimension indices < M
    mu: np.ndarray,     # (M,) float64, baseline intensities > 0
    alpha: np.ndarray,  # (M, M) float64, excitation ≥ 0
    beta: np.ndarray,   # (M, M) float64, decay rates > 0
    T: float            # observation window
) -> float:
    """
    Compute log-likelihood ℓ(θ) = Σ_i [Σ_k log λ_i(t^i_k) - ∫_0^T λ_i(t) dt].
    
    Implements spec §3, equation for ℓ(θ).
    Uses naive O(N²M²) double loops — clarity over speed.
    
    Returns -inf if any intensity λ_i ≤ 0 at an event.
    """
    M = mu.shape[0]
    N = len(times)
    
    # Event term: Σ_i Σ_k log λ_i(t^i_k)
    event_term = 0.0
    for k in range(N):
        t_k = times[k]
        i = types[k]
        
        # Compute λ_i(t_k) = μ_i + Σ_j Σ_{t^j_m < t_k} α_{ij} exp(-β_{ij}(t_k - t^j_m))
        lambda_i = mu[i]
        for j in range(M):
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    lambda_i += alpha[i, j] * np.exp(-beta[i, j] * (t_k - times[m]))
        
        if lambda_i <= 0:
            return -np.inf
        event_term += np.log(lambda_i)
    
    # Compensator term: ∫_0^T λ_i(t) dt
    compensator = 0.0
    for i in range(M):
        # μ_i * T
        compensator += mu[i] * T
        
        # Σ_j Σ_m (α_{ij}/β_{ij}) * (1 - exp(-β_{ij}(T - t^j_m)))
        for j in range(M):
            for m in range(N):
                if types[m] == j:
                    compensator += (alpha[i, j] / beta[i, j]) * (1 - np.exp(-beta[i, j] * (T - times[m])))
    
    return event_term - compensator


def grad_oracle(
    times: np.ndarray,
    types: np.ndarray,
    mu: np.ndarray,
    alpha: np.ndarray,
    beta: np.ndarray,
    T: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute gradient ∇ℓ(θ) = (∂ℓ/∂μ, ∂ℓ/∂α, ∂ℓ/∂β).
    
    Implements spec §5, gradient formulas.
    Uses naive O(N²M²) loops.
    
    Returns:
        grad_mu: (M,) array
        grad_alpha: (M, M) array
        grad_beta: (M, M) array
    """
    M = mu.shape[0]
    N = len(times)
    
    grad_mu = np.zeros(M)
    grad_alpha = np.zeros((M, M))
    grad_beta = np.zeros((M, M))
    
    # Event contributions
    for k in range(N):
        t_k = times[k]
        i = types[k]
        
        # Compute λ_i(t_k) and S_{ij}(t_k)
        lambda_i = mu[i]
        S = np.zeros((M, M))
        
        for j in range(M):
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    exp_term = np.exp(-beta[i, j] * (t_k - times[m]))
                    S[i, j] += exp_term
                    lambda_i += alpha[i, j] * exp_term
        
        if lambda_i <= 0:
            # Gradient undefined at -inf
            return np.full(M, np.nan), np.full((M, M), np.nan), np.full((M, M), np.nan)
        
        # ∂ℓ/∂μ_i: add 1/λ_i for this event
        grad_mu[i] += 1.0 / lambda_i
        
        # ∂ℓ/∂α_{ij}: add S_{ij} / λ_i
        for j in range(M):
            grad_alpha[i, j] += S[i, j] / lambda_i
        
        # ∂ℓ/∂β_{ij}: needs D_{ij} = -Σ_m (t_k - t^j_m) exp(...)
        for j in range(M):
            D_ij = 0.0
            for m in range(N):
                if types[m] == j and times[m] < t_k:
                    D_ij -= (t_k - times[m]) * np.exp(-beta[i, j] * (t_k - times[m]))
            grad_beta[i, j] += alpha[i, j] * D_ij / lambda_i
    
    # Compensator contributions (subtract)
    for i in range(M):
        # ∂/∂μ_i: subtract T
        grad_mu[i] -= T
        
        for j in range(M):
            for m in range(N):
                if types[m] == j:
                    exp_term = np.exp(-beta[i, j] * (T - times[m]))
                    # ∂/∂α_{ij}: subtract (1/β_{ij})(1 - exp(...))
                    grad_alpha[i, j] -= (1 - exp_term) / beta[i, j]
                    
                    # ∂/∂β_{ij}: subtract -(α_{ij}/β_{ij}²)(1 - exp(...)) + (α_{ij}/β_{ij})(T - t_m)exp(...)
                    grad_beta[i, j] -= (-alpha[i, j] / beta[i, j]**2) * (1 - exp_term) + \
                                       (alpha[i, j] / beta[i, j]) * (T - times[m]) * exp_term
    
    return grad_mu, grad_alpha, grad_beta
```

REQUIREMENTS:
- Follow spec exactly (cite equation numbers in comments)
- Use double loops (clarity over speed)
- Handle λ ≤ 0 case (return -inf for loglik, NaN for grad)
- Docstrings explain what formula from spec
- No dependencies except NumPy

EXIT CRITERIA:
- File created at correct path
- Compiles (no syntax errors)
- Docstrings cite spec sections

COMMIT: "H1.1: Oracle implementation from spec — loglik and gradient"

NEXT: H1.2 (write gradient test)
```

---

## H1.2: GRADIENT VERIFICATION TEST (2 hours, Sonnet 5.5)

**Prompt**:

```
ROLE: Test engineer verifying gradient correctness

TASK: Write `oracle/test_oracle_gradient.py` — test that oracle gradient matches central finite differences.

Create `D:\hawkes-engine-v2\repo-template\oracle\test_oracle_gradient.py`:

```python
"""Test oracle gradient vs finite differences."""

import numpy as np
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
        grad_mu_a, grad_alpha_a, grad_beta_a = grad_oracle(times, types, mu, alpha, beta, T)
        
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
        rel_err_mu = np.abs(grad_mu_a - grad_mu_n) / (np.abs(grad_mu_n) + 1e-10)
        if np.max(rel_err_mu) > 1e-6:
            failures.append(f"Test {test_idx}: μ gradient error {np.max(rel_err_mu):.2e}")
        
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
                rel_err = np.abs(grad_alpha_a[i, j] - grad_alpha_n) / (np.abs(grad_alpha_n) + 1e-10)
                
                if rel_err > 1e-6:
                    failures.append(f"Test {test_idx}: α[{i},{j}] gradient error {rel_err:.2e}")
        
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
                rel_err = np.abs(grad_beta_a[i, j] - grad_beta_n) / (np.abs(grad_beta_n) + 1e-10)
                
                if rel_err > 1e-6:
                    failures.append(f"Test {test_idx}: β[{i},{j}] gradient error {rel_err:.2e}")
    
    # Report
    if failures:
        print(f"\n❌ {len(failures)} failures out of {n_tests} tests:")
        for f in failures[:10]:  # Show first 10
            print(f"  {f}")
        raise AssertionError(f"{len(failures)}/{n_tests} gradient tests failed")
    else:
        print(f"✅ All {n_tests} gradient tests passed (rel err < 1e-6)")

if __name__ == "__main__":
    test_gradient_vs_findiff()
```

REQUIREMENTS:
- Test 200 random cases (M ∈ {2,3,4}, N ∈ {50–200})
- Central finite differences with h=1e-5
- Check relative error < 1e-6
- Report first failure with details

EXIT CRITERIA:
- Test runs without import errors
- **Test passes** (all 200 cases < 1e-6 error)

VERIFICATION:
```bash
cd D:\hawkes-engine-v2\repo-template
python oracle/test_oracle_gradient.py
```

**Expected output**: `✅ All 200 gradient tests passed`

IF TEST FAILS:
- Debug oracle implementation (likely sign error or missing term)
- Re-read spec, check formulas
- Fix and re-run test

COMMIT: "H1.2: Oracle gradient test passes 200 cases"

NEXT: H1.3 (lock oracle)
```

---

## H1.3: LOCK ORACLE (2 hours, Sonnet 5.5)

**Prompt**:

```
ROLE: Repository maintainer enforcing verification rule

TASK: Lock oracle implementation so it cannot be accidentally edited.

ACTIONS:

1. **Create git tag** marking oracle as frozen:
```bash
cd D:\hawkes-engine  # actual repo
git add oracle/
git commit -m "H1: Oracle implementation locked

- hawkes_oracle.py: reference likelihood and gradient (O(N²M²) NumPy)
- test_oracle_gradient.py: verified against finite differences (200 cases pass)
- Source of truth: docs/spec/mathematics.md (frozen at H0)

Oracle is now read-only. C++ tests will compare against this."

git tag -a H1-oracle-locked -m "Oracle frozen per verification rule"
```

2. **Create pre-commit hook** to reject oracle edits:

Create `.pre-commit-config.yaml` in repo root:
```yaml
repos:
  - repo: local
    hooks:
      - id: protect-oracle
        name: Protect oracle (verification rule)
        entry: 'oracle/*.py is read-only. See docs/verification-rule.md'
        language: fail
        files: ^oracle/.*\.py$
```

Install hook:
```bash
pip install pre-commit
pre-commit install
```

3. **Test hook**:
```bash
echo "# test" >> oracle/hawkes_oracle.py
git add oracle/hawkes_oracle.py
git commit -m "Test hook"
# Should FAIL with "oracle/*.py is read-only"

# Undo test
git checkout oracle/hawkes_oracle.py
```

4. **Document rule** in `docs/verification-rule.md`:
```markdown
# Verification Rule

**Oracle is frozen**: The NumPy reference implementation in `oracle/hawkes_oracle.py` is the source of truth for correctness.

- Pre-commit hook rejects edits to `oracle/*.py`
- C++ code tested against oracle (<1e-12 relative error)
- Two simulators (thinning, cluster) cross-check each other
- Tests are never weakened to pass

**Why**: Two independent implementations prove each other correct.

**Locked**: H1 gate, [date], git tag `H1-oracle-locked`
```

EXIT CRITERIA:
- Tag `H1-oracle-locked` exists
- Pre-commit hook rejects oracle edits (verified by test)
- `docs/verification-rule.md` explains rule

COMMIT: "H1.3: Oracle locked with pre-commit hook"

DONE: H1 complete!
```

---

## H1 EXIT TEST

After completing all 3 sub-tasks, verify:

```bash
cd D:\hawkes-engine
python oracle/test_oracle_gradient.py
# Expected: ✅ All 200 gradient tests passed

git tag -l H1-*
# Expected: H1-oracle-locked

echo "# test edit" >> oracle/hawkes_oracle.py
git add oracle/hawkes_oracle.py
git commit -m "Test"
# Expected: FAIL (hook rejects)
git checkout oracle/hawkes_oracle.py
```

If all pass, H1 is complete. Update STATE.md:

```markdown
### H1 (Oracle Implementation) — ✅ COMPLETE
- [x] H1.1: Oracle implemented from spec
- [x] H1.2: Gradient test passes (200 cases)
- [x] H1.3: Oracle locked with hook

**Completed**: [date]
**Time**: [actual hours, target 12h]
**Next**: H2 (C++ Likelihood)
```

---

## NEXT GATE

**H2: C++ Likelihood** (22 hours, C++ implementation tested against oracle)

See `gates/H2-cpp-likelihood.md` for prompts.
