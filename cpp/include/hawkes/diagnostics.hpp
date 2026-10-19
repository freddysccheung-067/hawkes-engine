// SPDX-License-Identifier: MIT
//
// Stability quantities and the time-rescaling diagnostic. mathematics.md
// sections 2 and 8.

#pragma once

#include <vector>

#include "hawkes/types.hpp"

namespace hawkes {

// rho(Gamma) for Gamma_ij = alpha_ij / beta_ij.
//
// Gamma is entrywise non-negative, so rho is its Perron root and power
// iteration with Collatz-Wielandt bounds applies. Iterating on Gamma + I rather
// than Gamma matters: a periodic Gamma (a permutation, say) has several
// eigenvalues of modulus rho and plain iteration oscillates forever, while the
// shift makes the diagonal positive and shifts rho by exactly 1. For positive x,
// min_i (Ax)_i / x_i <= rho(A) <= max_i (Ax)_i / x_i, so the loop stops on a
// certified bracket rather than on a guess. The starting vector is positive and
// A has a positive diagonal, so x stays positive. An eigenvalue routine would
// need a linear-algebra dependency for a quantity this cheap.
//
// Returns the bracket midpoint; the bracket width is below 1e-13 unless the
// iteration cap is hit on a defective Gamma, where convergence is only O(1/k)
// and the midpoint is still within the bracket.
[[nodiscard]] Real spectral_radius(const ParamView& params);

// (I - Gamma)^{-1} mu, the mean intensity of the stationary process. Requires
// rho(Gamma) < 1; throws std::domain_error otherwise.
[[nodiscard]] std::vector<Real> stationary_mean(const ParamView& params);

// Rescaled gaps tau^i_k = integral of lambda_i between consecutive type-i events
// (mathematics.md section 8), one vector per type. The first gap runs from time
// 0; the stretch after the last event of a type is not a gap and is omitted.
//
// Uses the one-pass recursion of the likelihood: between events S_ij decays, so
// the integral of S_ij over a step of length dt is S_ij(prev+) (1 - e^{-beta dt})
// / beta, with the difference written -expm1(-beta dt) via one_minus_decay. The
// running integral is kept per type since its last event and reset there, never
// as a global compensator that is later differenced: that subtraction loses
// digits once T is large against a gap.
//
// Events must satisfy validate_events. Events at exactly equal times are
// treated as sequential in the given order.
[[nodiscard]] std::vector<std::vector<Real>> time_rescale(const EventView& events,
                                                          const ParamView& params);

}  // namespace hawkes
