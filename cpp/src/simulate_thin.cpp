// SPDX-License-Identifier: MIT

#include "hawkes/simulate_thin.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>

#include "hawkes/diagnostics.hpp"
#include "hawkes/rng.hpp"
#include "hawkes/validation.hpp"

namespace hawkes {

EventStream simulate_thin(const ParamView& p, Real T, std::uint64_t seed, Real t0, Real burn_in) {
    validate_simulation(p, T, t0, burn_in);

    const auto M = static_cast<std::size_t>(p.M);
    Rng rng(seed);

    EventStream out;
    {
        Real total = 0.0;
        for (Real m : stationary_mean(p)) {
            total += m;
        }
        const Real guess = std::min(1.1 * total * (T - t0) + 16.0, 6.7e7);
        out.first.reserve(static_cast<std::size_t>(guess));
        out.second.reserve(static_cast<std::size_t>(guess));
    }

    // S[i*M + j] = sum over past type-j events of exp(-beta_ij (t - t_m)).
    std::vector<Real> S(M * M, 0.0);
    std::vector<Real> lam(M);
    Real clock = t0 - burn_in;

    Real mu_total = 0.0;
    for (std::size_t i = 0; i < M; ++i) {
        mu_total += p.mu[i];
    }
    // The bound is the total intensity just after the last event or probe. The
    // process only excites, so intensity decays between events and the bound
    // stays valid until the next one.
    Real bound = mu_total;

    while (bound > 0.0) {
        const Real next = clock + rng.exponential(bound);
        if (!(next < T)) {
            break;
        }
        const Real dt = next - clock;
        clock = next;
        for (std::size_t k = 0; k < M * M; ++k) {
            S[k] *= std::exp(-p.beta[k] * dt);
        }
        Real total = 0.0;
        for (std::size_t i = 0; i < M; ++i) {
            Real l = p.mu[i];
            for (std::size_t j = 0; j < M; ++j) {
                l += p.alpha[i * M + j] * S[i * M + j];
            }
            lam[i] = l;
            total += l;
        }
        if (rng.uniform01() * bound > total) {
            bound = total;
            continue;
        }
        // Type i with probability lam_i / total; the last type absorbs rounding
        // in the running sum.
        const Real pick = rng.uniform01() * total;
        Real acc = 0.0;
        std::size_t kind = M - 1;
        for (std::size_t i = 0; i < M; ++i) {
            acc += lam[i];
            if (pick < acc) {
                kind = i;
                break;
            }
        }
        Real jump = 0.0;
        for (std::size_t i = 0; i < M; ++i) {
            S[i * M + kind] += 1.0;
            jump += p.alpha[i * M + kind];
        }
        // Total just after the jump: the accepted rate plus the new bump.
        bound = total + jump;
        if (clock >= t0) {
            out.first.push_back(clock);
            out.second.push_back(static_cast<std::uint8_t>(kind));
        }
    }
    return out;
}

}  // namespace hawkes
