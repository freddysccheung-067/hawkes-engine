"""Multi-dimensional Hawkes process library with trust calibration.

Pre-alpha: only the compiled core and packaging are in place. The estimator,
simulators and trust map land over gates H2-H6; see docs/ROADMAP.md.
"""

from hawkes_engine._core import build_info

__version__ = "0.1.0.dev0"
__license__ = "MIT"

__all__ = ["__version__", "build_info"]
