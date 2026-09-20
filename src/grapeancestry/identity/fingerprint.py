"""Core fingerprint SNP + purity / mix-up heuristics."""

from __future__ import annotations

import numpy as np

from grapeancestry.resource.coresnp import greedy_coresnp


def fingerprint_sites(mat: np.ndarray, sites: list[str], n: int = 50) -> list[str]:
    """High-discrimination SNP set (CoreSNP greedy)."""
    return greedy_coresnp(mat, sites, max_markers=n)


def purity_z(query: np.ndarray, panel: np.ndarray, n_ref: int = 500) -> dict[str, float]:
    """Het rate vs panel; z>3 suggests mixture / mix-up."""
    q = query.astype(float)
    ok = q >= 0
    qhet = float(np.mean(q[ok] == 1)) if ok.any() else float("nan")
    hets = []
    for i in range(min(panel.shape[0], n_ref)):
        row = panel[i].astype(float)
        m = row >= 0
        if m.sum() < 50:
            continue
        hets.append(float(np.mean(row[m] == 1)))
    if not hets or qhet != qhet:
        return {"het": qhet, "panel_mean": float("nan"), "z": float("nan")}
    mu, sd = float(np.mean(hets)), float(np.std(hets) + 1e-9)
    return {"het": qhet, "panel_mean": mu, "z": (qhet - mu) / sd}


def is_mixture(z: float, z_cut: float = 3.0) -> bool:
    return z == z and z > z_cut
