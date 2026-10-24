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
