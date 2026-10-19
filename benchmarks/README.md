# Benchmarks

`bench_loglik.py` times the compiled likelihood and the reference
implementation and writes one CSV per day to `results/`.

The numbers are a baseline for this project on one machine. They are not a
comparison against any other library, and no speed claim elsewhere in the
repository is derived from them: the README says nothing about speed on
purpose, because there is no estimator yet for a speed comparison to mean
anything.

## Running

```bash
python benchmarks/bench_loglik.py
python benchmarks/bench_loglik.py --sizes 100000 --dims 2,4 --oracle-sizes 200,1000
```

The reference is O(N²M²), so it is timed on its own small grid
(`--oracle-sizes`, default 200/1000/2000). At N = 100 000 it would take hours
and tell you nothing you cannot read off the complexity.

## Baseline, 2026-10-19

`results/loglik_2026-10-19.csv`. Windows 11, MSVC 19.44, Python 3.12.10,
NumPy 2.5.4, Release build. Median seconds, N = 1 000 000:

| M | pair value | pair value+grad | shared value | shared value+grad |
|---|---|---|---|---|
| 2 | 0.037 | 0.053 | 0.037 | 0.045 |
| 4 | 0.145 | 0.120 | 0.028 | 0.040 |
| 8 | 0.456 | 0.501 | 0.094 | 0.105 |

The pair and shared columns at M = 2 are close because both loops are then
nearly the same length; the ratio widens with M, as it should, since the
shared state is O(M) and the pair state is O(M²).

The reference, same machine, N = 2 000: 1.34 s for M = 2, 3.54 s for M = 8.
That is the quadratic term doing what it says.
