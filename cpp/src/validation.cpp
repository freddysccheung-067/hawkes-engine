// SPDX-License-Identifier: MIT
//
// Boundary checks. Everything here allocates and formats, so it runs once per
// call at the API boundary and never from the event loop. The messages name the
// offending index and value because a validation error the user cannot locate is
// barely better than a crash.

#include "hawkes/validation.hpp"

#include <cmath>
#include <cstddef>
#include <sstream>
#include <string>

namespace hawkes {

namespace {

std::string at(Index index, Real value) {
    std::ostringstream os;
    os.precision(17);
    os << "index " << index << ", value " << value;
    return os.str();
}

void require_finite(Real value, const char* name, Index index) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument(std::string(name) + " must be finite at " +
                                    at(index, value));
    }
}

}  // namespace

void validate_events(const EventView& ev, Index M) {
    if (ev.n < 0) {
        throw std::invalid_argument("event count must be non-negative, got " +
                                    std::to_string(ev.n));
    }
    if (ev.n == 0) {
        return;
    }
    if (ev.times == nullptr) {
        throw std::invalid_argument("event times pointer is null with a non-zero count");
    }
    if (ev.types == nullptr) {
        throw std::invalid_argument("event types pointer is null with a non-zero count");
    }
    for (Index k = 0; k < ev.n; ++k) {
        const Real t = ev.times[k];
        if (!std::isfinite(t)) {
            throw std::invalid_argument("event time must be finite at " + at(k, t));
        }
        if (k > 0 && t < ev.times[k - 1]) {
            std::ostringstream os;
            os.precision(17);
            os << "event times must be non-decreasing: index " << k << " at " << t
               << " follows index " << (k - 1) << " at " << ev.times[k - 1];
            throw std::invalid_argument(os.str());
        }
        const Index type = static_cast<Index>(ev.types[k]);
        if (type >= M) {
            throw std::invalid_argument("event type " + std::to_string(type) +
                                        " is not less than M = " + std::to_string(M) +
                                        " at index " + std::to_string(k));
        }
    }
}

namespace {

void validate_common(const ParamView& p, const char* beta_name, Index beta_count) {
    if (p.M < 1) {
        throw std::invalid_argument("M must be at least 1, got " + std::to_string(p.M));
    }
    if (p.M > 256) {
        throw std::invalid_argument(
            "M must not exceed 256, because event types are stored as uint8 (ADR-003); got " +
            std::to_string(p.M));
    }
    if (p.mu == nullptr || p.alpha == nullptr || p.beta == nullptr) {
        throw std::invalid_argument("parameter pointers must be non-null");
    }
    for (Index i = 0; i < p.M; ++i) {
        require_finite(p.mu[i], "mu", i);
        if (p.mu[i] < 0.0) {
            throw std::invalid_argument("mu must be non-negative at " + at(i, p.mu[i]));
        }
    }
    const std::size_t MM = static_cast<std::size_t>(p.M) * static_cast<std::size_t>(p.M);
    for (std::size_t k = 0; k < MM; ++k) {
        require_finite(p.alpha[k], "alpha", static_cast<Index>(k));
        if (p.alpha[k] < 0.0) {
            throw std::invalid_argument("alpha must be non-negative at " +
                                        at(static_cast<Index>(k), p.alpha[k]));
        }
    }
    for (Index k = 0; k < beta_count; ++k) {
        require_finite(p.beta[k], beta_name, k);
        if (!(p.beta[k] > 0.0)) {
            throw std::invalid_argument(std::string(beta_name) +
                                        " must be strictly positive at " + at(k, p.beta[k]));
        }
    }
}

}  // namespace

void validate_params(const ParamView& p) {
    validate_common(p, "beta", p.M * p.M);
}

void validate_params_shared(const ParamView& p) {
    validate_common(p, "beta", p.M);
}

}  // namespace hawkes
