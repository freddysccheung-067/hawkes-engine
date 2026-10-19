"""Multi-dimensional Hawkes process library with trust calibration.

Pre-alpha. The compiled likelihood and its gradient are in place, as is the
maximum-likelihood estimator with its standard errors and its reliability
verdict. The simulators and the calibration map land over gates H4-H6. See
docs/ROADMAP.md.
"""

from hawkes_engine._core import build_info
from hawkes_engine.fit import fit
from hawkes_engine.loglik import LoglikResult, loglik, loglik_grad_log_space
from hawkes_engine.model import FitResult

__version__ = "0.1.0.dev0"
__license__ = "MIT"

__all__ = [
    "__version__",
    "build_info",
    "fit",
    "FitResult",
    "loglik",
    "loglik_grad_log_space",
    "LoglikResult",
]
