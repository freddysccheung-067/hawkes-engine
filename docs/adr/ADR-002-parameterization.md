# ADR-002: Parameterization and Index Conventions

**Status**: Accepted (amended 2026-10-19)
**Date**: 2026-10-18
**Deciders**: freddysccheung-067

## Context

The Hawkes process has three parameter families: baseline intensities μᵢ > 0, excitation weights αᵢⱼ ≥ 0, and decay rates βᵢⱼ > 0. Optimizers need unconstrained parameters (log-space: θ = log(x)) to avoid hitting boundaries, but users think in natural units. Similarly, the 2D arrays α and β can index as row=source/col=target or row=target/col=source. Once committed in the type system, these conventions are frozen.

The stability condition ρ(Γ) < 1, where Γᵢⱼ = αᵢⱼ/βᵢⱼ, is the headline number reported to users (§2 of mathematics.md). When β is shared across targets (βᵢⱼ = βⱼ), the branching matrix simplifies and the recursion drops from O(NM²) to O(NM). The parameterization must support both cases without breaking the API.

Log-space parameterization makes gradients messier (chain rule on every term) but eliminates box constraints. Natural-space parameterization is intuitive but requires the optimizer to enforce μ, α, β > 0. Most numerical libraries (scipy.optimize, L-BFGS-B) handle box constraints efficiently, and users expect to see μ = 0.5, not log(μ) = -0.693.

## Decision

- **Parameterization**: Two layers, deliberately distinct.
  - **Public API and all stored results**: natural space (μ, α, β). This is what
    the user writes, reads and plots.
  - **Optimizer working coordinates**: log space, μ = eᵃ, α = eᵇ, β = eᶜ, as
    specified in mathematics.md §5. The chain rule is applied once, in the
    objective wrapper: ∂ℓ/∂a = (∂ℓ/∂μ)·μ, and likewise for b and c.
- **Why both**: the spec's log-space instruction is about what the optimizer
  sees, and it is right about that. Positivity is structural rather than
  enforced, so no candidate is ever rejected for being infeasible, and β —
  which spans orders of magnitude between a fast and a slow market — gets a
  well-scaled step size. The natural-space requirement is about what the user
  sees. Exposing log coordinates would leak an implementation detail into every
  result object and every plot.
- **What this replaced**: the original version of this ADR chose natural space
  throughout, arguing that L-BFGS-B handles box bounds cheaply enough. That
  argument is sound for μ but weaker for β, and it contradicted the frozen
  spec. Since the spec is upstream of both the ADR and the code, the ADR moved.
- **Index convention**: Row = target, column = source. αᵢⱼ is the effect of a type-j event on the intensity of type i. Matrix multiplication Γ = α / β (element-wise) reads as "target i depends on source j."
- **Branching ratio**: ρ = spectral radius of Γ. When β is shared (βᵢⱼ = βⱼ), report ρ(Γ) where Γᵢⱼ = αᵢⱼ/βⱼ.
- **Indexing base**: Zero-indexed everywhere (C++ and Python). Type indices are `0, 1, ..., M-1`.
- **Stability check**: Fit reports ρ(Γ) and warns if ρ ≥ 0.95 (near-critical).

## Alternatives Considered

### Option 1: Log-space throughout, including the public API
- **Pros**: Unconstrained optimization (no box bounds), gradients never hit boundaries
- **Cons**: User-facing parameters are unintuitive (log(0.5) = -0.693), harder to interpret fit results, every result object and plot carries a representation the user did not ask for, and simulation takes natural parameters anyway (so the API would need exp() at the boundary regardless)
- **Why rejected**: This is the option the original ADR rejected, and the rejection still holds — but only for the *public* layer. Log space is adopted as the optimizer's internal coordinates; see Decision.

### Option 2: Row = source, column = target (opposite convention)
- **Pros**: Some papers use this (especially older econophysics literature)
- **Cons**: Less intuitive to read: "λᵢ depends on Σⱼ αᵢⱼ" reads as "target i sums over sources j," which means row = target. Switching conventions later breaks all user code that indexes α.
- **Why rejected**: The intensity equation λᵢ(t) = μᵢ + Σⱼ Σₘ αᵢⱼ exp(-βᵢⱼ(t - tⱼₘ)) groups by target i first. Row = target is the natural reading. Fix it now and never touch it again.

### Option 3: One-indexed arrays (Fortran style)
- **Pros**: Matches some textbooks (especially older numerical analysis books)
- **Cons**: Python and C++ are zero-indexed. One-indexing adds off-by-one bugs at every API boundary. NumPy, Eigen, and std::vector are all zero-indexed.
- **Why rejected**: Zero-indexing is non-negotiable. Every modern language uses it except MATLAB and Fortran.

## Consequences

**Positive**:
- Users see natural parameters directly: μ = [0.5, 0.3], α = [[0, 0.2], [0.3, 0]], β = [[1, 1], [1, 1]] is readable JSON.
- Index convention matches math notation: λᵢ depends on sources j, so row i is target, column j is source.
- Stability check is free: ρ(Γ) is one eigenvalue computation. Report it in every fit summary.
- Box constraints handled by optimizer: L-BFGS-B in scipy.optimize.minimize supports bounds natively. Pass `bounds=[(1e-8, None), ...]` for positivity.

**Negative**:
- The optimizer never sees a bound, so it cannot report "hit the positivity boundary" as a diagnostic. Under log-space a parameter can drift towards zero indefinitely. Mitigation: report the natural-space estimate with its standard error, and flag when an estimate is small on the scale of its own standard error rather than when it touches a fixed floor. A fixed floor was the old design and it was worse — it turns a soft diagnostic into a hard wall that biases the estimate.
- Two representations exist, so the conversion has to be tested. The natural↔log round trip is exercised in H3 alongside the estimator.
- Clipping gradients is no longer needed: under log space ∂ℓ/∂a cannot blow up as μ → 0 the way ∂ℓ/∂μ does, because the factor μ multiplies it away. This was listed as a cost in the original ADR and it is in fact a benefit of the change.

**Neutral**:
- ρ(Γ) near 1 is not a failure: it means the process is near-critical (self-exciting feedback dominates). The fit is valid, but forecasts become uncertain. The literature argues about whether ρ > 0.9 is realistic or an artifact of overfitting. We report ρ and let the user decide.
- Shared-β case (βᵢⱼ = βⱼ) drops recursion cost from O(NM²) to O(NM). Offer this as a parameterization option (`shared_beta=True`). The math is identical, just faster.

## References

- mathematics.md §2: stability condition and branching matrix
- Ogata (1978): MLE asymptotics for Hawkes processes (uses natural parameterization)
- Laub, Taimre & Pollett (2015): row=target convention in equations (2.1)–(2.3)
- scipy.optimize.minimize documentation: L-BFGS-B bounds parameter
