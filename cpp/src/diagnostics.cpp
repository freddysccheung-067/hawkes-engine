// SPDX-License-Identifier: MIT

#include "hawkes/diagnostics.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <sstream>
#include <stdexcept>

#include "hawkes/kernel_exp.hpp"
#include "hawkes/validation.hpp"

namespace hawkes {

namespace {

std::vector<Real> branching_matrix(const ParamView& p) {
    const auto n = static_cast<std::size_t>(p.M) * static_cast<std::size_t>(p.M);
    std::vector<Real> gamma(n);
    for (std::size_t k = 0; k < n; ++k) {
        gamma[k] = p.alpha[k] / p.beta[k];
    }
    return gamma;
}

}  // namespace

Real spectral_radius(const ParamView& p) {
    const auto M = static_cast<std::size_t>(p.M);
    const std::vector<Real> gamma = branching_matrix(p);
    std::vector<Real> x(M, 1.0), y(M);
    Real lo = 0.0, hi = 0.0;
    for (int iter = 0; iter < 200000; ++iter) {
        lo = 1e300;
        hi = 0.0;
        Real norm = 0.0;
        for (std::size_t i = 0; i < M; ++i) {
            Real s = x[i];
            for (std::size_t j = 0; j < M; ++j) {
                s += gamma[i * M + j] * x[j];
            }
            y[i] = s;
            const Real ratio = s / x[i];
            lo = std::min(lo, ratio);
            hi = std::max(hi, ratio);
            norm = std::max(norm, s);
        }
        for (std::size_t i = 0; i < M; ++i) {
            x[i] = y[i] / norm;
        }
        if (hi - lo < 1e-13) {
            break;
        }
    }
    return 0.5 * (lo + hi) - 1.0;
}

std::vector<Real> stationary_mean(const ParamView& p) {
    const Real rho = spectral_radius(p);
    if (!(rho < 1.0)) {
        std::ostringstream os;
        os.precision(17);
        os << "stationary mean requires spectral radius < 1, got " << rho;
        throw std::domain_error(os.str());
    }
    const auto M = static_cast<std::size_t>(p.M);
    const std::vector<Real> gamma = branching_matrix(p);
    // Gaussian elimination with partial pivoting on (I - Gamma) x = mu.
    std::vector<Real> a(M * M);
    std::vector<Real> x(p.mu, p.mu + M);
    for (std::size_t i = 0; i < M; ++i) {
        for (std::size_t j = 0; j < M; ++j) {
            a[i * M + j] = (i == j ? 1.0 : 0.0) - gamma[i * M + j];
        }
    }
    for (std::size_t c = 0; c < M; ++c) {
        std::size_t pivot = c;
        for (std::size_t r = c + 1; r < M; ++r) {
            if (std::fabs(a[r * M + c]) > std::fabs(a[pivot * M + c])) {
                pivot = r;
            }
        }
        if (pivot != c) {
            for (std::size_t j = 0; j < M; ++j) {
                std::swap(a[c * M + j], a[pivot * M + j]);
            }
            std::swap(x[c], x[pivot]);
        }
        for (std::size_t r = c + 1; r < M; ++r) {
            const Real f = a[r * M + c] / a[c * M + c];
            for (std::size_t j = c; j < M; ++j) {
                a[r * M + j] -= f * a[c * M + j];
            }
            x[r] -= f * x[c];
        }
    }
    for (std::size_t c = M; c-- > 0;) {
        for (std::size_t j = c + 1; j < M; ++j) {
            x[c] -= a[c * M + j] * x[j];
        }
        x[c] /= a[c * M + c];
    }
    return x;
}

std::vector<std::vector<Real>> time_rescale(const EventView& ev, const ParamView& p) {
    validate_params(p);
    validate_events(ev, p.M);
    const auto M = static_cast<std::size_t>(p.M);
    std::vector<std::vector<Real>> gaps(M);
    std::vector<Real> S(M * M, 0.0);
    std::vector<Real> acc(M, 0.0);
    Real prev = 0.0;
    for (Index n = 0; n < ev.n; ++n) {
        const Real dt = ev.times[n] - prev;
        prev = ev.times[n];
        for (std::size_t i = 0; i < M; ++i) {
            Real a = p.mu[i] * dt;
            for (std::size_t j = 0; j < M; ++j) {
                const std::size_t c = i * M + j;
                a += p.alpha[c] * S[c] * one_minus_decay(p.beta[c] * dt) / p.beta[c];
                S[c] *= decay_factor(p.beta[c], dt);
            }
            acc[i] += a;
        }
        const std::size_t kind = ev.types[n];
        gaps[kind].push_back(acc[kind]);
        acc[kind] = 0.0;
        for (std::size_t i = 0; i < M; ++i) {
            S[i * M + kind] += 1.0;
        }
    }
    return gaps;
}

}  // namespace hawkes
