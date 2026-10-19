// SPDX-License-Identifier: MIT
//
// Input arrays for the Python boundary: one checker, shared by every binding, so
// that "float64, C-contiguous, native byte order" is one predicate rather than
// six near-copies that can drift apart.
//
// Nothing here converts. The library's claim is that a well-formed array reaches
// the core without being copied, and the only way to keep that claim is to
// refuse what cannot be a view. A float32 or strided input is the caller's
// mistake, and it is reported with the argument's own name so the traceback
// says which one.

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "hawkes/types.hpp"

namespace hawkes::pybindings {

namespace py = pybind11;

// A non-owning, read-only view of a NumPy buffer. The owning array is kept alive
// by the C++ caller for the duration of the core call; this struct owns nothing
// and must never outlive it.
template <class T>
struct View {
    const T*    data;
    py::ssize_t size;
};

namespace detail {

inline std::string dtype_name(const py::array& a) { return std::string(py::repr(a.dtype())); }

inline void require_kind(const py::array& a, char kind, py::ssize_t itemsize, const char* name,
                         const char* required) {
    const py::dtype dtype = a.dtype();
    if (dtype.kind() != kind || dtype.itemsize() != itemsize) {
        throw py::type_error(std::string(name) + " must have dtype " + required + ", got " +
                             dtype_name(a) + "; convert explicitly with np.asarray(..., dtype=...)");
    }
    // '=' is native, '<' and '>' are explicit. '|' is byte-order-not-applicable
    // and only a one-byte type can carry it, which the itemsize check above has
    // already restricted to uint8.
    const char order = dtype.byteorder();
    if (order != '=' && order != '|' && order != '<' && order != '>') {
        throw py::value_error(std::string(name) + " has an unrecognized byte order");
    }
    if (kind == 'f' && (order == '<' || order == '>')) {
        // A byte-swapped float64 would be read as garbage. Refusing is the only
        // honest option: NumPy has no flag for this because it never produces
        // such an array except by an explicit .astype(">f8").
        throw py::value_error(std::string(name) +
                              " is not in native byte order, which would be misread as float64; "
                              "convert with np.asarray(..., dtype=np.float64)");
    }
}

}  // namespace detail

// A 1-D float64 array, C-contiguous and native byte order, or a ValueError
// naming `name`. Throws TypeError for a wrong dtype and ValueError for a wrong
// shape or layout, which is the split the Python wrapper documents.
inline View<Real> real_1d(const py::object& obj, const char* name) {
    if (!py::isinstance<py::array>(obj)) {
        throw py::type_error(std::string(name) + " must be a NumPy array");
    }
    const auto a = py::reinterpret_borrow<py::array>(obj);
    detail::require_kind(a, 'f', static_cast<py::ssize_t>(sizeof(Real)), name, "float64");
    if (a.ndim() != 1) {
        throw py::value_error(std::string(name) + " must be 1-dimensional, got " +
                              std::to_string(a.ndim()) + " dimensions");
    }
    if (!(a.flags() & py::array::c_style)) {
        throw py::value_error(std::string(name) + " must be C-contiguous");
    }
    return View<Real>{static_cast<const Real*>(a.data()), a.size()};
}

// The same, for the event type array. M <= 256 is enforced in validation.cpp,
// which is why the dtype is one byte wide.
inline View<std::uint8_t> uint8_1d(const py::object& obj, const char* name) {
    if (!py::isinstance<py::array>(obj)) {
        throw py::type_error(std::string(name) + " must be a NumPy array");
    }
    const auto a = py::reinterpret_borrow<py::array>(obj);
    detail::require_kind(a, 'u', 1, name, "uint8");
    if (a.ndim() != 1) {
        throw py::value_error(std::string(name) + " must be 1-dimensional, got " +
                              std::to_string(a.ndim()) + " dimensions");
    }
    if (!(a.flags() & py::array::c_style)) {
        throw py::value_error(std::string(name) + " must be C-contiguous");
    }
    return View<std::uint8_t>{static_cast<const std::uint8_t*>(a.data()), a.size()};
}

// A float64 parameter block, flattened to the row-major order the core reads.
//
// 1-D and 2-D are both accepted because a shape carries no information the
// parameter block does not: alpha and beta are M*M contiguous doubles either
// way, and the element count is checked against M by the caller. No copy: a
// C-contiguous 2-D array reshapes to a 1-D view of the same buffer.
inline View<Real> real_block(const py::object& obj, const char* name) {
    if (!py::isinstance<py::array>(obj)) {
        throw py::type_error(std::string(name) + " must be a NumPy array");
    }
    const auto a = py::reinterpret_borrow<py::array>(obj);
    detail::require_kind(a, 'f', static_cast<py::ssize_t>(sizeof(Real)), name, "float64");
    if (a.ndim() != 1 && a.ndim() != 2) {
        throw py::value_error(std::string(name) + " must be 1- or 2-dimensional, got " +
                              std::to_string(a.ndim()) + " dimensions");
    }
    if (!(a.flags() & py::array::c_style)) {
        throw py::value_error(std::string(name) + " must be C-contiguous");
    }
    return View<Real>{static_cast<const Real*>(a.data()), a.size()};
}

inline void require_size(py::ssize_t actual, py::ssize_t expected, const char* name) {
    if (actual != expected) {
        throw py::value_error(std::string(name) + " has " + std::to_string(actual) +
                              " entries, expected " + std::to_string(expected));
    }
}

// The data address of any C-contiguous array, for the zero-copy test. Private:
// it exists so that a test can compare the pointer the core received with the
// one Python knows, and it is not part of the public surface.
inline std::uintptr_t address_of(const py::object& obj) {
    if (!py::isinstance<py::array>(obj)) {
        throw py::type_error("address_of expects a NumPy array");
    }
    const auto a = py::reinterpret_borrow<py::array>(obj);
    return reinterpret_cast<std::uintptr_t>(a.data());
}

}  // namespace hawkes::pybindings
