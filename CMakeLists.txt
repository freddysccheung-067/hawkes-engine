cmake_minimum_required(VERSION 3.24)

project(hawkes_engine LANGUAGES CXX VERSION 0.1.0)

# C++20 is required by ADR-001. No compiler-specific optimisation flags are added
# here; ADR-006 governs those and they must stay portable.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

option(HAWKES_BUILD_TESTS "Build the Catch2 test suite" OFF)
# Warnings are always on; promoting them to errors is opt-in so that installing
# from source on a compiler whose diagnostic set is wider than the one the code
# was developed against does not fail outright. The dev preset turns it on, so
# CI still enforces a warning-free build on at least one configuration.
option(HAWKES_WERROR "Treat warnings as errors" OFF)

add_library(hawkes_core STATIC
    cpp/src/loglik.cpp
    cpp/src/loglik_shared.cpp
    cpp/src/validation.cpp
    cpp/src/workspace.cpp
)
target_include_directories(hawkes_core PUBLIC cpp/include)

# Sanitizers for local and CI verification (ADR-006). Never part of a wheel.
set(HAWKES_SANITIZE "" CACHE STRING "address, undefined, or empty")
if(HAWKES_SANITIZE)
    if(MSVC)
        message(FATAL_ERROR "HAWKES_SANITIZE is not supported on MSVC")
    endif()
    # PUBLIC, not PRIVATE: hawkes_core is a static library, so flags attached
    # to it privately never reach the final link of the test executable. The
    # link then has instrumented objects and no runtime, which fails with
    # undefined __asan_* symbols. Both the compile flags and the link flag have
    # to propagate to anything that links the core.
    target_compile_options(hawkes_core PUBLIC -fsanitize=${HAWKES_SANITIZE}
                                               -fno-omit-frame-pointer
                                               -fno-sanitize-recover=all)
    target_link_options(hawkes_core INTERFACE -fsanitize=${HAWKES_SANITIZE})
endif()

# Deterministic floating point. ADR-006: -ffast-math is forbidden because the
# likelihood uses -inf as a value, and /fp:fast on MSVC has the same defect.
if(MSVC)
    target_compile_options(hawkes_core PRIVATE /W4 /permissive- /fp:precise)
    if(HAWKES_WERROR)
        target_compile_options(hawkes_core PRIVATE /WX)
    endif()
else()
    # Exactly the documented warning set. -Wconversion and -Wshadow were
    # removed: they are not part of the contract, and GCC's diagnostic set is
    # wider than MSVC's or Apple clang's, so they turned a portable build into
    # a GCC-only failure.
    target_compile_options(hawkes_core PRIVATE -Wall -Wextra -Wpedantic -fno-fast-math)
    if(HAWKES_WERROR)
        target_compile_options(hawkes_core PRIVATE -Werror)
    endif()
endif()

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core MODULE cpp/src/_core.cpp cpp/src/bindings.cpp)
target_link_libraries(_core PRIVATE hawkes_core)
target_include_directories(_core PRIVATE cpp/include)

install(TARGETS _core DESTINATION hawkes_engine)

# User opt-in native build, per ADR-006. Off by default so published wheels stay
# portable across every x86-64 machine.
option(NATIVE_OPTIMIZATIONS "Build for the host CPU (-march=native)" OFF)
if(NATIVE_OPTIMIZATIONS)
    if(MSVC)
        message(WARNING "NATIVE_OPTIMIZATIONS has no effect on MSVC builds")
    else()
        target_compile_options(hawkes_core PRIVATE -march=native)
    endif()
endif()

if(HAWKES_BUILD_TESTS)
    enable_testing()
    include(FetchContent)
    FetchContent_Declare(
        Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG v3.5.4
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(Catch2)
    add_executable(hawkes_tests
        cpp/tests/test_loglik.cpp
        cpp/tests/test_allocation.cpp
    )
    target_link_libraries(hawkes_tests PRIVATE hawkes_core Catch2::Catch2WithMain)
    target_include_directories(hawkes_tests PRIVATE cpp/include)
    add_test(NAME hawkes_tests COMMAND hawkes_tests)
endif()
