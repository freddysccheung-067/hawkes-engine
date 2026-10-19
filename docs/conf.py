"""Sphinx configuration for hawkes-engine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

project = "hawkes-engine"
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
# STATE.md is a maintainer note, not a published page; excluding it keeps
# sphinx-build -W from reporting it as an orphan.
exclude_patterns = [
    "_build",
    "adr/**",
    "spec/**",
    "competitor-analysis.md",
    "STATE.md",
]

autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True
