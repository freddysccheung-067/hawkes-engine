# hawkes-engine 0.2.0

Released 2026-10-24. Pre-alpha research release.

0.1.0 measured its own weakness and stopped there. It shipped a map that says, for
a given regime, how much the reported standard error understates the sampling
spread -- and left the user to read the map and decide what to do. 0.2.0 answers
that in code: `fit(..., se_method="auto")` consults the map, and where the map
measured a shortfall it reports a different interval rather than the one it knows
to be too narrow. This release also turns the paper into a submission.

The API may change between 0.x minor versions, and this one adds an argument and
three result fields. See
[ADR-009](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/adr/ADR-009-versioning.md).

## What changed in behaviour

This is the part to read before upgrading.

- **`se_method="auto"` is new; the default is unchanged.** `"hessian"` is still
  the default and still behaves exactly as in 0.1.0. `"auto"` is opt-in, and it may
  choose the bootstrap, which costs time.
- **A fit with `se_method="auto"` can take minutes.** The bootstrap refits the
  model 200 times. Before it runs, the projected cost is compared with
  `auto_max_seconds` (default 120). The projection is a power law fitted to the
  four measured serial configurations of the capability table, times the measured
  efficiency of the process pool; it reproduces every measured row to within three
  percent. Above the limit, `auto` keeps the Hessian interval, says in `se_note`
  what was indicated and what it would have cost, and emits a `RuntimeWarning`.
  It does not silently spend the time.
- **`FitResult` gains `se_source`, `se_note` and `auto`.** `se_source` is
  `"hessian"`, `"bootstrap"` or `"none"`, and it is the field to read before reading
  `se`: a result can carry `se is None` with `se_source == "none"`, which is a
  statement, not a failure. The serialisation schema is 2; schema-1 documents still
  load, with `se_source` reading as `"hessian"` and no record, because a 0.1.0
  document cannot know what it did not record.
- **`n_bootstrap` below 10 is refused** for `"bootstrap"` and `"auto"`. The
  bootstrap never reports an interval below ten usable replications; failing at the
  call is clearer than a fit that runs and returns nothing.
- **`fit` accepts `bootstrap_workers`.** A study that parallelises over fits should
  set it to 1; leaving it at `None` starts one pool per fit.

## What `auto` does when it does not know

The policy is written down in
[`docs/se_policy.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/se_policy.md)
before the feature, and the four cases are:

| The map says | `auto` does | `se_source` |
|---|---|---|
| a block's 2-SE interval around the measured `q` excludes 1 | bootstrap, if the projection fits in `auto_max_seconds` | `"bootstrap"` |
| the regime is outside the measured box | Hessian, labelled uncalibrated | `"hessian"` |
| the estimator is undefined in this regime | no interval at all | `"none"` |
| `q` is indistinguishable from 1, or the bootstrap was refused by the limit | Hessian | `"hessian"` |

The threshold is twice the Monte Carlo standard error of the measured `q` itself,
which is the precision the study's 2000 replications support. A consequence worth
stating: at that threshold **every** cell in the shipped map fires, so `auto`
chooses the bootstrap wherever the map has measured, and the Hessian only where the
map is silent or the projection exceeds the limit. That is a measured property of
the estimator, not an artefact of the rule, and the [Limits
page](https://github.com/freddysccheung-067/hawkes-engine/blob/main/docs/limits.md)
says so.

## The interval study

The switch is tested, not asserted. A second pre-registration was frozen before its
harness existed -- a fresh document rather than an amendment to H6, because H6
measured no alternative interval and the hypothesis this study tests is not in that
document. Three cells at 2000 events, 2000 replications each, both arms fitted to
the same simulated event stream so the comparison is paired.

The result, whatever it is, is in `studies/results/auto/analysis/report.txt` in the
repository, with the hypotheses labelled there. A null result is reported as a null
result.

## The paper

`paper/main.tex` builds to a PDF from one command, and every number and every table
in it is emitted by `studies/make_paper_tex.py` from a committed output; nothing is
typed by hand. `paper/refs.bib` holds the references, with the entries that could
not be verified marked in `paper/SUBMISSION.md` rather than presented as checked.
`paper/SUBMISSION.md` is the arXiv checklist. Nothing has been submitted.

## What this release does not fix

Stated as plainly as 0.1.0 stated its limits.

- **`auto` does not fix bias.** The point estimate is unchanged. Only the width of
  an interval it reports can change, and only where the map measured a reason to
  change it.
- **`auto` does not make the undefined region estimable.** Where the window holds
  too few decay times for the decay to be identified, `auto` refuses to report an
  interval. It does not find one.
- **`auto` does not cover `shared_decay=True`**, which is a different model with
  `M` decay rates and is outside the measured map. It says so and uses the Hessian.
- **`auto` does not extrapolate.** Outside the measured box it uses the Hessian
  and labels the interval uncalibrated.
- **If the bootstrap fails to produce a usable refit often enough**, the result is
  `se_source="none"` with a note, not a wider interval.
- Large `M` at small `N` remains slow and unreliable, and the calibration map still
  covers two types and one decay form.

## Install

```bash
python -m pip install hawkes-engine==0.2.0
```

Supported platforms and Python versions are unchanged from 0.1.0.
