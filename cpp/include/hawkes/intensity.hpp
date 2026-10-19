// SPDX-License-Identifier: MIT
//
// Recursion state for the exponential-kernel intensity. mathematics.md section 4.
//
// S_ij(t) = sum over past type-j events of exp(-beta_ij * (t - t_m)).
// The recursion is sequential over events: an event at tau_n decays every state
// to tau_n, reads lambda, then increments the states of the columns it excites.
// ADR-004 records why this cannot be parallelised over events.

#pragma once

#include <cstddef>
#include <vector>

#include "hawkes/types.hpp"

namespace hawkes {

// Pair decay: beta_ij distinct for every (target, source) pair. O(M*M) state.
//
// Workspace is allocated once, in the constructor; the event loop performs no
// allocation. Not thread-safe for concurrent use: each call needs its own
// instance.
class IntensityState {
public:
    explicit IntensityState(Index M)
        : M_(M), S_(static_cast<std::size_t>(M) * static_cast<std::size_t>(M), 0.0) {}

    // Decay every state from the previous event time to `t`. Precondition:
    // t >= last_time() and both are finite.
    void advance(Real t, const Real* beta) noexcept {
        const Real dt = t - t_;
        t_ = t;
        for (Index i = 0; i < M_; ++i) {
            const Real* beta_row = beta + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
            Real*       s_row    = S_.data() + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
            for (Index j = 0; j < M_; ++j) {
                s_row[j] *= decay_factor(beta_row[j], dt);
            }
        }
    }

    // Add one to column `source` of every row: an event of that type has just
    // occurred at the current time.
    void excite(Index source) noexcept {
        for (Index i = 0; i < M_; ++i) {
            S_[static_cast<std::size_t>(i) * static_cast<std::size_t>(M_) +
               static_cast<std::size_t>(source)] += 1.0;
        }
    }

    // lambda_i(t) = mu_i + sum_j alpha_ij * S_ij(t).
    [[nodiscard]] Real lambda(Index i, const Real* mu, const Real* alpha) const noexcept {
        const Real* a_row = alpha + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
        const Real* s_row = S_.data() + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
        Real sum = mu[i];
        for (Index j = 0; j < M_; ++j) {
            sum += a_row[j] * s_row[j];
        }
        return sum;
    }

    [[nodiscard]] Index M() const noexcept { return M_; }
    [[nodiscard]] Real last_time() const noexcept { return t_; }
    [[nodiscard]] const Real* S_row(Index i) const noexcept {
        return S_.data() + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
    }

private:
    Index             M_;
    Real              t_ = 0.0;
    std::vector<Real> S_;
};

// Shared decay: beta_ij = beta_j depends on the source only, so S_ij = S_j and
// the state is O(M). Same intensity, O(N*M) per evaluation instead of O(N*M*M);
// mathematics.md section 4 names this the fast path.
class IntensityStateShared {
public:
    explicit IntensityStateShared(Index M) : M_(M), S_(static_cast<std::size_t>(M), 0.0) {}

    void advance(Real t, const Real* beta) noexcept {
        const Real dt = t - t_;
        t_ = t;
        for (Index j = 0; j < M_; ++j) {
            S_[static_cast<std::size_t>(j)] *= decay_factor(beta[j], dt);
        }
    }

    void excite(Index source) noexcept { S_[static_cast<std::size_t>(source)] += 1.0; }

    // Note the row-major alpha and the column-indexed state: entry (i, j) times
    // S_j, so the inner loop walks the alpha row contiguously.
    [[nodiscard]] Real lambda(Index i, const Real* mu, const Real* alpha) const noexcept {
        const Real* a_row = alpha + static_cast<std::size_t>(i) * static_cast<std::size_t>(M_);
        Real sum = mu[i];
        for (Index j = 0; j < M_; ++j) {
            sum += a_row[j] * S_[static_cast<std::size_t>(j)];
        }
        return sum;
    }

    [[nodiscard]] Index M() const noexcept { return M_; }
    [[nodiscard]] Real last_time() const noexcept { return t_; }
    [[nodiscard]] const Real* S() const noexcept { return S_.data(); }

private:
    Index             M_;
    Real              t_ = 0.0;
    std::vector<Real> S_;
};

}  // namespace hawkes
