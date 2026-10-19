// SPDX-License-Identifier: MIT
//
// Python bindings for the likelihood core. Conversions only: every arithmetic
// decision is made in workspace.cpp; nothing here touches a floating-point value
// except to hand a pointer to it.
//
// GIL policy (ADR-004): the compute call runs with the GIL released. No Python
// object may be touched between the release and the re-acquire, so every array
// and buffer is obtained first and the released section is exactly one call.
//
// The output arrays are allocated before the release and written in place, so
// the gradient the core fills is the array the caller receives. No copy, and no
// pointer into a Python object outlives its owner.

#include <cstddef>
#include <string>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "hawkes/loglik.hpp"
#include "hawkes/types.hpp"
#include "hawkes/validation.hpp"

namespace py = pybind11;
using namespace hawkes;

namespace {

// A non-owning contiguous float64 view. The owning NumPy array is kept alive by
// the caller for the duration of the C++ call; this type owns nothing.
struct RealArray {
    const Real* data;
    Index       size;
};

RealArray real_array(const py::object& obj, const char* name) {
    if (!py::isinstance<py::array>(obj)) {
        throw py::type_error(std::string(name) + " must be a NumPy array");
    }
    py::array raw = py::reinterpret_borrow<py::array>(obj);
    if (raw.dtype().kind() != 'f' || raw.itemsize() != static_cast<py::ssize_t>(sizeof(Real))) {
        throw py::type_error(std::string(name) + " must have dtype float64, got " +
                             std::string(py::repr(raw.dtype())));
    }
    if (!(raw.flags() & py::array::c_style)) {
        throw py::value_error(std::string(name) + " must be C-contiguous");
    }
    auto typed = py::array_t<Real, py::array::c_style | py::array::forcecast>::ensure(obj);
    if (!typed) {
        throw py::type_error(std::string(name) + " could not be viewed as float64");
    }
    return RealArray{typed.data(), static_cast<Index>(typed.size())};
}

void require_size(Index actual, Index expected, const char* name) {
    if (actual != expected) {
        throw py::value_error(std::string(name) + " has " + std::to_string(actual) +
                              " entries, expected " + std::to_string(expected));
    }
}

// Parsed argument set. Everything is resolved before the GIL is released.
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
    const Index Mi = static_cast<Index>(M);
    const Index MM = static_cast<Index>(Mi * Mi);

    RealArray a_mu    = real_array(mu, "mu");
    RealArray a_alpha = real_array(alpha, "alpha");
    RealArray a_beta  = real_array(beta, "beta");
    RealArray a_times = real_array(times, "times");

    require_size(a_mu.size, Mi, "mu");
    require_size(a_alpha.size, MM, "alpha");
    require_size(a_beta.size, shared ? Mi : MM, shared ? "beta (shared)" : "beta");

    if (!py::isinstance<py::array>(types)) {
        throw py::type_error("types must be a NumPy array");
    }
    py::array raw_types = py::reinterpret_borrow<py::array>(types);
    if (raw_types.dtype().kind() != 'u' || raw_types.itemsize() != 1) {
        throw py::type_error("types must have dtype uint8, got " +
                             std::string(py::repr(raw_types.dtype())));
    }
    if (!(raw_types.flags() & py::array::c_style)) {
        throw py::value_error("types must be C-contiguous");
    }
    require_size(static_cast<Index>(raw_types.size()), a_times.size, "types");

    auto typed_types = py::array_t<std::uint8_t, py::array::c_style>::ensure(types);
    if (!typed_types) {
        throw py::type_error("types could not be viewed as uint8");
    }

    if (!(T >= 0.0)) {
        throw py::value_error("T must be non-negative, got " + std::to_string(T));
    }

    Call call;
    call.params = ParamView{Mi, a_mu.data, a_alpha.data, a_beta.data};
    call.events = EventView{a_times.data, typed_types.data(), a_times.size};
    call.T      = T;

    if (shared) {
        validate_params_shared(call.params);
    } else {
        validate_params(call.params);
    }
    validate_events(call.events, Mi);
    return call;
}

// The three output blocks, allocated before the GIL is released and written in
// place by the core.
struct Outputs {
    py::array_t<Real> dmu;
    py::array_t<Real> dalpha;
    py::array_t<Real> dbeta;
};

Outputs make_outputs(Index M, bool shared) {
    const auto Mi = static_cast<py::ssize_t>(M);
    const auto MM = static_cast<py::ssize_t>(M) * static_cast<py::ssize_t>(M);
    Outputs out{py::array_t<Real>(Mi), py::array_t<Real>({Mi, MM}),
                shared ? py::array_t<Real>(Mi) : py::array_t<Real>({Mi, MM})};
    return out;
}

Gradient gradient_of(Outputs& out) {
    return Gradient{out.dmu.mutable_data(), out.dalpha.mutable_data(), out.dbeta.mutable_data()};
}

py::dict loglik_py(const py::object& times, const py::object& types, const py::object& mu,
                   const py::object& alpha, const py::object& beta, double T, std::size_t M,
                   bool shared, bool grad) {
    const Call call = prepare(times, types, mu, alpha, beta, T, M, shared);

    py::dict out;
    Real     value = 0.0;

    if (!grad) {
        {
            py::gil_scoped_release release;
            value = shared ? loglik_shared(call.events, call.params, call.T)
                           : loglik(call.events, call.params, call.T);
        }
        out["value"] = value;
        return out;
    }

    Outputs outputs = make_outputs(call.params.M, shared);
    {
        py::gil_scoped_release release;
        Gradient g    = gradient_of(outputs);
        value         = shared ? loglik_shared(call.events, call.params, call.T, &g)
                               : loglik(call.events, call.params, call.T, &g);
    }
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

    Outputs outputs = make_outputs(call.params.M, shared);
    Real    value   = 0.0;
    {
        py::gil_scoped_release release;
        Gradient g = gradient_of(outputs);
        value      = shared ? loglik_shared(call.events, call.params, call.T, &g)
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
}
