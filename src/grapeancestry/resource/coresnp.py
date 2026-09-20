"""Greedy CoreSNP / fingerprint marker selection."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from grapeancestry.core.dosage import load_cache


def greedy_coresnp(mat: np.ndarray, sites: list[str], max_markers: int = 100) -> list[str]:
    """Select markers that maximize pairwise sample distinction.

    mat: (n_samples, n_sites) int8, -1 missing.
    """
    n_s, n_m = mat.shape
    # Treat missing as 0 for distinction heuristic (Occam)
    X = mat.astype(np.int16)
    X[X < 0] = 0
    selected: list[int] = []
    # undistinguished pairs mask (upper triangle flattened via boolean matrix)
    # Start: all pairs need distinction
    remaining = np.ones((n_s, n_s), dtype=bool)
    np.fill_diagonal(remaining, False)

    for _ in range(min(max_markers, n_m)):
        best_j, best_score = -1, -1
        for j in range(n_m):
            if j in selected:
                continue
            col = X[:, j]
            # pairs distinguished by this marker
            diff = col[:, None] != col[None, :]
            score = int((diff & remaining).sum())
            if score > best_score:
                best_score = score
                best_j = j
        if best_j < 0 or best_score == 0:
            break
        selected.append(best_j)
        col = X[:, best_j]
        remaining &= col[:, None] == col[None, :]
        if not remaining.any():
            break
    return [sites[j] for j in selected]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, default=Path("results/cache/panel_dosage_5k.npz"))
    p.add_argument("--out", type=Path, default=Path("results/fingerprint_snps.txt"))
    p.add_argument("--max-markers", type=int, default=100)
    args = p.parse_args(argv)
    mat, _samples, sites = load_cache(args.cache)
    # subsample samples for speed if huge
    if mat.shape[0] > 400:
        rng = np.random.default_rng(0)
        idx = rng.choice(mat.shape[0], size=400, replace=False)
        mat = mat[idx]
    markers = greedy_coresnp(mat, sites, max_markers=args.max_markers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(markers) + ("\n" if markers else ""))
    print(f"wrote {args.out} n={len(markers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
