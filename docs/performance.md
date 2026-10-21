# Performance

Every figure here is from one machine and is copied from
[`capability_2026-10-21.md`](https://github.com/freddysccheung-067/hawkes-engine/blob/main/benchmarks/results/capability_2026-10-21.md),
which `benchmarks/capability_report.py` generates from the CSVs beside it. The
tables below are extracted from that file when this page is built; nothing is
retyped. The machine was an Intel Core Ultra 9 275HX with 24 logical cores and 31.4
GiB of RAM, Windows 11, MSVC without `-march=native`, Python 3.12.10. Other
hardware will differ. Cells with `reps` of 1 are single runs and carry no spread.

## One fit, about a million events

Pair decay, one start, `se_method="hessian"`, a fresh process per run. `label` is the
library's own reliability label for that fit, a conditioning report and not a
statement about bias.

```{include} _generated/wall_clock.md
```

The slowest fit measured took 13.8 min (828.62 s), at eight types, $\rho = 0.3$ and
1,001,390 events. The one-hour wall was not reached. Nothing above $N = 10^6$ was timed. The full
table, including the smaller $N$ where large $M$ is dominated by iteration count, is
in the capability file.

## An honest interval costs more

`se_method="bootstrap"` at four types, $N = 10^5$, $B = 200$. "default" is the pool
of all logical cores. Larger bootstrap configurations were not timed.

```{include} _generated/bootstrap.md
```

## Pair decay against shared decay

Median time of one likelihood call at $N = 10^6$. This is a call-level ratio. A
fit-level speed-up for shared decay was not measured, and shared decay is a
different model.

```{include} _generated/pair_shared.md
```

## Memory

The capability file reports about 33 bytes per event, nearly independent of $M$ and
unchanged by the Hessian pass, and a peak of 316 MiB above the import baseline at
$N = 10^7$. Memory does not bind before time does on that machine. The Linux
measurement path was implemented but not run.
