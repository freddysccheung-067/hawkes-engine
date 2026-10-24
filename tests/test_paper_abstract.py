"""The plain-text abstract and the one the paper renders must be the same text.

`paper/SUBMISSION.md` carries a plain-text block for the arXiv metadata form and
says it is what `paper/generated/abstract.tex` renders. Nothing checked that, and
they had drifted: the rendered abstract said two hypotheses were "refuted", which
is stronger than the pre-registered verdict ("not confirmed", because H6.3's
threshold clause held and only its monotonicity clause failed), while the block
to be pasted into the form said "not confirmed". The form is the text a reader
sees first when the paper has no PDF in front of them, so the two disagreeing is
a defect in whatever a reader trusts.

This test expands the generated abstract exactly as the TeX would, then compares
word for word against the block in the submission checklist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ABSTRACT = ROOT / "paper" / "generated" / "abstract.tex"
MAIN = ROOT / "paper" / "main.tex"
SUBMISSION = ROOT / "paper" / "SUBMISSION.md"

MACRO = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{((?:[^{}]|\{[^{}]*\})*)\}")
BLOCK = re.compile(r"```\n(This paper measures.*?)\n```", re.S)


def _rendered() -> list[str]:
    """The abstract as a reader sees it: macros expanded, math made plain."""
    macros = dict(MACRO.findall(MAIN.read_text(encoding="utf-8")))
    text = ABSTRACT.read_text(encoding="utf-8")

    # Longest name first, so \HsixCell never eats \HsixCells.
    for name in sorted(macros, key=len, reverse=True):
        text = text.replace("\\" + name + "{}", macros[name])
        text = text.replace("\\" + name, macros[name])

    text = text.replace("$\\pm$", "+/-")
    text = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", text)
    return text.split()


def _pasted() -> list[str]:
    found = BLOCK.search(SUBMISSION.read_text(encoding="utf-8"))
    assert found, "SUBMISSION.md no longer carries the plain-text abstract block"
    return found.group(1).split()


def test_the_pasted_abstract_is_what_the_paper_renders():
    rendered, pasted = _rendered(), _pasted()
    if rendered != pasted:
        import difflib

        diff = "\n".join(
            difflib.unified_diff(rendered, pasted, "rendered", "pasted", lineterm="", n=3)
        )
        pytest.fail(f"the abstract to paste differs from the rendered one:\n{diff}")


def test_the_abstract_fits_the_form():
    """arXiv takes 1920 characters, and a word count under 200 is the usual rule."""
    pasted = " ".join(_pasted())
    assert len(pasted) <= 1920, f"{len(pasted)} characters, over the 1920 limit"
    assert len(pasted.split()) <= 200


def test_no_unexpanded_macros_reach_the_form():
    pasted = " ".join(_pasted())
    assert "\\" not in pasted, f"a LaTeX macro survived into the plain-text block: {pasted}"
    assert "$" not in pasted
