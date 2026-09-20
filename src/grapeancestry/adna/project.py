"""PCA fit on reference panel dosages + project query samples.

Uses allele dosage (0/1/2); missing → population mean imputation per site.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class PCAModel:
    mean: np.ndarray  # (n_sites,)
    components: np.ndarray  # (n_components, n_sites)
    ref_coords: np.ndarray  # (n_ref, n_components)
    ref_ids: list[str]
    explained_variance_ratio: np.ndarray | None = None


@dataclass
class SVDCacheResult:
    ref_ids: list[str]
    ref_coords: np.ndarray
    query_ids: list[str]
    query_coords: np.ndarray
    evals: list[float]
    method: str
    cache_name: str
    n_sites: int
    workdir: Path | None = None


SVD_CACHE_VERSION = 1


def write_svd_cache(
    path: "Path",
    *,
    ref_ids: list[str],
    ref_coords: np.ndarray,
    query_ids: list[str],
    query_coords: np.ndarray,
    evals: list[float] | np.ndarray,
    method: str,
    cache_name: str,
    n_sites: int,
) -> None:
    """Write a versioned 3-PC coordinate cache with its compatibility metadata."""
    ref_xy = np.asarray(ref_coords, dtype=float)
    query_xy = np.asarray(query_coords, dtype=float)
    if ref_xy.ndim != 2 or query_xy.ndim != 2:
        raise ValueError("SVD coordinates must be two-dimensional")
    if ref_xy.shape[0] != len(ref_ids) or query_xy.shape[0] != len(query_ids):
        raise ValueError("SVD coordinate rows do not match IDs")
    if ref_xy.shape[1] < 3 or query_xy.shape[1] < 3:
        raise ValueError("SVD cache requires at least 3 PCs")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        version=np.array(SVD_CACHE_VERSION, dtype=np.int64),
        ref_ids=np.asarray(ref_ids, dtype=object),
        ref_coords=ref_xy[:, :3],
        query_ids=np.asarray(query_ids, dtype=object),
        query_coords=query_xy[:, :3],
        evals=np.asarray(evals, dtype=float),
        method=np.array(method),
        cache_name=np.array(cache_name),
        n_sites=np.array(n_sites, dtype=np.int64),
    )


def load_svd_cache(
    path: "Path",
    *,
    expected_ref_ids: list[str],
    query_id: str,
    cache_name: str | None = None,
    n_sites: int | None = None,
    n_components: int = 3,
) -> SVDCacheResult | None:
    """Read a cache only when its IDs, dimensions, method, and matrix match."""
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=True) as z:
            version = int(np.asarray(z["version"]).item())
            ref_ids = [str(x) for x in np.asarray(z["ref_ids"], dtype=object).tolist()]
            query_ids = [str(x) for x in np.asarray(z["query_ids"], dtype=object).tolist()]
            ref_coords = np.asarray(z["ref_coords"], dtype=float)
            query_coords = np.asarray(z["query_coords"], dtype=float)
            evals = np.asarray(z["evals"], dtype=float).reshape(-1)
            method = str(np.asarray(z["method"]).item())
            stored_cache_name = str(np.asarray(z["cache_name"]).item())
            stored_n_sites = int(np.asarray(z["n_sites"]).item())
    except (KeyError, OSError, ValueError, TypeError, EOFError):
        return None
    if version != SVD_CACHE_VERSION or "svd" not in method.lower():
        return None
    if ref_ids != list(expected_ref_ids) or query_id not in query_ids:
        return None
    if cache_name is not None and stored_cache_name != cache_name:
        return None
    if n_sites is not None and stored_n_sites != n_sites:
        return None
    if (
        ref_coords.ndim != 2
        or query_coords.ndim != 2
        or ref_coords.shape[0] != len(ref_ids)
        or query_coords.shape[0] != len(query_ids)
        or ref_coords.shape[1] < n_components
        or query_coords.shape[1] < n_components
        or not np.isfinite(ref_coords[:, :n_components]).all()
        or not np.isfinite(query_coords[:, :n_components]).all()
    ):
        return None
    return SVDCacheResult(
        ref_ids=ref_ids,
        ref_coords=ref_coords[:, :n_components],
        query_ids=query_ids,
        query_coords=query_coords[:, :n_components],
        evals=[float(x) for x in evals],
        method=method,
        cache_name=stored_cache_name,
        n_sites=stored_n_sites,
        workdir=path.parent,
    )


def _impute_mean(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """X shape (n_samples, n_sites), missing=-1 → column mean."""
    X = X.astype(float).copy()
    missing = X < 0
    # column means over non-missing
    means = np.zeros(X.shape[1])
    for j in range(X.shape[1]):
        col = X[:, j]
        ok = col >= 0
        means[j] = col[ok].mean() if ok.any() else 0.0
        col[~ok] = means[j]
        X[:, j] = col
    return X, means


def fit_pca(ref_matrix: np.ndarray, ref_ids: list[str], n_components: int = 2) -> PCAModel:
    X, means = _impute_mean(ref_matrix)
    Xc = X - means
    # SVD on centered matrix
    _u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    components = vt[:n_components]
    coords = Xc @ components.T
    total = float(np.sum(np.square(s)))
    if total > 0 and np.isfinite(total):
        explained = np.square(s[:n_components]) / total
    else:
        explained = np.zeros(min(n_components, len(s)), dtype=float)
    return PCAModel(
        mean=means,
        components=components,
        ref_coords=coords,
        ref_ids=list(ref_ids),
        explained_variance_ratio=explained,
    )


def project(model: PCAModel, query: np.ndarray) -> np.ndarray:
    """Project query dosage vector(s) → (n_query, n_components)."""
    if query.ndim == 1:
        query = query.reshape(1, -1)
    Q = query.astype(float).copy()
    for j in range(Q.shape[1]):
        miss = Q[:, j] < 0
        Q[miss, j] = model.mean[j]
    Qc = Q - model.mean
    return Qc @ model.components.T
