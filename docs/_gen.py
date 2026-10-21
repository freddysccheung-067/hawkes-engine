"""Write the documentation fragments that are copied from committed measurements.

Nothing here computes a statistic. Each fragment is a reformatting of a committed
file, so a number on a published page is either produced here or pinned to its
source by tests/test_docs_claims.py. ``conf.py`` calls :func:`generate` at the
start of every build; the output directory is gitignored.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES = ROOT / "studies" / "results" / "analysis" / "hypotheses.json"
CAPABILITY = ROOT / "benchmarks" / "results" / "capability_2026-10-21.md"

HYPOTHESIS_NAMES = ("H6.1", "H6.2", "H6.3", "H6.4", "H6.5", "H6.6")


def _p_text(p: float) -> str:
    return "<1e-300" if p == 0.0 else f"{p:.3g}"


def _holm_text(holm: dict[str, object] | None) -> str:
    if holm is None:
        return "outside family"
    verdict = "met" if holm["passed"] else "missed"
    return f"step {holm['step']}, {float(holm['threshold']):.4g} {verdict}"  # type: ignore[arg-type]


def hypotheses_table() -> str:
    data = json.loads(HYPOTHESES.read_text(encoding="utf-8"))
    lines = [
        "| Hypothesis | Status | T | tau | SE | z | p | Holm | Final label |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in HYPOTHESIS_NAMES:
        h = data[name]
        lines.append(
            f"| {name} | {h['status']} | {h['T']:.4g} | {h['tau']:g} | {h['se']:.3g} "
            f"| {h['z']:.2f} | {_p_text(h['p'])} | {_holm_text(h['holm'])} | **{h['label']}** |"
        )
    return "\n".join(lines) + "\n"


def _section(text: str, heading: str) -> str:
    """The text from ``heading`` to the next heading of the same or higher level."""
    start = text.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    rest = text[start + len(heading) :]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: end.start()] if end else rest


def _first_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    started = False
    for line in block.splitlines():
        if line.startswith("|"):
            started = True
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif started:
            break
    return rows


def _render(rows: list[list[str]]) -> str:
    header, rule, *body = rows
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(out) + "\n"


def _filtered(heading: str, keep) -> str:  # type: ignore[no-untyped-def]
    text = CAPABILITY.read_text(encoding="utf-8")
    rows = _first_table(_section(text, heading))
    kept = [r for r in rows[2:] if keep(r)]
    if not kept:
        raise ValueError(f"no row of the table under {heading!r} passed the filter")
    return _render(rows[:2] + kept)


def wall_clock_table() -> str:
    """Section 1 rows with at least one million events."""
    return _filtered("## 1. Wall clock of one fit", lambda r: int(r[2].replace(",", "")) >= 10**6)


def bootstrap_table() -> str:
    """Section 3 rows for M = 4, 100,000 events, B = 200."""
    return _filtered(
        "## 3. What an honest interval costs",
        lambda r: r[0] == "4" and r[1] == "100,000" and r[2] == "200",
    )


def pair_shared_table() -> str:
    """Section 4 pair-against-shared rows at one million events."""
    return _filtered("### Pair against shared decay, as measured", lambda r: r[1] == "1,000,000")


def cannot_do_list() -> str:
    text = CAPABILITY.read_text(encoding="utf-8")
    block = _section(text, "## 6. What the library cannot do at a practical size on this machine")
    return block.strip() + "\n"


def generate(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fragments = {
        "hypotheses.md": hypotheses_table(),
        "wall_clock.md": wall_clock_table(),
        "bootstrap.md": bootstrap_table(),
        "pair_shared.md": pair_shared_table(),
        "cannot_do.md": cannot_do_list(),
    }
    for name, body in fragments.items():
        (out_dir / name).write_text(body, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    generate(Path(__file__).parent / "_generated")
