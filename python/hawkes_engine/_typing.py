"""Type aliases shared across the package.

Kept in one module so that a signature in ``fit``, ``hessian`` and ``trust``
spells the same type the same way, and so ``mypy --strict`` has one place to
look when a NumPy dtype leaks into an annotation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
IndexArray = npt.NDArray[np.intp]

# A callable that maps a free-parameter vector to the gradient of the
# log-likelihood in those same coordinates.
GradientFn = Callable[[FloatArray], FloatArray]

# Standard errors or estimates keyed by parameter family: "mu", "alpha", "beta".
FamilyArrays = dict[str, FloatArray]

JsonObject = dict[str, Any]
