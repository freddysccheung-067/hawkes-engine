// SPDX-License-Identifier: MIT
//
// Argument validation. Called once at the API boundary and never from the event
// loop: these functions allocate and format messages.

#pragma once

#include <stdexcept>

#include "hawkes/types.hpp"

namespace hawkes {

// Throws std::invalid_argument if the event view violates the preconditions in
// types.hpp. The message names the offending index and value.
//
// M is passed separately because EventView does not carry it; a type index is
// only out of range relative to the parameter block it will index.
void validate_events(const EventView& events, Index M);

// Throws std::invalid_argument if the parameter view violates the preconditions
// in types.hpp. Nothing here constrains the spectral radius: a supercritical
// parameter set is a legitimate input whose likelihood is still well defined,
// and mathematics.md section 2 leaves the warning to the caller that reports
// rho(Gamma).
void validate_params(const ParamView& params);

// Shared-decay overload: beta has M entries, one per source, not M*M.
void validate_params_shared(const ParamView& params);

}  // namespace hawkes
