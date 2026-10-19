"""Multi-dimensional Hawkes process library with trust calibration.

Pre-alpha. The compiled likelihood and its gradient, the maximum-likelihood
estimator with its standard errors, both exact simulators, the time-rescaling
diagnostics, the stability quantities and the reliability report are in place.
The calibration map that says how much to trust an estimate in a given region is
the subject of gate H6. See ``docs/ROADMAP.md``.

The surface below is the whole of the public API. Anything not named here --
the compiled module, the layout and bootstrap internals, the log-space
objective, the self-test -- is private and may change without notice.
"""

from hawkes_engine.diagnostics import ks_test, qq_data, time_rescale
from hawkes_engine.fit import fit
from hawkes_engine.loglik import LoglikResult, loglik
from hawkes_engine.model import FitResult
from hawkes_engine.simulation import simulate, simulate_many
from hawkes_engine.stability import spectral_radius, stationary_mean
from hawkes_engine.trust import report

__version__ = "0.1.0.dev0"
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
    "spectral_radius",
    "stationary_mean",
]
