"""Build the shipped trust map from the analysis output. Computes nothing new.

One row per grid cell, 128 rows, written to ``data/trust/v1_excitation_only.csv``.
Every number is copied from ``studies/results/analysis/`` (``cells.csv`` and
``blocks.csv``, both written by ``studies/analyze.py``); this script only selects
and renames columns and stamps the provenance.

CSV, not Parquet: the map is 128 rows, the standard library reads it, and the
package's runtime dependencies stay numpy and scipy.

    python -m studies.build_map
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

STUDIES = Path(__file__).resolve().parent
REPO = STUDIES.parent
ANALYSIS = STUDIES / "results" / "analysis"
TARGET = REPO / "data" / "trust" / "v1_excitation_only.csv"

BLOCKS = ("mu", "alpha", "beta", "all")
CELL_COLUMNS = (
    "M",
    "N",
    "rho",
    "r",
    "c",
    "satellite",
    "R",
    "T",
    "delta",
    "ticks",
    "beta_min_T",
    "beta_max_T",
    "mean_n_events",
    "convergence_rate",
    "se_convergence_rate",
    "no_se_rate",
    "se_no_se_rate",
    "bound_hit_rate",
    "se_bound_hit_rate",
    "n_reliable",
    "n_marginal",
    "n_unreliable",
    "resolved",
    "estimator_undefined",
)
BLOCK_COLUMNS = (
    "bias",
    "se_bias",
    "rel",
    "se_rel",
    "cov_all",
    "se_cov_all",
    "cov_cond",
    "se_cov_cond",
    "q",
    "se_q_boot",
    "se_q_delta",
)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build(target: Path = TARGET) -> Path:
    provenance = json.loads((ANALYSIS / "provenance.json").read_text(encoding="utf-8"))
    cells = _read(ANALYSIS / "cells.csv")
    blocks: dict[tuple[str, str], dict[str, str]] = {
        (row["cell"], row["block"]): row for row in _read(ANALYSIS / "blocks.csv")
    }
    header = (
        ["study_id", "preregistration_tag", "analysis_commit", "cell"]
        + list(CELL_COLUMNS)
        + [f"{b}_{c}" for b in BLOCKS for c in BLOCK_COLUMNS]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        for row in cells:
            out = [
                provenance["study_id"],
                provenance["preregistration_tag"],
                provenance["analysis_commit"],
                row["cell"],
            ]
            out += [row[c] for c in CELL_COLUMNS]
            for b in BLOCKS:
                out += [blocks[(row["cell"], b)][c] for c in BLOCK_COLUMNS]
            writer.writerow(out)
    print(f"wrote {len(cells)} rows to {target}")
    return target


if __name__ == "__main__":
    build()
    sys.exit(0)
