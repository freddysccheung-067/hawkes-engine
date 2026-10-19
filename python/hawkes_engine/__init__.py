"""Multi-dimensional Hawkes process library with trust calibration.

Pre-alpha. The compiled likelihood and its gradient are in place; the
estimator, the simulators and the trust map land over gates H3-H6, and until
they do there is nothing here that fits a model. See docs/ROADMAP.md.
"""

from hawkes_engine._core import build_info
from hawkes_engine.loglik import LoglikResult, loglik, loglik_grad_log_space

__version__ = "0.1.0.dev0"
__license__ = "MIT"

__all__ = [
    "__version__",
    "build_info",
    "loglik",
    "loglik_grad_log_space",
    "LoglikResult",
]
