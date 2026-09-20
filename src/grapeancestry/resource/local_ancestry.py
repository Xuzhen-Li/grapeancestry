"""Windowed local-ancestry sketch: nearest reference group per SNP window."""

from __future__ import annotations

import numpy as np


def window_paint(
    query: np.ndarray,
    ref: np.ndarray,
    ref_groups: np.ndarray,
    window: int = 25,
) -> list[str]:
    """For each window, assign the Grp with highest IBS to query."""
    n = query.shape[0]
    labels: list[str] = []
    for start in range(0, n, window):
        sl = slice(start, min(n, start + window))
        q = query[sl]
        scores = {}
        for g in np.unique(ref_groups):
            if not g:
                continue
            rows = ref[ref_groups == g][:, sl]
            if rows.size == 0:
                continue
            ibs = []
            for r in rows[:40]:
                m = (q >= 0) & (r >= 0)
                if m.sum() == 0:
                    continue
                ibs.append(float(np.mean(q[m] == r[m])))
            if ibs:
                scores[str(g)] = float(np.mean(ibs))
        labels.append(max(scores, key=scores.get) if scores else "NA")
    return labels
