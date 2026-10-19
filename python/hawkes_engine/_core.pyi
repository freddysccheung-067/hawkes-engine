"""Type stubs for the compiled extension module.

The extension is a compiled artifact, so it is not present when a type checker
or a linter reads the source tree. These stubs describe the surface that
``CMakeLists.txt`` and ``cpp/src/bindings.cpp`` build.
"""

from typing import TypedDict

import numpy as np
import numpy.typing as npt

class BuildInfo(TypedDict):
    cxx_standard: int
    compiler: str
    compiler_version: str
    pybind11_version: str

class CoreResult(TypedDict, total=False):
    value: float
    dmu: npt.NDArray[np.float64]
    dalpha: npt.NDArray[np.float64]
    dbeta: npt.NDArray[np.float64]

def build_info() -> BuildInfo:
    """Return the compiler and pybind11 versions used to build this module."""
    ...

def loglik(
    times: npt.NDArray[np.float64],
    types: npt.NDArray[np.uint8],
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
    T: float,
    M: int,
    shared_decay: bool = ...,
    grad: bool = ...,
) -> CoreResult:
    """Log-likelihood, optionally with the natural-space gradient."""
    ...

def loglik_grad_log_space(
    times: npt.NDArray[np.float64],
    types: npt.NDArray[np.uint8],
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
    T: float,
    M: int,
    shared_decay: bool = ...,
) -> CoreResult:
    """Log-likelihood with the gradient in log space."""
    ...
