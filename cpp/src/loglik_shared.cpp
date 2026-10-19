// SPDX-License-Identifier: MIT
//
// Shared-decay entry points, beta_ij = beta_j. Same likelihood as loglik.cpp,
// O(N*M) rather than O(N*M*M) because the recursion state is one vector
// (mathematics.md section 4).

#include <cstddef>

#include "hawkes/loglik.hpp"
#include "hawkes/workspace.hpp"

namespace hawkes {

Real loglik_shared(const EventView& events, const ParamView& params, Real T, Gradient* grad) {
    SharedWorkspace workspace(params.M);
    return workspace.evaluate(events, params, T, grad);
}

void log_space_gradient_shared(const ParamView& params, Gradient& grad) noexcept {
    const Index       M  = params.M;
    const std::size_t MM = static_cast<std::size_t>(M) * static_cast<std::size_t>(M);
    for (Index i = 0; i < M; ++i) {
        grad.dmu[i] *= params.mu[i];
    }
    for (std::size_t k = 0; k < MM; ++k) {
        grad.dalpha[k] *= params.alpha[k];
    }
    for (Index j = 0; j < M; ++j) {
        grad.dbeta[j] *= params.beta[j];
    }
}

}  // namespace hawkes
