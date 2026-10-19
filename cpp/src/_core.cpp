// Compiled core of hawkes-engine.
//
// H1 ships only the build plumbing: this module proves that the extension
// compiles and imports on every supported platform, so H2 can add the
// likelihood recursion without also debugging the toolchain.

#include <string>

#include <pybind11/pybind11.h>

namespace py = pybind11;

void register_loglik(py::module_& m);

namespace {

py::dict build_info() {
    py::dict info;
    info["cxx_standard"] = 20;

#if defined(__clang__)
    info["compiler"] = "clang";
    info["compiler_version"] =
        std::to_string(__clang_major__) + "." + std::to_string(__clang_minor__);
#elif defined(_MSC_VER)
    info["compiler"] = "msvc";
    info["compiler_version"] = std::to_string(_MSC_VER);
#elif defined(__GNUC__)
    info["compiler"] = "gcc";
    info["compiler_version"] =
        std::to_string(__GNUC__) + "." + std::to_string(__GNUC_MINOR__);
#else
    info["compiler"] = "unknown";
    info["compiler_version"] = "unknown";
#endif

    info["pybind11_version"] = std::to_string(PYBIND11_VERSION_MAJOR) + "." +
                               std::to_string(PYBIND11_VERSION_MINOR) + "." +
                               std::to_string(PYBIND11_VERSION_PATCH);
    return info;
}

}  // namespace

PYBIND11_MODULE(_core, m) {
    m.doc() = "Native core of hawkes-engine.";
    m.def("build_info", &build_info,
          "Return the compiler and pybind11 versions used to build this module.");

    register_loglik(m);
}
