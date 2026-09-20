"""Population Fst (Weir-Cockerham simplified) and GEA Spearman demo."""

from __future__ import annotations

import numpy as np


def weir_cockerham_fst(mat: np.ndarray, groups: np.ndarray) -> float:
    """Mean per-site Fst; mat (n_samples, n_sites) dosage 0/1/2, -1 missing."""
    uniq = [g for g in np.unique(groups) if g != ""]
    if len(uniq) < 2:
        return float("nan")
    fsts = []
    for j in range(mat.shape[1]):
        col = mat[:, j].astype(float)
        # allele freq per group (p = dose/2)
        ps, ns = [], []
        for g in uniq:
            idx = groups == g
            x = col[idx]
            x = x[x >= 0]
            if len(x) < 2:
                continue
            ps.append(x.mean() / 2.0)
            ns.append(len(x))
        if len(ps) < 2:
            continue
        ps = np.asarray(ps)
        ns = np.asarray(ns, float)
        pbar = np.average(ps, weights=ns)
        if pbar <= 0 or pbar >= 1:
            continue
        s2 = np.average((ps - pbar) ** 2, weights=ns)
        # WC simplified numerator/denom
        num = s2
        den = pbar * (1 - pbar)
        if den > 0:
            fsts.append(num / den)
    return float(np.mean(fsts)) if fsts else float("nan")


def spearman_gea(geno_score: np.ndarray, climate: np.ndarray) -> float:
    """Spearman correlation between a genetic PC/score and climate variable."""
    geno_score = np.asarray(geno_score, float)
    climate = np.asarray(climate, float)
    rg = geno_score.argsort().argsort().astype(float)
    rc = climate.argsort().argsort().astype(float)
    rg -= rg.mean()
    rc -= rc.mean()
    denom = np.linalg.norm(rg) * np.linalg.norm(rc)
    if denom < 1e-12:
        return float("nan")
    return float(np.dot(rg, rc) / denom)
