"""Parentage / hybridity and KING-like kinship from dosages."""

from __future__ import annotations

import numpy as np


def kinship_king(a: np.ndarray, b: np.ndarray) -> float:
    """KING-robust-ish kinship on 0/1/2 dosages (missing=-1).

    phi ≈ (E[N_IBD]/2 sites) via (1 - (a-b)^2 / 2) averaged on called sites.
    """
    mask = (a >= 0) & (b >= 0)
    if mask.sum() < 8:
        return float("nan")
    d = a[mask].astype(float) - b[mask].astype(float)
    return float(1.0 - np.mean(d * d) / 2.0)


def parentage_trio(child: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> dict[str, float]:
    """Mendelian-compatible fraction for a putative trio."""
    mask = (child >= 0) & (p1 >= 0) & (p2 >= 0)
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "mendel_ok": float("nan")}
    c, a, b = child[mask], p1[mask], p2[mask]
    lo = np.maximum(0, a + b - 2)
    hi = np.minimum(2, a + b)
    ok = (c >= lo) & (c <= hi)
    return {"n": n, "mendel_ok": float(np.mean(ok))}


def likely_parent(child: np.ndarray, cand: np.ndarray, mendel_min: float = 0.98) -> bool:
    """Single-parent: treat other parent as unknown (always 1/het)."""
    unknown = np.ones_like(cand)
    unknown[cand < 0] = -1
    r = parentage_trio(child, cand, unknown)
    return r["mendel_ok"] == r["mendel_ok"] and r["mendel_ok"] >= mendel_min
