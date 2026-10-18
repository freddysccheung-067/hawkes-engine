# Verification Rule

**The oracle is frozen.** `oracle/hawkes_oracle.py` is the source of truth for correctness. It was written directly from `docs/spec/mathematics.md` and is never edited to make a test pass.

## The rule

- The pre-commit hook rejects every edit to `oracle/*.py`.
- Every fast implementation (C++ at H2–H5) is tested against the oracle.
- Two independent simulators (Ogata thinning, cluster branching) cross-check each other.
- **Tests are never weakened to pass.** If the oracle and the C++ code disagree, one of them is wrong and the disagreement is diagnosed, not smoothed over.

## Why freeze it

Two independent implementations prove each other correct. The moment the reference can be edited to match the thing it is checking, it stops being a reference — it becomes a second copy of the same bug wearing a different hat. The cost of freezing is a few minutes of friction; the cost of an unfrozen oracle is that every later gate's evidence evaporates.

## How correctness was established

`oracle/test_oracle_gradient.py` compares the analytic gradient against central finite differences on 200 random cases (M ∈ {2,3,4}, N ∈ 50–200):

```
[PASS] All 200 gradient tests passed (rel err < 1e-5, with abs err < 1e-6 backstop)
```

The tolerance is a pair, not a single number, for a reason. Central differences at h=1e-5 carry O(h²) truncation error, which lands at 1–3e-6 relative on large gradients; and when a true derivative is near zero, the *relative* error of a finite difference blows up from cancellation while the *absolute* error stays at 1e-8. Requiring both to be large before failing separates finite-difference noise from a real defect. A genuine sign error or missing term produces errors of order 1e-2 or worse, which no tolerance on this list would hide.

Because a loosened tolerance is exactly the kind of thing that can hide a real bug, the oracle was also checked independently by **complex-step differentiation** (`tests/verify_complex_step.py`). Complex-step has no subtractive cancellation and reaches machine precision, so it is not amenable to the same noise floor. Result:

```
Complex-step check over 10 cases: worst rel err = 1.052e-12
[PASS] Oracle gradient confirmed to machine precision
```

This is what licenses the finite-difference tolerance: the gradient was confirmed to 1e-12 by a method that cannot be fooled, and the 1e-6-looking failures in the FD test were noise, as diagnosed. Both methods live in the repo so the next reader can re-run the argument rather than take it on trust.

## Changing the oracle

It cannot be done casually, and that is the point. If the oracle is genuinely wrong:

1. Write down the flaw and the correct formula, citing the spec statement it contradicts.
2. If the spec itself is wrong, amend the spec first and record why — the spec is upstream of the oracle, not downstream.
3. Bypass the hook deliberately (`git commit --no-verify`) with the reasoning in the message, and re-tag.

An unfrozen oracle with no record of why it moved is the failure mode this rule exists to prevent.

## Locked

H1 gate, 2026-10-18, git tag `H1-oracle-locked`.
