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
    version: str
    compiler: str
    compiler_version: str
    pybind11_version: str

class CoreResult(TypedDict, total=False):
    value: float
    dmu: npt.NDArray[np.float64]
    dalpha: npt.NDArray[np.float64]
    dbeta: npt.NDArray[np.float64]

def build_info() -> BuildInfo:
    """Return the version and compiler used to build this module."""
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

def simulate(
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
    T: float,
    method: str,
    seed: int,
    t0: float = ...,
    burn_in: float = ...,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.uint8]]:
    """Simulate on [t0, T) with the named algorithm."""
    ...

def time_rescale(
    times: npt.NDArray[np.float64],
    types: npt.NDArray[np.uint8],
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
) -> list[npt.NDArray[np.float64]]:
    """Rescaled gaps per type."""
    ...

def seed_stream(seed: int, index: int) -> int:
    """Seed of the index-th independent stream."""
    ...

def spectral_radius(
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
) -> float:
    """Spectral radius of alpha / beta."""
    ...

def stationary_mean(
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """(I - Gamma)^{-1} mu."""
    ...

# Private hooks read only by tests/test_zero_copy.py, which asserts that the
# core receives the caller's buffer rather than a copy of it.
def _view_addresses(
    times: npt.NDArray[np.float64],
    types: npt.NDArray[np.uint8],
    mu: npt.NDArray[np.float64],
    alpha: npt.NDArray[np.float64],
    beta: npt.NDArray[np.float64],
    T: float,
    M: int,
    shared_decay: bool = ...,
) -> tuple[int, int, int, int, int]:
    """Data addresses the core resolves for each argument."""
    ...

def _array_address(array: npt.NDArray[np.generic]) -> int:
    """Data address of a C-contiguous array."""
    ...
