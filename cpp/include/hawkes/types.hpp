// SPDX-License-Identifier: MIT
//
// Core scalar and view types shared by the likelihood, the estimator and the
// simulators.
//
// Index conventions are fixed by ADR-002 and must not change: alpha and beta are
// row-major M*M blocks with row = target, column = source. Entry (i, j) is the
// effect of a type-j event on the intensity of type i. mathematics.md section 2
// fixes the same convention for the branching matrix.

#pragma once

#include <cstdint>

namespace hawkes {

// The likelihood is advertised at 1e-12 relative agreement with the reference
// implementation, so this must stay binary64. ADR-002 restricts the public API
// to natural-space parameters.
using Real = double;

// Event counts reach 1e6 in the benchmarks and M*M stays small, so 32 bits is
// ample and keeps the hot indices cheap.
using Index = std::int32_t;

// Non-owning, read-only view of the event stream (ADR-003: struct of arrays).
//
// Invariants, checked once by validate_events() and not re-checked here:
//   - times[0..n) is non-decreasing and every entry is finite;
//   - types[k] < M for every k;
//   - n >= 0, and the pointers are non-null whenever n > 0.
//
// The caller retains ownership and must keep the buffers alive for the duration
// of the call. Views are trivially copyable and safe to read from several
// threads; nothing in this library mutates them.
struct EventView {
    const Real* times;
    const std::uint8_t* types;
    Index n;
};

// Non-owning, read-only view of the parameters.
//
// Invariants, checked once by validate_params():
//   - M >= 1 and M <= 256 (the event type array is uint8, ADR-003);
//   - mu[0..M) is finite and non-negative;
//   - alpha[0..M*M) is finite and non-negative;
//   - beta[0..M*M) is finite and strictly positive for the pair-decay
//     parameterization, or beta[0..M) for the shared-decay one, where
//     beta_ij = beta_j depends on the source only (mathematics.md section 4).
//
// mu may be zero. mathematics.md section 4 prefers a strictly positive bound,
// but the core has to be able to report the degenerate intensity that the
// reference implementation also reports, and a bound enforced here would make
// that path unreachable. The optimizer imposes the strict bound at H3.
struct ParamView {
    Index M;
    const Real* mu;
    const Real* alpha;
    const Real* beta;
};

}  // namespace hawkes
