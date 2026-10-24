0.2.0 is the release in which the calibration study drives the estimator, and the release in which the paper first compiled.

## What 0.2.0 adds

`fit(..., se_method="auto")` consults the shipped calibration map and acts on what was measured: where an estimated block's two-standard-error interval around `q` excludes 1 it reports a parametric-bootstrap interval, where the map has no measurement it keeps the Hessian interval and labels it uncalibrated, and where the map reports the estimator undefined it reports no interval. The default stays `"hessian"`.

The auto-v1 study tested the switch and is pre-registered separately from H6, with three cells at 2000 events and both arms on the same event streams. Coverage moves from 0.8937 to 0.9488 at rho = 0.95 and from 0.9207 to 0.9609 at rho = 0.3028. All three of its hypotheses are labelled in the release.

## The paper, and what had never been done to it

`paper/main.tex` is generated from committed outputs. It had never been typeset: every session that prepared the package reported that no TeX installation was available and that installing one was blocked, so the structure checks were the only evidence, and they cannot see a failing compile.

A `Paper` workflow now installs TeX Live, typesets, fails on an overfull box or an unresolved citation, and uploads the PDF. It found, in order:

- Twenty macros named `\Hsix61Label` and so on. A TeX control word ends at the first non-letter, so each was read as `\Hsix` plus the text `61Label`, which arrived in the preamble and produced "Missing \begin{document}". `check_paper.py` could not see them because its own pattern is `[A-Za-z]+` and stops at the digit; it now rejects any non-letter name.
- The abstract said two hypotheses were "refuted" where every other page says "not confirmed". H6.3's threshold clause held and only its monotonicity clause failed, so the stronger word was not the paper's to use.
- The plain-text abstract in `SUBMISSION.md`, which claims to be what the paper renders, was a different text: 168 words against 182, with a different claim in the middle. `tests/test_paper_abstract.py` now expands the generated abstract and compares word for word.
- The grid table overhung the margin by 78pt and the hypothesis table by 29pt.
- Five labelled floats that the prose never referenced, and a `\ref` with no matching `\label`, which compiles cleanly and prints "??".

## Provenance and dates

- The reproducibility section embedded `HEAD`, so committing it made it stale on arrival and its own guard failed on every clean checkout. It now reads `provenance.analysis_commit` from the analysed outputs, which is a property of the data and identical under a shallow clone.
- `run_auto.py` now writes the `provenance.json` that `preregistration_auto.md` promised and nothing produced.
- The auto pre-registration said it was frozen on 2026-10-26. The commit that froze it is dated 2026-10-24. Amendment 1 corrects the date and states what had been seen.

## README

The README said "Pre-alpha. Not on PyPI." five days after 0.1.0 went to PyPI, and said so on four other published pages including `install.md` and the competitor survey, which still described the library as having no estimator. Both are corrected. The README now leads with what was measured, as two figures drawn from the same analysis rows as the paper figures, so a README figure cannot drift from the paper.

## Checks

`python -m studies.gate`: 10 of 10. 460 fast tests, `sphinx -W`, ruff, mypy, the grid digest, the docs-claims pins and the paper structure checks. `oracle/` untouched.
