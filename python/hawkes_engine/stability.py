"""Stability quantities of the branching matrix.

Both are properties of the parameters alone, not of a sample: ``rho(Gamma)`` is
the branching ratio, and the stationary mean is what the process would settle to
if it ran undisturbed. They are exposed because a user who has parameters from
any source -- a fit, a paper, a prior -- needs to know whether the process they
describe is subcritical before simulating it or trusting a likelihood.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from hawkes_engine import _core
from hawkes_engine._arrays import as_real_1d, as_real_2d, flat

__all__ = ["spectral_radius", "stationary_mean"]


def _blocks(
    mu: npt.ArrayLike, alpha: npt.ArrayLike, beta: npt.ArrayLike
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    m = as_real_1d(mu, "mu")
    a = as_real_2d(alpha, "alpha")
    b = as_real_2d(beta, "beta")
    dim = int(m.shape[0])
    if a.shape != (dim, dim) or b.shape != (dim, dim):
        raise ValueError(f"alpha and beta must have shape ({dim}, {dim}) for mu of length {dim}")
    return m, flat(a), flat(b), dim


def spectral_radius(mu: npt.ArrayLike, alpha: npt.ArrayLike, beta: npt.ArrayLike) -> float:
    """``rho(Gamma)`` for ``Gamma = alpha / beta``: the branching ratio.

    Parameters
    ----------
    mu
        Baseline intensities, shape ``(M,)``. Unused by the computation but part
        of the parameter set, so it is required and validated here rather than
        silently defaulted.
    alpha, beta
        Excitation and decay blocks, shape ``(M, M)``, with ``beta`` strictly
        positive.

    Returns
    -------
    float
        The Perron root of the entrywise non-negative matrix ``Gamma``,
        certified to a bracket width below 1e-13.

    Notes
    -----
    A value at or above 1 means the process is supercritical: no stationary
    distribution exists, and simulation refuses the parameters. The function
    itself reports the value for any parameters, because knowing *how* far past
    criticality a set is is often the question.
    """
    m, a, b, _ = _blocks(mu, alpha, beta)
    return float(_core.spectral_radius(m, a, b))


def stationary_mean(
    mu: npt.ArrayLike, alpha: npt.ArrayLike, beta: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """``(I - Gamma)^{-1} mu``: the mean intensity of the stationary process.

    Parameters
    ----------
    mu, alpha, beta
        As for :func:`spectral_radius`.

    Returns
    -------
    numpy.ndarray
        Shape ``(M,)``, float64. A new array, writable, with no reference to the
        arguments.

    Raises
    ------
    ValueError
        When ``rho(Gamma) >= 1``: the inverse does not exist as a positive
        quantity, and the answer would be a meaningless sign pattern rather than
        a mean.
    """
    m, a, b, _ = _blocks(mu, alpha, beta)
    return _core.stationary_mean(m, a, b)
