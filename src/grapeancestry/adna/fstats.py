"""Patterson f3 / f4 on allele dosages (ADMIXTOOLS-style; no binary).

f3(C; A,B) = mean (c-a)(c-b) on allele frequency.
f4(A,B; C,D) = mean (a-b)(c-d).
qpAdm-class models deferred (need rotating outgroups on HPC).
"""

from __future__ import annotations

import numpy as np


def _p(dose: np.ndarray) -> np.ndarray:
    x = dose.astype(float)
    x[x < 0] = np.nan
    return x / 2.0


def f3(c: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    v = f3_per_site(c, a, b)
    m = np.isfinite(v)
    return float(np.nanmean(v[m])) if m.any() else float("nan")


def f4(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> float:
    v = f4_per_site(a, b, c, d)
    m = np.isfinite(v)
    return float(np.nanmean(v[m])) if m.any() else float("nan")


def f3_per_site(c: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    pc, pa, pb = _p(c), _p(a), _p(b)
    return (pc - pa) * (pc - pb)


def f4_per_site(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    pa, pb, pc, pd = _p(a), _p(b), _p(c), _p(d)
    return (pa - pb) * (pc - pd)


def chrom_blocks(sites: list[str]) -> np.ndarray:
    """One jackknife block per chromosome (site key ``chrom:pos``)."""
    return np.array([str(s).partition(":")[0] for s in sites], dtype=object)


def jackknife_mean(v: np.ndarray, blocks: np.ndarray) -> tuple[float, float, float, int]:
    """Delete-block jackknife on a per-site mean.

    SE formula is the unweighted leave-one-block-out jackknife used for
    f-statistics in Patterson et al. 2012 Genetics 192:1065–1093
    (doi:10.1534/genetics.112.145037). This is not the ADMIXTOOLS binary.
    """
    v = np.asarray(v, dtype=float)
    blocks = np.asarray(blocks)
    ok = np.isfinite(v)
    if not ok.any():
        return float("nan"), float("nan"), float("nan"), 0
    theta = float(np.mean(v[ok]))
    ids = list(np.unique(blocks[ok]))
    n = len(ids)
    if n < 3:
        return theta, float("nan"), float("nan"), n
    loo = np.array([float(np.mean(v[ok & (blocks != b)])) for b in ids], dtype=float)
    se = float(np.sqrt(((n - 1) / n) * np.sum((loo - loo.mean()) ** 2)))
    z = float(theta / se) if se > 0 else float("nan")
    return theta, se, z, n
