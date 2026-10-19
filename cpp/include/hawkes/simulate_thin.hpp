// SPDX-License-Identifier: MIT
//
// Ogata's modified thinning, mathematics.md section 6.

#pragma once

#include <cstdint>

#include "hawkes/types.hpp"

namespace hawkes {

// Events on [t0, T) of the process with the given parameters, deterministic in
// (params, T, seed, t0, burn_in).
//
// The clock starts at t0 - burn_in with an empty history and events before t0
// are discarded, so burn_in = 0 starts from an empty history and the intensity
// near t0 is below its stationary level (spec section 6 note).
//
// Throws std::invalid_argument for malformed arguments and std::domain_error,
// with rho in the message, when rho(alpha/beta) >= 1. A single clock is
// advanced, so the loop is sequential by construction (ADR-004).
[[nodiscard]] EventStream simulate_thin(const ParamView& params, Real T, std::uint64_t seed,
                                        Real t0 = 0.0, Real burn_in = 0.0);

}  // namespace hawkes
