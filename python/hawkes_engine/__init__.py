"""Multi-dimensional Hawkes process library with trust calibration.

Pre-alpha. The compiled likelihood and its gradient, the maximum-likelihood
estimator with its standard errors, both exact simulators, the time-rescaling
diagnostics, the stability quantities, the reliability report and the measured
trust map are in place. ``trust_lookup`` answers from the H6 study: it returns
measured coverage and SE honesty for the nearest measured regime, ``"unknown"``
outside the measured box, and ``"estimator undefined in this regime"`` where the
estimator does not exist.

The surface below is the whole of the public API. Anything not named here --
the compiled module, the layout and bootstrap internals, the log-space
objective, the self-test -- is private and may change without notice.
"""

from hawkes_engine._version import __version__
from hawkes_engine.diagnostics import ks_test, qq_data, time_rescale
from hawkes_engine.fit import fit
from hawkes_engine.loglik import LoglikResult, loglik
from hawkes_engine.model import FitResult
from hawkes_engine.simulation import simulate, simulate_many
from hawkes_engine.stability import spectral_radius, stationary_mean
from hawkes_engine.trust import report
from hawkes_engine.trust_map import MapAnswer
from hawkes_engine.trust_map import lookup as trust_lookup

__license__ = "MIT"

__all__ = [
    "__version__",
    "fit",
    "FitResult",
    "simulate",
    "simulate_many",
    "loglik",
    "LoglikResult",
    "time_rescale",
    "ks_test",
    "qq_data",
    "report",
    "trust_lookup",
    "MapAnswer",
    "spectral_radius",
    "stationary_mean",
]
