"""The H6 figures, generated from ``studies/results/analysis/`` with no manual touch-up.

    pip install -e ".[figures]"
    python -m studies.figures.make_figures

Writes one PDF per figure into ``studies/figures/``:

* ``coverage_heatmap.pdf``  coverage over (N, rho) per parameter block, c = 1,
  r = 0, M = 2, with the no-SE rate printed in every cell;
* ``se_vs_sd.pdf``          mean reported SE against empirical SD per cell and
  block, with the identity line (q = 1);
* ``bias_vs_N.pdf``         |relative bias| against N on log axes, mean-based
  and median-based, per block;
* ``verdict_crosstab.pdf``  measured coverage by verdict class, per cell.

matplotlib is an optional extra imported inside :func:`main` only. Colors are
the validated reference palette (categorical slots 1 to 4, sequential blue); the
two slots below 3:1 on white always carry a marker shape and a legend entry.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE.parent / "results" / "analysis"

SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")  # categorical slots 1-4, light
MARKERS = ("o", "s", "^", "D")
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SEQ = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
NS = (200, 1000, 2000, 10000, 50000)
RHOS = (0.3028, 0.6, 0.85, 0.95)
BLOCKS = ("mu", "alpha", "beta")


def _read(name: str) -> list[dict[str, str]]:
    with (ANALYSIS / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(x: str) -> float:
    return float(x) if x not in ("", None) else math.nan


def _style(plt: Any) -> None:
    plt.rcParams.update(
        {
            "font.size": 8,
            "axes.edgecolor": INK_2,
            "axes.labelcolor": INK,
            "axes.linewidth": 0.6,
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "savefig.bbox": "tight",
        }
    )


def _main_cells(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["M"] == "2" and r["c"] == "1.0" and r["r"] == "0.0"]


def coverage_heatmap(plt: Any, colors: Any) -> Path:
    blocks = {(r["cell"], r["block"]): r for r in _read("blocks.csv")}
    cells = {r["cell"]: r for r in _main_cells(_read("cells.csv"))}
    cmap = colors.ListedColormap(SEQ[::-1])
    norm = colors.BoundaryNorm([0.0, 0.5, 0.7, 0.8, 0.85, 0.9, 0.93, 1.0], cmap.N)
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.0), sharey=True)
    for ax, b in zip(axes, BLOCKS, strict=True):
        ax.grid(False)
        grid = [[math.nan] * len(NS) for _ in RHOS]
        for key, m in cells.items():
            i = RHOS.index(float(m["rho"]))
            j = NS.index(int(m["N"]))
            grid[i][j] = _f(blocks[(key, b)]["cov_all"])
            cov = grid[i][j]
            se = _f(blocks[(key, b)]["se_cov_all"])
            no_se = _f(m["no_se_rate"])
            ink = "white" if cov < 0.85 else INK
            ax.text(j, i + 0.13, f"{cov:.3f}", ha="center", va="center", color=ink, fontsize=6)
            ax.text(j, i - 0.2, f"±{se:.3f}", ha="center", va="center", color=ink, fontsize=4.5)
            if no_se >= 0.005:
                ax.text(
                    j,
                    i - 0.38,
                    f"ns {no_se:.2f}",
                    ha="center",
                    va="center",
                    color=ink,
                    fontsize=4.5,
                )
        im = ax.imshow(grid, cmap=cmap, norm=norm, origin="lower", aspect="auto")
        ax.set_xticks(range(len(NS)), [f"{n:,}" for n in NS], fontsize=6.5)
        ax.set_yticks(range(len(RHOS)), [str(r) for r in RHOS])
        ax.set_title(f"{b}", color=INK, fontsize=9)
        ax.set_xlabel("N (target events)")
    axes[0].set_ylabel("rho")
    cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cbar.set_label("coverage at nominal 0.95")
    fig.suptitle(
        "Interval coverage +/- MC SE, c = 1, r = 0, M = 2. A missing SE is a miss; "
        "ns = no-SE rate where at least 0.005",
        fontsize=9,
        color=INK,
        y=1.04,
    )
    return _save(fig, plt, "coverage_heatmap.pdf")


def se_vs_sd(plt: Any, colors: Any) -> Path:
    rows = [r for r in _read("blocks.csv") if r["block"] in BLOCKS]
    meta = {r["cell"]: r for r in _read("cells.csv")}
    fig, ax = plt.subplots(figsize=(4.2, 4.0))
    lo, hi = 1e-4, 1e7
    for k, b in enumerate(BLOCKS):
        xs, ys, xo, yo = [], [], [], []
        for r in rows:
            if r["block"] != b or meta[r["cell"]]["estimator_undefined"] == "1":
                continue
            sd, mse = _f(r["sd"]), _f(r["mse"])
            if not (sd > 0 and mse > 0):
                continue
            m = meta[r["cell"]]
            in_h65 = m["M"] == "2" and m["c"] == "1.0" and m["r"] == "0.0" and int(m["N"]) >= 2000
            (xs if in_h65 else xo).append(sd)
            (ys if in_h65 else yo).append(mse)
        ax.scatter(
            xo,
            yo,
            s=10,
            marker=MARKERS[k],
            facecolors="none",
            edgecolors=SERIES[k],
            linewidths=0.6,
            alpha=0.6,
        )
        ax.scatter(
            xs,
            ys,
            s=22,
            marker=MARKERS[k],
            color=SERIES[k],
            edgecolors="white",
            linewidths=0.6,
            label=f"{b} (H6.5 region)",
            zorder=3,
        )
    ax.plot([lo, hi], [lo, hi], color=INK_2, linewidth=1.0, linestyle="--", label="q = 1")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("empirical SD across replications (E3.3)")
    ax.set_ylabel("mean reported SE (E3.4)")
    ax.set_title(
        "Reported SE against sampling spread, defined cells\n"
        "filled: H6.5 region; open: all other cells",
        fontsize=9,
        color=INK,
    )
    ax.legend(loc="upper left", fontsize=7)
    return _save(fig, plt, "se_vs_sd.pdf")


def bias_vs_n(plt: Any, colors: Any) -> Path:
    blocks = {(r["cell"], r["block"]): r for r in _read("blocks.csv")}
    comp = {(r["cell"], r["block"]): r for r in _read("companions.csv")}
    cells = _main_cells(_read("cells.csv"))
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=True)
    for ax, b in zip(axes, BLOCKS, strict=True):
        for k, rho in enumerate(RHOS):
            pts = sorted((int(m["N"]), m["cell"]) for m in cells if float(m["rho"]) == rho)
            n = [p[0] for p in pts]
            mean = [abs(_f(blocks[(c, b)]["rel"])) for _, c in pts]
            med = [abs(_f(comp[(c, b)]["medrel"])) for _, c in pts]
            ax.plot(
                n,
                mean,
                color=SERIES[k],
                marker=MARKERS[k],
                markersize=4,
                linewidth=1.2,
                label=f"rho {rho}",
            )
            ax.plot(
                n,
                med,
                color=SERIES[k],
                marker=MARKERS[k],
                markersize=3,
                linewidth=0.8,
                linestyle=":",
                markerfacecolor="none",
            )
        ax.axhline(0.05, color=INK_2, linewidth=0.8, linestyle="--")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(b, fontsize=9, color=INK)
        ax.set_xlabel("N (target events)")
    axes[0].set_ylabel("|relative bias|")
    axes[0].legend(fontsize=6.5, loc="lower left")
    fig.suptitle(
        "Relative bias, c = 1, r = 0, M = 2: solid = mean (E3.2), dotted = median (E4.1); "
        "dashed = 0.05",
        fontsize=8.5,
        color=INK,
        y=1.04,
    )
    return _save(fig, plt, "bias_vs_N.pdf")


def verdict_crosstab(plt: Any, colors: Any) -> Path:
    rows = [r for r in _read("crosstab.csv") if r["M"] and r["c"] == "1.0" and r["r"] == "0.0"]
    rows.sort(key=lambda r: (int(r["M"]), int(r["N"]), float(r["rho"])))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    labels = [f"M{r['M']} N{int(r['N']):,} rho{r['rho']}" for r in rows]
    for k, cls in enumerate(("reliable", "marginal", "unreliable")):
        xs, ys, es = [], [], []
        for i, r in enumerate(rows):
            if int(r[f"n_{cls}"]) == 0:
                continue
            xs.append(i + (k - 1) * 0.22)
            ys.append(_f(r[f"cov_{cls}"]))
            es.append(2 * _f(r[f"se_{cls}"]))
        ax.errorbar(
            xs,
            ys,
            yerr=es,
            fmt=MARKERS[k],
            color=SERIES[k],
            markersize=4,
            elinewidth=0.8,
            capsize=0,
            label=cls,
        )
    ax.axhline(0.95, color=INK_2, linewidth=0.8, linestyle="--")
    ax.set_xticks(range(len(rows)), labels, rotation=60, ha="right", fontsize=6)
    ax.set_ylim(-0.03, 1.03)
    ax.set_ylabel("coverage (all coordinates)")
    ax.set_title(
        "Measured coverage by verdict, c = 1, r = 0 (bars: 2 MC SE; dashed: 0.95). "
        "A class is shown only where it occurs.",
        fontsize=8.5,
        color=INK,
    )
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(0.0, -0.42), ncol=3)
    return _save(fig, plt, "verdict_crosstab.pdf")


def _save(fig: Any, plt: Any, name: str) -> Path:
    path = HERE / name
    fig.savefig(path, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)
    print(f"wrote {path}")
    return path


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import colors
    from matplotlib import pyplot as plt

    _style(plt)
    for make in (coverage_heatmap, se_vs_sd, bias_vs_n, verdict_crosstab):
        make(plt, colors)


if __name__ == "__main__":
    main()
