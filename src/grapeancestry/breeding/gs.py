"""Minimal genomic selection: rrBLUP / GBLUP / trainable MLP."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _center_impute(X: np.ndarray) -> np.ndarray:
    X = X.astype(float).copy()
    for j in range(X.shape[1]):
        col = X[:, j]
        ok = col >= 0
        mu = col[ok].mean() if ok.any() else 0.0
        col[~ok] = mu
        X[:, j] = col - mu
    return X


def gblup_predict(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray, lam: float = 1e-2) -> np.ndarray:
    """GBLUP via ridge on genomic relationship (VanRaden-ish)."""
    Xt = _center_impute(X_train)
    Xs = _center_impute(X_test)
    n, p = Xt.shape
    G = (Xt @ Xt.T) / max(p, 1)
    G += lam * np.eye(n)
    alpha = np.linalg.solve(G, y_train - y_train.mean())
    K = (Xs @ Xt.T) / max(p, 1)
    return K @ alpha + y_train.mean()


def rrblup_predict(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray, lam: float = 1e-2) -> np.ndarray:
    Xt = _center_impute(X_train)
    Xs = _center_impute(X_test)
    p = Xt.shape[1]
    A = Xt.T @ Xt + lam * np.eye(p)
    b = Xt.T @ (y_train - y_train.mean())
    beta = np.linalg.solve(A, b)
    return Xs @ beta + y_train.mean()


def mlp_predict(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray, seed: int = 0) -> np.ndarray:
    """Backward-compatible one-shot MLP predict (no weight save)."""
    pred, _ = train_mlp(X_train, y_train, X_test, seed=seed)
    return pred


def train_mlp(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    *,
    seed: int = 0,
    epochs: int = 400,
    lr: float = 0.01,
    patience: int = 40,
    weight_path: Path | None = None,
) -> tuple[np.ndarray, dict]:
    """Train MLP with val split + early stopping; optionally save weights (.npz)."""
    rng = np.random.default_rng(seed)
    Xt = _center_impute(X_train)
    Xs = _center_impute(X_test)
    y = y_train.astype(float)
    y_mu = float(y.mean())
    y = y - y_mu
    n, p = Xt.shape
    # train/val split
    idx = rng.permutation(n)
    n_val = max(1, n // 5)
    va, tr = idx[:n_val], idx[n_val:]
    h = min(32, max(4, p // 2))
    W1 = rng.normal(0, 0.1, size=(p, h))
    b1 = np.zeros(h)
    W2 = rng.normal(0, 0.1, size=(h,))
    b2 = 0.0
    best = (np.inf, W1.copy(), b1.copy(), W2.copy(), b2)
    wait = 0
    for _ in range(epochs):
        z = np.tanh(Xt[tr] @ W1 + b1)
        pred = z @ W2 + b2
        err = pred - y[tr]
        dW2 = z.T @ err / max(len(tr), 1)
        db2 = err.mean()
        dz = np.outer(err, W2) * (1 - z**2)
        dW1 = Xt[tr].T @ dz / max(len(tr), 1)
        db1 = dz.mean(axis=0)
        W2 -= lr * dW2
        b2 -= lr * db2
        W1 -= lr * dW1
        b1 -= lr * db1
        # val
        zv = np.tanh(Xt[va] @ W1 + b1)
        pv = zv @ W2 + b2
        vloss = float(np.mean((pv - y[va]) ** 2))
        if vloss < best[0] - 1e-8:
            best = (vloss, W1.copy(), b1.copy(), W2.copy(), b2)
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break
    _, W1, b1, W2, b2 = best
    if weight_path is not None:
        weight_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(weight_path, W1=W1, b1=b1, W2=W2, b2=np.array([b2]), y_mu=np.array([y_mu]))
    z = np.tanh(Xs @ W1 + b1)
    return z @ W2 + b2 + y_mu, {
        "val_mse": best[0],
        "hidden": h,
        "W1": W1,
        "b1": b1,
        "W2": W2,
        "b2": float(b2),
        "y_mu": y_mu,
    }


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    if y_true.std() < 1e-12 or y_pred.std() < 1e-12:
        r = 0.0
    else:
        r = float(np.corrcoef(y_true, y_pred)[0, 1])
    return {"r": r, "rmse": rmse}


def evaluate_models(
    X: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 0,
    weight_dir: Path | None = None,
) -> dict[str, float]:
    """80/20 holdout: rrBLUP, GBLUP, MLP (+ optional CNN from dl.py)."""
    rng = np.random.default_rng(seed)
    n = len(y)
    idx = rng.permutation(n)
    tr, te = idx[: int(0.8 * n)], idx[int(0.8 * n) :]
    if len(te) < 2 or len(tr) < 5:
        return {}
    out: dict[str, float] = {}
    for name, fn in (
        ("rrblup", rrblup_predict),
        ("gblup", gblup_predict),
    ):
        pred = fn(X[tr], y[tr], X[te])
        m = metrics(y[te], pred)
        out[f"{name}_r"] = m["r"]
        out[f"{name}_rmse"] = m["rmse"]
    wp = (weight_dir / "mlp.npz") if weight_dir else None
    pred_mlp, _ = train_mlp(X[tr], y[tr], X[te], seed=seed, weight_path=wp)
    m = metrics(y[te], pred_mlp)
    out["mlp_r"] = m["r"]
    out["mlp_rmse"] = m["rmse"]
    try:
        from grapeancestry.breeding.dl import train_cnn_gs

        pred_cnn, _ = train_cnn_gs(
            X[tr],
            y[tr],
            X[te],
            seed=seed,
            weight_path=(weight_dir / "cnn_gs.pt") if weight_dir else None,
        )
        m = metrics(y[te], pred_cnn)
        out["cnn_r"] = m["r"]
        out["cnn_rmse"] = m["rmse"]
    except Exception:
        out["cnn_r"] = float("nan")
        out["cnn_rmse"] = float("nan")
    return out


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Mann–Whitney AUC (numpy)."""
    y_true = np.asarray(y_true, float)
    y_score = np.asarray(y_score, float)
    n1 = np.sum(y_true == 1)
    n0 = np.sum(y_true == 0)
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    # average ranks for ties
    # simple: no-tie formula is enough for tests; add average ties
    uniq, inv, cnt = np.unique(y_score, return_inverse=True, return_counts=True)
    if np.any(cnt > 1):
        start = 0
        avg = np.zeros_like(uniq, dtype=float)
        for i, c in enumerate(cnt):
            # ranks of this value
            r = np.arange(start + 1, start + c + 1)
            avg[i] = r.mean()
            start += c
        ranks = avg[inv]
    return float((ranks[y_true == 1].sum() - n1 * (n1 + 1) / 2.0) / (n0 * n1))


def pearson_r(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


DEFAULT_CV_MODELS = (
    "gblup_reml",
    "rrblup_dual",
    "rkhs_gauss",
    "elastic_net_fista",
    "topk_ridge",
    "mlp",
)

# Marker-effect models: GSModel.beta drives predict_sample / crossing.
# Kernel / MLP best-in-CV still listed in index.tsv; npz stays shippable.
SHIPPABLE_MODELS = frozenset(
    {"rrblup_dual", "topk_ridge", "elastic_net_fista", "bayesc_pi"}
)


def choose_ship_model(cv_rows: list[dict]) -> dict:
    """Best CV row among models that write a usable marker-effect ``beta``."""
    ranked = sorted(
        cv_rows,
        key=lambda r: r["r_mean"] if r["r_mean"] == r["r_mean"] else -1.0,
        reverse=True,
    )
    if not ranked:
        raise ValueError("no CV rows")
    for row in ranked:
        if row["model"] in SHIPPABLE_MODELS:
            return row
    return ranked[0]


def read_cv_tsv(path: Path) -> list[dict]:
    import csv

    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            rec = dict(row)
            for k in ("r_mean", "r_sd", "rmse_mean", "auc_mean", "fit_s", "p_vs_gblup"):
                if k in rec:
                    try:
                        rec[k] = float(rec[k])
                    except (TypeError, ValueError):
                        rec[k] = float("nan")
            rec["n_folds"] = int(float(rec["n_folds"])) if rec.get("n_folds") else 0
            rows.append(rec)
    return rows


def cv_evaluate(
    X: np.ndarray,
    y: np.ndarray,
    *,
    scale: str = "ordinal",
    k: int = 5,
    repeats: int = 3,
    seed: int = 0,
    models: tuple[str, ...] | None = None,
    binary: bool = False,
) -> list[dict]:
    """Shared k-fold × repeats CV across models."""
    from grapeancestry.breeding import gs_models

    names = models or DEFAULT_CV_MODELS
    rng = np.random.default_rng(seed)
    n = len(y)
    k = min(k, n)
    fold_sets: list[tuple[np.ndarray, np.ndarray]] = []
    for r in range(repeats):
        idx = rng.permutation(n)
        folds = np.array_split(idx, k)
        for fi in range(k):
            te = folds[fi]
            tr = np.concatenate([folds[j] for j in range(k) if j != fi])
            if len(te) < 2 or len(tr) < 5:
                continue
            fold_sets.append((tr, te))

    rows: list[dict] = []
    per_model_r: dict[str, list[float]] = {m: [] for m in names}
    for name in names:
        rs, rmses, aucs = [], [], []
        t0 = __import__("time").time()
        for tr, te in fold_sets:
            try:
                mdl = gs_models.fit(name, X[tr], y[tr], seed=seed)
                pred = gs_models.predict(mdl, X[te])
            except Exception:
                continue
            rs.append(pearson_r(y[te], pred))
            rmses.append(float(np.sqrt(np.mean((y[te] - pred) ** 2))))
            if binary:
                aucs.append(roc_auc((y[te] >= 0.5).astype(float), pred))
        fit_s = (__import__("time").time() - t0) / max(len(fold_sets), 1)
        per_model_r[name] = rs
        rows.append(
            {
                "model": name,
                "r_mean": float(np.mean(rs)) if rs else float("nan"),
                "r_sd": float(np.std(rs, ddof=1)) if len(rs) > 1 else 0.0,
                "rmse_mean": float(np.mean(rmses)) if rmses else float("nan"),
                "auc_mean": float(np.nanmean(aucs)) if aucs else float("nan"),
                "fit_s": fit_s,
                "n_folds": len(rs),
            }
        )
    # paired t vs gblup
    g_r = per_model_r.get("gblup_reml") or []
    if g_r:
        from scipy.stats import ttest_rel

        for row in rows:
            other = per_model_r.get(row["model"]) or []
            if row["model"] == "gblup_reml" or len(other) != len(g_r) or len(g_r) < 2:
                row["p_vs_gblup"] = float("nan")
                continue
            try:
                row["p_vs_gblup"] = float(ttest_rel(other, g_r).pvalue)
            except Exception:
                row["p_vs_gblup"] = float("nan")
    return rows


@dataclass
class GSModel:
    name: str
    beta: np.ndarray | None
    sites: list[str]
    freqs: np.ndarray
    y_mu: float
    delta: float
    cv_r: float
    trait: str
    source: str
    scale: str
    n_train: int
    payload: dict


def fit_final(
    X: np.ndarray,
    y: np.ndarray,
    sites: list[str],
    *,
    model: str = "rrblup_dual",
    trait: str = "",
    source: str = "",
    scale: str = "ordinal",
    cv_r: float = float("nan"),
) -> GSModel:
    from grapeancestry.breeding import gs_models
    from grapeancestry.breeding.mixed_model import allele_freq, impute_mean

    mdl = gs_models.fit(model, X, y)
    Xi = impute_mean(X)
    freqs = np.asarray(mdl.get("freqs", allele_freq(Xi)), float)
    beta = mdl.get("beta")
    if beta is not None:
        beta = np.asarray(beta, float)
    return GSModel(
        name=model,
        beta=beta,
        sites=list(sites),
        freqs=freqs,
        y_mu=float(mdl.get("y_mu", float(np.mean(y)))),
        delta=float(mdl.get("delta", 0.0)),
        cv_r=float(cv_r),
        trait=trait,
        source=source,
        scale=scale,
        n_train=len(y),
        payload={k: v for k, v in mdl.items() if k not in {"X_train", "y_train", "beta", "kernels"}},
    )


def save_model(model: GSModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        name=model.name,
        beta=model.beta if model.beta is not None else np.array([]),
        sites=np.array(model.sites, dtype=object),
        freqs=model.freqs,
        y_mu=np.array([model.y_mu]),
        delta=np.array([model.delta]),
        cv_r=np.array([model.cv_r]),
        trait=model.trait,
        source=model.source,
        scale=model.scale,
        n_train=np.array([model.n_train]),
        payload_json=json.dumps({k: v for k, v in model.payload.items() if _jsonable(v)}),
    )


def _jsonable(v: object) -> bool:
    return isinstance(v, (int, float, str, bool, type(None), list, dict))


def load_model(path: Path) -> GSModel:
    z = np.load(path, allow_pickle=True)
    beta = z["beta"]
    if beta.size == 0:
        beta_arr = None
    else:
        beta_arr = np.asarray(beta, float)
    payload = {}
    if "payload_json" in z:
        raw = z["payload_json"]
        payload = json.loads(str(raw))
    return GSModel(
        name=str(z["name"]),
        beta=beta_arr,
        sites=list(z["sites"]),
        freqs=np.asarray(z["freqs"], float),
        y_mu=float(z["y_mu"][0]),
        delta=float(z["delta"][0]),
        cv_r=float(z["cv_r"][0]),
        trait=str(z["trait"]),
        source=str(z["source"]),
        scale=str(z["scale"]),
        n_train=int(z["n_train"][0]),
        payload=payload,
    )


def predict_sample(model: GSModel, dosage: np.ndarray) -> tuple[float, float]:
    """GEBV for one sample; missing (−1) filled with 2p. Returns (gebv, coverage)."""
    x = np.asarray(dosage, float)
    if x.size != len(model.sites) and model.beta is not None and x.size == model.beta.size:
        pass
    n = min(x.size, model.freqs.size)
    x = x[:n]
    freqs = model.freqs[:n]
    called = x >= 0
    coverage = float(called.mean()) if n else 0.0
    x = x.copy()
    x[~called] = 2.0 * freqs[~called]
    if model.beta is not None and model.beta.size >= n:
        z = x - 2.0 * freqs
        gebv = float(z @ model.beta[:n] + model.y_mu)
    else:
        gebv = float(model.y_mu)
    return gebv, coverage


def run_gs_train(
    cache_path: Path,
    pheno_path: Path,
    trait: str,
    source: str,
    out_dir: Path,
    *,
    binary: bool = False,
    min_n: int = 50,
    with_bayes: bool = False,
    maf: float = 0.05,
    max_missing: float = 0.2,
    max_sites: int | None = None,
    models: tuple[str, ...] | None = None,
    k_folds: int = 5,
    repeats: int = 3,
    seed: int = 0,
    skip_cv: bool = False,
) -> dict:
    from grapeancestry.breeding.mixed_model import impute_mean, site_filter
    from grapeancestry.breeding.phenotype import apply_binary_rule, load_phenotype_table, trait_slug
    from grapeancestry.core.dosage import load_cache

    mat, ref_ids, sites = load_cache(cache_path)
    phenomap = load_phenotype_table(pheno_path, trait=trait, source=source)
    if binary:
        phenomap = {
            k: v
            for k, v in ((i, apply_binary_rule(v, trait)) for i, v in phenomap.items())
            if v is not None
        }
    y_full = np.array([phenomap.get(i, np.nan) for i in ref_ids], float)
    mask = np.isfinite(y_full)
    n = int(mask.sum())
    if n < min_n:
        return {"ok": False, "n": n}
    X = mat[mask].astype(float)
    y = y_full[mask]
    keep = site_filter(X, maf_min=maf, max_missing=max_missing)
    if max_sites is not None:
        idx = np.where(keep)[0][:max_sites]
        keep = np.zeros_like(keep)
        keep[idx] = True
    sites_k = [s for s, k in zip(sites, keep) if k]
    Xk = impute_mean(X[:, keep])
    names = list(models or DEFAULT_CV_MODELS)
    if with_bayes and "bayesc_pi" not in names:
        names.append("bayesc_pi")
    slug = trait_slug(trait, binary=binary)
    dest = out_dir / source / slug
    dest.mkdir(parents=True, exist_ok=True)
    if skip_cv:
        cv_path = dest / "cv.tsv"
        if not cv_path.exists():
            return {"ok": False, "n": n, "reason": "no cv.tsv"}
        cv_rows = read_cv_tsv(cv_path)
    else:
        cv_rows = cv_evaluate(
            Xk, y, k=k_folds, repeats=repeats, seed=seed, models=tuple(names), binary=binary
        )
    best = max(cv_rows, key=lambda r: r["r_mean"] if r["r_mean"] == r["r_mean"] else -1)
    ship = choose_ship_model(cv_rows)
    gsm = fit_final(
        Xk,
        y,
        sites_k,
        model=str(ship["model"]),
        trait=trait,
        source=source,
        scale="binary" if binary else "ordinal",
        cv_r=float(ship["r_mean"]),
    )
    save_model(gsm, dest / "model.npz")
    cv_path = dest / "cv.tsv"
    if not skip_cv:
        with cv_path.open("w", encoding="utf-8") as fh:
            fh.write("model\tr_mean\tr_sd\trmse_mean\tauc_mean\tfit_s\tn_folds\tp_vs_gblup\n")
            for r in cv_rows:
                fh.write(
                    f"{r['model']}\t{r['r_mean']}\t{r['r_sd']}\t{r['rmse_mean']}\t"
                    f"{r.get('auc_mean', float('nan'))}\t{r['fit_s']}\t{r['n_folds']}\t"
                    f"{r.get('p_vs_gblup', float('nan'))}\n"
                )
    return {
        "ok": True,
        "trait": trait,
        "source": source,
        "slug": slug,
        "n": n,
        "m": int(keep.sum()),
        "best_model": best["model"],
        "ship_model": ship["model"],
        "cv_r": best["r_mean"],
        "cv_r_ship": ship["r_mean"],
        "cv_r_sd": best["r_sd"],
        "cv_rows": cv_rows,
        "out_dir": str(dest),
        "binary": binary,
        "k_folds": k_folds,
        "repeats": repeats,
    }


def refit_shipped_from_index(
    cache_path: Path,
    pheno_path: Path,
    gs_root: Path,
    *,
    max_sites: int | None = 3000,
) -> list[dict]:
    """Rewrite model.npz from existing cv.tsv (no new CV)."""
    import csv

    idx = gs_root / "index.tsv"
    if not idx.exists():
        return []
    out: list[dict] = []
    with idx.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sm = run_gs_train(
                cache_path,
                pheno_path,
                row["trait"],
                row["source"],
                gs_root,
                binary=row.get("scale") == "binary",
                max_sites=max_sites,
                skip_cv=True,
            )
            out.append(sm)
    return out


def run_gs_predict(
    sample: str,
    cache_path: Path,
    gs_root: Path,
    out_tsv: Path,
    *,
    min_cv_r: float = 0.3,
    query_vcf: Path | None = None,
) -> Path:
    from grapeancestry.core.dosage import load_cache, load_sample_dosage

    mat, ref_ids, sites = load_cache(cache_path)
    if sample in ref_ids:
        q = mat[ref_ids.index(sample)]
    elif query_vcf and query_vcf.exists():
        q = load_sample_dosage(query_vcf, sample, sites)
    else:
        raise FileNotFoundError(f"sample {sample} not in panel and no --vcf")
    site_index = {s: i for i, s in enumerate(sites)}
    rows = []
    for npz in sorted(gs_root.glob("*/*/model.npz")):
        mdl = load_model(npz)
        if mdl.cv_r != mdl.cv_r or mdl.cv_r < min_cv_r:
            flag = "low_cv_r"
        else:
            flag = "ok"
        idx = [site_index[s] for s in mdl.sites if s in site_index]
        if len(idx) != len(mdl.sites):
            # align by intersection
            q_al = np.full(len(mdl.sites), -1.0)
            for j, s in enumerate(mdl.sites):
                i = site_index.get(s)
                if i is not None:
                    q_al[j] = q[i]
        else:
            q_al = q[idx]
        gebv, cov = predict_sample(mdl, q_al)
        if cov < 0.5:
            flag = "low_coverage"
        rows.append((mdl.trait, mdl.source, gebv, mdl.cv_r, cov, flag, mdl.scale, npz.parent.name))
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", encoding="utf-8") as fh:
        fh.write("trait\tsource\tpred\tcv_r\tcoverage\tflag\tscale\tslug\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")
    return out_tsv


