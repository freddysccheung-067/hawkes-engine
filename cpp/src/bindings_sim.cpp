// SPDX-License-Identifier: MIT
//
// Bindings for the simulators and the time-rescaling diagnostic. Conversions
// only. The GIL is released around exactly one core call (ADR-004); every array
// is resolved first and every Python object is touched again only after the
// re-acquire. Simulated buffers are handed to NumPy without a copy: the vector
// is moved to the heap and a capsule frees it when the array dies.
//
// Input contract, as in bindings.cpp: float64/uint8, C-contiguous, native byte
// order, no coercion. The Python wrappers convert explicitly.

#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "array_input.hpp"
#include "hawkes/diagnostics.hpp"
#include "hawkes/rng.hpp"
#include "hawkes/simulate_cluster.hpp"
#include "hawkes/simulate_thin.hpp"
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

struct Model {
    View<Real> mu, alpha, beta;
    Index      M;
    ParamView  view() const { return ParamView{M, mu.data, alpha.data, beta.data}; }
};

Model model_of(const py::object& mu, const py::object& alpha, const py::object& beta) {
    const View<Real> a_mu    = real_1d(mu, "mu");
    const View<Real> a_alpha = real_block(alpha, "alpha");
    const View<Real> a_beta  = real_block(beta, "beta");
    if (a_mu.size < 1 || a_mu.size > 256) {
        throw py::value_error("mu must have between 1 and 256 entries, got " +
                              std::to_string(a_mu.size));
    }
    const auto M  = static_cast<Index>(a_mu.size);
    const auto MM = static_cast<py::ssize_t>(M) * M;
    require_size(a_alpha.size, MM, "alpha");
    require_size(a_beta.size, MM, "beta");
    return Model{a_mu, a_alpha, a_beta, M};
}

// Transfers ownership of `v` to NumPy.
//
// The array takes a PyCapsule as its base object. The capsule owns the vector;
// NumPy drops its reference to the base when the array is deallocated, and the
// capsule's destructor deletes the vector on the Python side, after the GIL has
// been taken (the deallocation is a Python call, so it cannot run inside a
// gil_scoped_release). The vector is moved onto the heap once and referenced
// only by that capsule, so there is exactly one owner and exactly one delete.
//
// An empty vector is not adopted: its data() need not be a valid address, and
// NumPy is asked for its own zero-length array instead.
template <class T>
py::array_t<T> adopt(std::vector<T>&& v) {
    if (v.empty()) {
        return py::array_t<T>(py::ssize_t{0});
    }
    auto* heap = new std::vector<T>(std::move(v));
    py::capsule owner(heap, [](void* p) { delete static_cast<std::vector<T>*>(p); });
    return py::array_t<T>(static_cast<py::ssize_t>(heap->size()), heap->data(), owner);
}

py::tuple simulate_py(const py::object& mu, const py::object& alpha, const py::object& beta,
                      double T, const std::string& method, std::uint64_t seed, double t0,
                      double burn_in) {
    if (method != "thinning" && method != "cluster") {
        throw py::value_error("method must be 'thinning' or 'cluster', got '" + method + "'");
    }
    const ParamView params = model_of(mu, alpha, beta).view();
    EventStream     out;
    {
        py::gil_scoped_release release;
        out = method == "thinning" ? simulate_thin(params, T, seed, t0, burn_in)
                                   : simulate_cluster(params, T, seed, t0, burn_in);
    }
    return py::make_tuple(adopt(std::move(out.first)), adopt(std::move(out.second)));
}

py::list time_rescale_py(const py::object& times, const py::object& types, const py::object& mu,
                         const py::object& alpha, const py::object& beta) {
    const View<Real>         a_times = real_1d(times, "times");
    const View<std::uint8_t> a_types = uint8_1d(types, "types");
    require_size(a_types.size, a_times.size, "types");
    const ParamView params = model_of(mu, alpha, beta).view();
    const EventView events{a_times.data, a_types.data, static_cast<Index>(a_times.size)};

    std::vector<std::vector<Real>> gaps;
    {
        py::gil_scoped_release release;
        gaps = time_rescale(events, params);
    }

    py::list out;
    for (auto& g : gaps) {
        out.append(adopt(std::move(g)));
    }
    return out;
}

}  // namespace

void register_simulate(py::module_& m) {
    m.def("simulate", &simulate_py, py::arg("mu"), py::arg("alpha"), py::arg("beta"),
          py::arg("T"), py::arg("method"), py::arg("seed"), py::arg("t0") = 0.0,
          py::arg("burn_in") = 0.0,
          "Simulate on [t0, T). Returns (times float64, types uint8).");
    m.def("time_rescale", &time_rescale_py, py::arg("times"), py::arg("types"), py::arg("mu"),
          py::arg("alpha"), py::arg("beta"),
          "Rescaled gaps per type under the given parameters.");
    m.def(
        "seed_stream",
        [](std::uint64_t seed, std::uint64_t index) { return seed_stream(seed, index); },
        py::arg("seed"), py::arg("index"), "Seed of the index-th independent stream.");
    m.def(
        "spectral_radius",
        [](const py::object& mu, const py::object& alpha, const py::object& beta) {
            return spectral_radius(model_of(mu, alpha, beta).view());
        },
        py::arg("mu"), py::arg("alpha"), py::arg("beta"), "Spectral radius of alpha/beta.");
    m.def(
        "stationary_mean",
        [](const py::object& mu, const py::object& alpha, const py::object& beta) {
            return adopt(stationary_mean(model_of(mu, alpha, beta).view()));
        },
        py::arg("mu"), py::arg("alpha"), py::arg("beta"), "(I - Gamma)^{-1} mu.");
}
