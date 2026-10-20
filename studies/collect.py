"""Is the H6 run finished, and is the data intact?

This module computes **no estimand**. E3.1 to E3.7 are Phase 4 and live in
``analyze.py``; putting a single mean in here would blur the line between "the
run is complete" and "the run says something", and the second question is only
answerable once the first is yes for every cell.

It reports: how many cells have a ``.done``, which are missing and why, whether
every ``.done`` checksum re-verifies against its rows, and whether any cell
reached ``R``. When everything is complete it also concatenates the rows into
one file, because a reader who wants the frame should not have to write the
concatenation.

Usage::

    python -m studies.collect            # report
    python -m studies.collect --concat   # also write studies/results/all.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from studies.grid import R, load_cells
from studies.run_cell import COLUMNS, is_complete, read_rows

STUDIES = Path(__file__).resolve().parent
RESULTS = STUDIES / "results"
CELLS_DIR = RESULTS / "cells"


def collect(out_dir: Path = CELLS_DIR) -> dict[str, object]:
    """The integrity report, as a plain dictionary."""
    cells = load_cells()
    complete, incomplete, short = [], [], []
    for cell in cells:
        ok, reason = is_complete(cell, out_dir)
        if not ok:
            incomplete.append((cell.key, reason))
            continue
        rows = read_rows(out_dir / f"{cell.key}.csv")
        complete.append(cell.key)
        if len(rows) < R:
            short.append((cell.key, len(rows)))
    return {
        "expected": len(cells),
        "complete": len(complete),
        "missing": incomplete,
        "short": short,
        "complete_keys": complete,
    }


def concatenate(out_dir: Path = CELLS_DIR, target: Path | None = None) -> Path:
    """Write every cell's rows to one CSV, cells in frozen grid order."""
    target = target or (RESULTS / "all.csv")
    cells = load_cells()
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for cell in cells:
            path = out_dir / f"{cell.key}.csv"
            if not path.exists():
                continue
            for row in read_rows(path):
                writer.writerow(row)
                written += 1
    print(f"wrote {written} rows to {target}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--concat", action="store_true", help="also write one combined CSV")
    args = parser.parse_args(argv)

    report = collect()
    print(f"cells complete : {report['complete']}/{report['expected']}")
    print(f"rows expected  : {report['expected'] * R}")
    if report["short"]:
        print(f"cells below R  : {len(report['short'])}")
        for key, count in report["short"]:
            print(f"  {key:44s} {count}/{R}")
    if report["missing"]:
        print(f"cells missing  : {len(report['missing'])}")
        for key, reason in report["missing"]:
            print(f"  {key:44s} {reason}")
        print("\nThe run is not finished. Do not compute estimands yet.")
        return 1
    print("every cell has a .done whose checksum re-verifies against its rows")
    if args.concat:
        concatenate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
