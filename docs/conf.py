"""Sphinx configuration for hawkes-engine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))
sys.path.insert(0, str(Path(__file__).parent))

import _gen  # noqa: E402
from hawkes_engine._version import __version__ as _version  # noqa: E402

# Fragments copied from committed measurements (docs/_gen.py). Rebuilt on every
# build, gitignored, and pulled into pages with the MyST include directive.
_gen.generate(Path(__file__).parent / "_generated")

project = "hawkes-engine"
# Read from the package rather than written here, so the documentation cannot
# claim a version the wheel does not have. tests/test_version.py checks the same
# string against pyproject.toml, CMakeLists.txt, CITATION.cff and the core.
release = _version
version = ".".join(release.split(".")[:2])
author = "Freddy Shi Chun Cheung"
copyright = "2026, Freddy Shi Chun Cheung"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_enable_extensions = ["dollarmath", "amsmath", "colon_fence"]

root_doc = "index"

html_theme = "sphinx_rtd_theme"
html_static_path: list[str] = []
html_title = "hawkes-engine"

# Only the user-facing pages are published. The specification and the ADRs stay
# in the repository: they matter to maintainers and are noise on a docs site.
# Excluding them here keeps sphinx-build -W quiet about orphans.
# STATE.md and preregistration.md are maintainer and referee documents, not
# published pages; excluding them keeps sphinx-build -W from reporting them as
# orphans. The pre-registration is read at the tag, where its text is frozen.
# _generated holds include fragments, not pages.
exclude_patterns = [
    "_build",
    "adr/**",
    "spec/**",
    "competitor-analysis.md",
    "STATE.md",
    "preregistration.md",
    "preregistration_auto.md",
    # The maintainer's release checklist: repository-only, like STATE.md.
    "RELEASING.md",
    "_generated",
    "_gen.py",
]

autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True
