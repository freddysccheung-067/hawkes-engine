"""The one place the version string is written in Python.

Every other place that names a version -- ``pyproject.toml``, ``CMakeLists.txt``,
``CITATION.cff``, ``docs/conf.py`` and ``CHANGELOG.md`` -- is checked against
this module by ``tests/test_version.py``. The compiled core carries its own copy
because CMake stamps ``PROJECT_VERSION`` into the extension at compile time;
``_core.build_info()["version"]`` is that copy, and the test compares it too.

A version is not a private detail here. A wheel that reports one version in
``__version__`` and another in its metadata is a wheel whose bug reports cannot
be matched to a source tree.
"""

from __future__ import annotations

__version__ = "0.2.0"

#: The version as a tuple, for callers that want to compare without parsing.
__version_tuple__ = tuple(int(part) for part in __version__.split("."))

__all__ = ["__version__", "__version_tuple__"]
