"""Goodness of fit by time rescaling (mathematics.md section 8).

If the model is right, the rescaled gaps ``tau^i_k`` are independent Exp(1)
variables (Papangelou). The Kolmogorov-Smirnov test checks the marginal law and
the Ljung-Box test checks independence. **Both must pass**: KS alone is blind to
dependence, so a model that gets the clustering wrong can still produce gaps
with a perfect Exp(1) histogram.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import stats  # type: ignore[import-untyped,unused-ignore]

from hawkes_engine import _core
from hawkes_engine._arrays import as_real_1d, as_real_2d, as_uint8_1d, flat

__all__ = ["TestResult", "ks_test", "ljung_box", "qq_data", "time_rescale"]

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class TestResult:
    """A test statistic and its p-value, per type."""

    __test__ = False

    statistic: FloatArray
    pvalue: FloatArray


def time_rescale(
    times: npt.ArrayLike,
    types: npt.ArrayLike,
    mu: npt.ArrayLike,
    alpha: npt.ArrayLike,
    beta: npt.ArrayLike,
) -> list[FloatArray]:
    """Rescaled gaps for each type, in event order.

    Parameters
    ----------
    times
        Event times, shape ``(N,)``, non-decreasing.
    types
        Type index of each event, shape ``(N,)``, in ``0..M-1``.
    mu, alpha, beta
        Parameters to rescale under, with the shapes :func:`hawkes_engine.loglik`
        documents. ``M`` is the length of ``mu``.

    Returns
    -------
    list of numpy.ndarray
        One float64 array per type. Under the true parameters each is
        independent Exp(1) (mathematics.md section 8), which is what
        :func:`ks_test` and :func:`ljung_box` test.

    Notes
    -----
    The first gap of each type runs from time 0. The stretch after a type's last
    event is not a gap and is dropped. A type with no events yields an empty
    array, not an error.

    Raises ``ValueError`` if the events are unsorted or a type index is not less
    than ``M``.
    """
    t = as_real_1d(times, "times")
    k = as_uint8_1d(types, "types")
    m = as_real_1d(mu, "mu")
    a = as_real_2d(alpha, "alpha")
    b = as_real_2d(beta, "beta")
    dim = int(m.shape[0])
    if a.shape != (dim, dim) or b.shape != (dim, dim):
        raise ValueError(f"alpha and beta must have shape ({dim}, {dim}) for mu of length {dim}")
    return _core.time_rescale(t, k, m, flat(a), flat(b))


def ks_test(gaps: list[FloatArray]) -> TestResult:
    """One-sample KS test of each type's gaps against Exp(1).

    Parameters
    ----------
    gaps
        Rescaled gaps, one array per type, as returned by :func:`time_rescale`.

    Returns
    -------
    TestResult
        ``statistic`` and ``pvalue``, one entry per element of ``gaps``.

    Notes
    -----
    Per type, so an empty type gets ``nan`` rather than ``1.0``: there is nothing
    to test, and a pass would read as evidence. Use it together with
    :func:`ljung_box`; the marginal law can be right while the dependence is
    wrong.
    """
    stat = np.full(len(gaps), np.nan)
    pval = np.full(len(gaps), np.nan)
    for i, g in enumerate(gaps):
        if g.size:
            r = stats.kstest(g, "expon")
            stat[i], pval[i] = r.statistic, r.pvalue
    return TestResult(stat, pval)


def ljung_box(gaps: list[FloatArray], lags: int = 10) -> TestResult:
    """Ljung-Box test of independence of each type's gaps.

    ``Q = n (n + 2) sum_{k<=h} r_k^2 / (n - k)`` against chi-square with ``h``
    degrees of freedom, where ``r_k`` is the lag-k sample autocorrelation. No
    parameters are fitted to the gaps, so no degrees of freedom are removed. The
    lag count is capped at ``n // 4`` for short series.
    """
    stat = np.full(len(gaps), np.nan)
    pval = np.full(len(gaps), np.nan)
    for i, g in enumerate(gaps):
        h = min(lags, g.size // 4)
        if h < 1:
            continue
        x = g - g.mean()
        denom = float(x @ x)
        if denom == 0.0:
            # A constant series has no autocorrelation to test. nan, not 1.0:
            # an untestable series is not evidence of independence.
            continue
        k = np.arange(1, h + 1)
        r = np.array([float(x[:-j] @ x[j:]) for j in k]) / denom
        q = g.size * (g.size + 2) * float(np.sum(r**2 / (g.size - k)))
        stat[i], pval[i] = q, stats.chi2.sf(q, h) if math.isfinite(q) else np.nan
    return TestResult(stat, pval)


def qq_data(gaps: list[FloatArray]) -> list[tuple[FloatArray, FloatArray]]:
    """``(theoretical, sample)`` quantile pairs against Exp(1), per type.

    Parameters
    ----------
    gaps
        Rescaled gaps, one array per type, as returned by :func:`time_rescale`.

    Returns
    -------
    list of tuple of numpy.ndarray
        Per type, the theoretical quantiles and the sorted sample. Plot them
        with ``matplotlib.pyplot.plot``; this module does not import pyplot, so
        a caller who never draws a plot never loads it.

    Notes
    -----
    Theoretical quantiles use the plotting positions ``(k - 1/2) / n``, which
    keep every point inside ``(0, 1)`` so the logarithm is finite.
    """
    out = []
    for g in gaps:
        n = g.size
        p = (np.arange(1, n + 1) - 0.5) / n if n else np.empty(0)
        out.append((-np.log1p(-p), np.sort(g)))
    return out
