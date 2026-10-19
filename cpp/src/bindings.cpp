// SPDX-License-Identifier: MIT
//
// Python bindings for the likelihood core. Conversions only: every arithmetic
// decision is made in workspace.cpp; nothing here touches a floating-point value
// except to hand a pointer to it.
//
// Contract. Every input is a NumPy array that is already float64 (or uint8 for
// the event types), C-contiguous and in native byte order. Nothing is copied or
// coerced: an input that does not meet the contract raises, naming the argument.
// The Python wrappers in python/hawkes_engine convert explicitly, where the
// caller can see it in the traceback, so the compiled layer never has to guess.
//
// GIL policy (ADR-004). A compute call runs with the GIL released. No Python
// object may be touched between the release and the re-acquire, so every array,
// view and output buffer is obtained first, and the released section contains
// exactly one core call. Pointers are taken from the caller's arrays before the
// release; the caller's references keep the buffers alive for the duration.

#include <cstddef>
#include <cstdint>
#include <string>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "array_input.hpp"
#include "hawkes/loglik.hpp"
#include "hawkes/types.hpp"
#include "hawkes/validation.hpp"

namespace py = pybind11;
using namespace hawkes;
using hawkes::pybindings::real_1d;
using hawkes::pybindings::real_block;
using hawkes::pybindings::require_size;
using hawkes::pybindings::uint8_1d;
using hawkes::pybindings::View;

namespace {

// Every argument resolved before the GIL is released, and nothing in it is a
// Python object.
struct Call {
    ParamView params;
    EventView events;
    Real      T;
};

Call prepare(const py::object& times, const py::object& types, const py::object& mu,
             const py::object& alpha, const py::object& beta, double T, std::size_t M,
             bool shared) {
    if (M < 1 || M > 256) {
        throw py::value_error("M must be in 1..256, got " + std::to_string(M));
    }
    const auto  Mi = static_cast<Index>(M);
    const auto  MM = static_cast<Index>(Mi * Mi);

    const View<Real> a_mu    = real_1d(mu, "mu");
    const View<Real> a_alpha = real_block(alpha, "alpha");
    const View<Real> a_beta  = real_block(beta, "beta");
    const View<Real> a_times = real_1d(times, "times");
    const View<std::uint8_t> a_types = uint8_1d(types, "types");

    require_size(a_mu.size, Mi, "mu");
    require_size(a_alpha.size, MM, "alpha");
    require_size(a_beta.size, shared ? Mi : MM, shared ? "beta (shared)" : "beta");
    require_size(a_types.size, a_times.size, "types");

    if (!(T >= 0.0)) {
        throw py::value_error("T must be non-negative, got " + std::to_string(T));
    }

    Call call;
    call.params = ParamView{Mi, a_mu.data, a_alpha.data, a_beta.data};
    call.events = EventView{a_times.data, a_types.data, static_cast<Index>(a_times.size)};
    call.T      = T;

    if (shared) {
        validate_params_shared(call.params);
    } else {
        validate_params(call.params);
    }
    validate_events(call.events, Mi);

    // The likelihood integrates over [0, T], so an event after T lies outside
    // the window the model claims to describe. Silently evaluating it would
    // return a number for a question nobody asked.
    if (call.events.n > 0 && call.events.times[call.events.n - 1] > T) {
        throw py::value_error("T = " + std::to_string(T) + " is before the last event at index " +
                              std::to_string(call.events.n - 1) + ", value " +
                              std::to_string(call.events.times[call.events.n - 1]));
    }
    return call;
}

// Output blocks allocated before the GIL is released and written in place by the
// core, so what the core fills is what the caller receives. NumPy owns the
// memory; there is no second buffer and no adopt() on this path.
struct Outputs {
    py::array_t<Real> dmu;
    py::array_t<Real> dalpha;
    py::array_t<Real> dbeta;
};

Outputs make_outputs(Index M, bool shared) {
    const auto Mi = static_cast<py::ssize_t>(M);
    return Outputs{py::array_t<Real>(Mi), py::array_t<Real>({Mi, Mi}),
                   shared ? py::array_t<Real>(Mi) : py::array_t<Real>({Mi, Mi})};
}

// Called before the release: mutable_data() inspects the array's WRITEABLE flag
// and can throw, and both of those are Python-level operations.
Gradient gradient_of(Outputs& out) {
    return Gradient{out.dmu.mutable_data(), out.dalpha.mutable_data(), out.dbeta.mutable_data()};
}

py::dict loglik_py(const py::object& times, const py::object& types, const py::object& mu,
                   const py::object& alpha, const py::object& beta, double T, std::size_t M,
                   bool shared, bool grad) {
    const Call call = prepare(times, types, mu, alpha, beta, T, M, shared);

    if (!grad) {
        Real value = 0.0;
        {
            py::gil_scoped_release release;
            value = shared ? loglik_shared(call.events, call.params, call.T)
                           : loglik(call.events, call.params, call.T);
        }
        py::dict out;
        out["value"] = value;
        return out;
    }

    Outputs outputs = make_outputs(call.params.M, shared);
    Gradient g      = gradient_of(outputs);
    Real     value  = 0.0;
    {
        py::gil_scoped_release release;
        value = shared ? loglik_shared(call.events, call.params, call.T, &g)
                       : loglik(call.events, call.params, call.T, &g);
    }

    py::dict out;
    out["value"]  = value;
    out["dmu"]    = outputs.dmu;
    out["dalpha"] = outputs.dalpha;
    out["dbeta"]  = outputs.dbeta;
    return out;
}

py::dict loglik_grad_log_space(const py::object& times, const py::object& types,
                               const py::object& mu, const py::object& alpha,
                               const py::object& beta, double T, std::size_t M, bool shared) {
    const Call call = prepare(times, types, mu, alpha, beta, T, M, shared);

    Outputs  outputs = make_outputs(call.params.M, shared);
    Gradient g       = gradient_of(outputs);
    Real     value   = 0.0;
    {
        py::gil_scoped_release release;
        value = shared ? loglik_shared(call.events, call.params, call.T, &g)
                       : loglik(call.events, call.params, call.T, &g);
        if (shared) {
            log_space_gradient_shared(call.params, g);
        } else {
            log_space_gradient(call.params, g);
        }
    }

    py::dict out;
    out["value"]  = value;
    out["dmu"]    = outputs.dmu;
    out["dalpha"] = outputs.dalpha;
    out["dbeta"]  = outputs.dbeta;
    return out;
}

// Private instrument for tests/test_zero_copy.py. It resolves the same argument
// set through the same prepare() the compute path uses and reports the addresses
// that resolution produced, so a test can assert the core reads the caller's
// buffer rather than a copy. Stateless and read-only.
py::tuple view_addresses(const py::object& times, const py::object& types, const py::object& mu,
                         const py::object& alpha, const py::object& beta, double T,
                         std::size_t M, bool shared) {
    const Call call = prepare(times, types, mu, alpha, beta, T, M, shared);
    auto       addr = [](const void* p) { return reinterpret_cast<std::uintptr_t>(p); };
    return py::make_tuple(addr(call.events.times), addr(call.events.types), addr(call.params.mu),
                          addr(call.params.alpha), addr(call.params.beta));
}

}  // namespace

void register_loglik(py::module_& m) {
    m.def("loglik", &loglik_py, py::arg("times"), py::arg("types"), py::arg("mu"),
          py::arg("alpha"), py::arg("beta"), py::arg("T"), py::arg("M"),
          py::arg("shared_decay") = false, py::arg("grad") = false,
          "Log-likelihood and optional natural-space gradient. Returns a dict with "
          "\"value\" and, when grad is true, \"dmu\", \"dalpha\", \"dbeta\".");
    m.def("loglik_grad_log_space", &loglik_grad_log_space, py::arg("times"), py::arg("types"),
          py::arg("mu"), py::arg("alpha"), py::arg("beta"), py::arg("T"), py::arg("M"),
          py::arg("shared_decay") = false,
          "Log-likelihood with the gradient in log space (ADR-002).");
    m.def("_view_addresses", &view_addresses, py::arg("times"), py::arg("types"), py::arg("mu"),
          py::arg("alpha"), py::arg("beta"), py::arg("T"), py::arg("M"),
          py::arg("shared_decay") = false,
          "Private: data addresses the core resolved for each argument. Testing only.");
    m.def("_array_address", &hawkes::pybindings::address_of, py::arg("array"),
          "Private: data address of a C-contiguous array. Testing only.");
}
