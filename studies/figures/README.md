# Figures, and the claim each one supports

Every figure here is a vector PDF written by `studies/figures/make_figures.py` from
a committed output in `studies/results/`. None is edited by hand and none is
regenerated from a number typed anywhere else. Rebuild all of them with

```bash
python -m studies.figures.make_figures
```

The palette is the four categorical slots the figure script declares
(`#2a78d6`, `#eb6834`, `#1baf7a`, `#eda100`), which stay distinguishable in
greyscale and under the common forms of colour blindness; each series also carries a
distinct marker, so a reader who prints the page in black and white can still tell
them apart. Fonts are embedded (PDF font type 42), body text is set at 8 to 10 pt,
and every axis carries a label and its units.

## The figures

| File | The claim it supports | Where the claim is stated |
|---|---|---|
| `coverage_heatmap.pdf` | Nominal-95% intervals built from Hessian standard errors cover less than 95% at small sample size, and the shortfall is worst in the decay block. The heat map prints the measured coverage, its Monte Carlo standard error and the no-standard-error rate in every cell, so a reader can see which cells the claim rests on and which contribute nothing because no interval existed. | Section 4 of `paper/draft.md`; [](limits.md) section 1 |
| `se_vs_sd.pdf` | The mean reported standard error is below the empirical standard deviation of the estimates, cell by cell, and lies below the identity line almost everywhere inside the measured region. This is the direct picture of `q < 1`; the pooled number (`q = 0.779 +/- 0.011`) is a summary of the same points. | Section 4; H6.5 |
| `bias_vs_N.pdf` | Relative bias falls with the number of events on the mean scale, while the median-based companion stays flat and smaller: the mean is dominated by a heavy tail in the decay estimate at small sample size, so a mean-based bias figure should be read beside its robust companion. | Section 6 ("the heavy tail in `beta_hat`"); [](limits.md) section 5 |
| `verdict_crosstab.pdf` | Measured coverage differs between `reliable` and `unreliable` fits, and the difference is mostly mechanical: the `unreliable` class is largely composed of fits that returned no interval, which count as misses by definition. | Section 4 (H6.6); [](limits.md) section 4 |
| `auto_coverage.pdf` | Hessian and `auto` coverage of the same simulated event streams, per cell and block, with the nominal line. Each segment joins the two arms of one cell, so the direction and size of the change is visible. Supports the interval-decision section and the H-A1 and H-A2 verdicts. | Section 5 of `paper/main.tex`; `studies/results/auto/analysis/report.txt` |

## What is not shown

- No figure compares this implementation with another library. No such comparison
  was made, so no plot of one exists.
- No figure plots a speed or memory claim against a target. The capability table is
  a table, and [](performance.md) quotes it.
- `auto_coverage.pdf` is absent until the interval study has run; the figure script
  prints that it is skipping and exits cleanly rather than failing, so the other
  four can be rebuilt on a checkout that does not have the study's outputs.

## Printing

Every figure is sized for a single column of a two-column layout at roughly 84 mm
wide, except `coverage_heatmap.pdf` and `verdict_crosstab.pdf`, which are full-width
and should be placed as `figure*`. All are vector, so they scale without loss; none
contains raster data.
