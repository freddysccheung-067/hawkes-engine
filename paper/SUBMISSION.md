# Submitting the paper

This is the checklist for putting `paper/main.tex` on arXiv. **Nothing has been
submitted.** The session that prepared this package has no arXiv credentials and
does not submit; the steps below are the owner's.

## Order of operations

The order matters because two steps are hard to undo once a version is live.

1. **Resolve the unverified references** (below). Done: all seven entries are now
   checked, including the one this list used to block on. An arXiv submission can
   be replaced by a new version, but a wrong DOI in a bibliography is the kind of
   error a reader finds first and a correction cannot fully erase.
2. **Build the PDF** from a machine with a TeX distribution installed. The
   preparing session could not: no TeX is installed on it and installing one was
   blocked. See "Building" below.
3. **Read the PDF.** The structure checks in `studies/check_paper.py` catch a
   missing macro and an unbalanced brace, not a table that overflows the margin.
4. **Choose the primary category** (below) and check the cross-lists.
5. **Fill the metadata form** with the abstract in the plain-text block below.
6. **Submit.** The first submission to a category may need an endorsement; see
   below.
7. **After it is live**, update `docs/release_notes_0.2.0.md`, which currently says
   the paper has not been submitted. That sentence becoming false is the defect
   this step exists to prevent.

## Building

One command, from the repository root:

```bash
make -C paper
```

It regenerates every number and table, then typesets `main.pdf`. The three targets
separately:

```bash
make -C paper numbers   # regenerate every number and table
make -C paper pdf       # typeset from the committed .tex tree
make -C paper check     # structural checks, no TeX needed
```

`make numbers` runs `python -m studies.make_paper_tex`, which writes
`paper/generated/*.tex` and `paper/main.tex`. Both are committed, so a reader
without Python can still build from the `.tex` files as they stand; re-running the
generator is what proves they are current.
`python -m studies.make_paper_tex --check` fails if the committed tree is stale.

The build needs `booktabs`, `natbib`, `hyperref`, `lmodern`, `amsmath` and
`geometry`, all of which a standard TeX Live or MiKTeX installation carries.

## Primary category

**stat.ME (Methodology)**, with a cross-list to **stat.CO (Computation)**.

The paper's contribution is a measurement of an estimator's calibration and a change
to what the estimator reports; that is methodology, and stat.ME is where a reader
looking for "how well does this maximum-likelihood fit behave" will look. stat.CO is
the right cross-list because the artefact is a library and the cost of the bootstrap
is part of the argument, but the paper is not primarily about computation.

## Abstract for the metadata form

Plain text, no LaTeX macros. This is the text `paper/generated/abstract.tex`
renders, with the macros expanded and `$\pm$` written as `+/-`; it is reproduced
here because the submission form takes plain text and copying from a built PDF
loses the math. `tests/test_paper_abstract.py` expands the rendered abstract and
compares it to the block below, so the two cannot drift apart.

```
This paper measures whether a maximum-likelihood fit of a multivariate
exponential-kernel Hawkes process reports intervals that behave as a user is
entitled to assume, and it ships the answer as code. Over a pre-registered grid of
128 cells and 2000 simulated replications per cell, the inverse-Hessian standard
errors understate sampling spread: the ratio of mean reported standard error to
empirical standard deviation, pooled over the twelve two-type cells with at least
2000 events, is 0.779 +/- 0.011, and the four-type satellite agrees in direction
(0.336 +/- 0.023). Two hypotheses were not confirmed: H6.3 expected coverage to
fall monotonically toward criticality and it rose instead, and H6.4 expected
timestamp quantisation to bias the decay estimate upward and it biased it down.
The estimator is undefined in 67 of 128 cells, where the observation window holds
too few decay times to identify the decay rate. The library therefore refuses to
report an interval there, and where the map measures a shortfall it switches to a
parametric bootstrap rather than reporting the interval it knows to be too narrow;
the switch is tested in a second pre-registered study and its result is reported
either way.
```

The arXiv form takes 1920 characters, not words. This block is well inside it.

## Licence

**MIT**, matching the software. arXiv asks for a licence for the paper separately
from the code; MIT is the least restrictive choice that is compatible with the
repository's own, and it lets a reader reuse the figures.

## Endorsement

arXiv requires an endorsement for a first submission to a category by an author who
has not previously submitted there. The owner needs an endorser for **stat.ME**
before the submission can be completed, or should choose a category where they are
already endorsed. This is stated plainly here because it is the step most likely to
block a submission at the last minute.

## File list

| File | What it is |
|---|---|
| `paper/main.tex` | the document: preamble, section order, `\input`s |
| `paper/generated/*.tex` | section bodies, tables and macro definitions, all generated |
| `paper/refs.bib` | the bibliography |
| `studies/make_paper_tex.py` | the generator; not uploaded, but named in the paper |
| `studies/check_paper.py` | the structural checks; not uploaded |

arXiv takes a single `.tar.gz` of `main.tex`, `refs.bib`, the `generated/`
directory and the `figures/` directory. Five figures are included:

| File | Where it appears |
|---|---|
| `figures/coverage_heatmap.pdf` | section 4, full width |
| `figures/se_vs_sd.pdf` | section 4 |
| `figures/bias_vs_N.pdf` | section 4 |
| `figures/verdict_crosstab.pdf` | section 4 |
| `figures/auto_coverage.pdf` | section 5 |

All five are vector with embedded fonts (PDF font type 42) and are copied from
`studies/figures/` by the generator, so the archive builds without the rest of the
repository. `studies/figures/README.md` maps each figure to the claim it supports.

## What to check after the build

`studies/check_paper.py` verifies the structure a compile would fail on — every
macro defined exactly once, every `\input` present, every table's cell count
matching its column spec, every figure resolvable through `\graphicspath`, every
citation resolving to an entry with a year and a DOI. It cannot check that the
typeset result looks right. Read the PDF: a table wider than the margin and a
figure that collides with a caption both compile cleanly and both look wrong.

## Unverified references

All seven entries in `paper/refs.bib` have now been checked against the publisher
record or the arXiv listing.

The last open one was `laub2015`. Both candidate identifiers were opened: the
working paper is arXiv:1507.02822, "Hawkes Processes" by Laub, Taimre and Pollett
(math.PR, 10 July 2015), and 1907.02822 is "Deep Personalized Re-targeting", an
unrelated 2019 paper in cs.IR. The entry carried the correct identifier throughout;
it is now marked checked rather than `[VERIFY]`.

A check made during preparation also corrected the Chen & Hall entry, whose DOI had
been recorded as ending `0095` where the publisher record gives `0096`. That is the
reason the check is worth doing rather than assuming: a DOI off by one digit in the
last place resolves to nothing or, worse, to a different paper.
