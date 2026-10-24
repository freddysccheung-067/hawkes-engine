"""Render the two README figures as PNG, from the same analysis data as the paper figures.

The paper figures are PDF because a journal wants vector. A README is read in a
browser, so it wants PNG at a fixed pixel size. Both come from the same
``studies/results/analysis/`` rows, so a figure in the README cannot drift from the
figure in the paper.

    python -m studies.figures.make_readme
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent / "results" / "analysis"
OUT = HERE.parent.parent / "docs" / "figures"

SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
MARKERS = ("o", "s", "^")
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
# A diverging scale would imply a meaningful centre. Coverage has one: 0.95.
# So this is sequential, anchored at the nominal level, not at the midpoint.
SEQ = ("#f7d9d3", "#f3b5a9", "#eb8c7c", "#d95f4c", "#b8402f", "#8f2a1d", "#661a10")


def _read(name: str) -> list[dict[str, str]]:
    with (ANALYSIS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(x: str) -> float:
    return float(x) if x not in ("", None) else math.nan


def _style(plt: Any) -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.edgecolor": INK_2,
            "axes.labelcolor": INK,
            "axes.linewidth": 0.7,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "savefig.dpi": 200,
        }
    )


def _save(fig: Any, plt: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, metadata={"Software": None})
    plt.close(fig)
    print(f"wrote {path}")
    return path


def se_vs_sd(plt: Any) -> Path:
    """The honesty ratio q against sample size, per block.

    A scatter of SE against SD puts 40 of 60 points on the identity line and
    hides the finding in the tail. q against N is the same data with the ratio
    shown directly, so the reader sees where the interval is honest and where it
    collapses. Points are jittered in x so overlapping cells are visible.
    """
    rows = [
        r
        for r in _read("blocks.csv")
        if r["M"] == "2"
        and r["c"] == "1.0"
        and r["r"] == "0.0"
        and r["block"] in ("mu", "alpha", "beta")
    ]
    total = len(rows)
    below = sum(1 for r in rows if _f(r["q"]) < 1.0)

    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    ax.axhline(1.0, color=INK_2, linewidth=0.9, linestyle="--", zorder=1)
    ax.text(6.5e4, 1.06, "q = 1: honest interval", color=INK_2, fontsize=8.5, ha="right")

    offsets = {"mu": -0.055, "alpha": 0.0, "beta": 0.055}
    for k, block in enumerate(("mu", "alpha", "beta")):
        xs = [int(r["N"]) * (10 ** offsets[block]) for r in rows if r["block"] == block]
        ys = [_f(r["q"]) for r in rows if r["block"] == block]
        ax.scatter(
            xs,
            ys,
            s=40,
            marker=MARKERS[k],
            color=SERIES[k],
            label=block,
            alpha=0.85,
            zorder=3,
            edgecolors="white",
            linewidths=0.5,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(4e-4, 3.0)
    ax.set_xlim(120, 1.1e5)
    ax.set_xlabel("events N")
    ax.set_ylabel("q = mean reported SE / empirical SD")
    ax.set_title(
        f"q below 1 means the interval is narrower than the spread it describes.\n"
        f"{below} of {total} cells are below the line; the decay block collapses at "
        f"small N.",
        fontsize=10,
        color=INK,
        loc="left",
    )
    ax.legend(title="parameter block", title_fontsize=9, fontsize=9, loc="lower right", ncol=3)
    return _save(fig, plt, "se_vs_sd.png")


def coverage_heatmap(plt: Any, colors: Any) -> Path:
    """Coverage of nominal-95% intervals over (N, rho), decay block."""
    blocks = {(r["cell"], r["block"]): r for r in _read("blocks.csv")}
    cells = [r for r in _read("cells.csv") if r["M"] == "2" and r["c"] == "1.0" and r["r"] == "0.0"]
    ns = sorted({int(r["N"]) for r in cells})
    rhos = sorted({float(r["rho"]) for r in cells})

    grid = [[math.nan for _ in rhos] for _ in ns]
    for r in cells:
        b = blocks.get((r["cell"], "beta"))
        if b is None:
            continue
        i, j = ns.index(int(r["N"])), rhos.index(float(r["rho"]))
        grid[i][j] = _f(b["cov_all"])

    finite = [v for row in grid for v in row if not math.isnan(v)]
    big = [
        v for n, row in zip(ns, grid, strict=False) for v in row if not math.isnan(v) and n >= 10000
    ]
    cmap = colors.ListedColormap(SEQ[::-1])
    norm = colors.BoundaryNorm([0.0, 0.25, 0.5, 0.7, 0.85, 0.95, 1.01], cmap.N)
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    im = ax.imshow(grid, cmap=cmap, norm=norm, aspect="auto", origin="lower")
    for i in range(len(ns)):
        for j in range(len(rhos)):
            v = grid[i][j]
            if math.isnan(v):
                continue
            ax.text(
                j,
                i,
                f"{v:.2f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if v < 0.7 else INK,
            )
    ax.set_xticks(range(len(rhos)), [f"ρ = {r}" for r in rhos], fontsize=9)
    ax.set_yticks(range(len(ns)), [f"{n:,}" for n in ns], fontsize=9)
    ax.set_xlabel("branching ratio ρ")
    ax.set_ylabel("events N")
    ax.grid(False)
    ax.set_title(
        f"Coverage of the decay block at a nominal 95%.\n"
        f"{min(big):.3f} to {max(big):.3f} above 10,000 events; {min(finite):.2f} at the "
        f"smallest sample.",
        fontsize=10,
        color=INK,
        loc="left",
    )
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, ticks=[0, 0.25, 0.5, 0.7, 0.85, 0.95])
    cb.ax.tick_params(labelsize=8)
    cb.set_label("measured coverage", fontsize=9)
    return _save(fig, plt, "coverage_heatmap.png")


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import colors
    from matplotlib import pyplot as plt

    _style(plt)
    se_vs_sd(plt)
    coverage_heatmap(plt, colors)


if __name__ == "__main__":
    main()
