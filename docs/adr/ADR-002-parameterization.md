# ADR-002: Parameterization and Index Conventions

**Status**: Accepted  
**Date**: 2026-10-18  
**Deciders**: Principal Software Architect

## Context

The Hawkes process has three parameter families: baseline intensities μᵢ > 0, excitation weights αᵢⱼ ≥ 0, and decay rates βᵢⱼ > 0. Optimizers need unconstrained parameters (log-space: θ = log(x)) to avoid hitting boundaries, but users think in natural units. Similarly, the 2D arrays α and β can index as row=source/col=target or row=target/col=source. Once committed in the type system, these conventions are frozen.

The stability condition ρ(Γ) < 1, where Γᵢⱼ = αᵢⱼ/βᵢⱼ, is the headline number reported to users (§2 of mathematics.md). When β is shared across targets (βᵢⱼ = βⱼ), the branching matrix simplifies and the recursion drops from O(NM²) to O(NM). The parameterization must support both cases without breaking the API.

Log-space parameterization makes gradients messier (chain rule on every term) but eliminates box constraints. Natural-space parameterization is intuitive but requires the optimizer to enforce μ, α, β > 0. Most numerical libraries (scipy.optimize, L-BFGS-B) handle box constraints efficiently, and users expect to see μ = 0.5, not log(μ) = -0.693.

## Decision

- **Parameterization**: Natural space (μ, α, β) with positivity constraints enforced by optimizer box bounds (not log-space)
- **Index convention**: Row = target, column = source. αᵢⱼ is the effect of a type-j event on the intensity of type i. Matrix multiplication Γ = α / β (element-wise) reads as "target i depends on source j."
- **Branching ratio**: ρ = spectral radius of Γ. When β is shared (βᵢⱼ = βⱼ), report ρ(Γ) where Γᵢⱼ = αᵢⱼ/βⱼ.
- **Indexing base**: Zero-indexed everywhere (C++ and Python). Type indices are `0, 1, ..., M-1`.
- **Stability check**: Fit reports ρ(Γ) and warns if ρ ≥ 0.95 (near-critical).

## Alternatives Considered

### Option 1: Log-space parameterization (μ = exp(θμ))
- **Pros**: Unconstrained optimization (no box bounds), gradients never hit boundaries, some papers use it
- **Cons**: User-facing parameters are unintuitive (log(0.5) = -0.693), chain rule adds clutter to gradient code (∂ℓ/∂θ = (∂ℓ/∂μ) · μ), harder to interpret fit results, simulation takes natural params anyway (need to exp() at API boundary)
- **Why rejected**: Modern optimizers (L-BFGS-B) handle box constraints with negligible overhead. Users should see μ = 0.5, not θμ = -0.693. The gradient code is one extra multiplication per parameter; the clarity win is larger.

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
- Optimizer must enforce positivity: lower bound 1e-8 (not zero, to avoid log(0) in likelihood). If the optimizer hits the boundary, the fit may be unreliable — report this.
- Gradient computation has one extra check: if μᵢ or αᵢⱼ is near the boundary (< 1e-6), the gradient is large. Clip gradients to avoid numerical issues.

**Neutral**:
- ρ(Γ) near 1 is not a failure: it means the process is near-critical (self-exciting feedback dominates). The fit is valid, but forecasts become uncertain. The literature argues about whether ρ > 0.9 is realistic or an artifact of overfitting. We report ρ and let the user decide.
- Shared-β case (βᵢⱼ = βⱼ) drops recursion cost from O(NM²) to O(NM). Offer this as a parameterization option (`shared_beta=True`). The math is identical, just faster.

## References

- mathematics.md §2: stability condition and branching matrix
- Ogata (1978): MLE asymptotics for Hawkes processes (uses natural parameterization)
- Laub, Taimre & Pollett (2015): row=target convention in equations (2.1)–(2.3)
- scipy.optimize.minimize documentation: L-BFGS-B bounds parameter
