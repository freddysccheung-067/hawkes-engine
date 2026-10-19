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

// Checks shared by both simulators, so neither core loop carries its own copy.
// Throws std::invalid_argument for bad parameters, T, t0 or burn_in, and
// std::domain_error, with rho(Gamma) in the message, when rho >= 1: past the
// pole the process explodes and no finite window is representative.
//
// Event time may be negative only through burn_in; t0 and T are the window
// [t0, T] and must satisfy t0 < T.
void validate_simulation(const ParamView& params, Real T, Real t0, Real burn_in);

}  // namespace hawkes
