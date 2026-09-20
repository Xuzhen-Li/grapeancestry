"""Windowed selection-scan demo (G12-like heterozygosity dip)."""

from __future__ import annotations

import numpy as np


def window_het(mat: np.ndarray, window: int = 20) -> np.ndarray:
    """Mean het (dose==1) per site, then rolling mean."""
    X = mat.astype(float)
    het = np.array(
        [float(np.mean(col[col >= 0] == 1)) if (col >= 0).any() else float("nan") for col in X.T]
    )
    out = np.full_like(het, np.nan)
    for i in range(len(het)):
        lo, hi = max(0, i - window // 2), min(len(het), i + window // 2)
        chunk = het[lo:hi]
        chunk = chunk[np.isfinite(chunk)]
        if len(chunk):
            out[i] = float(chunk.mean())
    return out


def g12_like(het: np.ndarray, q: float = 0.05) -> list[int]:
    """Sites in the lowest q quantile of windowed het (outlier list)."""
    ok = het[np.isfinite(het)]
    if len(ok) == 0:
        return []
    cut = float(np.quantile(ok, q))
    return [i for i, v in enumerate(het) if v == v and v <= cut]
