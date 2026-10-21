# The trust map

`trust_lookup` reports what a pre-registered simulation study measured about this
estimator in a regime like yours. It is separate from `FitResult.reliable`, which
describes one fit. The study is called `h6-v1`; its design was frozen at the git tag
`H6-preregistration` before any cell ran.

```python
import hawkes_engine as he

answer = he.trust_lookup(N=2000, rho_hat=0.3028, beta=1.0, T=1722.6)
print(answer.status, answer.cell, answer.distance)
```

`N` is the number of events, `rho_hat` the fitted branching ratio, `beta` the
**smallest** fitted decay rate, `T` the observation window, and `resolution` the
timestamp resolution in the units of `T` (0 for exact times).

## The three outcomes

`status` is one of:

**`"measured"`.** The query lies inside the measured box. `coverage` gives, for each
block (`mu`, `alpha`, `beta`, `all`), the share of nominal-95% intervals that
covered the truth in the nearest cell over 2000 replications, with its Monte Carlo
standard error. A fit that returned no standard error counts as a miss. `q` gives
the ratio of mean reported standard error to empirical standard deviation per
block, with a bootstrap standard error; below 1 means the reported standard errors
were too small.

**`"unknown"`.** The query is outside the box, and no number is given. The lookup
does not extrapolate, because the study cannot say what happens beyond what it ran.

**`"estimator undefined in this regime"`.** The nearest cell is one where most fits
returned no standard error, or the window held too few decay times for $\beta$ to
be identified. No coverage is reported.

## The measured box

Two types (plus a four-type satellite of 8 cells), pair decay, $\rho \le 0.95$,
$200 \le N \le 50\,000$, $\beta\delta \le 0.13$ (where $\delta$ is the timestamp
resolution), and $\beta_{\min}T$ inside the range the grid spans. Anything else
returns `"unknown"` with a note saying which bound was crossed. The map has 128
cells; each was run at one fixed parameter set
([studies/theta0.json](https://github.com/freddysccheung-067/hawkes-engine/blob/main/studies/theta0.json)),
so the map describes those parameters at that $(N, \rho, \beta T)$, not every
process with the same summary numbers.

## How to read `distance`

`distance` is the Euclidean distance to the nearest cell in grid-step units over
$(\log_{10} N,\ \rho,\ r,\ \log_{10}\beta_{\min}T)$, each axis divided by a typical
step. 0 is a grid point and 1 is about one step away. **The lookup answers however
large the distance is.** It does not refuse a far-away cell, so a `"measured"`
status with a distance of 2 describes a cell two steps from your regime.

## The six hypotheses

The study pre-registered six hypotheses. The table is generated from
`studies/results/analysis/hypotheses.json` when this page is built. Where the
admissible readings of a standard error disagreed, the label is the least
favourable one any of them gave.

```{include} _generated/hypotheses.md
```

- **H6.5, confirmed.** The reported standard errors understate sampling spread. This
  is the headline result.
- **H6.6, confirmed but mostly mechanical.** The `reliable` verdict separates
  coverage because 96.4 percent of `unreliable` replications carry no standard
  error, and a replication without one counts as a miss. Among replications that do
  carry one, a post hoc check gives a separation of about +0.07 +/- 0.04. The
  verdict marks fits that produced an interval; it does not detect an interval that
  is wrong.
- **H6.3, not confirmed.** Coverage does not fall monotonically toward criticality.
- **H6.4, not confirmed.** Timestamp quantisation moved the decay estimate downward
  at $N \ge 10\,000$, the opposite of the hypothesis.
- **H6.1 and H6.2, confirmed (exploratory).** They replicate a direction found
  before the study was designed, so they are labelled exploratory and carry no
  headline.

The paper draft is generated from the same analysis:
[paper/draft.md](https://github.com/freddysccheung-067/hawkes-engine/blob/main/paper/draft.md).
