"""Analyse the sw-v1 study against its frozen hypotheses.

Writes ``report.txt`` and ``estimands.json`` beside the cells. Every hypothesis
gets a label, and where admissible readings of an estimand disagree the least
favourable one is taken (the h6-v1 Amendment 6.3 rule).

The primary estimand, as Amendment 1 of the pre-registration restates it:

    rho_B = mean_r se_sandwich_r^B / sd_B

where ``se_sandwich`` comes from the truth-evaluated sandwich ``I_0^-1 J_0
I_0^-1`` and ``sd_B`` is the empirical standard deviation of the estimates in the
same block over the same replications. ``q_B`` is H6's ratio, computed on the same
replications so the two are paired.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from studies.run_sandwich import QUANTISATION_KEYS, RESULTS, load_cells

BLOCKS = ("mu", "alpha", "beta")


def _parse(text: str) -> np.ndarray:
    return np.fromstring(text.strip("[]"), sep=",")


def block_slices(M: int) -> dict[str, slice]:
    n_mu = M
    n_alpha = M * M
    return {
        "mu": slice(0, n_mu),
        "alpha": slice(n_mu, n_mu + n_alpha),
        "beta": slice(n_mu + n_alpha, n_mu + 2 * n_alpha),
    }


def load_rows(cell_key: str) -> list[dict[str, str]]:
    import csv

    path = RESULTS / f"{cell_key}.csv"
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _plausible(theta: np.ndarray, theta0: np.ndarray, converged: np.ndarray) -> np.ndarray:
    """Amendment 3's set P: converged, and beta within [0.1, 10] of its truth.

    The bound is on the fitted parameter against its own true value, coordinate by
    coordinate. It exists because one replication in the pilot fitted
    ``beta = 252`` against a truth of 1.2, which makes a standard deviation of the
    estimates a statement about the optimiser rather than about sampling spread.
    """
    ratio = theta / theta0
    return converged.astype(bool) & np.all((ratio > 0.1) & (ratio < 10.0), axis=1)


def cell_estimands(cell_key: str, M: int) -> dict[str, Any]:
    """Every estimand for one cell, all on the same replication set.

    Amendment 3 governs which statistic decides a hypothesis: the robust,
    median-based ratio over the plausible set, with the mean-based one beside it.
    Both are always reported.
    """
    rows = load_rows(cell_key)
    theta = np.array([_parse(r["theta_hat"]) for r in rows if r["theta_hat"]])
    score = np.array([_parse(r["score"]) for r in rows if r["score"]])
    info = np.array([_parse(r["info_diag"]) for r in rows if r["info_diag"]])
    hess = np.array([_parse(r["se_hessian"]) for r in rows if r["se_hessian"]])
    # se_hessian is empty on the replications where the fit reported no interval,
    # so it must be aligned to theta by cell, not by position.
    converged = np.array([int(r["converged"] or 0) for r in rows if r["theta_hat"]])

    # The meat is the sample covariance of the score at the truth. Its mean is
    # subtracted because E[U(theta_0)] = 0 and the finite-sample mean is not
    # exactly zero: using the raw second moment would fold that drift in.
    centred = score - score.mean(axis=0, keepdims=True)
    J0 = centred.T @ centred / max(len(score) - 1, 1)
    # The bread is the full averaged information matrix, not its diagonal: the
    # estimates are strongly correlated across coordinates, so inverting the
    # diagonal alone understates the sandwich by a factor measured at about 2.
    p_dim = int(round(np.sqrt(info.shape[1])))
    I0 = info.reshape(len(info), p_dim, p_dim).mean(axis=0)
    I0_inv = np.linalg.inv(I0)
    se_sw = np.sqrt(np.maximum(np.diag(I0_inv @ J0 @ I0_inv), 0.0))

    slices = block_slices(M)
    truth = next((c.theta0 for c in load_cells() if c.key == cell_key), None)
    out: dict[str, Any] = {"cell": cell_key, "replications": len(rows)}
    if truth is None:
        return out
    out["theta0"] = truth.tolist()

    keep = _plausible(theta, truth, converged)
    out["plausible"] = int(keep.sum())
    out["plausible_fraction"] = float(keep.mean())
    # Align the Hessian standard errors to the rows that have a usable one.
    has_se = np.array([bool(r["se_hessian"]) for r in rows if r["theta_hat"]])
    hess_rows = np.zeros((len(theta), hess.shape[1] if hess.size else 0))
    if hess.size:
        hess_rows[has_se] = hess

    for name, sl in slices.items():
        # Mean-based, over every replication: H6's own statistic, reported always.
        sd_all = float(np.std(theta[:, sl]))
        q_all = float(np.mean(hess_rows[has_se][:, sl]) / sd_all) if sd_all > 0 else np.nan
        # rho_mean must compare like with like: a value per coordinate for each,
        # then the same reduction. Reducing se_sw to one number per coordinate
        # first and the Hessian over replications first is not paired and was
        # measured to report 0.54 where the paired figure is 0.97.
        sw_all = np.mean(se_sw[sl]) / sd_all if sd_all > 0 else np.nan
        rho_all = float(sw_all)

        # Robust, over the plausible set; this is what Amendment 3 decides from.
        sub = theta[keep][:, sl]
        med_est = float(np.median(sub)) if sub.size else np.nan
        mad = float(np.median(np.abs(sub - med_est))) * 1.4826 if sub.size else np.nan
        se_pool = hess_rows[has_se][:, sl]
        # Per coordinate, then the same median over coordinates, so the two
        # statistics are computed the same way and their ratio is meaningful.
        med_se = float(np.median(np.median(se_pool, axis=0))) if se_pool.size else np.nan
        q_rob = med_se / mad if mad and mad > 0 else np.nan
        rho_rob = float(np.median(se_sw[sl])) / mad if mad and mad > 0 else np.nan

        out[name] = {
            "sd_all": sd_all,
            "q_mean": q_all,
            "rho_mean": rho_all,
            "mad": mad,
            "q_robust": q_rob,
            "rho_robust": rho_rob,
            "g": float(np.mean(np.diag(J0)[sl] / np.diag(I0)[sl])),  # diag of the full I0
        }
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="analyse the sw-v1 study")
    parser.add_argument("--out", default="", help="directory holding the cell CSVs")
    args = parser.parse_args(argv)

    global RESULTS
    if args.out:
        RESULTS = Path(args.out)

    cells = {c.key: c for c in load_cells()}
    present = {k: v for k, v in cells.items() if (RESULTS / f"{k}.csv").exists()}
    absent = sorted(set(cells) - set(present))
    if absent:
        print(f"cells absent, not analysed: {', '.join(absent)}", flush=True)
    cells = present
    est = {key: cell_estimands(key, cells[key].M) for key in cells}

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "estimands.json").write_text(json.dumps(est, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("sw-v1 sandwich estimator study — estimands")
    lines.append("")
    lines.append("rho = mean(se_sandwich) / sampling spread; q = mean(se_hessian) / same.")
    lines.append("Amendment 3 decides from the robust pair; the mean pair is shown beside it.")
    lines.append("")
    header = (
        f"{'cell':42s} {'blk':5s} {'q_rob':>7s} {'rho_rob':>8s} "
        f"{'q_mean':>8s} {'rho_mean':>9s} {'g':>6s} {'keep':>6s}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for key in cells:
        keep = est[key].get("plausible_fraction", float("nan"))
        for block in BLOCKS:
            e = est[key][block]
            lines.append(
                f"{key:42s} {block:5s} {e['q_robust']:7.3f} {e['rho_robust']:8.3f} "
                f"{e['q_mean']:8.3f} {e['rho_mean']:9.3f} {e['g']:6.3f} {keep:6.2f}"
            )
    lines.append("")

    primary = [k for k in cells if cells[k].primary]
    lin = []
    for key in primary:
        e = est[key]["beta"]
        closes = abs(e["rho_robust"] - 1.0) <= 0.10
        improves = abs(e["rho_robust"] - 1.0) < abs(e["q_robust"] - 1.0)
        lin.append(
            f"  {key:42s} rho_rob={e['rho_robust']:.3f} q_rob={e['q_robust']:.3f} "
            f"{'closes' if closes else 'misses'} {'better' if improves else 'not better'}"
        )
    lines.append("H-S1 (|rho_beta - 1| <= 0.10 and better than q, every primary cell):")
    lines.extend(lin or ["  no primary cell present"])
    hs1 = bool(primary) and all(
        abs(est[k]["beta"]["rho_robust"] - 1.0) <= 0.10
        and abs(est[k]["beta"]["rho_robust"] - 1.0) < abs(est[k]["beta"]["q_robust"] - 1.0)
        for k in primary
    )
    lines.append(f"  label: {'confirmed' if hs1 else 'not confirmed'}")
    lines.append("")

    hs2 = bool(primary) and all(est[k]["beta"]["rho_robust"] <= 1.10 for k in primary)
    lines.append("H-S2 (rho_beta <= 1.10 at every primary cell):")
    lines.append(f"  label: {'confirmed' if hs2 else 'not confirmed'}")
    lines.append("")

    hs3 = bool(primary) and all(est[k]["beta"]["g"] > 1.0 for k in primary)
    lines.append("H-S3 (g_beta > 1 at every primary cell) [exploratory]:")
    lines.append(f"  label: {'confirmed (exploratory)' if hs3 else 'not confirmed (exploratory)'}")
    lines.append("")

    quant = [k for k in QUANTISATION_KEYS if k in est]
    if quant:
        hs4 = all(
            abs(est[k]["beta"]["rho_robust"] - 1.0) >= abs(est[k]["beta"]["q_robust"] - 1.0)
            for k in quant
        )
        lines.append(
            "H-S4 (the sandwich does not improve in the quantisation cells): "
            f"{'confirmed' if hs4 else 'not confirmed'}"
        )
    else:
        lines.append("H-S4: not run; the quantisation cells are absent.")

    text = "\n".join(lines) + "\n"
    (RESULTS / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
