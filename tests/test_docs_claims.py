"""Pin the figures quoted in the published pages to the committed outputs they come from.

This covers the headline figures, not every number on every page: the pooled
standard-error ratio and its blocks, the cell and replication counts, the verdict
rule's mechanical share, the heavy-tail counts, the wall-clock figures, and the
hypothesis labels. Each entry names the pages that must quote the figure, the
committed file it comes from, and how to read it there. A quoted figure is
compared after rounding the source to the number of decimals the page uses, so a
figure that drifts from its source fails here.

Kinds of source:

``json``   a ``/``-separated path into a JSON file, with an optional scale
``regex``  the first capture group of a pattern over a text file
``count``  the number of rows of a CSV whose column equals a value

A figure not listed here is not pinned. Adding a number to a page without adding
it here is allowed; changing a listed number without changing its source is not.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = "studies/results/analysis"
HYP = f"{ANALYSIS}/hypotheses.json"
CAP = "benchmarks/results/capability_2026-10-21.md"
PHASE3 = f"{ANALYSIS}/phase3_report.txt"
RUN = "studies/RUN_REPORT.md"

README = "README.md"
INDEX = "docs/index.md"
QUICK = "docs/quickstart.md"
FIT = "docs/fitting.md"
TRUST = "docs/trust.md"
LIMITS = "docs/limits.md"
PERF = "docs/performance.md"
PAPER = "paper/draft.md"
NOTES = "docs/release_notes_0.1.0.md"
NOTES_2 = "docs/release_notes_0.2.0.md"
POLICY = "docs/se_policy.md"

PUBLISHED = [
    README,
    INDEX,
    QUICK,
    "docs/concepts.md",
    FIT,
    TRUST,
    LIMITS,
    PERF,
    "docs/reference.md",
    "docs/install.md",
    "docs/ROADMAP.md",
    "docs/verification-rule.md",
    NOTES,
    NOTES_2,
    POLICY,
]


@dataclass(frozen=True)
class Claim:
    quoted: str
    docs: tuple[str, ...]
    source: str
    kind: str
    locator: str
    scale: float = 1.0
    column: str = ""


CLAIMS = [
    # H6.5, the headline: pooled q and its bootstrap SE, per block, satellite.
    Claim("0.779", (README, INDEX, QUICK, LIMITS, PAPER, NOTES), HYP, "json", "H6.5/T"),
    Claim("0.011", (README, INDEX, QUICK, LIMITS, PAPER, NOTES), HYP, "json", "H6.5/se"),
    Claim("0.61", (README, INDEX, QUICK, LIMITS, NOTES), HYP, "json", "H6.5/per_block/beta/q"),
    Claim("0.611", (PAPER,), HYP, "json", "H6.5/per_block/beta/q"),
    Claim("0.936", (LIMITS, NOTES), HYP, "json", "H6.5/per_block/mu/q"),
    Claim("0.869", (LIMITS, NOTES), HYP, "json", "H6.5/per_block/alpha/q"),
    Claim("0.336", (LIMITS, PAPER, NOTES), HYP, "json", "H6.5/satellite/q"),
    Claim("0.023", (LIMITS, PAPER, NOTES), HYP, "json", "H6.5/satellite/se_boot"),
    Claim("0.983", (LIMITS, NOTES), HYP, "json", "H6.5/qrob_pooled"),
    Claim("0.003", (LIMITS, NOTES), HYP, "json", "H6.5/qrob_se_boot"),
    # H6.3 and H6.6 statistics quoted on the limits page and in the release notes.
    Claim("0.0167", (LIMITS, NOTES), HYP, "json", "H6.3/T"),
    Claim("0.0059", (LIMITS, NOTES), HYP, "json", "H6.3/se"),
    Claim("0.775", (LIMITS, PAPER), HYP, "json", "H6.6/T"),
    # Study size.
    Claim(
        "128", (README, INDEX, TRUST, PAPER, NOTES), f"{ANALYSIS}/cells.csv", "count", "", column=""
    ),
    Claim(
        "2000", (README, INDEX, PAPER, NOTES), RUN, "regex", r"128 cells, (\d+) replications each"
    ),
    Claim(
        "67",
        (LIMITS, PAPER, NOTES),
        f"{ANALYSIS}/cells.csv",
        "count",
        "1",
        column="estimator_undefined",
    ),
    # H6.6 is mostly mechanical.
    Claim(
        "96.4",
        (README, INDEX, TRUST, LIMITS, PAPER, NOTES),
        PHASE3,
        "regex",
        r"without an SE \((0\.\d+)\)",
        scale=100.0,
    ),
    Claim(
        "0.0726",
        (LIMITS, PAPER, NOTES),
        PHASE3,
        "regex",
        r"\+(0\.\d{4}) \+/- 0\.0394 \(independent cells\)",
    ),
    # The heavy tail in beta_hat at small N, and the verdict that missed it.
    Claim("5454", (LIMITS, NOTES), RUN, "regex", r"In total (\d+) such fits"),
    Claim("3211", (LIMITS, FIT, NOTES), RUN, "regex", r"of which (\d+) carry the verdict"),
    Claim("1.305", (LIMITS, NOTES), PHASE3, "regex", r"beta\[0,1\]: median ([\d.]+), mean"),
    Claim("43914", (LIMITS, NOTES), PHASE3, "regex", r"max (\d+) \(truth 1\.2\)"),
    # Wall clock: the slowest measured fit.
    Claim(
        "828.62",
        (PERF,),
        CAP,
        "regex",
        r"\| 8 \| 0\.3 \| 1,001,390 \| 1 \| 812 \| \S+ min \| ([\d.]+)-",
    ),
    Claim(
        "13.8", (PERF,), CAP, "regex", r"\| 8 \| 0\.3 \| 1,001,390 \| 1 \| 812 \| ([\d.]+) min \|"
    ),
    # Bootstrap cost quoted in the fitting guide.
    Claim("70", (FIT,), CAP, "regex", r"\| 2 \| 100,000 \| 200 \| 1 \| (\d+\.\d+) s \|"),
    Claim("8.5", (FIT,), CAP, "regex", r"\| 4 \| 100,000 \| 200 \| 1 \| ([\d.]+) min \|"),
    Claim("86", (FIT,), CAP, "regex", r"\| 4 \| 100,000 \| 200 \| default \| (\d+\.\d+) s \|"),
    # The machine and memory figures quoted on the performance page.
    Claim("24", (FIT, PERF), CAP, "regex", r"logical_cores: (\d+)"),
    Claim("31.4", (PERF,), CAP, "regex", r"ram_gib: ([\d.]+)"),
    Claim("316", (PERF,), CAP, "regex", r"10,001,305 \| [\d.]+ MiB \| ([\d.]+) MiB"),
    Claim("33", (PERF,), CAP, "regex", r"bytes = ([\d.]+) \* N"),
]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _source_value(claim: Claim) -> float | str:
    path = ROOT / claim.source
    if claim.kind == "json":
        node = json.loads(path.read_text(encoding="utf-8"))
        for key in claim.locator.split("/"):
            node = node[key]
        return float(node) * claim.scale
    if claim.kind == "regex":
        found = re.search(claim.locator, path.read_text(encoding="utf-8"))
        assert found, f"{claim.locator!r} not found in {claim.source}"
        return float(found.group(1)) * claim.scale
    if claim.kind == "count":
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not claim.column:
            return float(len(rows))
        return float(sum(r[claim.column] == claim.locator for r in rows))
    raise AssertionError(claim.kind)


def _decimals(quoted: str) -> int:
    return len(quoted.split(".")[1]) if "." in quoted else 0


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: f"{c.quoted}<-{c.source.split('/')[-1]}")
def test_quoted_figure_matches_its_source(claim):
    value = _source_value(claim)
    rounded = round(value, _decimals(claim.quoted))
    assert rounded == pytest.approx(
        float(claim.quoted), abs=1e-9
    ), f"{claim.quoted} is quoted but {claim.source} gives {value!r}"


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: f"{c.quoted}<-{c.source.split('/')[-1]}")
def test_quoted_figure_appears_in_its_pages(claim):
    for doc in claim.docs:
        pattern = rf"(?<![\d.]){re.escape(claim.quoted)}(?![\d])"
        assert re.search(pattern, _text(doc)), f"{claim.quoted} is not in {doc}"


# ------------------------------------------------------------- computed ranges


def _per_cell_q():
    per_cell = json.loads(_text(HYP))["H6.5"]["per_cell"]
    return {k: v["q"] for k, v in per_cell.items()}


def _n_of(cell: str) -> int:
    return int(cell.split("_")[1][1:])


def test_per_cell_q_ranges_quoted_on_the_limits_page():
    q = _per_cell_q()
    small = [v for k, v in q.items() if _n_of(k) == 2000]
    large = [v for k, v in q.items() if _n_of(k) >= 10000]
    text = _text(LIMITS)
    assert f"between\n  {min(small):.2f} and {max(small):.2f}" in text
    assert "between 0.875 and 0.977" in text.replace("\n  ", " ")
    assert round(min(large), 3) == 0.875
    assert round(max(large), 3) == 0.977


def test_quantisation_range_quoted_on_the_limits_page():
    cells = json.loads(_text(HYP))["H6.4"]["cells"]
    big = [c["D"] for c in cells if c["c"] == 1.0 and c["N"] >= 10000]
    assert round(-max(big) * 100) == 37
    assert round(-min(big) * 100) == 62
    assert "by 37 to 62\n  percent" in _text(LIMITS)


def test_coverage_range_quoted_on_the_limits_page():
    with (ROOT / ANALYSIS / "blocks.csv").open(newline="", encoding="utf-8") as fh:
        rows = [
            r
            for r in csv.DictReader(fh)
            if r["M"] == "2"
            and r["r"] == "0.0"
            and r["c"] == "1.0"
            and r["block"] in ("mu", "alpha", "beta")
        ]
    large = [float(r["cov_all"]) for r in rows if int(r["N"]) >= 10000]
    lowest = min(rows, key=lambda r: float(r["cov_all"]))
    assert round(min(large), 3) == 0.918
    assert round(max(large), 3) == 0.953
    assert (lowest["N"], lowest["rho"], lowest["block"]) == ("200", "0.95", "mu")
    assert round(float(lowest["cov_all"]), 3) == 0.171
    text = _text(LIMITS).replace("\n  ", " ")
    assert "between 0.918 and 0.953" in text
    assert "as little as 0.171" in text


def test_large_m_small_n_iteration_range_quoted_on_the_limits_page():
    table = _text(CAP).split("## 1. Wall clock of one fit")[1].split("###")[0]
    rows = [
        [c.strip() for c in line.strip("|").split("|")]
        for line in table.splitlines()
        if line.startswith("| ") and line[2].isdigit()
    ]
    small = [r for r in rows if int(r[0]) >= 6 and int(r[2].replace(",", "")) < 20000]
    iters = [int(r[4]) for r in small]
    assert len(small) == 4
    assert (min(iters), max(iters)) == (942, 2765)
    assert all(r[-1] in ("marginal", "unreliable") for r in small)
    text = _text(LIMITS).replace("\n", " ")
    assert "942 to 2765 iterations" in text
    assert "in all four cases measured" in text


# ---------------------------------------------------------------- the labels


def test_hypothesis_labels_on_the_trust_page_match_the_analysis():
    data = json.loads(_text(HYP))
    lines = _text(TRUST).splitlines()
    for name in ("H6.3", "H6.4", "H6.5", "H6.6"):
        bullet = next(line for line in lines if line.startswith(f"- **{name},"))
        assert f", {data[name]['label']}" in bullet.split(".**")[0] + ".", name
    both = next(line for line in lines if line.startswith("- **H6.1 and H6.2,"))
    assert data["H6.1"]["label"] == data["H6.2"]["label"] == "confirmed (exploratory)"
    assert "confirmed (exploratory)" in both


def test_the_two_unconfirmed_hypotheses_named_on_the_front_pages():
    data = json.loads(_text(HYP))
    assert data["H6.3"]["label"] == data["H6.4"]["label"] == "not confirmed"
    assert data["H6.6"]["label"] == "confirmed"
    for doc in (README, INDEX):
        assert "H6.3 and H6.4, were not confirmed" in _text(doc).replace("\n", " ")


# ------------------------------------------------------------------ hygiene

BANNED = re.compile(
    r"\b(fast|faster|fastest|robust|accurate|production-ready|validated|blazing|seamless)\b",
    re.I,
)
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅❌]")
TOOLING = re.compile(r"\b(claude|anthropic|copilot|chatgpt|llm|years? old)\b", re.I)
BLOB = re.compile(r"https://github\.com/freddysccheung-067/hawkes-engine/blob/main/([^)\s#]+)")
RELATIVE = re.compile(r"\]\((?!https?:|#|mailto:)([^)\s#]+)")
TOCTREE = re.compile(r"```\{toctree\}\n(.*?)```", re.S)


@pytest.mark.parametrize("page", [*PUBLISHED, PAPER])
def test_every_repository_link_resolves(page):
    text = _text(page)
    for rel in BLOB.findall(text):
        assert (ROOT / rel).exists(), f"{page} links to {rel}, which is not in the repository"
    if page == README:
        for rel in RELATIVE.findall(text):
            assert (ROOT / rel).exists(), f"{page} links to {rel}, which is not in the repository"


@pytest.mark.parametrize("page", PUBLISHED)
def test_no_unmeasured_adjectives_emoji_or_tooling_mentions(page):
    text = _text(page)
    assert not BANNED.search(text), BANNED.search(text).group(0)
    assert not EMOJI.search(text)
    assert not TOOLING.search(text), TOOLING.search(text).group(0)


def test_the_toctree_lists_exactly_the_published_pages():
    listed = set()
    for block in TOCTREE.findall(_text(INDEX)):
        listed |= {ln.strip() for ln in block.splitlines() if ln.strip() and ln[0] != ":"}
    pages = {Path(p).stem for p in PUBLISHED if p.startswith("docs/") and p != INDEX}
    assert listed == pages


# ------------------------------------------------- the paper's prose, not its numbers
#
# Every number in the paper is pinned to a committed output elsewhere in this file.
# None of that checks the prose, and the prose is what a reader meets first. These
# are the patterns that creep into generated text and that survive a spell-check:
# stock vocabulary, dashes used for rhythm, and one construction used so often it
# becomes a tic. The counts are set where the current text sits, not at zero, so the
# tests catch a regression without forbidding a word that has a legitimate use.

PAPER_TEX = [
    Path("paper/main.tex"),
    *sorted(Path("paper/generated").glob("*.tex")),
]

# Words that say nothing and mark the register as promotional or generated. The
# repository's own hygiene test bans these on published pages; the paper is submitted
# under the author's name, so it is held to the same list plus the stock ones.
PAPER_BANNED = re.compile(
    r"\b(delve|tapestry|intricate|interplay|intricacies|foster|garner|showcase|"
    r"meticulous|crucial|pivotal|multifaceted|ever-changing|seamless|"
    r"landscape|realm|leverage|harness|unlock|elevate|embark)\b",
    re.I,
)
# Openers that delay the sentence rather than starting it.
PAPER_FILLER = re.compile(
    r"\b(it is worth noting|it should be noted|it is important to note|"
    r"notably|interestingly|importantly|in conclusion|in summary|ultimately)\b",
    re.I,
)
# A construction that is fine once and conspicuous at four times per thousand words.
RATHER_THAN = re.compile(r"rather than", re.I)
RATHER_RATE_MAX = 2.6  # per thousand words; the file sat at 3.2 before the rewrite


def _paper_words() -> int:
    return sum(len(re.findall(r"[A-Za-z]+", p.read_text(encoding="utf-8"))) for p in PAPER_TEX)


@pytest.mark.parametrize("path", PAPER_TEX, ids=lambda p: p.name)
def test_the_paper_uses_no_stock_or_promotional_vocabulary(path):
    text = path.read_text(encoding="utf-8")
    for pattern, what in ((PAPER_BANNED, "stock vocabulary"), (PAPER_FILLER, "a filler opener")):
        match = pattern.search(text)
        assert match is None, f"{path} uses {what}: {match.group(0)!r}"


@pytest.mark.parametrize("path", PAPER_TEX, ids=lambda p: p.name)
def test_the_paper_has_no_em_dash_or_emoji(path):
    # An em dash in LaTeX source is almost always a typing habit rather than a
    # typographic choice: the paper does not use "---" anywhere. En dashes are
    # written as "--" and are left alone.
    text = path.read_text(encoding="utf-8")
    assert "—" not in text, f"{path} contains an em dash"
    assert not EMOJI.search(text), f"{path} contains an emoji"


def test_the_paper_does_not_lean_on_one_construction():
    """'rather than' is the paper's favourite move and it was doing too much work.

    It was at 3.2 per thousand words before the prose rewrite, in a paper of under
    ten thousand, which reads as a tic rather than an argument. The ceiling is set
    just above where the rewritten text sits so a later section that reaches for it
    again fails here rather than in a reader's patience.
    """
    total = sum(len(RATHER_THAN.findall(p.read_text(encoding="utf-8"))) for p in PAPER_TEX)
    rate = 1000.0 * total / _paper_words()
    assert rate <= RATHER_RATE_MAX, (
        f"'rather than' appears {total} times, {rate:.1f} per thousand words, "
        f"above the {RATHER_RATE_MAX} ceiling"
    )


# ------------------------------------------------------------- the auto study


AUTO_ANALYSIS = "studies/results/auto/analysis"


def test_the_auto_study_outputs_exist_and_agree_with_their_report():
    """The auto study's analysis is committed, and its labels are in the paper.

    Skips when the study has not been run in this checkout, which is the normal
    case for someone installing the sdist: ``studies/results/auto/*.csv`` are
    gitignored, and only ``analysis/`` is committed. A missing analysis is a
    checkout that never ran the study, not a failing claim.
    """
    path = ROOT / AUTO_ANALYSIS / "hypotheses.json"
    if not path.exists():
        pytest.skip("auto-v1 analysis is not present in this checkout")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["study_id"] == "auto-v1"
    assert data["preregistration"] == "docs/preregistration_auto.md"
    for name in ("H-A1", "H-A2", "H-A3"):
        assert data["hypotheses"][name]["label"] in (
            "confirmed",
            "not confirmed",
            "confirmed (exploratory)",
        )
    # Every cell in the study is one of the three the pre-registration fixes.
    keys = {c["cell"] for c in data["cells"]}
    assert keys == {
        "M2_N2000_rho0.3028_r0.0_c1.0",
        "M2_N2000_rho0.85_r0.0_c1.0",
        "M2_N2000_rho0.95_r0.0_c1.0",
    }


def test_the_auto_labels_in_the_paper_match_the_study():
    """The paper's verdict macros quote the analysis, not a paraphrase of it."""
    path = ROOT / AUTO_ANALYSIS / "hypotheses.json"
    main_tex = ROOT / "paper" / "main.tex"
    if not path.exists() or not main_tex.exists():
        pytest.skip("auto-v1 analysis is not present in this checkout")
    data = json.loads(path.read_text(encoding="utf-8"))
    text = main_tex.read_text(encoding="utf-8")
    for name, macro in (("H-A1", "AutoHoneLabel"), ("H-A2", "AutoHtwoLabel")):
        label = data["hypotheses"][name]["label"]
        found = re.search(rf"\\newcommand\{{\\{macro}\}}\{{(.*?)\}}\n", text)
        assert found, f"{macro} is not defined in main.tex"
        assert label in found.group(1), f"{name} is {label!r} but main.tex says {found.group(1)!r}"


def test_the_auto_study_numbers_quoted_in_the_release_notes():
    """Every coverage figure in the 0.2.0 notes is the study's own number."""
    path = ROOT / AUTO_ANALYSIS / "hypotheses.json"
    notes = ROOT / NOTES_2
    if not path.exists():
        pytest.skip("auto-v1 analysis is not present in this checkout")
    data = json.loads(path.read_text(encoding="utf-8"))
    text = notes.read_text(encoding="utf-8")
    for cell in data["cells"]:
        pooled = cell["blocks"]["all"]
        for value, digits in (
            (pooled["cov_hessian"], 4),
            (pooled["cov_auto"], 4),
            (pooled["delta"], 4),
            (pooled["delta_se"], 4),
        ):
            quoted = f"{abs(value):.{digits}f}" if value >= 0 else f"{value:.{digits}f}"
            assert quoted in text, (
                f"{cell['cell']} gives {quoted!r} for a pooled statistic, "
                f"which the release notes do not quote"
            )
    # The overshoot ceiling and the worst measured coverage.
    assert f"{data['hypotheses']['H-A2']['ceiling']:.4f}" in text
    assert "0.9762" in text


def test_the_auto_study_decision_counts_quoted_in_the_release_notes():
    path = ROOT / AUTO_ANALYSIS / "hypotheses.json"
    if not path.exists():
        pytest.skip("auto-v1 analysis is not present in this checkout")
    data = json.loads(path.read_text(encoding="utf-8"))
    text = (ROOT / NOTES_2).read_text(encoding="utf-8")
    for cell in data["cells"]:
        actions = cell["actions"]
        if "hessian_unmapped" in actions:
            assert f"{actions['hessian_unmapped']} of 2000" in text, (
                f"{cell['cell']} had {actions['hessian_unmapped']} unmapped "
                f"replications, which the notes do not report"
            )


# ------------------------------------------------------------------- figures


def test_every_paper_figure_is_the_generator_output():
    """A figure in paper/figures must be byte-identical to the one that was generated.

    A hand-edited figure is the same defect as a hand-typed number: the paper would
    show something no script produced. The copies exist so the arXiv archive builds
    alone, not so they can be touched.
    """
    paper_figures = ROOT / "paper" / "figures"
    if not paper_figures.exists():
        pytest.skip("paper/figures is not present in this checkout")
    for path in sorted(paper_figures.glob("*.pdf")):
        source = ROOT / "studies" / "figures" / path.name
        if not source.exists():
            pytest.skip(f"{path.name}: the study output is not in this checkout")
        assert path.read_bytes() == source.read_bytes(), (
            f"{path.name} differs from studies/figures/{path.name}; "
            f"regenerate with python -m studies.make_paper_tex"
        )


def test_every_paper_figure_is_vector_with_embedded_fonts():
    """No raster panel, and every font embedded: both are visible at print size."""
    paper_figures = ROOT / "paper" / "figures"
    if not paper_figures.exists():
        pytest.skip("paper/figures is not present in this checkout")
    for path in sorted(paper_figures.glob("*.pdf")):
        raw = path.read_bytes()
        assert (
            b"/Subtype /Image" not in raw and b"/Subtype/Image" not in raw
        ), f"{path.name} embeds a raster image; a paper figure must be vector"
        # Every distinct face must have an embedded program. A PDF names a font
        # twice — once for the Type0 composite and once for its descendant — so the
        # count is over distinct BaseFont names, not over declarations. Comparing
        # against declarations would fail a correctly embedded figure.
        names = set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)", raw))
        embedded = len(re.findall(rb"/FontFile[23]?\b", raw))
        assert names, f"{path.name} declares no font at all"
        assert embedded >= len(names), (
            f"{path.name} declares {len(names)} distinct faces and embeds {embedded}; "
            f"a reader without the missing face would see a substitute"
        )


def test_the_figure_readme_names_every_figure_once():
    """The figure list maps each file to a claim, and each file appears in it."""
    readme = ROOT / "studies" / "figures" / "README.md"
    text = readme.read_text(encoding="utf-8")
    for path in sorted((ROOT / "studies" / "figures").glob("*.pdf")):
        assert text.count(f"`{path.name}`") >= 1, f"{path.name} is not in the figure list"


# ------------------------------------------------- the theory and discussion block
#
# The theory section and the discussion are the most numerically loaded pages of the
# paper and until now had no coverage here: every figure they quote arrives as a
# \Th... or \Disc... macro defined by ``theory_macros`` in
# ``studies/make_paper_tex.py``, and nothing compared those macros to the outputs
# they are computed from. The tests below recompute each quantity from the committed
# CSVs and JSON with an implementation written independently of the generator. They
# are not a check that the derivation is right; they are a check that the paper
# prints the number the committed outputs imply.
#
# Three of the macros, ``ThCvMu``, ``ThCvAlpha`` and ``ThCvBeta``, invert the Jensen
# correction at the measured ratio, and every macro derived from them inherits that.
# The generator says so and so does the paper: the inversion describes the
# dispersion of the reported variance and is not an independent test of the
# correction, because the right-hand side is fitted from the same q as the left.
# They are pinned anyway, for the reason above: paper and generator must agree.
#
# Four further properties are checked that no single-macro test can see, because
# they are relations between a macro and a claim the prose makes: that the two ratio
# macros are algebraically dependent, that the block shares sum to one and the
# pooled ratio really is their weighted mean, that the discussion's interval macro
# carries both of its numbers, and that the coordinate the theory names as the flat
# one is the coordinate the analysis measures as the worst.

THEORY_CELL = "M2_N2000_rho0.3028_r0.0_c1.0"
MACRO = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{((?:[^{}]|\{[^{}]*\})*)\}")


def _macros() -> dict[str, str]:
    """Every ``\\newcommand`` in the generated paper, by name, without the braces."""
    found = MACRO.findall((ROOT / "paper" / "main.tex").read_text(encoding="utf-8"))
    assert found, "paper/main.tex defines no macros; run python -m studies.make_paper_tex"
    return dict(found)


def _tex_number(body: str) -> float:
    """Read one of the generator's numbers back out of its rendered form.

    ``tex_num`` writes three shapes the paper uses: plain digits (``0.221``), a
    thousands-separated integer (``5{,}454``) and scientific notation with a
    typeset exponent (``$4.3\\times 10^{4}$``). Anything else is a format this
    test does not know about, which is a failure rather than a pass.
    """
    text = body.strip().strip("$").replace("{,}", "").replace("\\,", "")
    sci = re.fullmatch(r"(-?[\d.]+)\\times 10\^\{(-?\d+)\}", text)
    if sci:
        return float(sci.group(1)) * 10.0 ** int(sci.group(2))
    return float(text)


def _tex_pm(body: str) -> tuple[float, float]:
    """Read an ``estimate \\pm se`` macro as two numbers."""
    text = body.strip().strip("$")
    parts = text.split(r"\pm")
    assert len(parts) == 2, f"not an estimate +/- se macro: {body!r}"
    return _tex_number(parts[0]), _tex_number(parts[1])


def _h6() -> dict:
    return json.loads((ROOT / HYP).read_text(encoding="utf-8"))


def _blocks() -> list[dict[str, str]]:
    with (ROOT / ANALYSIS / "blocks.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _companions() -> list[dict[str, str]]:
    with (ROOT / ANALYSIS / "companions.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _cells() -> list[dict[str, str]]:
    with (ROOT / ANALYSIS / "cells.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _coordinate_weights() -> dict[str, int]:
    """Coordinates per block at M = 2: two baselines, four alphas, four betas."""
    return {"mu": 2, "alpha": 4, "beta": 4}


def _deficits() -> dict[str, float]:
    """``1 - q`` per block, over the pooled cells, from the H6.5 analysis output."""
    per_block = _h6()["H6.5"]["per_block"]
    return {b: 1.0 - per_block[b]["q"] for b in _coordinate_weights()}


def _block_q(n_lo: int, n_hi: int) -> list[float]:
    """Sorted per-cell decay-block q over the primary cells in an event-count band."""
    return sorted(
        float(r["q"])
        for r in _blocks()
        if r["M"] == "2"
        and r["c"] == "1.0"
        and r["r"] == "0.0"
        and r["block"] == "beta"
        and n_lo <= int(r["N"]) <= n_hi
    )


def _tail_share(n: int) -> float:
    """Mean over the four branching-ratio columns of the wild-beta share at N."""
    size = {r["cell"]: int(r["N"]) for r in _blocks()}
    vals = [
        float(r["medbias"])
        for r in _companions()
        if r["block"] == "tail"
        and r["cell"].startswith("M2_")
        and "_c1.0" in r["cell"]
        and "_r0.0_" in r["cell"]
        and size[r["cell"]] == n
        and r["medbias"] not in ("", "nan", "inf")
    ]
    assert vals, f"no companions rows for the tail at N = {n}"
    return sum(vals) / len(vals)


ANCHOR_LINE = re.compile(
    r"beta\[0,1\]: median ([\d.]+), mean ([\d.]+), p95 ([\d.]+), p99 ([\d.]+), "
    r"max (\d+) \(truth ([\d.]+)\)"
)


def _anchor_line() -> tuple[float, ...]:
    """The beta[0,1] distribution at the anchor: median, mean, p95, p99, max, truth."""
    found = ANCHOR_LINE.search((ROOT / PHASE3).read_text(encoding="utf-8"))
    assert found, "phase3_report.txt no longer states the beta[0,1] distribution"
    return tuple(float(g) for g in found.groups())


def _anchor_row(block: str) -> dict[str, str]:
    return next(r for r in _blocks() if r["cell"] == THEORY_CELL and r["block"] == block)


def _anchor_companion(block: str) -> dict[str, str]:
    return next(r for r in _companions() if r["cell"] == THEORY_CELL and r["block"] == block)


def _theory_expected() -> list[tuple[str, float, int]]:
    """Each theory macro, the value the committed outputs imply, and its decimals.

    Recomputing here rather than importing ``theory_macros`` is deliberate: a test
    that called the generator and compared two of its own outputs would pass even if
    both were wrong in the same way.
    """
    deficits = _deficits()
    weights = _coordinate_weights()
    total_weight = sum(weights.values())
    pooled_deficit = sum(weights[b] * deficits[b] for b in weights) / total_weight
    cv = {b: math.sqrt(8.0 * deficits[b]) for b in deficits}
    pooled_cells = set(_h6()["H6.5"]["cells"])
    n_floor = min(int(k.split("_")[1][1:]) for k in pooled_cells)
    regular = 1.0 / (8.0 * n_floor)
    small = _block_q(2000, 2000)
    large = _block_q(10000, 50000)
    anchor = _anchor_row("beta")
    anchor_comp = _anchor_companion("beta")
    median, mean, p95, p99, _, truth = _anchor_line()
    beta_min_t = [float(r["beta_min_T"]) for r in _cells() if r["c"] == "1.0" and r["r"] == "0.0"]
    shallow = [r for r in _cells() if r["c"] == "0.001" and r["r"] == "0.0"]
    run_report = (ROOT / RUN).read_text(encoding="utf-8")
    tail_fits = int(re.search(r"In total (\d+) such fits", run_report).group(1))
    tail_reliable = int(re.search(r"of which (\d+) carry the verdict", run_report).group(1))

    with (ROOT / ANALYSIS / "crosstab.csv").open(newline="", encoding="utf-8") as fh:
        crosstab = list(csv.DictReader(fh))
    c1_shares = []
    for row in crosstab:
        if "_c1.0" not in row["cell"]:
            continue
        n = sum(int(row[k] or 0) for k in ("n_reliable", "n_marginal", "n_unreliable"))
        if n:
            c1_shares.append(int(row["n_unreliable"] or 0) / n)

    pooled_cov = [
        float(r["cov_all"])
        for r in _blocks()
        if r["cell"] in pooled_cells and r["block"] == "all" and int(r["N"]) == n_floor
    ]
    qrob = {
        b: sorted(
            float(r["qrob"])
            for r in _companions()
            if r["block"] == b and r["cell"] in pooled_cells and r["qrob"] not in ("", "nan", "inf")
        )
        for b in ("beta", "mu")
    }
    h4 = [c for c in _h6()["H6.4"]["cells"] if c["c"] == 1.0 and c["N"] >= 10000]
    return [
        # The pooled deficit and the decomposition of the headline into blocks.
        ("ThPooledDeficit", pooled_deficit, 3),
        ("ThShareMu", 100.0 * weights["mu"] * deficits["mu"] / (pooled_deficit * total_weight), 1),
        (
            "ThShareAlpha",
            100.0 * weights["alpha"] * deficits["alpha"] / (pooled_deficit * total_weight),
            1,
        ),
        (
            "ThShareBeta",
            100.0 * weights["beta"] * deficits["beta"] / (pooled_deficit * total_weight),
            1,
        ),
        # Per-block deficits and the coefficients of variation inverted from them.
        ("ThDefMu", deficits["mu"], 3),
        ("ThDefAlpha", deficits["alpha"], 3),
        ("ThDefBeta", deficits["beta"], 3),
        ("ThCvMu", cv["mu"], 3),
        ("ThCvAlpha", cv["alpha"], 3),
        ("ThCvBeta", cv["beta"], 3),
        ("ThCvRatio", cv["beta"] / cv["mu"], 2),
        ("ThDefRatio", deficits["beta"] / deficits["mu"], 2),
        # The regularity benchmark and the factor by which the decay block exceeds it.
        ("ThRegDeficit", regular, 3),
        ("ThMismatch", deficits["beta"] / regular, 0),
        # The decay block's q by event count.
        ("ThBetaQSmallLow", small[0], 4),
        ("ThBetaQSmallHigh", small[-1], 4),
        ("ThBetaQLargeLow", large[0], 4),
        ("ThBetaQLargeHigh", large[-1], 4),
        # The wild-beta share by event count.
        ("ThTailNtwohundred", _tail_share(200), 3),
        ("ThTailNtwothousand", _tail_share(2000), 3),
        ("ThTailNtenthousand", _tail_share(10000), 4),
        # The window-length range, restricted to the exact-timestamp c = 1 cells.
        ("ThBetaMinTLow", min(beta_min_t), 1),
        ("ThBetaMinTHigh", max(beta_min_t), -1),
        ("ThShallowBelowOne", float(sum(float(r["beta_min_T"]) < 1.0 for r in shallow)), 0),
        ("ThShallowCells", float(len(shallow)), 0),
        # The anchor cell.
        ("ThAnchorBetaSd", float(anchor["sd"]), 1),
        ("ThAnchorBetaMse", float(anchor["mse"]), 3),
        ("ThAnchorBetaQ", float(anchor["q"]), 4),
        ("ThAnchorBetaQrob", float(anchor_comp["qrob"]), 4),
        ("ThAnchorBetaCov", float(anchor["cov_all"]), 4),
        # The beta[0,1] distribution at the anchor, from the phase-3 report.
        ("ThBetaMedian", median, 3),
        ("ThBetaMean", mean, 2),
        ("ThBetaPninetyfive", p95, 2),
        ("ThBetaPninetynine", p99, 1),
        ("ThBetaTruth", truth, 1),
        ("ThBetaMeanOverTruth", mean / truth, 1),
        ("ThBetaMedianRelErr", (median - truth) / truth, 2),
        ("ThAnchorBetaGap", 1.0 / float(anchor["q"]), 0),
        # Counts and ranges the tail and discussion subsections quote.
        ("ThTailFits", float(tail_fits), 0),
        ("ThTailReliable", float(tail_reliable), 0),
        ("ThWorstUnreliableShare", 100.0 * max(c1_shares), 1),
        ("ThCovSmallLow", min(pooled_cov), 3),
        ("ThCovSmallHigh", max(pooled_cov), 3),
        ("ThQrobBetaLow", qrob["beta"][0], 3),
        ("ThQrobBetaHigh", qrob["beta"][-1], 3),
        ("ThQrobMuLow", qrob["mu"][0], 3),
        ("ThQrobMuHigh", qrob["mu"][-1], 3),
        # H6.3's threshold clause and H6.4's downward movement, quoted in the discussion.
        ("DiscFourLow", 100.0 * -max(c["D"] for c in h4), 0),
        ("DiscFourHigh", 100.0 * -min(c["D"] for c in h4), 0),
        ("DiscFourCells", float(len(h4)), 0),
    ]


@pytest.mark.parametrize(
    ("name", "expected", "digits"),
    _theory_expected(),
    ids=[row[0] for row in _theory_expected()],
)
def test_theory_macro_is_the_committed_output(name, expected, digits):
    """The paper's theory and discussion figures are the ones the outputs imply."""
    body = _macros().get(name)
    assert body is not None, f"\\{name} is not defined in paper/main.tex"
    printed = _tex_number(body)
    if digits < 0:
        # Rendered to two significant figures rather than to a decimal place, so a
        # relative comparison is the honest one: $4.3\times10^{4}$ is 43000 here and
        # 43065.7 in the output, and both are the same number at the precision the
        # paper quotes.
        assert printed == pytest.approx(
            expected, rel=0.01
        ), f"\\{name} prints {body!r} but the committed outputs give {expected!r}"
        return
    assert round(printed, digits) == pytest.approx(round(expected, digits), abs=1e-9), (
        f"\\{name} prints {body!r} but the committed outputs give {expected!r}, "
        f"which rounds to {round(expected, digits)}"
    )


def test_the_discussion_interval_macro_carries_both_numbers():
    """``DiscThreeT`` is estimate +/- se, and each half is pinned separately.

    The single-register test above can only read the estimate out of it, so the
    standard error half needs its own check.
    """
    estimate, se = _tex_pm(_macros()["DiscThreeT"])
    h63 = _h6()["H6.3"]
    assert estimate == pytest.approx(round(h63["T"], 4), abs=1e-9)
    assert se == pytest.approx(round(h63["se"], 4), abs=1e-9)


def test_the_two_ratio_macros_are_algebraically_dependent():
    """``ThDefRatio`` is ``ThCvRatio`` squared, so the paper does not count them twice.

    The theory section says so explicitly. If the relation stops holding, the
    sentence that calls the deficit ratio redundant is wrong and the paper has to
    change with it.
    """
    macros = _macros()
    ratio = _tex_number(macros["ThCvRatio"])
    squared = _tex_number(macros["ThDefRatio"])
    assert squared == pytest.approx(ratio**2, rel=0.01), (
        f"ThDefRatio {squared} is not the square of ThCvRatio {ratio}; the paper's "
        "claim that the deficit ratio carries no further information fails"
    )


def test_the_pooled_deficit_decomposes_into_its_blocks():
    """The headline is the coordinate-weighted mean of the three block ratios.

    The theory section says the block shares sum to one and that the pooled figure
    adds nothing beyond the block account. Both are checked against the weights the
    design fixes: two baselines, four excitation entries and four decay rates.
    """
    macros = _macros()
    shares = [_tex_number(macros[f"ThShare{b}"]) for b in ("Mu", "Alpha", "Beta")]
    assert sum(shares) == pytest.approx(100.0, abs=0.2), shares
    weights = _coordinate_weights()
    per_block = _h6()["H6.5"]["per_block"]
    weighted = sum(weights[b] * per_block[b]["q"] for b in weights) / sum(weights.values())
    assert weighted == pytest.approx(
        _h6()["H6.5"]["T"], abs=1e-9
    ), "the pooled q is not the coordinate-weighted mean of the block q values"


def test_the_coordinate_the_theory_calls_flat_is_the_one_measured_worst():
    """The ridge narrative needs one source-target pair to be worst in both blocks.

    The theory section says the pair with the smallest true excitation weight,
    (0, 1), is the pair whose reported ratio is worst in the excitation block and in
    the decay block at the anchor cell. That is a claim about the committed
    per-coordinate output, so it is checked there rather than asserted.
    """
    with (ROOT / ANALYSIS / "coordinates.csv").open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["cell"] == THEORY_CELL]
    assert rows, f"coordinates.csv has no rows for {THEORY_CELL}"
    alpha = {r["coordinate"]: float(r["q"]) for r in rows if r["coordinate"].startswith("alpha")}
    beta = {r["coordinate"]: float(r["q"]) for r in rows if r["coordinate"].startswith("beta")}
    truth = {
        r["coordinate"]: float(r["theta0"]) for r in rows if r["coordinate"].startswith("alpha")
    }
    weakest = min(truth, key=lambda k: truth[k])
    assert min(alpha, key=lambda k: alpha[k]) == weakest, (
        f"the smallest true alpha is {weakest} but the worst excitation ratio is "
        f"{min(alpha, key=lambda k: alpha[k])}"
    )
    as_beta = weakest.replace("alpha", "beta")
    assert min(beta, key=lambda k: beta[k]) == as_beta, (
        "the worst decay ratio is not the same source-target pair as the worst "
        "excitation ratio, which the theory section's ridge argument relies on"
    )


def test_the_sandwich_figures_in_the_paper_are_the_studys_own():
    """The paper's J0/I0 range quotes the sw-v1 estimands, not a paraphrase.

    The theory section used to say the sandwich experiment could not be run. It now
    reports one, so the three figures that carry the claim have to come from the
    committed output: the low and high ends of the ratio across the primary cells,
    and the factor by which a sandwich can move the interval.
    """
    path = ROOT / "studies" / "results" / "sandwich" / "estimands.json"
    main_tex = ROOT / "paper" / "main.tex"
    if not path.exists() or not main_tex.exists():
        pytest.skip("sw-v1 estimands are not present in this checkout")
    est = json.loads(path.read_text(encoding="utf-8"))
    primary = [
        key
        for key in est
        if key.startswith("M2_") and "_r0.0_" in key and not key.endswith("c0.001")
    ]
    g = [est[key]["beta"]["g"] for key in primary]
    text = main_tex.read_text(encoding="utf-8")

    def _macro(name: str) -> str:
        found = re.search(rf"\\newcommand\{{\\{name}\}}\{{(.*?)\}}", text)
        assert found, f"{name} is not defined in main.tex"
        return found.group(1)

    assert float(_macro("SwGRatioLow")) == pytest.approx(min(g), abs=5e-4)
    assert float(_macro("SwGRatioHigh")) == pytest.approx(max(g), abs=5e-4)
    assert float(_macro("SwMaxFactor")) == pytest.approx(
        max(max(g) ** 0.5, min(g) ** -0.5), abs=5e-4
    )
    assert int(_macro("SwCells")) == len(est)
