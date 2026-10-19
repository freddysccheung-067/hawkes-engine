"""Type stubs for the compiled extension module.

The extension is a compiled artifact, so it is not present when a type checker
or a linter reads the source tree. These stubs describe the surface that
``CMakeLists.txt`` and ``cpp/src/_core.cpp`` build.
"""

from typing import TypedDict

class BuildInfo(TypedDict):
    cxx_standard: int
    compiler: str
    compiler_version: str
    pybind11_version: str

def build_info() -> BuildInfo:
    """Return the compiler and pybind11 versions used to build this module."""
    ...
