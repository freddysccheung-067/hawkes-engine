"""Argument conversion at the Python boundary.

The compiled core reads exactly what it can read without copying: float64 or
uint8, C-contiguous, native byte order, one dimension, and the shape the
callee's parameter block requires. This module is the single place that turns
whatever the caller passed into such an array, so the conversion is explicit in
one file instead of implicit in six bindings.

An argument that is already in that form is returned unchanged, which is what
``np.ascontiguousarray`` does for a conforming array and what makes the
zero-copy path in ``tests/test_zero_copy.py`` observable: the data pointer the
core receives is the caller's.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

__all__ = ["as_real_1d", "as_real_2d", "as_uint8_1d", "flat"]

RealArray = npt.NDArray[np.float64]


def as_real_1d(value: npt.ArrayLike, name: str) -> RealArray:
    """A 1-D C-contiguous float64 array, converting only if it is not one."""
    arr = np.ascontiguousarray(value, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-dimensional, got shape {arr.shape}")
    return arr


def as_real_2d(value: npt.ArrayLike, name: str) -> RealArray:
    """A 2-D C-contiguous float64 array, converting only if it is not one."""
    arr = np.ascontiguousarray(value, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be 2-dimensional, got shape {arr.shape}")
    return arr


def as_uint8_1d(value: npt.ArrayLike, name: str) -> npt.NDArray[np.uint8]:
    """A 1-D C-contiguous uint8 array, refusing values that would not survive.

    ``np.asarray(x, dtype=np.uint8)`` wraps: 256 becomes 0 and 1.7 becomes 1,
    both silently. A wrong type index produces a plausible likelihood for the
    wrong model, so the range and integrality are checked on the original values
    before the cast.
    """
    arr = np.asarray(value)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-dimensional, got shape {arr.shape}")
    if arr.size and arr.dtype.kind in "iuf":
        bad = np.flatnonzero((arr < 0) | (arr > 255))
        if bad.size:
            i = int(bad[0])
            raise ValueError(f"{name} has {arr[i]!r} at index {i}, outside 0..255")
        if arr.dtype.kind == "f" and not np.all(arr == np.floor(arr)):
            i = int(np.flatnonzero(arr != np.floor(arr))[0])
            raise ValueError(f"{name} has the non-integral value {arr[i]!r} at index {i}")
    return np.ascontiguousarray(arr, dtype=np.uint8)


def flat(arr: npt.NDArray[np.float64]) -> RealArray:
    """A 1-D view of a C-contiguous array. Never copies; asserts that in tests."""
    return arr.reshape(-1)
