# hawkes-engine 0.3.0

Released <!-- RELEASE_DATE -->. Pre-alpha research release.

0.2.0 gave the estimator a calibration map and a switch that consults it. 0.3.0
does three things: it makes the package installable on the Python versions most
people are actually running, it stops the bootstrap losing a fit when its worker
pool dies, and it runs the experiment the paper had named but could not do. That
experiment came back null, and the null is the most useful result in this release.

The API does not change. There is one new keyword argument and one new export, both
additive.

## What changed in behaviour

This is the part to read before upgrading.

- **Wheels for CPython 3.13 and 3.14.** `requires-python` has been `>=3.10` with no
  upper bound since 0.1.0, so pip told a user on 3.13 the package supported them and
  then handed them an sdist that needs a C++20 toolchain. Most new installs are 3.13
  or 3.14. Nothing in the build requirements moved: pybind11 binds the NumPy C API
  through a runtime capsule, and `CMakeLists.txt` has no `NumPy::NumPy` target, so
  there is no compile-time ABI to match. The free-threaded `cp314t` builds are
  excluded on purpose, because the pool-based bootstrap is not supported there.
- **A bootstrap no longer fails because its pool died.** The worker pool could die
  under load with `RuntimeError("the bootstrap worker pool died")`, and the README's
  own example lost its fit to it in 2 of 25 runs. The replications are now computed
  in the caller's process when that happens. The draws are identical, because
  `_child_seed` derives each replication's seed from the caller's seed and its index
  alone; the fit is slower and its notes say so.
- **A missing `if __name__ == "__main__":` guard still fails.** That is deliberate.
  A pool that produced nothing keeps the existing error with its guard advice, and a
  pool that produced something is retried. The two cases are told apart by completion
  count, which was measured: an unguarded run died with 0 completions in 3 of 3, and
  the load race died at 12.
- **`fit` accepts `bootstrap_progress`.** A callable taking `(done, total)`, so a
  two-minute bootstrap is not silent. It observes and cannot change a draw.
- **`ljung_box` and `ReliabilityReport` are in `__all__`.** They were documented and
  importable from their module, but not exported from the package.

## The sandwich study: the fix the paper named was aimed at the wrong term

The paper's theory section derives the sandwich covariance
`I^-1 J I^-1` and shows that the information equality `J = I` collapses it to the
inverse Hessian the library computes. It measures a shortfall (`q = 0.779` pooled)
that a Jensen correction predicts in sign and ordering but not in magnitude, and it
said plainly that a sandwich estimator computed from a correctly evaluated `J` was
the natural candidate for closing the gap, and that the study had stored no
per-replication Hessian so it could not be tested.

It can be tested now, and the answer is no. The study was pre-registered and frozen
at tag `SW-preregistration` before it ran: 7 cells, 2000 replications each, 543 s for
the two expensive cells.

| Hypothesis | Label |
|---|---|
| H-S1, the sandwich ratio is within 0.10 of 1 and better than `q` in every primary cell | **not confirmed** |
| H-S2, the sandwich ratio is at most 1.10 in every primary cell | confirmed |
| H-S3, the sandwich improves more where the estimate is more irregular (exploratory) | **not confirmed** |
| H-S4, the sandwich does not improve in the quantisation cells | **not confirmed** |

The mechanism is the result. The information equality holds to within the
finite-window effect: `J0/I0` is between 0.951 and 1.053 coordinate by coordinate
across the five primary cells. A sandwich therefore differs from the inverse Hessian
by at most a factor of 1.026 and cannot close a gap of 0.15 to 0.25. The shortfall
`h6-v1` measured is not an information-equality failure.

The second finding is about the headline itself. At the anchor cell the decay block's
`q` is 0.007 on the mean statistic and 0.835 on the median/MAD companion, both from
the same 2000 replications; the difference is one replication that fitted
`beta = 252` against a truth of 1.2. So the pooled `q = 0.779` describes the tail of
the estimate distribution rather than the width of the interval, and the paper now
says so.

Two defects in the study's own harness were found and fixed before those numbers, and
both would have produced a confident wrong answer rather than an error: the score was
taken in log space and compared against a natural-space information matrix, and the
bread was inverted from its diagonal only, discarding correlations reaching 1806
against a diagonal of 2624. `tests/test_sandwich_harness.py` pins both, using the
information equality as the check that catches either.

## The paper

The paper is now about 9,700 words, up from 3,300. Section 2b derives the standard
error instead of describing it; section 8 says what a practitioner should take from
the result and what the work does not establish. Every number in it is emitted by
`studies/make_paper_tex.py` from a committed output, and 193 tests pin those numbers
to their sources, including four that pin the prose itself against the vocabulary and
constructions that creep back into generated text.

The eigenvector claim is now stated as an assumption the study is consistent with,
in those words, because the committed outputs record no per-replication Hessian and
cannot settle it.

The paper is deposited on HAL as `hal-05838093` and is **in moderation**: HAL assigns
an identifier at deposit and does not serve the record until a moderator accepts it.
The API indexes public records only, returns nothing for that identifier, and returns
public neighbours numbered above it, so the deposit is held rather than missing. It is
not submitted to arXiv, which needs an endorsement for `stat.ME`.

## What this release does not fix

- **The shortfall has no explanation yet.** The sandwich study ruled out the
  information-equality term without supplying a replacement. Equation (qvarcv) closes
  the derivation, and the part that would predict the magnitude needs the joint
  distribution of the reported variance's fluctuation in the decay direction.
- **`auto` still does not cover `shared_decay=True`**, which is a different model with
  `M` decay rates and sits outside the measured map.
- **The map is still two types, one kernel, one decay form.** Nothing in this release
  widens it.
- **`auto` does not extrapolate.** Outside the measured box it uses the Hessian and
  labels the interval uncalibrated.
- **The GIL smoke test now takes about a second longer.** Its window grew from 40 ms
  to 350 ms, because at 90 ms the measurement inverted under load on a busy runner.
  It is measuring a real property and needed the longer window to do it.

## Install

```bash
python -m pip install hawkes-engine==0.3.0
```

## The DOI

This release has no DOI yet. Zenodo mints one when the GitHub release is archived.

There are two existing Zenodo records, and they are separate series rather than
versions of one another: `10.5281/zenodo.23613789` for 0.1.0 (deposited by hand) and
`10.5281/zenodo.23620653` for 0.2.0 (deposited by the GitHub integration), with
concept DOIs `23613788` and `23620652`. The integration did not fire for 0.2.0 on
its own, so 0.3.0 should be deposited into the `23620652` series by hand, or the
repository toggled in Zenodo's GitHub settings and the release re-published. Check
zenodo.org before assuming a DOI exists; a GitHub release existing is not evidence
that it does.

When the DOI is minted, this paragraph and `CITATION.cff` are updated in one commit,
which `tests/test_release_metadata.py` enforces.
