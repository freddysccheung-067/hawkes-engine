// SPDX-License-Identifier: MIT
//
// Log-likelihood and its gradient for the exponential-kernel Hawkes process.
// mathematics.md sections 3, 4 and 5.
//
// Event ordering. The intensity at an event sums over strictly earlier events,
// t^j_m < t, never <= (mathematics.md section 1). An implementation that
// decays, reads lambda, then excites therefore matches the reference by
// construction, and two events at the same timestamp do not excite each other.
// Getting this wrong is invisible to a gradient check, so it is stated here and
// tested explicitly.

#pragma once

#include "hawkes/types.hpp"

namespace hawkes {

// Gradient of the log-likelihood with respect to the natural-space parameters.
//
// Layout, always contiguous, all supplied by the caller:
//   dmu     M
//   dalpha  M*M, row-major, target-major (ADR-002)
//   dbeta   M*M, row-major for the pair parameterization;
//           M for the shared one, indexed by source.
//
// ADR-002 keeps the public surface in natural space. The optimizer's log-space
// coordinates are reached by log_space_gradient below, once, at the boundary.
struct Gradient {
    Real* dmu;
    Real* dalpha;
    Real* dbeta;
};

// One evaluation of ell and, when grad is non-null, of its gradient.
//
// Complexity: O(N*M*M) time for the pair parameterization, O(N*M) for the
// shared one, O(M*M) or O(M) working memory. The workspaces are allocated once
// per call, never inside the event loop.
//
// Error behaviour, mathematics.md section 4: if any lambda_i at an event is
// not strictly positive, the return value is exactly -inf and every gradient
// entry is set to NaN. Nothing is clipped. A NaN is never returned as the
// value itself; the caller can distinguish "undefined here" (-inf) from
// "computation failed" (NaN would be a bug).
//
// Thread-safety: pure. All state is local to the call, and the inputs are
// read-only, so concurrent calls on disjoint outputs are safe. Releases no GIL
// itself; the binding layer owns that (ADR-004).
[[nodiscard]] Real loglik(const EventView& events, const ParamView& params, Real T,
                          Gradient* grad = nullptr);

// Shared-decay variant, beta_ij = beta_j. Produces the same value as loglik()
// when the pair block is a row-broadcast of the shared vector, at lower cost.
[[nodiscard]] Real loglik_shared(const EventView& events, const ParamView& params, Real T,
                                 Gradient* grad = nullptr);

// Apply the log-space chain rule in place: d/d(log x) = x * d/dx.
//
// Parameters are natural space (mu = e^a, alpha = e^b, beta = e^c), so the
// optimizer-side gradient is obtained by scaling each entry by the natural
// parameter it differentiates against (ADR-002, mathematics.md section 5).
// In place because the natural-space gradient has no use once the optimizer
// has it, and it keeps the H3 objective wrapper allocation-free. NaN entries
// stay NaN: NaN * x is NaN.
void log_space_gradient(const ParamView& params, Gradient& grad) noexcept;

// Shared-decay variant: beta has M entries.
void log_space_gradient_shared(const ParamView& params, Gradient& grad) noexcept;

}  // namespace hawkes
