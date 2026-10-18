cmake_minimum_required(VERSION 3.18)
project(hawkes_engine LANGUAGES CXX)

# C++20 required (per ADR-001)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Find Python and pybind11
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

# Empty for now — H2 will add C++ sources
# This file just needs to exist for scikit-build-core to work

# Placeholder comment: C++ extension will be added in H2
# For now, package installs as pure Python
