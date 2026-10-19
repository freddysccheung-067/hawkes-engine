// SPDX-License-Identifier: MIT
//
// Free-function entry points. The arithmetic lives in workspace.cpp, where the
// state buffers are owned; these wrappers only construct the workspace and
// apply the log-space chain rule.

#include "hawkes/loglik.hpp"

#include <cstddef>

#include "hawkes/workspace.hpp"

namespace hawkes {

Real loglik(const EventView& events, const ParamView& params, Real T, Gradient* grad) {
    PairWorkspace workspace(params.M);
    return workspace.evaluate(events, params, T, grad);
}

void log_space_gradient(const ParamView& params, Gradient& grad) noexcept {
    const Index       M  = params.M;
    const std::size_t MM = static_cast<std::size_t>(M) * static_cast<std::size_t>(M);
    for (Index i = 0; i < M; ++i) {
        grad.dmu[i] *= params.mu[i];
    }
    for (std::size_t k = 0; k < MM; ++k) {
        grad.dalpha[k] *= params.alpha[k];
        grad.dbeta[k] *= params.beta[k];
    }
}

}  // namespace hawkes
