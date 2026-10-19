cmake_minimum_required(VERSION 3.24)

project(hawkes_engine LANGUAGES CXX VERSION 0.1.0)

# C++20 is required by ADR-001. No compiler-specific flags are added here;
# ADR-006 governs optimisation settings and they must stay portable.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_core MODULE cpp/src/_core.cpp)
target_include_directories(_core PRIVATE cpp/include)

install(TARGETS _core DESTINATION hawkes_engine)

# User opt-in native build, per ADR-006. Off by default so published wheels
# stay portable across every x86-64 machine.
option(NATIVE_OPTIMIZATIONS "Build for the host CPU (-march=native)" OFF)
if(NATIVE_OPTIMIZATIONS)
    if(MSVC)
        message(WARNING "NATIVE_OPTIMIZATIONS has no effect on MSVC builds")
    else()
        target_compile_options(_core PRIVATE -march=native)
    endif()
endif()
