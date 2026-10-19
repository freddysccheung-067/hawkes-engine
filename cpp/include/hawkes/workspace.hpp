// SPDX-License-Identifier: MIT
//
// Preallocated scratch space for one likelihood evaluation.
//
// The recursion runs O(N) steps and allocates nothing inside them: every buffer
// an evaluation needs is sized from M in the constructor. A caller that
// evaluates many times (an optimizer at H3, a benchmark loop) constructs one
// workspace and reuses it, which is also what makes the zero-allocation
// property testable: count operator new between entry and return and the count
// must be zero.

#pragma once

#include <cstddef>
#include <vector>

#include "hawkes/loglik.hpp"
#include "hawkes/types.hpp"

namespace hawkes {

// Pair parameterization, beta_ij distinct for every (target, source).
//
// State, all M*M row-major, indexed by (i, j) = (target, source):
//   S_  sum_m exp(-beta_ij (t - t_m))            the intensity recursion
//   U_  sum_m (t - t_m) exp(-beta_ij (t - t_m))  = -dS_ij/dbeta
//   C_  sum_m (1 - exp(-beta_ij (T - t_m)))      the compensator sum
//   Q_  sum_m [1 - (1 + x_m) exp(-x_m)]          its beta weight, x_m = beta_ij (T - t_m)
//
// None of these is formed as a difference of large nearly equal numbers, which
// is why C and Q are carried explicitly (see workspace.cpp).
//
// Not thread-safe: one workspace belongs to one call at a time.
class PairWorkspace {
public:
    explicit PairWorkspace(Index M);

    // No allocation. Preconditions are those of validate_params and
    // validate_events; this method does not check them. Returns -inf and
    // poisons *grad if any lambda at an event is not strictly positive.
    [[nodiscard]] Real evaluate(const EventView& events, const ParamView& params, Real T,
                                Gradient* grad);

    [[nodiscard]] Index M() const noexcept { return M_; }

private:
    Index             M_;
    std::size_t       MM_;
    std::vector<Real> S_;
    std::vector<Real> U_;
    std::vector<Real> C_;
    std::vector<Real> Q_;
};

// Shared-decay parameterization, beta_ij = beta_j. State is O(M).
class SharedWorkspace {
public:
    explicit SharedWorkspace(Index M);

    [[nodiscard]] Real evaluate(const EventView& events, const ParamView& params, Real T,
                                Gradient* grad);

    [[nodiscard]] Index M() const noexcept { return M_; }

private:
    Index             M_;
    std::vector<Real> S_;
    std::vector<Real> U_;
    std::vector<Real> C_;
    std::vector<Real> Q_;
};

}  // namespace hawkes
