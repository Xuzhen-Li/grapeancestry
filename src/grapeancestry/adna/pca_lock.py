"""Locked PCA: GCTA64 2449 freeze + least-squares projection of new samples.

Panel axes: GCTA v1.95.3 GRM-PCA, 2449 × 153,483 non-GWAS sites,
``--autosome-num 19`` (Yang et al. 2011 AJHG doi:10.1016/j.ajhg.2010.11.011).
New samples: Patterson / EIGENSOFT least-squares onto those frozen axes
(Patterson et al. 2006 PLoS Genet doi:10.1371/journal.pgen.0020190;
smartPCA ``lsqproject``). Do not recompute 2449 with numpy SVD.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from grapeancestry.adna.panel167k_nogwas import EXPECTED_KEEP_SITES, PANEL167K_NOGWAS_FAMILY
from grapeancestry.adna.project import SVDCacheResult

SNP_SET = PANEL167K_NOGWAS_FAMILY
VITIS_AUTOSOME_NUM = 19
N_PCS = 10
METHOD_GCTA = "GCTA64 GRM-PCA (panel167k_nogwas)"
METHOD_SMARTPCA = "smartPCA lsqproject (panel167k_nogwas)"
_STAMP_NAME = "pca_lock.json"
_SITE_SLACK = 16
_GCTA_PREFIX = "gcta_nogwas"


def parse_gcta_eigenvec(path: Path, n_pcs: int = N_PCS) -> tuple[list[str], np.ndarray]:
    """GCTA ``--pca`` eigenvec: FID IID PC1… (optional header)."""
    ids: list[str] = []
    rows: list[list[float]] = []
    with Path(path).open() as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 2 + n_pcs:
                continue
            if parts[0].upper() in {"FID", "IID"}:
                continue
            try:
                vec = [float(x) for x in parts[2 : 2 + n_pcs]]
            except ValueError:
                continue
            if not np.isfinite(vec).all():
                continue
            ids.append(parts[1])
            rows.append(vec)
    return ids, np.asarray(rows, float).reshape(-1, n_pcs)


def parse_gcta_eigenval(path: Path, n_pcs: int = N_PCS) -> list[float]:
    """Variance fractions: top PCs over the sum of every eigenvalue in the file."""
    raw: list[float] = []
    with Path(path).open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw.append(float(line.split()[0]))
            except ValueError:
                continue
    total = float(sum(v for v in raw if np.isfinite(v) and v >= 0))
    if total <= 0:
        return [float("nan")] * n_pcs
    out = [v / total for v in raw[:n_pcs]]
    while len(out) < n_pcs:
        out.append(float("nan"))
    return out


def parse_gcta_eigenval_raw(path: Path, n_pcs: int = N_PCS) -> list[float]:
    vals: list[float] = []
    with Path(path).open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                vals.append(float(line.split()[0]))
            except ValueError:
                continue
            if len(vals) >= n_pcs:
                break
    while len(vals) < n_pcs:
        vals.append(float("nan"))
    return vals


def write_smartpca_stamp(
    workdir: Path,
    sample: str,
    n_pcs: int = N_PCS,
    n_sites: int = EXPECTED_KEEP_SITES,
    snp_set: str = SNP_SET,
) -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / _STAMP_NAME
    path.write_text(
        json.dumps(
            {
                "snp_set": snp_set,
                "n_sites": int(n_sites),
                "n_pcs": int(n_pcs),
                "sample": sample,
            }
        )
        + "\n"
    )
    return path


def smartpca_stamp_ok(workdir: Path, sample: str, n_pcs: int = N_PCS) -> bool:
    path = Path(workdir) / _STAMP_NAME
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if str(data.get("sample") or "") != sample:
        return False
    if str(data.get("snp_set") or "") != SNP_SET:
        return False
    try:
        got_pcs = int(data.get("n_pcs") or 0)
        got_sites = int(data.get("n_sites") or 0)
    except (TypeError, ValueError):
        return False
    if got_pcs < int(n_pcs):
        return False
    return abs(got_sites - EXPECTED_KEEP_SITES) <= _SITE_SLACK


def write_keep_nogwas_snps(map_path: Path, keep_chrpos: list[str], out: Path) -> int:
    """Write MAP SNP IDs whose chrom:pos is in ``keep_chrpos`` (``18:1``)."""
    want = set(keep_chrpos)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with Path(map_path).open() as fh, out.open("w") as oh:
        for line in fh:
            if not line.strip():
                continue
            chrom, snp, _g, pos, *_ = line.split()
            key = f"{chrom}:{pos}"
            key_id = ":".join(snp.split(":")[:2])
            if key in want or key_id in want:
                oh.write(f"{snp}\n")
                n += 1
    return n


def gcta_prefix(root: Path) -> Path:
    return Path(root) / "data" / "panel" / "pca" / _GCTA_PREFIX


@dataclass
class GctaFreeze:
    ids: list[str]
    xy: np.ndarray
    evals: list[float]
    evals_raw: list[float]
    path: Path


def load_gcta_freeze(root: Path, n_pcs: int = N_PCS) -> GctaFreeze | None:
    prefix = gcta_prefix(root)
    evec = prefix.with_suffix(".eigenvec")
    evl = prefix.with_suffix(".eigenval")
    if not evec.exists() or not evl.exists():
        return None
    ids, xy = parse_gcta_eigenvec(evec, n_pcs=n_pcs)
    if len(ids) < 10 or xy.shape[1] < 3:
        return None
    return GctaFreeze(
        ids=ids,
        xy=xy,
        evals=parse_gcta_eigenval(evl, n_pcs=n_pcs),
        evals_raw=parse_gcta_eigenval_raw(evl, n_pcs=n_pcs),
        path=evec,
    )


def _zchunk(block: np.ndarray, mu: np.ndarray, sd: np.ndarray, ok_snp: np.ndarray) -> np.ndarray:
    sl = np.asarray(block, float)
    sl = np.where(sl < 0, np.nan, sl)
    z = (sl - mu) / sd
    return np.where(np.isfinite(z) & ok_snp, z, 0.0)


def lsq_project_onto_gcta(
    ref_ids: list[str],
    ref_dosage: np.ndarray,
    query_dosage: np.ndarray,
    gcta_ids: list[str],
    gcta_xy: np.ndarray,
    *,
    chunk: int = 128,
) -> np.ndarray:
    """Project one query row onto frozen GCTA sample PCs (Patterson lsq).

    SNP weights are chosen so the 2449 rows reconstruct the freeze; the query
    uses the same weights. Missing query genotypes (dosage < 0) are skipped.
    """
    q = np.asarray(query_dosage, float).reshape(-1)
    x = np.asarray(ref_dosage)
    if x.ndim != 2:
        raise ValueError("ref_dosage must be 2-d")
    idx = {sid: i for i, sid in enumerate(ref_ids)}
    keep = [i for i, sid in enumerate(gcta_ids) if sid in idx]
    if len(keep) < 10:
        raise ValueError("too few IDs overlap GCTA freeze")
    rows = [idx[gcta_ids[i]] for i in keep]
    v = np.asarray(gcta_xy, float)[keep]
    x_keep = x[rows]
    n, p = x_keep.shape
    k = v.shape[1]
    miss = x_keep < 0
    valid = (~miss).sum(axis=0).astype(float)
    acc = np.where(miss, 0, x_keep).sum(axis=0).astype(float)
    mu = np.divide(acc, np.maximum(valid, 1.0))
    paf = np.clip(mu / 2.0, 1e-6, 1.0 - 1e-6)
    sd = np.sqrt(2.0 * paf * (1.0 - paf))
    ok_snp = (valid >= 10) & (sd > 0)
    w = np.zeros((p, k), dtype=float)
    for i0 in range(0, n, chunk):
        zsl = _zchunk(x_keep[i0 : i0 + chunk], mu, sd, ok_snp)
        w += zsl.T @ v[i0 : i0 + chunk]
    ref_hat = np.zeros((n, k), dtype=float)
    for i0 in range(0, n, chunk):
        zsl = _zchunk(x_keep[i0 : i0 + chunk], mu, sd, ok_snp)
        ref_hat[i0 : i0 + chunk] = zsl @ w
    den = np.sum(ref_hat * ref_hat, axis=0)
    num = np.sum(ref_hat * v, axis=0)
    alpha = np.divide(num, den, out=np.zeros(k), where=den > 1e-12)
    qmiss = (q < 0) | ~np.isfinite(q) | ~ok_snp
    zq = np.where(qmiss, 0.0, (q - mu) / sd)
    zq = np.where(np.isfinite(zq), zq, 0.0)
    return (zq @ w) * alpha


def locked_pca_for_sample(
    root: Path,
    sample: str,
    ref_ids: list[str],
    ref_dosage: np.ndarray,
    query_dosage: np.ndarray,
    cache_sites: list[str],
    nogwas_sites: list[str],
) -> SVDCacheResult | None:
    """2449 from GCTA freeze; query lsq-projected onto those axes."""
    freeze = load_gcta_freeze(root)
    if freeze is None:
        return None
    site_i = {s: i for i, s in enumerate(cache_sites)}
    cols = [site_i[s] for s in nogwas_sites if s in site_i]
    if len(cols) < EXPECTED_KEEP_SITES - _SITE_SLACK:
        return None
    x = np.asarray(ref_dosage)[:, cols]
    q = np.asarray(query_dosage).reshape(-1)[cols]
    gcta_set = set(freeze.ids)
    if sample in gcta_set:
        qi = freeze.ids.index(sample)
        qxy = freeze.xy[qi]
    else:
        qxy = lsq_project_onto_gcta(ref_ids, x, q, freeze.ids, freeze.xy)
    method = METHOD_GCTA
    if not np.isfinite(qxy).all():
        return None
    return SVDCacheResult(
        ref_ids=list(freeze.ids),
        ref_coords=np.asarray(freeze.xy, float),
        query_ids=[sample],
        query_coords=np.asarray(qxy, float).reshape(1, -1),
        evals=list(freeze.evals),
        method=method,
        cache_name="gcta_nogwas",
        n_sites=len(cols),
    )


def pca_focus_range(
    values: np.ndarray,
    extra: np.ndarray | None = None,
    *,
    lo_pct: float = 1.0,
    hi_pct: float = 98.0,
    pad: float = 0.12,
) -> tuple[float, float] | None:
    """Axis window for PCA plots: 1–98% of the cloud, plus query, plus pad.

    GCTA PC2 is a real axis (OUT / a few C-Ad hybrids at |PC2|>0.1). Autoscale
    to those points flattens vinifera. This is a view window, not a new PCA.
    """
    v = np.asarray(values, float).ravel()
    v = v[np.isfinite(v)]
    if v.size < 8:
        return None
    lo, hi = (float(x) for x in np.percentile(v, [lo_pct, hi_pct]))
    if extra is not None:
        e = np.asarray(extra, float).ravel()
        e = e[np.isfinite(e)]
        if e.size:
            lo = min(lo, float(e.min()))
            hi = max(hi, float(e.max()))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return None
    span = hi - lo
    p = span * pad if span > 0 else 0.01
    return lo - p, hi + p
