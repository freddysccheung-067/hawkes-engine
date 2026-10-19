// SPDX-License-Identifier: MIT
//
// The exponential kernel and its integrated form. mathematics.md sections 1
// and 3.

#pragma once

#include <cmath>

#include "hawkes/types.hpp"

namespace hawkes {

// exp(-beta * dt), the factor by which one component of S decays over dt.
//
// dt >= 0 is a precondition. Very large beta*dt underflows to 0, which is the
// correct answer: the tail contributes less than the smallest subnormal. No
// special case is needed, and the caller must not use the result as a divisor.
[[nodiscard]] inline Real decay_factor(Real beta, Real dt) noexcept {
    return std::exp(-beta * dt);
}

// 1 - exp(-x) for x >= 0, evaluated without cancellation.
//
// Written as -expm1(-x): for small x the direct form subtracts two numbers that
// are nearly equal and loses every significant digit, while expm1 is accurate to
// a few ulp across the whole positive axis. This term is the whole of the
// compensator contribution of one event (mathematics.md section 3), and it is
// the difference that the H1 review of the reference had to leave alone; do not
// "simplify" it back to 1 - exp(-x).
[[nodiscard]] inline Real one_minus_decay(Real x) noexcept {
    return -std::expm1(-x);
}

// exp(-x) - 1, for x >= 0. The compensator accumulates 1 - exp(-x) and
// u*exp(-x) from the same draw in the pair loop; one call to expm1 yields both,
// with exp(-x) recovered as em1 + 1. That sum is accurate wherever it matters:
// when x is small, exp(-x) is close to 1 and its absolute error is at the
// epsilon level of 1, which is all the absolute scale it has.
[[nodiscard]] inline Real decay_minus_one(Real x) noexcept {
    return std::expm1(-x);
}

}  // namespace hawkes
