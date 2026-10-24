# The `se_method="auto"` policy

This page is written before the feature. It states what `auto` will do, why each
rule is the one the shipped map supports, and what the switch costs. The code in
`python/hawkes_engine/se_policy.py` implements this page; `docs/preregistration_auto.md`
freezes the study that tests whether the switch helps.

`auto` adds no mathematics to the estimator. It is a decision layer above the fit:
the likelihood, the gradient, the Hessian and the bootstrap are unchanged.

## The question `auto` answers

The H6 study measured the inverse-Hessian standard errors against the sampling
spread of the same estimates, per cell and per block, and shipped the result as
`data/trust/v1_excitation_only.csv`. The ratio `q = mean reported SE / empirical
SD` is below 1 wherever the interval is narrower than the spread it describes.
A user who calls `fit` cannot be expected to look that up, read a distance, and
choose a method. `auto` does it for them, and records what it did.

## The rule

`auto` runs the fit, looks the fitted regime up in the shipped map, and takes one
of four actions.

1. **The map does not cover the regime** (`status == "unknown"`). Use the Hessian.
   `se_source="hessian"`, and `se_note` says the interval is uncalibrated because
   nothing was measured there. `auto` does **not** bootstrap here. Bootstrapping
   would produce a number with no measured property behind it and would imply
   knowledge the map does not have; the Hessian interval at least has the same
   asymptotic theory as the point estimate, and the note says what it is.

2. **The map says the estimator is undefined** (`status == "estimator undefined in
   this regime"`). Return no standard error. `se_source="none"`, no `se`, no
   intervals, `reliable="unreliable"`. `se_note` names the regime axis that failed,
   which is `beta_min*T` when the window holds too few decay times and the
   no-standard-error rate when most fits in the cell returned none. A number must
   never be returned here: in these cells the measured rate of fits with a usable
   standard error is at most 0.5, and the map's own rule made that the definition
   of the flag.

3. **The map is measured and a block is miscalibrated in a known direction.** Use
   the parametric bootstrap with `B = 200`. This is the case the release exists for.

4. **The map is measured and no block is miscalibrated.** Use the Hessian.

### The threshold, and why it is two Monte Carlo standard errors

The map reports, per block, `q` with a bootstrap standard error `se_q`. The rule
compares each **estimated** block (a block the caller fixed is not estimated and is
not tested) against

```
q + 2 * se_q < 1        (the interval is narrower than the spread)
q - 2 * se_q > 1        (the interval is wider than the spread)
```

The 2 is not a convention imported from elsewhere. Each cell in the map is a mean
over 2000 replications, so `se_q` is the Monte Carlo uncertainty of the measured
ratio itself. If the 2-SE interval around `q` excludes 1, then the direction of the
miscalibration is resolved at the level the study's own replication count supports:
the observed shortfall is larger than the noise in measuring it. If the interval
contains 1, the map cannot distinguish this cell from a correctly calibrated one,
and switching method on that evidence would be switching on noise.

Two Monte Carlo standard errors rather than 1.96 is deliberate. It is the
conventional two-sided rule, it is stated to the user as "twice the study's own
error bar", and the difference from 1.96 changes no decision anywhere in the
shipped map (see the table below).

**A consequence, stated plainly.** At this threshold, **every** measured cell in
the shipped map fires: 61 of the 61 cells that are not estimator-undefined carry at
least one block whose 2-SE interval excludes 1. The map does not certify a single
regime in which the Hessian interval is measurably adequate. `auto` therefore
chooses the bootstrap for every regime the map has measured, and the Hessian only
where the map is silent or where the caller's projection exceeds the time limit.
That is a real property of the measurement, not a defect of the rule, and the
release notes say so. It is also why the cost control below is not optional.

The blocks, over the 61 defined cells:

| Block | `q + 2 se < 1` | `q - 2 se > 1` | Neither |
|---|---|---|---|
| `mu` | 40 | 1 | 20 |
| `alpha` | 32 | 12 | 17 |
| `beta` | 46 | 11 | 4 |

## The cost of the switch, and the limit on it

The bootstrap refits the model `B = 200` times. Measured on the machine the
capability table describes, at M = 4, N = 1e5, `B = 200` costs 8.5 min on one
worker, 2.3 min on four, and **86 s on the default 24-process pool**. A switch that
silently spends minutes is not acceptable in a function whose other path costs
milliseconds, so the policy has three parts:

- **Project before spending.** `auto` estimates the cost from the work it has
  already done: the wall time of the fit it just ran, times `B`, divided by the
  number of workers the pool would use. That is a projection from a measurement of
  this machine on this data, not a constant from another machine.
- **Record it.** When `auto` chooses the bootstrap, the decision it stores in
  `FitResult` carries the projected seconds, and the fit's `se_note` says the
  switch happened and what it was projected to cost.
- **Refuse to blow through a limit.** `auto_max_seconds` defaults to **120**. If the
  projection exceeds it, `auto` does not bootstrap: it returns the Hessian interval,
  sets `se_source="hessian"`, and the note says that a bootstrap was indicated, what
  it was projected to cost, and that the limit prevented it. A warning is raised.
  The interval is then the uncalibrated one, and the note says which limit stopped
  the switch, so the user can raise `auto_max_seconds` deliberately.

The default of 120 s is chosen against the capability table: it admits the
bootstrap at M = 4, N = 1e5 on the default pool (86 s, measured) and refuses the
same configuration on one worker (8.5 min, measured), which is the boundary between
a wait a user will accept inside a fit call and one they will not.

## What `auto` does not do

- It does not fix bias. The point estimate is unchanged; only the width of an
  interval it reports can change.
- It does not make the undefined region estimable. Where `beta_min*T` is small
  enough the decay is not identified, `auto` refuses to report an interval rather
  than papering over it.
- It does not widen beyond what the bootstrap measures. `auto` never scales a
  Hessian interval by a constant; it either uses the Hessian as it is or replaces
  it with the bootstrap's.
- It does not extrapolate. Outside the measured box it says so and uses the
  Hessian.
- It does not cover `shared_decay=True`, which is a different model with `M` decay
  rates and is outside the measured map.

## The record

Every `auto` fit carries a `FitResult.auto` decision record with the fields the
audit needs: the map status, the cell, the distance, the `q` and `se_q` it read per
block, the threshold, the action taken with its reason, the projected and limit
seconds, and whether the bootstrap ran. `FitResult.se_source` is one of
`"hessian"`, `"bootstrap"`, `"none"`; `FitResult.se_note` is one sentence.

Both survive `to_dict` / `from_dict` unchanged. A number whose provenance is not
in the object is a number the user has to trust.

## Verifying it

Whether the switch actually improves coverage is a measurement, not an argument.
`docs/preregistration_auto.md` freezes that measurement before it runs, and
`studies/results/auto/` holds the result. If the bootstrap does not move coverage
toward nominal, that is the finding, and it ships as one.
