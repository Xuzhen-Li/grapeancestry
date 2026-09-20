"""EMMAX/P3D mixed-model GWAS primitives (numpy + scipy only).

Formulas follow Kang et al. 2008 (EMMA δ; doi:10.1534/genetics.107.080101),
Kang et al. 2010 (EMMAX; doi:10.1038/ng.548), Zhang et al. 2010 (P3D;
doi:10.1038/ng.546), VanRaden 2008 GRM (doi:10.3168/jds.2007-0980).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar

# χ²_1 median. Devlin & Roeder 1999 use ~0.456; scipy chi2.ppf(0.5, 1) = 0.454936...
CHI2_1_MEDIAN = 0.45493642311957283


def allele_freq(X: np.ndarray) -> np.ndarray:
    """p = mean dosage / 2 on called genotypes (X<0 missing)."""
    X = np.asarray(X, float)
    n_ok = np.sum(X >= 0, axis=0)
    s = np.sum(np.where(X >= 0, X, 0.0), axis=0)
    p = np.divide(s, 2.0 * np.maximum(n_ok, 1), dtype=float)
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    return p


def impute_mean(X: np.ndarray, freqs: np.ndarray | None = None) -> np.ndarray:
    """Replace X<0 with 2p (column mean)."""
    X = np.asarray(X, float).copy()
    if freqs is None:
        freqs = allele_freq(X)
    miss = X < 0
    if miss.any():
        X[miss] = np.take(2.0 * freqs, np.where(miss)[1])
    return X


def site_filter(
    mat: np.ndarray,
    *,
    maf_min: float = 0.05,
    max_missing: float = 0.2,
) -> np.ndarray:
    """Boolean keep mask on the rows of ``mat`` (phenotype subset)."""
    X = np.asarray(mat, float)
    miss = np.mean(X < 0, axis=0)
    p = allele_freq(X)
    maf = np.minimum(p, 1.0 - p)
    return (maf >= maf_min) & (miss <= max_missing)


def grm_vanraden(
    X: np.ndarray,
    freqs: np.ndarray | None = None,
    *,
    return_scale: bool = False,
) -> np.ndarray | tuple[np.ndarray, float, float]:
    """VanRaden (2008) method 1: Z = X−2p; K = ZZᵀ / (2 Σ p(1−p)), then mean-diag=1."""
    X = np.asarray(X, float)
    if freqs is None:
        freqs = allele_freq(X)
    Z = X - 2.0 * freqs
    denom = 2.0 * float(np.sum(freqs * (1.0 - freqs)))
    if denom < 1e-12:
        denom = 1.0
    K = Z @ Z.T / denom
    K = 0.5 * (K + K.T)
    dmean = float(np.mean(np.diag(K)))
    if dmean > 1e-12:
        K = K / dmean
    else:
        dmean = 1.0
    if return_scale:
        return K, denom, dmean
    return K


def reml_delta(
    y: np.ndarray,
    K: np.ndarray,
    C: np.ndarray,
) -> tuple[float, float, float, np.ndarray, np.ndarray, float]:
    """EMMA δ = σ_e²/σ_g² via 1-D REML (Kang 2008).

    Returns (delta, sigma_g2, sigma_e2, U, S, reml_ll).
    """
    y = np.asarray(y, float)
    C = np.asarray(C, float)
    if C.ndim == 1:
        C = C[:, None]
    K = np.asarray(K, float)
    K = 0.5 * (K + K.T)
    S, U = np.linalg.eigh(K)
    S = np.clip(S, 0.0, None)
    yt = U.T @ y
    Ct = U.T @ C
    n, q = C.shape[0], C.shape[1]
    df = max(n - q, 1)

    def nll(log_delta: float) -> float:
        delta = float(np.exp(log_delta))
        d = np.maximum(S + delta, 1e-12)
        inv_d = 1.0 / d
        Cw = Ct * inv_d[:, None]
        xtx = Ct.T @ Cw
        try:
            beta = np.linalg.solve(xtx, Cw.T @ yt)
        except np.linalg.LinAlgError:
            return 1e12
        resid = yt - Ct @ beta
        ssr = float(resid @ (resid * inv_d))
        sg = ssr / df
        if sg <= 1e-18:
            return 1e12
        logdet_d = float(np.sum(np.log(d)))
        sign, logdet_x = np.linalg.slogdet(xtx)
        if sign <= 0:
            return 1e12
        ll = -0.5 * (df * np.log(2.0 * np.pi * sg) + logdet_d + logdet_x + df)
        return -ll

    opt = minimize_scalar(nll, bounds=(-10.0, 10.0), method="bounded")
    log_d = float(opt.x)
    delta = float(np.exp(log_d))
    d = np.maximum(S + delta, 1e-12)
    inv_d = 1.0 / d
    Cw = Ct * inv_d[:, None]
    xtx = Ct.T @ Cw
    beta = np.linalg.solve(xtx, Cw.T @ yt)
    resid = yt - Ct @ beta
    sg = float(resid @ (resid * inv_d) / df)
    se = delta * sg
    ll = -float(opt.fun)
    return delta, sg, se, U, S, ll


def pcs_from_K(U: np.ndarray, n_pcs: int) -> np.ndarray:
    """Leading PCs = eigenvectors of largest eigenvalues (eigh ascending)."""
    n_pcs = min(n_pcs, U.shape[1])
    if n_pcs <= 0:
        return np.zeros((U.shape[0], 0))
    return U[:, -n_pcs:]


def p3d_scan(
    X: np.ndarray,
    y: np.ndarray,
    C: np.ndarray,
    U: np.ndarray,
    S: np.ndarray,
    delta: float,
    *,
    chunk: int = 10_000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """P3D/EMMAX SNP scan: weight by 1/sqrt(λ_i+δ), WLS t-test (vectorized chunks)."""
    X = np.asarray(X)
    y = np.asarray(y, float)
    C = np.asarray(C, float)
    n, m = X.shape
    q = C.shape[1]
    d = np.maximum(S + delta, 1e-12)
    w = 1.0 / np.sqrt(d)
    yt = (U.T @ y) * w
    Ct = (U.T @ C) * w[:, None]
    Q, _ = np.linalg.qr(Ct, mode="reduced")
    yres = yt - Q @ (Q.T @ yt)
    yy = float(yres @ yres)
    df = max(n - q - 1, 1)

    beta = np.zeros(m)
    se = np.zeros(m)
    tstat = np.zeros(m)
    pval = np.ones(m)

    for start in range(0, m, chunk):
        sl = slice(start, min(start + chunk, m))
        Xc = np.asarray(X[:, sl], dtype=np.float64)
        Xt = (U.T @ Xc) * w[:, None]
        Xres = Xt - Q @ (Q.T @ Xt)
        xtx = np.sum(Xres * Xres, axis=0)
        xty = Xres.T @ yres
        good = xtx > 1e-12
        b = np.zeros_like(xtx)
        b[good] = xty[good] / xtx[good]
        rss = np.maximum(yy - b * b * xtx, 1e-18)
        sigma2 = rss / df
        se_j = np.sqrt(sigma2 / np.maximum(xtx, 1e-12))
        t = np.zeros_like(b)
        t[good] = b[good] / se_j[good]
        pv = np.ones_like(t)
        pv[good] = 2.0 * stats.t.sf(np.abs(t[good]), df)
        beta[sl] = b
        se[sl] = se_j
        tstat[sl] = t
        pval[sl] = np.clip(pv, 1e-300, 1.0)
    return beta, se, tstat, pval


def genomic_inflation_lambda(p: np.ndarray) -> float:
    """λ_GC = median(χ²_1(p)) / 0.4549 (Devlin & Roeder 1999)."""
    p = np.asarray(p, float)
    p = p[np.isfinite(p) & (p > 0) & (p <= 1.0)]
    if p.size < 10:
        return float("nan")
    chi = stats.chi2.isf(p, df=1)
    return float(np.median(chi) / CHI2_1_MEDIAN)


def bh_fdr(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg 1995 q-values."""
    p = np.asarray(p, float)
    n = p.size
    order = np.argsort(p)
    ranked = np.clip(p[order], 0.0, 1.0)
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0.0, 1.0)
    out = np.empty_like(q)
    out[order] = q
    return out


def parse_site(site: str) -> tuple[str, int]:
    chrom, _, pos = site.partition(":")
    try:
        return chrom, int(pos)
    except ValueError:
        return chrom, 0


def clump_hits(
    chrom: list[str],
    pos: np.ndarray,
    p: np.ndarray,
    *,
    window_bp: int = 200_000,
    p_max: float = 1.0,
) -> list[dict]:
    """Greedy p-ascending clumping ±window_bp on the same chromosome."""
    idx = np.argsort(p)
    taken: dict[str, list[int]] = defaultdict(list)
    leads: list[dict] = []
    for i in idx:
        if p[i] > p_max:
            continue
        c = chrom[i]
        x = int(pos[i])
        if any(abs(x - t) <= window_bp for t in taken[c]):
            continue
        taken[c].append(x)
        leads.append({"i": int(i), "chrom": c, "pos": x, "p": float(p[i])})
    return leads


def chrom_sort_key(c: str) -> tuple[int, str]:
    try:
        return (int(c), "")
    except ValueError:
        return (10_000, c)
