"""Genomic selection models (numpy + scipy only; no sklearn).

Unified fit(X, y) -> dict; predict(model, X_test) -> yhat.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from grapeancestry.breeding.mixed_model import (
    allele_freq,
    grm_vanraden,
    impute_mean,
    reml_delta,
)


def _center_y(y: np.ndarray) -> tuple[np.ndarray, float]:
    y = np.asarray(y, float)
    mu = float(y.mean())
    return y - mu, mu


def fit_gblup_reml(X_train: np.ndarray, y_train: np.ndarray, **_hp: Any) -> dict:
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    K, denom, dmean = grm_vanraden(X, freqs, return_scale=True)
    y, y_mu = _center_y(y_train)
    C = np.ones((len(y), 1))
    delta, sg, se, U, S, ll = reml_delta(y, K, C)
    d = np.maximum(S + delta, 1e-12)
    alpha = U @ ((U.T @ y) / d)
    return {
        "name": "gblup_reml",
        "X_train": X,
        "freqs": freqs,
        "alpha": alpha,
        "y_mu": y_mu,
        "delta": delta,
        "sigma_g2": sg,
        "sigma_e2": se,
        "ll": ll,
        "denom": denom,
        "diag_scale": dmean,
    }


def predict_gblup_reml(model: dict, X_test: np.ndarray) -> np.ndarray:
    freqs = model["freqs"]
    Xs = impute_mean(X_test, freqs)
    Zt = model["X_train"] - 2.0 * freqs
    Zs = Xs - 2.0 * freqs
    Kst = (Zs @ Zt.T) / model["denom"] / max(float(model.get("diag_scale", 1.0)), 1e-12)
    return Kst @ model["alpha"] + model["y_mu"]


def fit_rrblup_dual(X_train: np.ndarray, y_train: np.ndarray, **_hp: Any) -> dict:
    """GBLUP dual: β = Zᵀ (ZZᵀ + λI)⁻¹ (y−μ), λ = δ · 2Σp(1−p)."""
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    y, y_mu = _center_y(y_train)
    Z = X - 2.0 * freqs
    denom = 2.0 * float(np.sum(freqs * (1.0 - freqs)))
    denom = max(denom, 1e-12)
    K, _d, _s = grm_vanraden(X, freqs, return_scale=True)
    C = np.ones((len(y), 1))
    delta, sg, se, U, S, ll = reml_delta(y, K, C)
    lam = delta * denom
    G = Z @ Z.T
    n = G.shape[0]
    try:
        alpha = np.linalg.solve(G + lam * np.eye(n), y)
    except np.linalg.LinAlgError:
        alpha = np.linalg.lstsq(G + lam * np.eye(n), y, rcond=None)[0]
    beta = Z.T @ alpha
    return {
        "name": "rrblup_dual",
        "beta": beta,
        "freqs": freqs,
        "y_mu": y_mu,
        "delta": delta,
        "lambda": lam,
        "sigma_g2": sg,
        "sigma_e2": se,
        "ll": ll,
        "X_train": X,
        "denom": denom,
        "alpha": alpha,
    }


def predict_rrblup_dual(model: dict, X_test: np.ndarray) -> np.ndarray:
    freqs = model["freqs"]
    Xs = impute_mean(X_test, freqs)
    Zs = Xs - 2.0 * freqs
    return Zs @ model["beta"] + model["y_mu"]


def _sqdist(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    aa = np.sum(A * A, axis=1, keepdims=True)
    bb = np.sum(B * B, axis=1, keepdims=True)
    d = aa + bb.T - 2.0 * (A @ B.T)
    return np.maximum(d, 0.0)


def fit_rkhs_gauss(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    hs: tuple[float, ...] = (0.2, 1.0, 5.0),
    **_hp: Any,
) -> dict:
    """Gaussian RKHS with kernel averaging (de los Campos 2010)."""
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    y, y_mu = _center_y(y_train)
    D2 = _sqdist(X, X)
    tri = D2[np.triu_indices_from(D2, 1)]
    med = float(np.median(tri)) if tri.size else 1.0
    med = max(med, 1e-8)
    C = np.ones((len(y), 1))
    kernels: list[dict] = []
    lls: list[float] = []
    for h in hs:
        K = np.exp(-D2 / (h * med))
        delta, sg, se, U, S, ll = reml_delta(y, K, C)
        d = np.maximum(S + delta, 1e-12)
        alpha = U @ ((U.T @ y) / d)
        kernels.append({"h": h, "delta": delta, "alpha": alpha, "ll": ll, "sigma_g2": sg})
        lls.append(ll)
    w = np.array(lls, float)
    w = w - np.max(w)
    w = np.exp(w)
    w = w / w.sum()
    return {
        "name": "rkhs_gauss",
        "X_train": X,
        "freqs": freqs,
        "y_mu": y_mu,
        "med": med,
        "kernels": kernels,
        "weights": w,
        "delta": kernels[int(np.argmax(w))]["delta"],
    }


def predict_rkhs_gauss(model: dict, X_test: np.ndarray) -> np.ndarray:
    freqs = model["freqs"]
    Xs = impute_mean(X_test, freqs)
    D2 = _sqdist(Xs, model["X_train"])
    pred = np.zeros(Xs.shape[0])
    for w, ker in zip(model["weights"], model["kernels"]):
        Kst = np.exp(-D2 / (ker["h"] * model["med"]))
        pred += float(w) * (Kst @ ker["alpha"])
    return pred + model["y_mu"]


def _soft(x: np.ndarray, t: float) -> np.ndarray:
    return np.sign(x) * np.maximum(np.abs(x) - t, 0.0)


def _en_fista(
    Z: np.ndarray,
    y: np.ndarray,
    *,
    alpha: float,
    lam: float,
    L0: float,
    max_iter: int = 80,
    beta0: np.ndarray | None = None,
) -> np.ndarray:
    L = L0 + lam * (1.0 - alpha)
    step = 1.0 / max(L, 1e-12)
    beta = np.zeros(Z.shape[1]) if beta0 is None else beta0.copy()
    z = beta.copy()
    t = 1.0
    for _ in range(max_iter):
        resid = Z @ z - y
        grad = Z.T @ resid + lam * (1.0 - alpha) * z
        beta_new = _soft(z - step * grad, step * lam * alpha)
        t_new = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * t * t))
        z = beta_new + ((t - 1.0) / t_new) * (beta_new - beta)
        if np.max(np.abs(beta_new - beta)) < 1e-5:
            beta = beta_new
            break
        beta = beta_new
        t = t_new
    return beta


def fit_elastic_net_fista(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    alphas: tuple[float, ...] = (0.5, 0.9),
    n_lambda: int = 8,
    inner_folds: int = 2,
    seed: int = 0,
    **_hp: Any,
) -> dict:
    """Elastic net via FISTA (Beck & Teboulle 2009; Zou & Hastie 2005)."""
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    y, y_mu = _center_y(y_train)
    mu_x = X.mean(axis=0)
    sd_x = X.std(axis=0)
    sd_x[sd_x < 1e-8] = 1.0
    Z = (X - mu_x) / sd_x
    n, p = Z.shape
    if n <= p:
        L0 = float(np.linalg.eigvalsh(Z @ Z.T)[-1])
    else:
        # power iteration on ZᵀZ without forming p×p
        rng = np.random.default_rng(seed)
        v = rng.normal(size=n)
        v /= np.linalg.norm(v)
        G = Z @ Z.T
        for _ in range(20):
            v = G @ v
            v /= max(np.linalg.norm(v), 1e-12)
        L0 = float(v @ (G @ v))

    zy = Z.T @ y
    a0 = max(min(alphas), 0.05)
    lam_max = float(np.max(np.abs(zy))) / max(n * a0, 1e-8)
    lams = np.logspace(np.log10(max(lam_max, 1e-8)), np.log10(max(lam_max * 1e-4, 1e-12)), n_lambda)

    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, max(inner_folds, 2))
    best = (np.inf, alphas[0], lams[0], np.zeros(p))
    for a in alphas:
        beta_warm = np.zeros(p)
        for lam in lams:
            mses = []
            for fi, te in enumerate(folds):
                tr = np.concatenate([folds[j] for j in range(len(folds)) if j != fi])
                b = _en_fista(Z[tr], y[tr], alpha=a, lam=lam, L0=L0, beta0=beta_warm)
                pred = Z[te] @ b
                mses.append(float(np.mean((pred - y[te]) ** 2)))
            mse = float(np.mean(mses))
            beta_warm = _en_fista(Z, y, alpha=a, lam=lam, L0=L0, beta0=beta_warm)
            if mse < best[0]:
                best = (mse, a, float(lam), beta_warm.copy())
    mse, a, lam, beta_std = best
    # back to dosage scale: Z = (X-mu)/sd → β_x = β_z / sd
    beta = beta_std / sd_x
    intercept = y_mu - float(mu_x @ beta)
    return {
        "name": "elastic_net_fista",
        "beta": beta,
        "freqs": freqs,
        "y_mu": intercept,
        "alpha_en": a,
        "lambda": lam,
        "delta": lam,
        "cv_mse": mse,
        "n_nz": int(np.sum(np.abs(beta) > 1e-3)),
        "mu_x": mu_x,
    }


def predict_elastic_net_fista(model: dict, X_test: np.ndarray) -> np.ndarray:
    Xs = impute_mean(X_test, model["freqs"])
    return Xs @ model["beta"] + model["y_mu"]


def fit_bayesc_pi(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    n_iter: int = 2000,
    burn: int = 500,
    seed: int = 0,
    pi0: float = 0.95,
    **_hp: Any,
) -> dict:
    """BayesCπ Gibbs (Habier et al. 2011). Marker loop is the allowed exception."""
    rng = np.random.default_rng(seed)
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    y, y_mu = _center_y(y_train)
    Z = X - 2.0 * freqs
    n, p = Z.shape
    xtx = np.sum(Z * Z, axis=0)
    beta = np.zeros(p)
    include = np.zeros(p, dtype=bool)
    r = y.copy()
    ve = float(np.var(y) + 1e-8)
    vb = ve / max((1.0 - pi0) * p, 1.0)
    pi = pi0
    beta_acc = np.zeros(p)
    pip_acc = np.zeros(p)
    n_keep = 0
    a_pi, b_pi = 1.0, 1.0
    for it in range(n_iter):
        n_in = 0
        for j in range(p):
            if include[j]:
                r += Z[:, j] * beta[j]
            rhs = float(Z[:, j] @ r)
            x2 = float(xtx[j])
            if x2 < 1e-12:
                include[j] = False
                beta[j] = 0.0
                continue
            inv_var = x2 / ve + 1.0 / vb
            mu = (rhs / ve) / inv_var
            log_bf = 0.5 * np.log(1.0 / vb) - 0.5 * np.log(inv_var) + 0.5 * mu * mu * inv_var
            odds = (pi / max(1.0 - pi, 1e-12)) * np.exp(-log_bf)
            p_in = 1.0 / (1.0 + odds)
            if rng.random() < p_in:
                include[j] = True
                beta[j] = float(mu + rng.normal() * np.sqrt(1.0 / inv_var))
                r -= Z[:, j] * beta[j]
                n_in += 1
            else:
                include[j] = False
                beta[j] = 0.0
        sse = float(r @ r)
        ve = (sse + 4.0 * float(np.var(y))) / (n + 4.0)
        ve = max(ve, 1e-12)
        if n_in > 0:
            vb = (float(beta[include] @ beta[include]) + 4.0 * float(np.var(y)) / p) / (n_in + 4.0)
            vb = max(vb, 1e-12)
        pi = float(rng.beta(a_pi + (p - n_in), b_pi + n_in))
        pi = min(max(pi, 1e-4), 1.0 - 1e-4)
        if it >= burn:
            beta_acc += beta
            pip_acc += include.astype(float)
            n_keep += 1
    n_keep = max(n_keep, 1)
    beta_mean = beta_acc / n_keep
    pip = pip_acc / n_keep
    return {
        "name": "bayesc_pi",
        "beta": beta_mean,
        "pip": pip,
        "freqs": freqs,
        "y_mu": y_mu,
        "delta": ve / max(vb, 1e-12),
        "pi": pi,
        "n_iter": n_iter,
        "burn": burn,
    }


def predict_bayesc_pi(model: dict, X_test: np.ndarray) -> np.ndarray:
    Xs = impute_mean(X_test, model["freqs"])
    Zs = Xs - 2.0 * model["freqs"]
    return Zs @ model["beta"] + model["y_mu"]


def _ols_pvals(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    y = y - y.mean()
    Xc = X - X.mean(axis=0)
    xtx = np.sum(Xc * Xc, axis=0)
    xty = Xc.T @ y
    good = xtx > 1e-12
    b = np.zeros_like(xtx)
    b[good] = xty[good] / xtx[good]
    n = len(y)
    rss = np.maximum(float(y @ y) - b * b * xtx, 1e-18)
    se = np.sqrt((rss / max(n - 2, 1)) / np.maximum(xtx, 1e-12))
    t = np.zeros_like(b)
    t[good] = b[good] / se[good]
    from scipy.stats import t as tdist

    p = np.ones_like(t)
    p[good] = 2.0 * tdist.sf(np.abs(t[good]), max(n - 2, 1))
    return p


def fit_topk_ridge(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    ks: tuple[int, ...] = (100, 250, 500),
    seed: int = 0,
    **_hp: Any,
) -> dict:
    X = impute_mean(X_train)
    freqs = allele_freq(X)
    y, y_mu = _center_y(y_train)
    pvals = _ols_pvals(X, y)
    order = np.argsort(pvals)
    rng = np.random.default_rng(seed)
    n = len(y)
    n_val = max(1, n // 5)
    perm = rng.permutation(n)
    va, tr = perm[:n_val], perm[n_val:]
    best = (np.inf, ks[0], np.array([], dtype=int), np.zeros(0), 1.0)
    Zfull = X - 2.0 * freqs
    for k in ks:
        k_use = min(k, X.shape[1])
        idx = order[:k_use]
        Ztr = Zfull[tr][:, idx]
        G = Ztr @ Ztr.T
        lam = 1e-2 * np.trace(G) / max(len(tr), 1)
        try:
            alpha = np.linalg.solve(G + lam * np.eye(len(tr)), y[tr])
        except np.linalg.LinAlgError:
            continue
        beta_k = Ztr.T @ alpha
        pred = Zfull[va][:, idx] @ beta_k
        mse = float(np.mean((pred - y[va]) ** 2))
        if mse < best[0]:
            best = (mse, k_use, idx, beta_k, lam)
    _, k_use, idx, _, lam = best
    Z = Zfull[:, idx]
    G = Z @ Z.T
    alpha = np.linalg.solve(G + lam * np.eye(n), y)
    beta_k = Z.T @ alpha
    beta = np.zeros(X.shape[1])
    beta[idx] = beta_k
    return {
        "name": "topk_ridge",
        "beta": beta,
        "idx": idx,
        "k": k_use,
        "freqs": freqs,
        "y_mu": y_mu,
        "delta": lam,
    }


def predict_topk_ridge(model: dict, X_test: np.ndarray) -> np.ndarray:
    Xs = impute_mean(X_test, model["freqs"])
    Zs = Xs - 2.0 * model["freqs"]
    return Zs @ model["beta"] + model["y_mu"]


def fit_mlp_gs(X_train: np.ndarray, y_train: np.ndarray, **hp: Any) -> dict:
    from grapeancestry.breeding.gs import train_mlp

    X = impute_mean(X_train)
    freqs = allele_freq(X)
    _, info = train_mlp(
        X,
        y_train,
        X[:1],
        seed=int(hp.get("seed", 0)),
        epochs=int(hp.get("epochs", 80)),
    )
    return {
        "name": "mlp",
        "freqs": freqs,
        "y_mu": float(info["y_mu"]),
        "delta": 0.0,
        "W1": info["W1"],
        "b1": info["b1"],
        "W2": info["W2"],
        "b2": info["b2"],
        "seed": int(hp.get("seed", 0)),
    }


def predict_mlp_gs(model: dict, X_test: np.ndarray) -> np.ndarray:
    from grapeancestry.breeding.gs import _center_impute

    Xs = _center_impute(impute_mean(X_test, model["freqs"]))
    z = np.tanh(Xs @ model["W1"] + model["b1"])
    return z @ model["W2"] + model["b2"] + model["y_mu"]


def fit_cnn_gs(X_train: np.ndarray, y_train: np.ndarray, **hp: Any) -> dict:
    from grapeancestry.breeding.dl import train_cnn_gs

    X = impute_mean(X_train)
    freqs = allele_freq(X)
    pred, info = train_cnn_gs(
        X, y_train, X[:1], seed=int(hp.get("seed", 0)), epochs=int(hp.get("epochs", 40))
    )
    return {
        "name": "cnn",
        "X_train": X,
        "y_train": np.asarray(y_train, float),
        "freqs": freqs,
        "y_mu": float(np.mean(y_train)),
        "delta": 0.0,
        "info": info,
        "seed": int(hp.get("seed", 0)),
        "epochs": int(hp.get("epochs", 40)),
    }


def predict_cnn_gs(model: dict, X_test: np.ndarray) -> np.ndarray:
    from grapeancestry.breeding.dl import train_cnn_gs

    Xs = impute_mean(X_test, model["freqs"])
    pred, _ = train_cnn_gs(
        model["X_train"], model["y_train"], Xs, seed=model["seed"], epochs=model["epochs"]
    )
    return pred


FITTERS = {
    "gblup_reml": fit_gblup_reml,
    "rrblup_dual": fit_rrblup_dual,
    "rkhs_gauss": fit_rkhs_gauss,
    "elastic_net_fista": fit_elastic_net_fista,
    "bayesc_pi": fit_bayesc_pi,
    "topk_ridge": fit_topk_ridge,
    "mlp": fit_mlp_gs,
    "cnn": fit_cnn_gs,
}

PREDICTORS = {
    "gblup_reml": predict_gblup_reml,
    "rrblup_dual": predict_rrblup_dual,
    "rkhs_gauss": predict_rkhs_gauss,
    "elastic_net_fista": predict_elastic_net_fista,
    "bayesc_pi": predict_bayesc_pi,
    "topk_ridge": predict_topk_ridge,
    "mlp": predict_mlp_gs,
    "cnn": predict_cnn_gs,
}


def fit(name: str, X: np.ndarray, y: np.ndarray, **hp: Any) -> dict:
    return FITTERS[name](X, y, **hp)


def predict(model: dict, X: np.ndarray) -> np.ndarray:
    return PREDICTORS[model["name"]](model, X)
