"""The pre-registered H6 analysis: estimands, companions, hypotheses, Holm.

Everything here implements ``docs/preregistration.md`` as amended (Amendments 1
to 5). Where the file admits two readings, or names a standard error without
saying how to combine it, the choice is recorded in ``studies/ANALYSIS_NOTES.md``
under the tag quoted in the code (``R<n>`` for a reading, ``C<n>`` for a
combination). Nothing in this module chooses silently.

Order of computation, as the brief fixes it:

1. per cell, per block and per coordinate: E3.1 to E3.7 with their Monte Carlo
   standard errors, rates, and coverage twice;
2. per cell: E4.1 to E4.4 with a seeded bootstrap over replications;
3. H6.1 to H6.6 in Amendment 5's table form, with the Holm procedure over the
   four confirmatory hypotheses;
4. the verdict-by-coverage cross-tab of section 9 item 5;
5. sensitivity statements, labelled as such.

Usage::

    python -m studies.analyze            # all 128 cells, 1000 resamples
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

from studies.grid import STUDY_ID, Cell, load_cells, splitmix64

csv.field_size_limit(2**30)

STUDIES = Path(__file__).resolve().parent
REPO = STUDIES.parent
CELLS_DIR = STUDIES / "results" / "cells"
OUT_DIR = STUDIES / "results" / "analysis"
MANIFEST = STUDIES / "results" / "manifest.json"

PREREG_TAG = "H6-preregistration"
Z95 = 1.959964  # section 3, E3.5, as written
MAD_SCALE = 1.4826  # Amendment 4.2, E4.2, as written
TAIL_FACTOR = 10.0  # Amendment 4.2, E4.4
BOOT_RESAMPLES = 1000  # Amendment 4.2; fixed, never tuned
HOLM_ALPHA = 0.05
HOLM_THRESHOLDS = tuple(HOLM_ALPHA / (5 - k) for k in range(1, 5))  # Amendment 5.4
RESOLVED_TICKS = 100.0  # Amendment 3.3
H64_FLOOR = 10  # Amendment 3.3, applied to the 22 cells of Amendment 5.5
UNDEFINED_NO_SE = 0.5  # M1 in ANALYSIS_NOTES.md: map flag only, decides nothing
BLOCKS = ("mu", "alpha", "beta")
VERDICTS = ("reliable", "marginal", "unreliable")
FAMILY = ("H6.3", "H6.4", "H6.5", "H6.6")
LABELS = (
    "confirmed",
    "confirmed before correction only",
    "not confirmed",
    "inconclusive",
)
# Amendment 6.3: when admissible forms disagree, the label is the least favourable
# one any of them produces. The order below is worst-last, so a disagreement can
# only weaken a claim.
_LABEL_RANK = {
    "confirmed": 3,
    "confirmed before correction only": 2,
    "inconclusive": 1,
    "not confirmed": 0,
}


def least_favourable(labels: set[str]) -> str:
    """The weakest label among the admissible forms (Amendment 6.3)."""
    if not labels:
        raise ValueError("no labels to combine")
    unknown = labels - set(_LABEL_RANK)
    if unknown:
        raise ValueError(f"unranked label(s): {sorted(unknown)}")
    return min(labels, key=_LABEL_RANK.__getitem__)


_SE_FORM = {"A": "independent cells", "B": "between-cell spread"}
_POP_FORM = {"A": "all qualifying cells", "B": "c = 1 cells only"}


# ----------------------------------------------------------------- the data


@dataclass(frozen=True)
class CellData:
    """One cell's rows, parsed into arrays. ``se`` is NaN where a fit had none."""

    key: str
    M: int
    theta0: np.ndarray
    theta_hat: np.ndarray  # (R, P)
    se: np.ndarray  # (R, P)
    has_se: np.ndarray  # (R,)
    converged: np.ndarray  # (R,)
    verdict: np.ndarray  # (R,) of str
    bound_hit: np.ndarray  # (R,)
    nit: np.ndarray  # (R,), NaN where the fit did not run
    n_events: np.ndarray  # (R,)
    failure: tuple[str, ...]
    axes: dict[str, Any]

    @property
    def R(self) -> int:
        return int(self.theta_hat.shape[0])

    @property
    def P(self) -> int:
        return int(self.theta_hat.shape[1])


def block_index(M: int) -> dict[str, np.ndarray]:
    """Coordinate positions of each block in ``theta_hat`` (``run_cell`` order)."""
    m2 = M * M
    return {
        "mu": np.arange(0, M),
        "alpha": np.arange(M, M + m2),
        "beta": np.arange(M + m2, M + 2 * m2),
        "all": np.arange(0, M + 2 * m2),
    }


def coordinate_names(M: int) -> list[str]:
    pairs = [f"{i},{j}" for i in range(M) for j in range(M)]
    return (
        [f"mu[{i}]" for i in range(M)]
        + [f"alpha[{p}]" for p in pairs]
        + [f"beta[{p}]" for p in pairs]
    )


def _flat(text: str) -> list[float]:
    value = json.loads(text)
    out: list[float] = []
    for item in value:
        if isinstance(item, list):
            out.extend(float(v) for v in item)
        else:
            out.append(float(item))
    return out


def parse_rows(
    rows: list[dict[str, str]],
    *,
    key: str,
    M: int,
    theta0: np.ndarray,
    axes: dict[str, Any],
) -> CellData:
    """Arrays from the CSV rows of one cell. A row without ``theta_hat`` is refused.

    Every one of the 256 000 rows of the study carries a ``theta_hat`` (the
    simulator and the fit raised nowhere), so a row without one would mean the
    data are not the data the notes describe.
    """
    P = M + 2 * M * M
    R = len(rows)
    theta_hat = np.empty((R, P))
    se = np.full((R, P), np.nan)
    has_se = np.zeros(R, dtype=bool)
    converged = np.zeros(R, dtype=bool)
    bound_hit = np.zeros(R, dtype=bool)
    nit = np.full(R, np.nan)
    n_events = np.full(R, np.nan)
    verdict = np.empty(R, dtype=object)
    failure = []
    for i, row in enumerate(rows):
        if int(row["rep_index"]) != i:
            raise ValueError(f"{key}: row {i} has rep_index {row['rep_index']}")
        if not row["theta_hat"]:
            raise ValueError(f"{key}: replication {i} has no theta_hat")
        theta_hat[i] = _flat(row["theta_hat"])
        if row["se_mu"]:
            has_se[i] = True
            se[i] = _flat(row["se_mu"]) + _flat(row["se_alpha"]) + _flat(row["se_beta"])
        converged[i] = row["converged"] == "1"
        bound_hit[i] = row.get("bound_hit", "") == "1"
        if row.get("nit"):
            nit[i] = float(row["nit"])
        if row.get("n_events"):
            n_events[i] = float(row["n_events"])
        verdict[i] = row["verdict"]
        failure.append(row["failure"])
    return CellData(
        key=key,
        M=M,
        theta0=np.asarray(theta0, dtype=float),
        theta_hat=theta_hat,
        se=se,
        has_se=has_se,
        converged=converged,
        verdict=verdict,
        bound_hit=bound_hit,
        nit=nit,
        n_events=n_events,
        failure=tuple(failure),
        axes=dict(axes),
    )


def _axes(cell: Cell) -> dict[str, Any]:
    ticks = cell.T / cell.delta if cell.delta > 0 else math.inf
    return {
        "N": cell.N_target,
        "rho": cell.rho,
        "r": cell.r,
        "c": cell.c,
        "satellite": cell.satellite,
        "T": cell.T,
        "delta": cell.delta,
        "ticks": ticks,
        "beta_min_T": cell.beta_min * cell.T,
        "beta_max_T": max(max(row) for row in cell.beta) * cell.T,
        "rate": cell.rate,
    }


def load_cell(cell: Cell, cells_dir: Path = CELLS_DIR) -> CellData:
    with (cells_dir / f"{cell.key}.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    theta0 = np.array(
        list(cell.mu)
        + [v for row in cell.alpha for v in row]
        + [v for row in cell.beta for v in row]
    )
    return parse_rows(rows, key=cell.key, M=cell.M, theta0=theta0, axes=_axes(cell))


# -------------------------------------------------------- E3.1 to E3.7


def _binom_se(p: float, n: int) -> float:
    """Section 3: ``sqrt(p (1 - p) / n)``; R13 in the notes."""
    if n <= 0 or not np.isfinite(p):
        return math.nan
    return math.sqrt(max(p * (1.0 - p), 0.0) / n)


def _div(a: float, b: float) -> float:
    """IEEE division: a zero spread gives inf or nan, reported, never an exception."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(np.float64(a) / np.float64(b))


def _mean_or_nan(x: np.ndarray) -> float:
    return float(np.mean(x)) if x.size else math.nan


def coverage_hits(cell: CellData) -> np.ndarray:
    """E3.5 indicator per replication and coordinate; a missing se is a miss."""
    dev = np.abs(cell.theta_hat - cell.theta0)
    with np.errstate(invalid="ignore"):
        inside = dev <= Z95 * cell.se
    return cell.has_se[:, None] & inside


def _verdict_split(share: np.ndarray, verdict: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    """E3.7: coverage by verdict class, and ``Delta`` with its delta-method SE."""
    out: dict[str, Any] = {}
    for v in VERDICTS:
        sel = mask & (verdict == v)
        n = int(sel.sum())
        cov = _mean_or_nan(share[sel])
        out[v] = {"n": n, "cov": cov, "se": _binom_se(cov, n)}
    rel, unrel = out["reliable"], out["unreliable"]
    if rel["n"] and unrel["n"]:
        out["delta"] = rel["cov"] - unrel["cov"]
        out["se_delta"] = math.sqrt(rel["se"] ** 2 + unrel["se"] ** 2)
    else:
        out["delta"] = math.nan
        out["se_delta"] = math.nan
    return out


def _spread_stats(
    X: np.ndarray, S: np.ndarray, has: np.ndarray, theta0: np.ndarray
) -> dict[str, Any]:
    """E3.1 to E3.4 and E3.6 for one block over the rows given."""
    R = X.shape[0]
    scale = float(np.mean(np.abs(theta0)))
    bias = float(np.mean(X - theta0))  # E3.1
    sd = float(np.sqrt(np.mean(np.var(X, axis=0))))  # E3.3, divisor R (R2)
    Sh = S[has]
    n_se = int(has.sum())
    mse = float(np.mean(Sh)) if n_se else math.nan  # E3.4 (R3)
    if n_se > 1:
        se_mse = float(np.std(np.mean(Sh, axis=1), ddof=1) / math.sqrt(n_se))
    else:
        se_mse = math.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        q = _div(mse, sd)  # E3.6
        se_q_delta = abs(q) * math.sqrt(_div(se_mse, mse) ** 2 + 1.0 / (2 * (R - 1)))
        sd_matched = float(np.sqrt(np.mean(np.var(X[has], axis=0)))) if n_se else math.nan
        q_matched = _div(mse, sd_matched)
    se_bias = sd / math.sqrt(R)
    return {
        "R": R,
        "bias": bias,
        "se_bias": se_bias,
        "rel": bias / scale,  # E3.2
        "se_rel": se_bias / scale,
        "scale": scale,
        "sd": sd,
        "mse": mse,
        "se_mse": se_mse,
        "n_se": n_se,
        "q": q,
        "se_q_delta": se_q_delta,
        "q_matched": q_matched,
    }


def cell_estimands(cell: CellData, population: str = "all") -> dict[str, Any]:
    """E3.1 to E3.7, rates and the E4 point values for one cell.

    ``population`` is R1: ``"all"`` (implemented) or ``"converged"``
    (sensitivity). It governs E3.1 to E3.4 and E3.6. Coverage is always reported
    twice, over all replications and conditioned on convergence, as E3.5 says.
    """
    if population == "all":
        pop = np.ones(cell.R, dtype=bool)
    elif population == "converged":
        pop = cell.converged.copy()
    else:
        raise ValueError(f"population must be 'all' or 'converged', got {population!r}")
    idx = block_index(cell.M)
    hits = coverage_hits(cell)
    everyone = np.ones(cell.R, dtype=bool)
    blocks: dict[str, Any] = {}
    for name, J in idx.items():
        stats = _spread_stats(
            cell.theta_hat[pop][:, J], cell.se[pop][:, J], cell.has_se[pop], cell.theta0[J]
        )
        share = hits[:, J].mean(axis=1)
        n_all = cell.R
        n_cond = int(cell.converged.sum())
        cov_all = _mean_or_nan(share)
        cov_cond = _mean_or_nan(share[cell.converged])
        stats.update(
            {
                "cov_all": cov_all,
                "se_cov_all": _binom_se(cov_all, n_all),
                "n_cov_all": n_all,
                "cov_cond": cov_cond,
                "se_cov_cond": _binom_se(cov_cond, n_cond),
                "n_cov_cond": n_cond,
                "verdict_all": _verdict_split(share, cell.verdict, everyone),
                "verdict_cond": _verdict_split(share, cell.verdict, cell.converged),
            }
        )
        blocks[name] = stats

    names = coordinate_names(cell.M)
    coords = []
    for j, name in enumerate(names):
        stats = _spread_stats(
            cell.theta_hat[pop][:, [j]],
            cell.se[pop][:, [j]],
            cell.has_se[pop],
            cell.theta0[[j]],
        )
        cov_all = _mean_or_nan(hits[:, j].astype(float))
        cov_cond = _mean_or_nan(hits[cell.converged, j].astype(float))
        stats.update(
            {
                "name": name,
                "theta0": float(cell.theta0[j]),
                "cov_all": cov_all,
                "se_cov_all": _binom_se(cov_all, cell.R),
                "cov_cond": cov_cond,
                "se_cov_cond": _binom_se(cov_cond, int(cell.converged.sum())),
            }
        )
        coords.append(stats)

    R = cell.R
    no_se = 1.0 - float(cell.has_se.mean())
    conv = float(cell.converged.mean())
    bound = float(cell.bound_hit.mean())
    nit = cell.nit[np.isfinite(cell.nit)]
    meta = {
        "key": cell.key,
        "M": cell.M,
        "P": cell.P,
        "R": R,
        "population": population,
        **cell.axes,
        "no_se_rate": no_se,
        "se_no_se_rate": _binom_se(no_se, R),
        "convergence_rate": conv,
        "se_convergence_rate": _binom_se(conv, R),
        "bound_hit_rate": bound,
        "se_bound_hit_rate": _binom_se(bound, R),
        "mean_nit": _mean_or_nan(nit),
        "se_mean_nit": float(np.std(nit, ddof=1) / math.sqrt(nit.size)) if nit.size > 1 else 0.0,
        "verdict_counts": {v: int((cell.verdict == v).sum()) for v in VERDICTS},
        "n_converged": int(cell.converged.sum()),
        "n_se": int(cell.has_se.sum()),
        "n_converged_with_se": int((cell.converged & cell.has_se).sum()),
        "mean_n_events": _mean_or_nan(cell.n_events[np.isfinite(cell.n_events)]),
    }
    point = e4_statistics(cell, np.arange(R)[None, :])
    companions: dict[str, Any] = {
        b: {k: float(v[0]) for k, v in point[b].items()} for b in (*BLOCKS, "all")
    }
    companions["tail"] = float(point["tail"][0])
    companions["n_tail"] = int(cell.converged.sum())
    return {"meta": meta, "blocks": blocks, "coordinates": coords, "companions": companions}


# --------------------------------------------------------- E4 and the bootstrap


def boot_seed(key: str) -> int:
    """Amendment 4.2: section 10's construction on ``"h6-v1-boot|<cell key>"``."""
    digest = hashlib.sha256(f"{STUDY_ID}-boot|{key}".encode()).digest()
    return int(splitmix64(int.from_bytes(digest[:16], "big"))[1])


def e4_statistics(cell: CellData, idx: np.ndarray) -> dict[str, Any]:
    """E4.1 to E4.4 and E3.6's ``q`` for each row of resample indices ``idx``.

    ``idx`` has shape ``(B, R)``; the identity row ``arange(R)`` gives the point
    estimate. ``q`` is computed here by a second, independent route (the test
    suite checks it against :func:`cell_estimands`), because the bootstrap of
    ``q`` is what H6.5's standard error is (Amendment 5.3).
    """
    X = cell.theta_hat[idx]  # (B, R, P)
    S = cell.se[idx]
    H = cell.has_se[idx]
    C = cell.converged[idx]
    out: dict[str, Any] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        for name, J in block_index(cell.M).items():
            XJ = X[:, :, J]
            t0 = cell.theta0[J]
            scale = float(np.mean(np.abs(t0)))
            med = np.median(XJ, axis=1)  # (B, |J|)
            medbias = np.mean(med - t0, axis=1)  # E4.1
            mad = np.mean(MAD_SCALE * np.median(np.abs(XJ - med[:, None, :]), axis=1), axis=1)
            # E4.3 over the replications that have a standard error (R11).
            XS = np.where(H[:, :, None], XJ, np.nan)
            med_s = np.nanmedian(XS, axis=1)
            mad_s = MAD_SCALE * np.nanmedian(np.abs(XS - med_s[:, None, :]), axis=1)
            se_med = np.nanmedian(S[:, :, J], axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                qrob = np.mean(se_med / mad_s, axis=1)
                sd = np.sqrt(np.mean(np.var(XJ, axis=1), axis=1))
                q = np.nanmean(S[:, :, J].reshape(S.shape[0], -1), axis=1) / sd
            out[name] = {
                "medbias": medbias,
                "medrel": medbias / scale,
                "mad": mad,
                "qrob": qrob,
                "q": q,
            }
        cap = TAIL_FACTOR * float(np.max(cell.theta0[block_index(cell.M)["beta"]]))
        wild = np.any(X[:, :, block_index(cell.M)["beta"]] > cap, axis=2) & C
        with np.errstate(divide="ignore", invalid="ignore"):
            out["tail"] = wild.sum(axis=1) / C.sum(axis=1)  # E4.4
    return out


def bootstrap_cell(
    cell: CellData, resamples: int = BOOT_RESAMPLES, chunk: int = 50
) -> dict[str, Any]:
    """``resamples`` nonparametric resamples of the replications, seeded per cell.

    Indices are drawn as one ``(resamples, R)`` array from numpy's PCG64 seeded
    with :func:`boot_seed` (R12), so a rerun reproduces every interval exactly.
    """
    rng = np.random.Generator(np.random.PCG64(boot_seed(cell.key)))
    idx = rng.integers(0, cell.R, size=(resamples, cell.R))
    parts = [e4_statistics(cell, idx[i : i + chunk]) for i in range(0, resamples, chunk)]
    out: dict[str, Any] = {}
    for name in (*BLOCKS, "all"):
        out[name] = {
            stat: np.concatenate([p[name][stat] for p in parts]) for stat in parts[0][name]
        }
    out["tail"] = np.concatenate([p["tail"] for p in parts])
    return out


def summarise_boot(values: np.ndarray) -> dict[str, float]:
    v = values[np.isfinite(values)]
    if v.size < 2:
        return {"boot_sd": math.nan, "lo": math.nan, "hi": math.nan, "n_finite": int(v.size)}
    return {
        "boot_sd": float(np.std(v, ddof=1)),
        "lo": float(np.percentile(v, 2.5)),
        "hi": float(np.percentile(v, 97.5)),
        "n_finite": int(v.size),
    }


# ---------------------------------------------------------- decision rules


def section4_verdict(z: float) -> str:
    """Section 4: confirmed if ``T - 2 SE > tau``; refuted if ``T + 2 SE <= tau``.

    Confirmation is strict and every falsifier in section 4 is non-strict, so
    ``z = 2`` is inconclusive and ``z = -2`` is refuted.
    """
    if np.isnan(z):
        return "inconclusive"
    if z > 2.0:
        return "confirmed"
    if z <= -2.0:
        return "refuted"
    return "inconclusive"


def p_from_z(z: float) -> float:
    if np.isnan(z):
        return 1.0
    return float(norm.sf(z))


def z_from_p(p: float) -> float:
    return float(norm.isf(p))


def holm(p: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Amendment 5.4: ascending ``p``, step ``k`` against ``0.05 / (5 - k)``, stop at
    the first failure. Ties are broken by hypothesis name, which is fixed."""
    order = sorted(p, key=lambda k: (p[k], k))
    out: dict[str, dict[str, Any]] = {}
    alive = True
    for step, name in enumerate(order, start=1):
        threshold = HOLM_THRESHOLDS[step - 1]
        passed = alive and p[name] <= threshold
        out[name] = {
            "step": step,
            "threshold": threshold,
            "p": p[name],
            "passed": bool(passed),
            "reached": alive,
        }
        alive = passed
    return out


def final_label(section4: str, holm_passed: bool) -> str:
    """Amendment 5.4: both bars. Section 4 failing is never rescued by Holm."""
    if section4 == "confirmed":
        return "confirmed" if holm_passed else "confirmed before correction only"
    if section4 == "inconclusive":
        return "inconclusive"
    return "not confirmed"


def mean_of_differences(D: np.ndarray, se: np.ndarray) -> dict[str, float]:
    """The mean of K cell-level values and its two candidate SEs (C3, C5)."""
    K = D.size
    return {
        "T": float(np.mean(D)),
        "K": K,
        "se_independent": float(np.sqrt(np.sum(se**2)) / K),
        "se_between": float(np.std(D, ddof=1) / math.sqrt(K)) if K > 1 else math.nan,
    }


def _test(T: float, tau: float, se: float, *, lower: bool = False) -> dict[str, Any]:
    """``z = (T - tau) / SE`` (or ``(tau - T) / SE`` for a ``<`` hypothesis)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        z = float((tau - T) / se if lower else (T - tau) / se)
    if se == 0:
        z = math.copysign(math.inf, (tau - T) if lower else (T - tau))
    return {"T": T, "tau": tau, "se": se, "z": z, "p": p_from_z(z), "section4": section4_verdict(z)}


# ------------------------------------------------------------ regions


def _m(s: dict[str, Any]) -> dict[str, Any]:
    return s["meta"]


def _find(summaries: dict[str, Any], **want: Any) -> list[str]:
    keys = []
    for key, s in summaries.items():
        m = _m(s)
        if all(m[k] == v for k, v in want.items()):
            keys.append(key)
    return keys


def _one(summaries: dict[str, Any], **want: Any) -> str:
    keys = _find(summaries, **want)
    if len(keys) != 1:
        raise RuntimeError(f"expected one cell for {want}, found {keys}")
    return keys[0]


def h65_cells(summaries: dict[str, Any]) -> list[str]:
    """Amendment 4.4: the 12 ``M = 2`` cells with ``N >= 2000, c = 1, r = 0``."""
    return [
        k
        for k, s in summaries.items()
        if _m(s)["M"] == 2
        and not _m(s)["satellite"]
        and _m(s)["N"] >= 2000
        and _m(s)["c"] == 1.0
        and _m(s)["r"] == 0.0
    ]


def h65_satellite_cells(summaries: dict[str, Any]) -> list[str]:
    return [
        k
        for k, s in summaries.items()
        if _m(s)["satellite"] and _m(s)["N"] >= 2000 and _m(s)["c"] == 1.0 and _m(s)["r"] == 0.0
    ]


def _weights(M: int) -> dict[str, int]:
    return {"mu": M, "alpha": M * M, "beta": M * M}


def pooled_q(summaries: dict[str, Any], keys: list[str]) -> dict[str, float]:
    """R7: coordinate-weighted mean of block ``q`` (implemented) and the ratio form."""
    num = den = q_sum = w_sum = 0.0
    for k in keys:
        s = summaries[k]
        w = _weights(_m(s)["M"])
        for b in BLOCKS:
            q_sum += w[b] * s["blocks"][b]["q"]
            w_sum += w[b]
            num += w[b] * s["blocks"][b]["mse"]
            den += w[b] * s["blocks"][b]["sd"]
    return {"q": q_sum / w_sum, "q_ratio": num / den}


def _pooled_boot(summaries: dict[str, Any], boots: dict[str, Any], keys: list[str], stat: str):
    total = None
    w_sum = 0.0
    for k in keys:
        w = _weights(_m(summaries[k])["M"])
        for b in BLOCKS:
            term = w[b] * boots[k][b][stat]
            total = term if total is None else total + term
            w_sum += w[b]
    assert total is not None
    return total / w_sum


def _cell_q_delta_se(s: dict[str, Any]) -> float:
    """Delta-method SE of a cell's coordinate-weighted q, blocks treated as independent."""
    w = _weights(_m(s)["M"])
    tot = sum(w.values())
    return math.sqrt(sum((w[b] / tot * s["blocks"][b]["se_q_delta"]) ** 2 for b in BLOCKS))


# ----------------------------------------------------------- hypotheses


def h61(summaries: dict[str, Any]) -> dict[str, Any]:
    keys = [
        k
        for N in (200, 2000)
        for rho in (0.85, 0.95)
        for k in _find(summaries, M=2, N=N, rho=rho, r=0.0, c=1.0, satellite=False)
    ]
    cells = []
    for k in keys:
        a = summaries[k]["blocks"]["alpha"]
        t = _test(a["rel"], 0.05, a["se_rel"])
        cells.append({"cell": k, **t})
    return _any_cell(cells, "rel_alpha of the cell with the largest z", keys)


def h62(summaries: dict[str, Any]) -> dict[str, Any]:
    keys = [
        k for N in (200, 1000) for k in _find(summaries, M=2, N=N, r=0.0, c=1.0, satellite=False)
    ]
    cells = []
    for k in keys:
        for b in BLOCKS:
            blk = summaries[k]["blocks"][b]
            t = _test(blk["cov_all"], 0.90, blk["se_cov_all"], lower=True)
            cells.append({"cell": k, "block": b, **t})
    return _any_cell(
        cells, "cov_B (all replications, R4) of the cell-block with the largest z", keys
    )


def _any_cell(cells: list[dict[str, Any]], what: str, keys: list[str]) -> dict[str, Any]:
    """ "Confirmed if in at least one cell ...; refuted if every cell ..." (R9)."""
    best = max(cells, key=lambda c: c["z"])
    if any(c["section4"] == "confirmed" for c in cells):
        verdict = "confirmed"
    elif all(c["section4"] == "refuted" for c in cells):
        verdict = "refuted"
    else:
        verdict = "inconclusive"
    return {
        "T": best["T"],
        "tau": best["tau"],
        "se": best["se"],
        "se_used": "section 3 MC SE of the cell with the largest z",
        "statistic": what,
        "z": best["z"],
        "p": best["p"],
        "p_note": "1 - Phi(z_max), not corrected for the maximum over cells (R9)",
        "section4": verdict,
        "cells": cells,
        "region_cells": keys,
    }


def h63(summaries: dict[str, Any]) -> dict[str, Any]:
    rhos = (0.3028, 0.6, 0.85, 0.95)
    pooled: dict[float, dict[str, Any]] = {}
    for rho in rhos:
        ks = [
            _one(summaries, M=2, N=N, rho=rho, r=0.0, c=1.0, satellite=False) for N in (2000, 10000)
        ]
        b = [summaries[k]["blocks"]["all"] for k in ks]
        n = sum(x["n_cov_all"] for x in b)
        cov = sum(x["cov_all"] * x["n_cov_all"] for x in b) / n
        pooled[rho] = {
            "cells": ks,
            "cov": cov,
            "n": n,
            "se_A": _binom_se(cov, n),  # C1 form A: pooled binomial
            "se_B": math.sqrt(sum(x["se_cov_all"] ** 2 for x in b)) / len(b),  # C1 form B
            "per_cell": [
                {"cell": k, "cov": x["cov_all"], "se": x["se_cov_all"]}
                for k, x in zip(ks, b, strict=True)
            ],
        }
    forms: dict[str, Any] = {}
    for c1, c2 in itertools.product("AB", "AB"):
        se_key = f"se_{c1}"
        lo, hi = pooled[0.3028], pooled[0.95]
        T = lo["cov"] - hi["cov"]
        se = math.sqrt(lo[se_key] ** 2 + hi[se_key] ** 2)
        t = _test(T, 0.0, se)
        steps = []
        for a, b in itertools.pairwise(rhos):
            rise = pooled[b]["cov"] - pooled[a]["cov"]
            if c2 == "A":
                step_se = math.sqrt(pooled[a][se_key] ** 2 + pooled[b][se_key] ** 2)
            else:
                step_se = pooled[b][se_key]
            steps.append(
                {"from": a, "to": b, "rise": rise, "se": step_se, "ok": rise <= 2 * step_se}
            )
        monotone = all(s["ok"] for s in steps)
        verdict = t["section4"] if monotone else "refuted"
        forms[f"C1{c1}-C2{c2}"] = {
            **t,
            "threshold_clause": t["section4"],
            "monotone": monotone,
            "steps": steps,
            "section4": verdict,
            "se_used": f"C1 form {c1}, monotonicity step SE form {c2}",
        }
    return {
        "pooled": {str(k): v for k, v in pooled.items()},
        "forms": forms,
        "statistic": "cov(0.3028) - cov(0.95), coverage over all coordinates and all "
        "replications (R4, R5), pooled over N in {2000, 10000}",
    }


def h64_population(summaries: dict[str, Any]) -> list[str]:
    """Amendment 5.5: resolved ``r = 0.1`` cells at ``M = 2``."""
    return [
        k
        for k, s in summaries.items()
        if _m(s)["M"] == 2
        and not _m(s)["satellite"]
        and _m(s)["r"] == 0.1
        and _m(s)["ticks"] >= RESOLVED_TICKS
    ]


def _diff_row(summaries: dict[str, Any], k: str) -> dict[str, Any]:
    m = _m(summaries[k])
    k0 = _one(summaries, M=2, N=m["N"], rho=m["rho"], r=0.0, c=m["c"], satellite=False)
    b1, b0 = summaries[k]["blocks"]["beta"], summaries[k0]["blocks"]["beta"]
    D = b1["rel"] - b0["rel"]
    se = math.sqrt(b1["se_rel"] ** 2 + b0["se_rel"] ** 2)
    return {
        "cell": k,
        "matched": k0,
        "N": m["N"],
        "rho": m["rho"],
        "c": m["c"],
        "ticks": m["ticks"],
        "rel_beta_r01": b1["rel"],
        "se_r01": b1["se_rel"],
        "rel_beta_r0": b0["rel"],
        "se_r0": b0["se_rel"],
        "D": D,
        "se_D": se,
        "n_converged_with_se": _m(summaries[k])["n_converged_with_se"],
    }


def h64(summaries: dict[str, Any]) -> dict[str, Any]:
    population = h64_population(summaries)
    rows = [_diff_row(summaries, k) for k in population]
    qualifies = [r for r in rows if r["n_converged_with_se"] > 0]
    forms: dict[str, Any] = {}
    for c4 in "AB":
        use = qualifies if c4 == "A" else [r for r in qualifies if r["c"] == 1.0]
        for c3 in "AB":
            name = f"C3{c3}-C4{c4}"
            if len(use) < H64_FLOOR:
                forms[name] = {
                    "T": math.nan,
                    "tau": 0.01,
                    "se": math.nan,
                    "z": math.nan,
                    "p": 1.0,
                    "section4": "inconclusive",
                    "floor": f"{len(use)} cells qualify, fewer than {H64_FLOOR}",
                    "K": len(use),
                }
                continue
            agg = mean_of_differences(
                np.array([r["D"] for r in use]), np.array([r["se_D"] for r in use])
            )
            se = agg["se_independent"] if c3 == "A" else agg["se_between"]
            t = _test(agg["T"], 0.01, se)
            sign = None
            if np.isfinite(se) and agg["T"] + 2 * se < 0:
                sign = "significantly negative: refuted with its direction"
            forms[name] = {
                **t,
                "K": len(use),
                "cells": [r["cell"] for r in use],
                "se_independent": agg["se_independent"],
                "se_between": agg["se_between"],
                "se_used": f"C3 form {c3} ({_SE_FORM[c3]}), C4 form {c4} ({_POP_FORM[c4]})",
                "sign_note": sign,
            }
    others = [
        _diff_row(summaries, k)
        for k, s in summaries.items()
        if _m(s)["M"] == 2 and not _m(s)["satellite"] and _m(s)["r"] > 0.0 and k not in population
    ]
    return {
        "population": population,
        "n_population": len(population),
        "n_qualifying": len(qualifies),
        "n_qualifying_c1": sum(1 for r in qualifies if r["c"] == 1.0),
        "cells": rows,
        "forms": forms,
        "not_evidence": {
            "unresolved_r01": [
                r for r in others if r["ticks"] < RESOLVED_TICKS and _approx(r, 0.1, summaries)
            ],
            "resolved_r001": [
                r for r in others if r["ticks"] >= RESOLVED_TICKS and _approx(r, 0.01, summaries)
            ],
            "unresolved_r001": [
                r for r in others if r["ticks"] < RESOLVED_TICKS and _approx(r, 0.01, summaries)
            ],
        },
        "statistic": "mean over cells of rel_beta(r = 0.1) - rel_beta(r = 0) (R10)",
    }


def _approx(row: dict[str, Any], r: float, summaries: dict[str, Any]) -> bool:
    return _m(summaries[row["cell"]])["r"] == r


def h65(summaries: dict[str, Any], boots: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(h65_cells(summaries))
    pooled = pooled_q(summaries, keys)
    boot_q = _pooled_boot(summaries, boots, keys, "q")
    finite = boot_q[np.isfinite(boot_q)]
    se_boot = float(np.std(finite, ddof=1))
    se_delta = math.sqrt(sum(_cell_q_delta_se(summaries[k]) ** 2 for k in keys)) / len(keys)
    ratio = max(se_boot, se_delta) / min(se_boot, se_delta)
    if ratio > 2.0:
        se, used = (
            max(se_boot, se_delta),
            ("larger of bootstrap and delta method (they differ by more than 2x)"),
        )
    else:
        se, used = se_boot, "bootstrap SD over 1000 resamples (Amendment 5.3)"
    t = _test(pooled["q"], 1.0, se, lower=True)

    sat = sorted(h65_satellite_cells(summaries))
    sat_q = pooled_q(summaries, sat)
    sat_boot = _pooled_boot(summaries, boots, sat, "q")
    sat_se = float(np.std(sat_boot[np.isfinite(sat_boot)], ddof=1))

    per_block = {}
    for b in BLOCKS:
        vals = np.mean([boots[k][b]["q"] for k in keys], axis=0)
        per_block[b] = {
            "q": float(np.mean([summaries[k]["blocks"][b]["q"] for k in keys])),
            "se_boot": float(np.std(vals[np.isfinite(vals)], ddof=1)),
        }
    rob_boot = _pooled_boot(summaries, boots, keys, "qrob")
    rob = float(
        np.sum(
            [_weights(2)[b] * summaries[k]["companions"][b]["qrob"] for k in keys for b in BLOCKS]
        )
        / (10 * len(keys))
    )
    return {
        **t,
        "se_boot": se_boot,
        "se_delta": se_delta,
        "se_ratio": ratio,
        "se_used": used,
        "n_boot_finite": int(finite.size),
        "cells": keys,
        "q_ratio_form": pooled["q_ratio"],
        "per_block": per_block,
        "per_cell": {
            k: {
                "q": sum(_weights(2)[b] * summaries[k]["blocks"][b]["q"] for b in BLOCKS) / 10,
                "se_boot": float(
                    np.std(sum(_weights(2)[b] * boots[k][b]["q"] for b in BLOCKS) / 10, ddof=1)
                ),
            }
            for k in keys
        },
        "satellite": {
            "cells": sat,
            "q": sat_q["q"],
            "se_boot": sat_se,
            "q_ratio_form": sat_q["q_ratio"],
            "same_direction": (sat_q["q"] < 1) == (pooled["q"] < 1),
        },
        "qrob_pooled": rob,
        "qrob_se_boot": float(np.std(rob_boot[np.isfinite(rob_boot)], ddof=1)),
        "statistic": "coordinate-weighted mean of block q over the 12 M = 2 cells (R7)",
    }


def h66(summaries: dict[str, Any], *, m2_only: bool = False, cond: bool = False) -> dict[str, Any]:
    keys = [
        k
        for k, s in summaries.items()
        if _m(s)["c"] == 1.0 and _m(s)["r"] == 0.0 and not (m2_only and _m(s)["satellite"])
    ]
    split_name = "verdict_cond" if cond else "verdict_all"
    rows = []
    for k in sorted(keys):
        v = summaries[k]["blocks"]["all"][split_name]
        rows.append(
            {
                "cell": k,
                "n_reliable": v["reliable"]["n"],
                "n_unreliable": v["unreliable"]["n"],
                "n_marginal": v["marginal"]["n"],
                "cov_reliable": v["reliable"]["cov"],
                "cov_unreliable": v["unreliable"]["cov"],
                "cov_marginal": v["marginal"]["cov"],
                "delta": v["delta"],
                "se_delta": v["se_delta"],
                "both": bool(v["reliable"]["n"] and v["unreliable"]["n"]),
            }
        )
    both = [r for r in rows if r["both"]]
    forms: dict[str, Any] = {}
    if len(both) < 2:
        for c5 in "AB":
            forms[f"C5{c5}"] = {
                "T": math.nan,
                "tau": 0.02,
                "se": math.nan,
                "z": math.nan,
                "p": 1.0,
                "section4": "inconclusive",
                "by_design": f"{len(both)} cells contain both classes, fewer than 2",
            }
    else:
        agg = mean_of_differences(
            np.array([r["delta"] for r in both]), np.array([r["se_delta"] for r in both])
        )
        for c5 in "AB":
            se = agg["se_independent"] if c5 == "A" else agg["se_between"]
            forms[f"C5{c5}"] = {
                **_test(agg["T"], 0.02, se),
                "K": agg["K"],
                "se_independent": agg["se_independent"],
                "se_between": agg["se_between"],
                "se_used": f"C5 form {c5} ({_SE_FORM[c5]})",
            }
    # Sensitivity only (R6): pool replications across the region.
    pool: dict[str, list[float]] = {"reliable": [0.0, 0.0], "unreliable": [0.0, 0.0]}
    for k in keys:
        v = summaries[k]["blocks"]["all"][split_name]
        for cls in pool:
            if v[cls]["n"]:
                pool[cls][0] += v[cls]["cov"] * v[cls]["n"]
                pool[cls][1] += v[cls]["n"]
    pc = {c: (s / n if n else math.nan, int(n)) for c, (s, n) in pool.items()}
    pooled_delta = pc["reliable"][0] - pc["unreliable"][0]
    pooled_se = math.sqrt(
        _binom_se(pc["reliable"][0], pc["reliable"][1]) ** 2
        + _binom_se(pc["unreliable"][0], pc["unreliable"][1]) ** 2
    )
    return {
        "region": sorted(keys),
        "n_cells_both": len(both),
        "min_class_count_in_both": min(
            (min(r["n_reliable"], r["n_unreliable"]) for r in both), default=0
        ),
        "cells": rows,
        "forms": forms,
        "replication_pooled": {
            "delta": pooled_delta,
            "se": pooled_se,
            "cov_reliable": pc["reliable"][0],
            "n_reliable": pc["reliable"][1],
            "cov_unreliable": pc["unreliable"][0],
            "n_unreliable": pc["unreliable"][1],
            "label": "sensitivity only: mixes cells, confounded with N (R6)",
        },
        "statistic": "mean over cells containing both classes of cov_reliable - "
        "cov_unreliable, coverage over all coordinates and all replications (R4-R6)",
    }


def decide(summaries: dict[str, Any], boots: dict[str, Any]) -> dict[str, Any]:
    """Every hypothesis, every combination, Holm per combination, final labels."""
    res = {
        "H6.1": h61(summaries),
        "H6.2": h62(summaries),
        "H6.3": h63(summaries),
        "H6.4": h64(summaries),
        "H6.5": h65(summaries, boots),
        "H6.6": h66(summaries),
    }
    options = {
        "H6.3": sorted(res["H6.3"]["forms"]),
        "H6.4": sorted(res["H6.4"]["forms"]),
        "H6.5": ["single"],
        "H6.6": sorted(res["H6.6"]["forms"]),
    }

    def form(h: str, f: str) -> dict[str, Any]:
        return res[h] if h == "H6.5" else res[h]["forms"][f]

    scenarios = []
    for combo in itertools.product(*(options[h] for h in FAMILY)):
        chosen = dict(zip(FAMILY, combo, strict=True))
        p = {h: form(h, chosen[h])["p"] for h in FAMILY}
        hl = holm(p)
        labels = {h: final_label(form(h, chosen[h])["section4"], hl[h]["passed"]) for h in FAMILY}
        scenarios.append({"forms": chosen, "p": p, "holm": hl, "labels": labels})
    primary = scenarios[0]  # every combination at form A
    for h in FAMILY:
        labels = {s["labels"][h] for s in scenarios}
        f = primary["forms"][h]
        entry = form(h, f)
        res[h].update(
            {
                "family": True,
                "status": "confirmatory",
                "primary_form": f,
                "T": entry["T"],
                "tau": entry["tau"],
                "se": entry["se"],
                "z": entry["z"],
                "p": entry["p"],
                "section4": entry["section4"],
                "se_used": entry.get("se_used", ""),
                "holm": primary["holm"][h],
                "labels_across_forms": sorted(labels),
                "label": least_favourable(labels),
            }
        )
    for h in ("H6.1", "H6.2"):
        res[h].update(
            {
                "family": False,
                "status": "exploratory",
                "holm": None,
                "label": {
                    "confirmed": "confirmed (exploratory)",
                    "refuted": "not confirmed (exploratory)",
                    "inconclusive": "inconclusive (exploratory)",
                }[res[h]["section4"]],
            }
        )
    res["scenarios"] = scenarios
    return res


# ------------------------------------------------------------ cross-tab


def crosstab(summaries: dict[str, Any]) -> list[dict[str, Any]]:
    """Section 9 item 5: measured coverage by verdict, per cell and pooled."""
    rows = []
    groups: dict[str, dict[str, list[float]]] = {}
    for k in sorted(summaries):
        s = summaries[k]
        m = _m(s)
        v = s["blocks"]["all"]["verdict_all"]
        row = {"cell": k, "M": m["M"], "N": m["N"], "rho": m["rho"], "r": m["r"], "c": m["c"]}
        for cls in VERDICTS:
            row[f"n_{cls}"] = v[cls]["n"]
            row[f"cov_{cls}"] = v[cls]["cov"]
            row[f"se_{cls}"] = v[cls]["se"]
        row["delta"] = v["delta"]
        row["se_delta"] = v["se_delta"]
        rows.append(row)
        group = f"pooled M={m['M']} c={m['c']} r={m['r']}"
        for name in (group, "pooled all cells"):
            g = groups.setdefault(name, {c: [0.0, 0.0] for c in VERDICTS})
            for cls in VERDICTS:
                if v[cls]["n"]:
                    g[cls][0] += v[cls]["cov"] * v[cls]["n"]
                    g[cls][1] += v[cls]["n"]
    for name in sorted(groups):
        g = groups[name]
        row = {"cell": name, "M": "", "N": "", "rho": "", "r": "", "c": ""}
        for cls in VERDICTS:
            s, n = g[cls]
            cov = s / n if n else math.nan
            row[f"n_{cls}"] = int(n)
            row[f"cov_{cls}"] = cov
            row[f"se_{cls}"] = _binom_se(cov, int(n))
        ok = g["reliable"][1] and g["unreliable"][1]
        row["delta"] = row["cov_reliable"] - row["cov_unreliable"] if ok else math.nan
        row["se_delta"] = (
            math.sqrt(row["se_reliable"] ** 2 + row["se_unreliable"] ** 2) if ok else math.nan
        )
        rows.append(row)
    return rows


# ---------------------------------------------------------- sensitivities


def sensitivity(
    summaries: dict[str, Any],
    conv_summaries: dict[str, Any],
    boots: dict[str, Any],
    res: dict[str, Any],
) -> dict[str, Any]:
    """Section 4.2 of Amendment 4 and the R-readings: what *would* differ. Not results."""
    out: dict[str, Any] = {"label": "sensitivity statements, not results"}

    # E4 companions as the estimand.
    h61_rob = []
    for c in res["H6.1"]["cells"]:
        k = c["cell"]
        se = summarise_boot(boots[k]["alpha"]["medrel"])["boot_sd"]
        h61_rob.append(
            {"cell": k, **_test(summaries[k]["companions"]["alpha"]["medrel"], 0.05, se)}
        )
    out["H6.1_if_medrel"] = _any_cell(h61_rob, "medrel_alpha", res["H6.1"]["region_cells"])[
        "section4"
    ]
    out["H6.1_if_medrel_cells"] = h61_rob

    rows = []
    for k in res["H6.4"]["population"]:
        r0 = res["H6.4"]["cells"][[c["cell"] for c in res["H6.4"]["cells"]].index(k)]
        k0 = r0["matched"]
        d = (
            summaries[k]["companions"]["beta"]["medrel"]
            - summaries[k0]["companions"]["beta"]["medrel"]
        )
        se = math.sqrt(
            summarise_boot(boots[k]["beta"]["medrel"])["boot_sd"] ** 2
            + summarise_boot(boots[k0]["beta"]["medrel"])["boot_sd"] ** 2
        )
        rows.append({"cell": k, "c": r0["c"], "D": d, "se": se, "q": r0["n_converged_with_se"]})
    h64_rob = {}
    for c4 in "AB":
        use = [r for r in rows if r["q"] > 0 and (c4 == "A" or r["c"] == 1.0)]
        if len(use) < H64_FLOOR:
            h64_rob[f"C4{c4}"] = "inconclusive (floor)"
            continue
        agg = mean_of_differences(np.array([r["D"] for r in use]), np.array([r["se"] for r in use]))
        h64_rob[f"C4{c4}"] = {
            "T": agg["T"],
            "A": _test(agg["T"], 0.01, agg["se_independent"]),
            "B": _test(agg["T"], 0.01, agg["se_between"]),
        }
    out["H6.4_if_medrel"] = h64_rob

    h5 = res["H6.5"]
    out["H6.5_if_qrob"] = _test(h5["qrob_pooled"], 1.0, h5["qrob_se_boot"], lower=True)
    out["H6.5_ratio_form"] = {"q": h5["q_ratio_form"], "note": "R7 sensitivity"}

    # R1: converged-only population for the mean-based estimands.
    conv_keys = sorted(h65_cells(conv_summaries))
    out["H6.5_converged_only_q"] = pooled_q(conv_summaries, conv_keys)["q"]
    out["H6.1_converged_only"] = h61(conv_summaries)["section4"]
    h64c = h64(conv_summaries)
    out["H6.4_converged_only"] = {f: v["section4"] for f, v in h64c["forms"].items()}
    out["H6.4_converged_only_T"] = {f: v["T"] for f, v in h64c["forms"].items()}

    # R3: matched-set q.
    keys = sorted(h65_cells(summaries))
    qm = np.mean(
        [
            sum(_weights(2)[b] * summaries[k]["blocks"][b]["q_matched"] for b in BLOCKS) / 10
            for k in keys
        ]
    )
    out["H6.5_matched_set_q"] = float(qm)

    # R4: coverage conditioned on convergence.
    h62c = []
    for c in res["H6.2"]["cells"]:
        blk = summaries[c["cell"]]["blocks"][c["block"]]
        h62c.append(
            {
                "cell": c["cell"],
                "block": c["block"],
                **_test(blk["cov_cond"], 0.90, blk["se_cov_cond"], lower=True),
            }
        )
    out["H6.2_conditional"] = _any_cell(h62c, "cov_cond", res["H6.2"]["region_cells"])["section4"]
    out["H6.6_conditional"] = {
        f: v["section4"] for f, v in h66(summaries, cond=True)["forms"].items()
    }
    out["H6.6_m2_only"] = {
        f: v["section4"] for f, v in h66(summaries, m2_only=True)["forms"].items()
    }
    out["H6.6_m2_only_T"] = {f: v["T"] for f, v in h66(summaries, m2_only=True)["forms"].items()}

    # R5: H6.3 per block.
    per_block = {}
    for b in BLOCKS:
        vals = {}
        for rho in (0.3028, 0.95):
            ks = [
                _one(summaries, M=2, N=N, rho=rho, r=0.0, c=1.0, satellite=False)
                for N in (2000, 10000)
            ]
            vals[rho] = (
                np.mean([summaries[k]["blocks"][b]["cov_all"] for k in ks]),
                math.sqrt(sum(summaries[k]["blocks"][b]["se_cov_all"] ** 2 for k in ks)) / 2,
            )
        T = vals[0.3028][0] - vals[0.95][0]
        se = math.sqrt(vals[0.3028][1] ** 2 + vals[0.95][1] ** 2)
        per_block[b] = _test(float(T), 0.0, se)
    out["H6.3_threshold_clause_per_block"] = per_block
    return out


# ------------------------------------------------------------- writing


def _clean(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_clean(v) for v in x]
    if isinstance(x, np.floating | float):
        f = float(x)
        return f if math.isfinite(f) else (None if math.isnan(f) else ("inf" if f > 0 else "-inf"))
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_clean(payload), indent=1) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: _fmt(v) for k, v in row.items()})


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return repr(v) if math.isfinite(v) else ("" if math.isnan(v) else repr(v))
    return v


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()


def manifest_digest(cells_dir: Path = CELLS_DIR) -> str:
    """``sha256("\\n".join(key:checksum))`` over the ``.done`` files, sorted by key.

    This is the construction that reproduces ``manifest_digest`` in
    ``studies/results/manifest.json``; recorded here because the commit that wrote
    the manifest did not record it.
    """
    lines = []
    for done in sorted(cells_dir.glob("*.done")):
        d = json.loads(done.read_text(encoding="utf-8"))
        lines.append(f"{d['cell_key']}:{d['checksum']}")
    lines.sort()
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def cell_rows(summaries: dict[str, Any], boots: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in sorted(summaries):
        s = summaries[k]
        m = s["meta"]
        for b in (*BLOCKS, "all"):
            x = s["blocks"][b]
            qb = summarise_boot(boots[k][b]["q"])
            rows.append(
                {
                    "cell": k,
                    "block": b,
                    "M": m["M"],
                    "N": m["N"],
                    "rho": m["rho"],
                    "r": m["r"],
                    "c": m["c"],
                    "satellite": int(m["satellite"]),
                    "R": m["R"],
                    "bias": x["bias"],
                    "se_bias": x["se_bias"],
                    "rel": x["rel"],
                    "se_rel": x["se_rel"],
                    "sd": x["sd"],
                    "mse": x["mse"],
                    "se_mse": x["se_mse"],
                    "n_se": x["n_se"],
                    "q": x["q"],
                    "se_q_delta": x["se_q_delta"],
                    "se_q_boot": qb["boot_sd"],
                    "q_matched": x["q_matched"],
                    "cov_all": x["cov_all"],
                    "se_cov_all": x["se_cov_all"],
                    "cov_cond": x["cov_cond"],
                    "se_cov_cond": x["se_cov_cond"],
                    "n_cov_cond": x["n_cov_cond"],
                }
            )
    return rows


def meta_rows(summaries: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in sorted(summaries):
        m = summaries[k]["meta"]
        resolved = m["r"] == 0.0 or m["ticks"] >= RESOLVED_TICKS
        rows.append(
            {
                "cell": k,
                "M": m["M"],
                "N": m["N"],
                "rho": m["rho"],
                "r": m["r"],
                "c": m["c"],
                "satellite": int(m["satellite"]),
                "R": m["R"],
                "T": m["T"],
                "delta": m["delta"],
                "ticks": m["ticks"] if math.isfinite(m["ticks"]) else "",
                "beta_min_T": m["beta_min_T"],
                "beta_max_T": m["beta_max_T"],
                "mean_n_events": m["mean_n_events"],
                "convergence_rate": m["convergence_rate"],
                "se_convergence_rate": m["se_convergence_rate"],
                "no_se_rate": m["no_se_rate"],
                "se_no_se_rate": m["se_no_se_rate"],
                "bound_hit_rate": m["bound_hit_rate"],
                "se_bound_hit_rate": m["se_bound_hit_rate"],
                "mean_nit": m["mean_nit"],
                "se_mean_nit": m["se_mean_nit"],
                "n_reliable": m["verdict_counts"]["reliable"],
                "n_marginal": m["verdict_counts"]["marginal"],
                "n_unreliable": m["verdict_counts"]["unreliable"],
                "n_converged": m["n_converged"],
                "n_se": m["n_se"],
                "n_converged_with_se": m["n_converged_with_se"],
                "resolved": int(resolved),
                "estimator_undefined": int((not resolved) or m["no_se_rate"] > UNDEFINED_NO_SE),
            }
        )
    return rows


def companion_rows(summaries: dict[str, Any], boots: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in sorted(summaries):
        comp = summaries[k]["companions"]
        for b in (*BLOCKS, "all"):
            row: dict[str, Any] = {"cell": k, "block": b}
            for stat in ("medbias", "medrel", "mad", "qrob"):
                bs = summarise_boot(boots[k][b][stat])
                row[stat] = comp[b][stat]
                row[f"{stat}_boot_sd"] = bs["boot_sd"]
                row[f"{stat}_lo"] = bs["lo"]
                row[f"{stat}_hi"] = bs["hi"]
            rows.append(row)
        bs = summarise_boot(boots[k]["tail"])
        rows.append(
            {
                "cell": k,
                "block": "tail",
                "medbias": comp["tail"],
                "medbias_boot_sd": bs["boot_sd"],
                "medbias_lo": bs["lo"],
                "medbias_hi": bs["hi"],
            }
        )
    return rows


def coordinate_rows(summaries: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in sorted(summaries):
        for c in summaries[k]["coordinates"]:
            rows.append(
                {
                    "cell": k,
                    "coordinate": c["name"],
                    "theta0": c["theta0"],
                    "bias": c["bias"],
                    "se_bias": c["se_bias"],
                    "rel": c["rel"],
                    "se_rel": c["se_rel"],
                    "sd": c["sd"],
                    "mse": c["mse"],
                    "q": c["q"],
                    "se_q_delta": c["se_q_delta"],
                    "cov_all": c["cov_all"],
                    "se_cov_all": c["se_cov_all"],
                    "cov_cond": c["cov_cond"],
                    "se_cov_cond": c["se_cov_cond"],
                }
            )
    return rows


def run(out_dir: Path = OUT_DIR, resamples: int = BOOT_RESAMPLES) -> dict[str, Any]:
    started = time.time()
    cells = load_cells()  # verifies the grid digest
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))["manifest_digest"]
    digest = manifest_digest()
    if digest != recorded:
        raise RuntimeError(f"manifest digest {digest} != recorded {recorded}; data changed")
    summaries: dict[str, Any] = {}
    conv_summaries: dict[str, Any] = {}
    boots: dict[str, Any] = {}
    counts = []
    for i, cell in enumerate(cells, start=1):
        data = load_cell(cell)
        summaries[cell.key] = cell_estimands(data)
        conv_summaries[cell.key] = cell_estimands(data, population="converged")
        boots[cell.key] = bootstrap_cell(data, resamples)
        counts.append(
            {
                "cell": cell.key,
                "rows": data.R,
                "n_bias": summaries[cell.key]["blocks"]["all"]["R"],
                "n_mse": summaries[cell.key]["blocks"]["all"]["n_se"],
                "n_cov_all": summaries[cell.key]["blocks"]["all"]["n_cov_all"],
                "n_cov_cond": summaries[cell.key]["blocks"]["all"]["n_cov_cond"],
                "n_tail": summaries[cell.key]["companions"]["n_tail"],
            }
        )
        print(f"[{i:3d}/{len(cells)}] {cell.key}", flush=True)
    res = decide(summaries, boots)
    sens = sensitivity(summaries, conv_summaries, boots, res)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "cells.csv", meta_rows(summaries))
    write_csv(out_dir / "blocks.csv", cell_rows(summaries, boots))
    write_csv(out_dir / "coordinates.csv", coordinate_rows(summaries))
    write_csv(out_dir / "companions.csv", companion_rows(summaries, boots))
    write_csv(out_dir / "crosstab.csv", crosstab(summaries))
    write_csv(out_dir / "row_counts.csv", counts)
    head = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain", "--", "studies/analyze.py"))
    provenance = {
        "study_id": STUDY_ID,
        "preregistration_tag": PREREG_TAG,
        "preregistration_commit": _git("rev-parse", f"{PREREG_TAG}^{{commit}}"),
        "analysis_commit": head,
        "analyze_py_dirty": dirty,
        "manifest_digest": digest,
        "cells": len(cells),
        "rows": sum(c["rows"] for c in counts),
        "bootstrap_resamples": resamples,
        "seconds": round(time.time() - started, 1),
    }
    write_json(out_dir / "hypotheses.json", {"provenance": provenance, **res})
    write_json(out_dir / "sensitivity.json", {"provenance": provenance, **sens})
    write_json(out_dir / "provenance.json", provenance)
    return {"provenance": provenance, "hypotheses": res, "sensitivity": sens}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    result = run(args.out)
    res = result["hypotheses"]
    print()
    for h in ("H6.1", "H6.2", *FAMILY):
        r = res[h]
        holm_txt = (
            f"step {r['holm']['step']} vs {r['holm']['threshold']:.5f} "
            f"{'met' if r['holm']['passed'] else 'missed'}"
            if r["holm"]
            else "outside family"
        )
        print(
            f"{h}: T={r['T']:.6g} tau={r['tau']} SE={r['se']:.4g} z={r['z']:.3f} "
            f"p={r['p']:.3g} s4={r['section4']} {holm_txt} -> {r['label']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
