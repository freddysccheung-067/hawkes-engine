# Limits

What this library does not do, where its estimates should not be believed, and the
file that shows it. Every figure on this page is copied from a committed output or
pinned to one by `tests/test_docs_claims.py`. The links go to the evidence on the
`main` branch.

## 1. The reported standard errors understate sampling spread

For the Hessian method, the ratio q of mean reported standard error to empirical
standard deviation, pooled over the 12 two-type cells with at least 2000 events
(`c = 1`, exact timestamps), is **0.779 +/- 0.011**. Per block over the same cells it
is 0.936 for the baselines, 0.869 for the excitation weights and **0.61** for the
decay rates. The four-type satellite points the same way (0.336 +/- 0.023). This is
hypothesis H6.5, confirmed after Holm correction.

How far it generalises:

- The pooled value is driven by the 2000-event cells, where per-cell q is between
  0.22 and 0.60. At 10 000 events and above every cell lies between 0.875 and 0.977.
- A median-based companion that ignores the heavy tail of the decay estimate gives
  0.983 +/- 0.003 (`qrob`). The shortfall is concentrated in the tail, not spread
  evenly.
- Nominal-95% intervals built from these standard errors covered between 0.918 and
  0.953 of the time at 10 000 events and above, and as little as 0.171 (the baseline
  block) at 200 events and a branching ratio of 0.95 (`paper/draft.md`, section 5).

Evidence: [`hypotheses.json`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/results/analysis/hypotheses.json),
[`paper/draft.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/paper/draft.md).
`trust_lookup` returns q and coverage per block for the nearest measured cell.

## 2. Two of the six hypotheses were not confirmed

- **H6.3, not confirmed.** The hypothesis was that coverage falls toward criticality.
  The threshold clause held (coverage at $\rho = 0.3028$ minus coverage at
  $\rho = 0.95$ was 0.0167 +/- 0.0059), but coverage rose from $\rho = 0.3028$ to
  $\rho = 0.60$, which fails the monotonicity clause.
- **H6.4, not confirmed.** The hypothesis was that timestamp quantisation biases the
  decay estimate upward. At $N \ge 10\,000$ it moved it **downward**, by 37 to 62
  percent. The very large negative mean over all 22 cells comes from the heavy tail
  of the small-$N$ cells and is not an effect of that size.

The labels of all six are on [](trust.md). Evidence:
[`ANALYSIS_NOTES.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/ANALYSIS_NOTES.md),
[`hypotheses.json`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/results/analysis/hypotheses.json).

## 3. The estimator is undefined where $\beta_{\min}T$ is small

If the observation window holds only a fraction of one decay time, $\beta$ cannot be
identified. In the study this happened in 67 of the 128 cells: all 60 cells at
decay scale `c = 1e-3` and 7 of the 68 at `c = 1`. In the `c = 1e-3`, exact-timestamp
cells 75 percent of fits returned no standard error, and the fitted $\beta$ ran to
its upper search bound, 10^4 to 10^6 times the true value. `trust_lookup` answers
`"estimator undefined in this regime"` for these. Nothing on the way into `fit`
stops you fitting such data; check $\beta_{\min}T$ yourself. The study ran at
$\beta_{\min}T$ from 0.012 to 43 066.

Evidence: [`RUN_REPORT.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/RUN_REPORT.md),
section 2.

## 4. H6.6 is confirmed but mostly mechanical

The `reliable` verdict separates coverage (a difference of 0.775 +/- 0.011), and the
pre-registered rule was met. But 96.4 percent of the `unreliable` replications
carry no standard error, and a replication without one counts as a miss. Among
replications that do carry a standard error, a post hoc check gives a separation of
+0.0726 +/- 0.0394. The verdict marks fits that produced an interval. It does not
detect an interval that is wrong.

Evidence: [`phase3_report.txt`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/results/analysis/phase3_report.txt),
`paper/draft.md` section 4.

## 5. Small $N$: a heavy tail in the decay estimate, and the verdict does not see it

At `c = 1`, exact timestamps, two types, the study found 5454 converged fits whose
$\hat\beta$ exceeded ten times the largest true $\beta$. The library labelled **3211
of them `reliable`**. At the anchor cell ($N = 2000$, $\rho = 0.3028$, true
$\beta_{01} = 1.2$) the estimate of $\beta_{01}$ has median 1.305 and maximum 43914.
Means and standard deviations of $\hat\beta$ are not meaningful summaries there.

You can see one such fit in `examples/01_simulate_and_fit.py`: a 2000-unit window of
the quickstart process returns $\hat\beta_{11} \approx 452$ against a truth of 1.7,
converged, `reliable`. `examples/02_time_rescaling_check.py` shows the time-rescaling
diagnostic also passes on it. Neither the verdict nor that diagnostic catches this.

Evidence: [`RUN_REPORT.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/RUN_REPORT.md),
section 3, and [`phase3_report.txt`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/results/analysis/phase3_report.txt).

## 6. Large $M$ at small $N$ is slow and unreliable

At $M \ge 6$ with about $10^4$ events, fits finish but the optimiser needs 942 to
2765 iterations, and the library labels the fit `marginal` or `unreliable` in all
four cases measured. Time is not the limit there; identifiability is.

```{include} _generated/cannot_do.md
```

Evidence: [capability table](https://github.com/freddysccheung-067/hawkes-engine/blob/main/benchmarks/results/capability_2026-10-21.md), sections 1 and 6.

## 7. What was not measured

- Nothing above $N = 10^6$ was timed, and no fit reached an hour, so the upper limit
  is not located. Memory was measured up to $10^7$ events.
- Every timing is from one machine (see [](performance.md)). Single-run cells
  carry no spread.
- The calibration study covers two types and a four-type satellite of 8 cells, pair
  decay and exponential kernels. `shared_decay=True` is a different model with
  $M$ decay rates, and its fits are outside the measured map. Only the speed of the
  shared-decay likelihood call was measured, not of a fit.
- The bootstrap standard errors were not part of the calibration study.
- `trust_lookup` answers from the nearest of 128 cells, each run at one parameter
  set, and gives that answer however far the cell is.
- All events must be observed. Censoring and missing data are not modelled.
