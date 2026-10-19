# Verification rule

**The reference implementation is frozen.** `oracle/hawkes_oracle.py` is the
source of truth for correctness. It was written directly from
`docs/spec/mathematics.md` and is never edited to make a test pass.

## The rule

- The pre-commit hook rejects every edit to `oracle/*.py`.
- Every fast implementation (C++, from H2) is tested against the reference.
- Two independent simulators (thinning, cluster) cross-check each other.
- **Tests are never weakened to pass.** If the reference and the C++ code
  disagree, one of them is wrong; the disagreement is diagnosed, not smoothed
  over.

## Why freeze it

Two independent implementations prove each other correct. The moment the
reference can be edited to match the thing it is checking, it stops being a
reference and becomes a second copy of the same bug. The cost of freezing is
friction; the cost of an unfrozen reference is that every later gate's evidence
evaporates.

## How the gradient is established

`oracle/test_oracle_gradient.py` checks the analytic gradient against the
likelihood by two methods that share no code path.

**Complex-step differentiation** is the primary check. It evaluates the
likelihood at `x + ih`, where `i² = -1` and `h = 1e-20`, and reads the
derivative off the imaginary part. There is no subtraction, so there is no
cancellation: the method is exact to machine precision and can tell a correct
gradient from one that is wrong at the tenth digit. It runs over **every**
parameter entry — M ∈ {1, 2, 3}, N ∈ {10, 30, 60}, eight random parameter sets
per combination — against a tolerance of `rtol 1e-9, atol 1e-10`. The tightest
attained relative error across the grid is around 1e-13, several orders of
magnitude inside the bound.

**Central finite differences** are the independent second opinion. They use no
complex arithmetic, so an error in the complex-step harness cannot hide behind
agreement between two copies of the same mistake. The step is `h = 1e-6`, and
failing requires **both** a relative error above 1e-5 *and* an absolute error
above 1e-6.

Why a pair of bounds rather than one: central differences carry O(h²)
truncation error, which lands around 1e-8 relative on large gradients, and the
relative error of a difference of nearly equal numbers blows up when the true
derivative is near zero even though the absolute error stays at 1e-9. Requiring
both to be large before failing separates finite-difference noise from a
defect. A sign error or a missing term produces errors of order 1e-2, which no
bound on this list would hide.

The earlier version of this suite used a single relative bound of 1e-5 with an
absolute backstop applied to the maximum over the whole array, and spot-checked
only four α and four β entries per case. Both are fixed: on the first point the
bound is now per entry, and on the second the coverage is every entry.

## Edge cases with closed-form answers

The gradient check would pass on a likelihood that is wrong in the same way
everywhere, so the suite also pins the likelihood against answers worked out by
hand:

- **N = 0** — the likelihood is exactly −ΣμᵢT; all gradients except ∂/∂μ are zero.
- **N = 1** — baseline intensity at the event, closed-form compensator.
- **N = 1, M = 1** — same, with the β derivative carrying the
  `α/β²` and `α/β` terms expanded explicitly.
- **Simultaneous events** — two events at the same timestamp must not excite
  each other, because the spec sums over `t^j_m < t` and not `≤`. This is the
  defect most likely to survive a gradient check, since it is a difference of
  measure-zero input that random continuous timestamps never produce.
- **M = 1, many events** — checked against a separately written one-line
  recursion, so the O(N²M²) oracle is compared to an O(N) implementation of the
  same mathematics.
- **λᵢ ≤ 0** — must return −inf and a NaN gradient, never a finite number.
  Clipping would turn a diagnosable failure into a plausible-looking result.

## Changing the reference

It is possible, but it is recorded. If the reference is genuinely wrong:

1. Write down the flaw and the correct formula, citing the spec statement it
   contradicts.
2. If the spec itself is wrong, amend the spec first and record why — the spec
   is upstream of the reference, not downstream.
3. Bypass the hook deliberately (`git commit --no-verify`) with the reasoning in
   the message, and re-tag.

An unfrozen reference with no record of why it moved is the failure mode this
rule exists to prevent.

## Revision history

- **H1-oracle-locked** — 2026-10-18. The reference implementation and the first
  gradient test.
- **H1-oracle-locked-v2** — 2026-10-19. The reference implementation is
  **unchanged**; it was re-verified against complex-step over every parameter
  entry and passed at 1e-9. What moved is the test suite, which gained full
  entry coverage, seven closed-form edge cases, and per-entry rather than
  array-wide tolerance. The standalone `tests/verify_complex_step.py` was folded
  into the suite, so the complex-step check now runs under pytest instead of
  being a script someone has to remember to invoke.
- **H2** — 2026-10-19. The reference is still **unchanged**. It now checks a
  second, independent implementation: `tests/test_oracle_agreement.py` compares
  the C++ core against it over M in {1,2,3,4,6} and N up to 1000, entry by
  entry in all three gradient blocks. Measured worst case 7.5e-14 on the value
  and 3.6e-12 per gradient entry. The core's gradient is additionally checked
  against complex-step differentiation of the reference likelihood, using the
  reference suite's own helper, so the check shares no code path with either
  analytic implementation.

## Two implementations proving each other

The point of freezing the reference is that a disagreement is information. H2
produced several, and every one was resolved by finding the defect in the new
code rather than by adjusting the reference or the tolerance:

- The first event loop let two events at the same timestamp excite each other.
  The reference is right about `t^m_j < t`; the loop was wrong.
- A gradient block was returned with the wrong shape. The reference's shape is
  correct; the binding was wrong.

An implementation that has never disagreed with the reference has not been
tested yet, in the sense that matters.
