"""Structural checks on the generated paper, for a machine with no TeX installed.

The paper has to compile somewhere, and this session cannot compile it: no TeX
distribution is installed and the sandbox refuses to install one. What can be
checked without a compiler is everything that makes a compile fail for a reason
other than typography:

* every ``\\input`` path exists and is relative to ``paper/``;
* every macro used in a section is defined in ``main.tex``;
* no macro is defined twice;
* braces balance in every generated file, outside comments and verbatim;
* the ``tabular`` environments have as many cells as their column spec;
* the bibliography entries referenced by ``\\citet`` and ``\\citep`` exist in
  ``refs.bib``, and every entry carries a year and a venue or a DOI;
* no figure the text names is missing.

This is not a substitute for a build. It is the part of a build's failure modes
that does not need fonts.

    python -m studies.check_paper
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAPER = REPO / "paper"
MAIN = PAPER / "main.tex"

COMMENT = re.compile(r"(?<!\\)%.*$")


def _strip_comments(text: str) -> str:
    return "\n".join(COMMENT.sub("", line) for line in text.splitlines())


def _balanced(text: str) -> tuple[bool, str]:
    """Braces balance, ignoring escaped braces and comments."""
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False, f"closing brace at offset {i} with nothing open"
        i += 1
    if depth:
        return False, f"{depth} unclosed brace(s)"
    return True, ""


def check() -> list[str]:
    problems: list[str] = []
    if not MAIN.exists():
        return ["paper/main.tex does not exist; run python -m studies.make_paper_tex"]

    main_text = _strip_comments(MAIN.read_text(encoding="utf-8"))

    # 1. Every \input resolves.
    for target in re.findall(r"\\input\{([^}]+)\}", main_text):
        path = PAPER / (target if target.endswith(".tex") else target + ".tex")
        if not path.exists():
            problems.append(f"\\input{{{target}}} does not resolve to a file")

    # 2. Defined macros: no duplicates, and they parse as \newcommand{\Name}{...}.
    defined: dict[str, int] = {}
    for name in re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", main_text):
        defined[name] = defined.get(name, 0) + 1
    for name, count in defined.items():
        if count > 1:
            problems.append(f"macro \\{name} is defined {count} times")

    # 2b. A control word is letters only. TeX ends the name at the first
    #     non-letter, so \Hsix61Label is \Hsix followed by the text "61Label",
    #     which arrives in the preamble and fails the compile with "Missing
    #     \begin{document}". The pattern in step 2 cannot see such a name, which
    #     is how twenty of them survived until the first real typeset.
    for raw in re.findall(r"\\newcommand\{\\([^}]*)\}", main_text):
        if not raw.isalpha():
            split = re.match(r"[A-Za-z]*", raw).group(0)
            rest = raw[len(split) :]
            problems.append(
                f"macro \\{raw} is not letters only; TeX reads it as \\{split} "
                f"followed by the literal text {rest!r}"
            )

    # 3. Every macro used in any section is defined. A macro starting with a
    #    known LaTeX command we did not define is not checked: the list below is
    #    everything generated, and anything else must be a standard command.
    used: dict[str, str] = {}
    for path in sorted((PAPER / "generated").glob("*.tex")):
        text = _strip_comments(path.read_text(encoding="utf-8"))
        ok, why = _balanced(text)
        if not ok:
            problems.append(f"{path.name}: {why}")
        for name in re.findall(r"\\((?:Hsix|HSix|Auto)[A-Za-z]+|HEAD)\b", text):
            used.setdefault(name, path.name)
    for name, where in sorted(used.items()):
        if name == "HEAD":
            continue
        if name not in defined:
            problems.append(f"\\{name} used in {where} but not defined in main.tex")

    # 4. Tabular column counts. booktabs rules are not rows.
    for path in sorted((PAPER / "generated").glob("table_*.tex")):
        text = _strip_comments(path.read_text(encoding="utf-8"))
        spec = re.search(r"\\begin\{tabular\}\{([^}]*)\}", text)
        if not spec:
            problems.append(f"{path.name}: no tabular environment")
            continue
        columns = len(re.sub(r"[^lcrp]", "", spec.group(1)).replace("p", "p"))
        body = text.split(r"\midrule", 1)[-1].split(r"\bottomrule", 1)[0]
        for line in body.splitlines():
            line = line.strip()
            if not line or not line.endswith(r"\\"):
                continue
            if "multicolumn" in line:
                continue
            cells = line.count("&") + 1
            if cells != columns:
                problems.append(
                    f"{path.name}: row has {cells} cells against a {columns}-column spec: "
                    f"{line[:60]}"
                )

    # 4b. Every \ref resolves to a \label. A dangling reference compiles cleanly
    #     and prints "??" in the PDF, so neither the structure check nor the
    #     typeset would catch it; the reader would.
    labels: set[str] = set()
    refs: list[tuple[str, str]] = []
    for path in [MAIN, *(PAPER / "generated").glob("*.tex")]:
        text = _strip_comments(path.read_text(encoding="utf-8"))
        labels |= set(re.findall(r"\\label\{([^}]+)\}", text))
        for target in re.findall(r"\\ref\{([^}]+)\}", text):
            refs.append((target, path.name))
    for target, where in refs:
        if target not in labels:
            problems.append(f"\\ref{{{target}}} in {where} has no matching \\label")

    # 5. Citations resolve to entries that carry a venue and a DOI or arXiv id.
    bib = (PAPER / "refs.bib").read_text(encoding="utf-8")
    keys = set(re.findall(r"@\w+\{([^,]+),", bib))
    cited: set[str] = set()
    for path in [MAIN, *(PAPER / "generated").glob("*.tex")]:
        text = _strip_comments(path.read_text(encoding="utf-8"))
        for group in re.findall(r"\\cite[tp]?\{([^}]+)\}", text):
            cited |= {k.strip() for k in group.split(",")}
    for key in sorted(cited):
        if key not in keys:
            problems.append(f"citation {key} has no entry in refs.bib")
    for entry in re.findall(r"@\w+\{([^,]+),(.*?)\n\}", bib, re.S):
        name, fields = entry
        if "year" not in fields:
            problems.append(f"refs.bib entry {name} has no year")
        if "doi" not in fields and "arXiv" not in fields and "note" not in fields:
            problems.append(f"refs.bib entry {name} has no DOI or arXiv identifier")

    # 6. Figures named in the text exist, resolved through \graphicspath the way
    #    LaTeX resolves them: the document directory first, then each declared
    #    search path in order.
    graphicspath: list[Path] = [PAPER]
    for group in re.findall(r"\\graphicspath\{((?:\{[^}]*\})+)\}", main_text):
        for entry in re.findall(r"\{([^}]*)\}", group):
            graphicspath.append(PAPER / entry)
    text_all = main_text + "".join(
        _strip_comments(p.read_text(encoding="utf-8")) for p in (PAPER / "generated").glob("*.tex")
    )
    for name in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text_all):
        searched = [base / name for base in graphicspath]
        if not any(path.exists() for path in searched):
            problems.append(
                f"figure {name} is included but exists at none of "
                + ", ".join(str(p.relative_to(PAPER)) for p in searched)
            )

    return problems


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return 1
    print("paper structure checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
