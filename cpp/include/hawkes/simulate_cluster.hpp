// SPDX-License-Identifier: MIT
//
// The branching representation, mathematics.md section 6.

#pragma once

#include <cstdint>

#include "hawkes/types.hpp"

namespace hawkes {

// Default bound on the number of events in one forest, about 16 bytes each.
inline constexpr std::uint64_t kDefaultMaxNodes = 100000000ULL;

// Same contract as simulate_thin, drawn as a branching forest instead: no code
// is shared between the two beyond the generator and validation.
//
// burn_in = 0 starts from an empty history, so clusters that began before t0 are
// missing and early-window intensity is below stationary; a positive burn_in
// starts the immigrant process earlier and discards what falls before t0.
//
// Throws std::runtime_error naming rho if the forest exceeds max_nodes events,
// which happens only near criticality or for an enormous window.
[[nodiscard]] EventStream simulate_cluster(const ParamView& params, Real T, std::uint64_t seed,
                                           Real t0 = 0.0, Real burn_in = 0.0,
                                           std::uint64_t max_nodes = kDefaultMaxNodes);

}  // namespace hawkes
