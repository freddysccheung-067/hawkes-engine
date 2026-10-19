"""Goodness of fit by time rescaling (mathematics.md section 8).

If the model is right, the rescaled gaps ``tau^i_k`` are independent Exp(1)
variables (Papangelou). The Kolmogorov-Smirnov test checks the marginal law and
the Ljung-Box test checks independence. **Both must pass**: KS alone is blind to
dependence, so a model that gets the clustering wrong can still produce gaps
with a perfect Exp(1) histogram.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import stats  # type: ignore[import-untyped,unused-ignore]

from hawkes_engine import _core

__all__ = ["TestResult", "ks_test", "ljung_box", "qq_data", "qq_plot", "time_rescale"]

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

    The first gap of each type runs from time 0. The stretch after a type's last
    event is not a gap and is dropped.
    """
    return _core.time_rescale(
        np.ascontiguousarray(times, dtype=np.float64),
        np.ascontiguousarray(types, dtype=np.uint8),
        np.ascontiguousarray(mu, dtype=np.float64),
        np.ascontiguousarray(alpha, dtype=np.float64),
        np.ascontiguousarray(beta, dtype=np.float64),
    )


def ks_test(gaps: list[FloatArray]) -> TestResult:
    """One-sample KS test of each type's gaps against Exp(1)."""
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
        k = np.arange(1, h + 1)
        r = np.array([float(x[:-j] @ x[j:]) for j in k]) / denom
        q = g.size * (g.size + 2) * float(np.sum(r**2 / (g.size - k)))
        stat[i], pval[i] = q, stats.chi2.sf(q, h)
    return TestResult(stat, pval)


def qq_data(gaps: list[FloatArray]) -> list[tuple[FloatArray, FloatArray]]:
    """``(theoretical, sample)`` quantile pairs against Exp(1), per type."""
    out = []
    for g in gaps:
        n = g.size
        p = (np.arange(1, n + 1) - 0.5) / n if n else np.empty(0)
        out.append((-np.log1p(-p), np.sort(g)))
    return out


def qq_plot(gaps: list[FloatArray]):  # type: ignore[no-untyped-def]
    """Q-Q plot against Exp(1); needs matplotlib, an optional dependency."""
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found,unused-ignore]
    except ImportError as exc:
        raise ImportError(
            "qq_plot needs matplotlib, which is optional: pip install matplotlib"
        ) from exc
    fig, axes = plt.subplots(1, len(gaps), squeeze=False, figsize=(4 * len(gaps), 4))
    for ax, (theo, samp) in zip(axes[0], qq_data(gaps), strict=True):
        ax.plot(theo, samp, ".", markersize=3)
        top = max(float(np.max(theo, initial=1.0)), float(np.max(samp, initial=1.0)))
        ax.plot([0, top], [0, top], "k--", linewidth=1)
        ax.set_xlabel("Exp(1) quantile")
        ax.set_ylabel("rescaled gap")
    return fig
