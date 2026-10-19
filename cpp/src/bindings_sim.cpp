// SPDX-License-Identifier: MIT
//
// Bindings for the simulators and the time-rescaling diagnostic. Conversions
// only. The GIL is released around exactly one core call (ADR-004); every array
// is resolved first and every Python object is touched again only after the
// re-acquire. Simulated buffers are handed to NumPy without a copy: the vector
// is moved to the heap and a capsule frees it when the array dies.

#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "hawkes/diagnostics.hpp"
#include "hawkes/rng.hpp"
#include "hawkes/simulate_cluster.hpp"
#include "hawkes/simulate_thin.hpp"
#include "hawkes/types.hpp"
#include "hawkes/validation.hpp"

namespace py = pybind11;
using namespace hawkes;

namespace {

using RealIn = py::array_t<Real, py::array::c_style | py::array::forcecast>;

struct Model {
    RealIn mu, alpha, beta;
    Index  M;
    ParamView view() const { return ParamView{M, mu.data(), alpha.data(), beta.data()}; }
};

Model model_of(const py::object& mu, const py::object& alpha, const py::object& beta) {
    Model m{RealIn::ensure(mu), RealIn::ensure(alpha), RealIn::ensure(beta), 0};
    if (!m.mu || !m.alpha || !m.beta) {
        throw py::type_error("mu, alpha and beta must be convertible to float64 arrays");
    }
    m.M = static_cast<Index>(m.mu.size());
    const auto MM = static_cast<py::ssize_t>(m.M) * m.M;
    if (m.alpha.size() != MM || m.beta.size() != MM) {
        throw py::value_error("alpha and beta must have M*M entries for mu of length M");
    }
    return m;
}

template <class T>
py::array_t<T> adopt(std::vector<T>&& v) {
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
    const Model m = model_of(mu, alpha, beta);
    const ParamView params = m.view();
    EventStream out;
    {
        py::gil_scoped_release release;
        out = method == "thinning" ? simulate_thin(params, T, seed, t0, burn_in)
                                   : simulate_cluster(params, T, seed, t0, burn_in);
    }
    return py::make_tuple(adopt(std::move(out.first)), adopt(std::move(out.second)));
}

py::list time_rescale_py(const py::array_t<Real, py::array::c_style | py::array::forcecast>& times,
                         const py::array_t<std::uint8_t, py::array::c_style>& types,
                         const py::object& mu, const py::object& alpha, const py::object& beta) {
    if (times.size() != types.size()) {
        throw py::value_error("times and types must have the same length");
    }
    const Model m = model_of(mu, alpha, beta);
    const ParamView params = m.view();
    const EventView events{times.data(), types.data(), static_cast<Index>(times.size())};
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
            const Model md = model_of(mu, alpha, beta);
            return spectral_radius(md.view());
        },
        py::arg("mu"), py::arg("alpha"), py::arg("beta"), "Spectral radius of alpha/beta.");
    m.def(
        "stationary_mean",
        [](const py::object& mu, const py::object& alpha, const py::object& beta) {
            const Model md = model_of(mu, alpha, beta);
            return adopt(stationary_mean(md.view()));
        },
        py::arg("mu"), py::arg("alpha"), py::arg("beta"), "(I - Gamma)^{-1} mu.");
}
