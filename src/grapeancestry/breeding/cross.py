"""Cross recommendation: usefulness criterion + kinship/sex filters.

UC = μ_progeny + i·σ_progeny (Zhong & Jannink 2007; Lehermeier 2017).
Progeny variance is an independent-loci approximation (no genetic map).
KING-like thresholds from Manichaikul 2010 (0.0884 second degree; 0.354 duplicate).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from grapeancestry.identity.ibs import ibs_counts, king_robust
from grapeancestry.identity.parentage import kinship_king

# Truncation intensity i = φ(x)/p, x = Φ^{-1}(1-p), p = 0.10 → ≈1.755
# (standard normal; same i used in Zhong & Jannink 2007 doi:10.1534/genetics.107.075358).
I_INTENSITY_10PCT = 1.755

# Manichaikul et al. 2010 Bioinformatics doi:10.1093/bioinformatics/btq559
KING_SECOND = 0.0884
KING_DUP = 0.354


def progeny_mean(gebv_i: float, gebv_j: float) -> float:
    return 0.5 * (float(gebv_i) + float(gebv_j))


def progeny_var_indep(beta: np.ndarray, g_i: np.ndarray, g_j: np.ndarray) -> float:
    """Σ β_k² · 0.25 · (het_i + het_j); het = dosage==1. Ignores LD."""
    beta = np.asarray(beta, float)
    gi = np.asarray(g_i, float)
    gj = np.asarray(g_j, float)
    n = min(beta.size, gi.size, gj.size)
    het_i = (gi[:n] == 1.0) & (gi[:n] >= 0)
    het_j = (gj[:n] == 1.0) & (gj[:n] >= 0)
    return float(np.sum((beta[:n] ** 2) * 0.25 * (het_i.astype(float) + het_j.astype(float))))


def usefulness(mu: float, var: float, intensity: float = I_INTENSITY_10PCT) -> float:
    sd = float(np.sqrt(max(var, 0.0)))
    return mu + intensity * sd


def desirability(pred: float, target: float, lo: float, hi: float) -> float:
    span = max(hi - lo, 1e-9)
    return float(1.0 - min(abs(pred - target) / span, 1.0))


def parse_target(spec: str) -> list[tuple[str, float]]:
    """'OIV 225=1,OIV 241=1' → [(trait, value), ...]."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"target item {part!r} missing '='")
        k, v = part.rsplit("=", 1)
        out.append((k.strip(), float(v)))
    return out


def _is_female(sex: str) -> bool:
    s = (sex or "").upper()
    return "FEMALE" in s and "HERMAPH" not in s


def recommend_crosses(
    *,
    ids: list[str],
    dosages: np.ndarray,
    gebv: dict[str, dict[str, float]],
    beta_by_trait: dict[str, np.ndarray],
    targets: list[tuple[str, float]],
    weights: list[float] | None = None,
    sex: dict[str, str] | None = None,
    kin_filter: bool = True,
    top: int = 50,
    parent: str | None = None,
    parent_dosage: np.ndarray | None = None,
    mas_sites: dict[str, list[int]] | None = None,
    scale_range: dict[str, tuple[float, float]] | None = None,
    intensity: float = I_INTENSITY_10PCT,
) -> tuple[list[dict], dict]:
    """Score parent pairs. gebv[id][trait] = predicted value."""
    n = len(ids)
    w = np.array(weights if weights is not None else [1.0] * len(targets), float)
    w = w / w.sum()
    scale_range = scale_range or {}
    sex = sex or {}
    mas_sites = mas_sites or {}

    def index_of(i: int, j: int) -> tuple[float, dict]:
        stats: dict[str, float] = {}
        des = []
        for t_i, (trait, tgt) in enumerate(targets):
            gi = gebv.get(ids[i], {}).get(trait)
            gj = gebv.get(ids[j], {}).get(trait)
            if gi is None or gj is None:
                des.append(0.0)
                continue
            mu = progeny_mean(gi, gj)
            beta = beta_by_trait.get(trait)
            if beta is not None:
                var = progeny_var_indep(beta, dosages[i], dosages[j])
            else:
                var = 0.0
            uc = usefulness(mu, var, intensity)
            lo, hi = scale_range.get(trait, (0.0, 1.0))
            des.append(desirability(mu, tgt, lo, hi))
            stats[f"mean_{trait}"] = mu
            stats[f"sd_{trait}"] = float(np.sqrt(max(var, 0.0)))
            stats[f"uc_{trait}"] = uc
        idx = float(np.dot(w, des)) if des else 0.0
        return idx, stats

    n_pairs = 0
    n_kin = n_sex = n_clone = 0
    rows: list[dict] = []

    def consider(i: int, j: int) -> None:
        nonlocal n_pairs, n_kin, n_sex, n_clone
        if i == j:
            return
        n_pairs += 1
        ibs0, ibs1, _ibs2, ibs2s, _n = ibs_counts(dosages[i], dosages[j])
        kin = king_robust(ibs0, ibs1, ibs2s)
        kin_legacy = kinship_king(dosages[i], dosages[j])
        if kin != kin:
            kin = kin_legacy
        if kin_filter:
            if kin == kin and kin >= KING_DUP:
                n_clone += 1
                return
            if kin == kin and kin > KING_SECOND:
                n_kin += 1
                return
        s1, s2 = sex.get(ids[i], ""), sex.get(ids[j], "")
        if _is_female(s1) and _is_female(s2):
            n_sex += 1
            return
        score, st = index_of(i, j)
        mas = []
        for trait, idxs in mas_sites.items():
            bits = []
            for k in idxs:
                if k >= dosages.shape[1]:
                    continue
                bits.append(f"{trait}:{k}={int(dosages[i, k])}/{int(dosages[j, k])}")
            mas.extend(bits)
        rows.append(
            {
                "p1": ids[i],
                "p2": ids[j],
                "index": score,
                "kinship": kin,
                "kinship_legacy": kin_legacy,
                "sex_p1": s1,
                "sex_p2": s2,
                "mas_flags": ";".join(mas[:12]),
                **st,
            }
        )

    if parent is not None:
        if parent in ids:
            pi = ids.index(parent)
        else:
            # append query as extra parent
            if parent_dosage is None:
                raise ValueError("parent not in panel and no parent_dosage")
            ids = list(ids) + [parent]
            dosages = np.vstack([dosages, parent_dosage.reshape(1, -1)])
            n = len(ids)
            pi = n - 1
            gebv.setdefault(parent, {})
        for j in range(n):
            consider(pi, j)
    else:
        for i in range(n):
            for j in range(i + 1, n):
                consider(i, j)

    rows.sort(key=lambda r: r["index"], reverse=True)
    rows = rows[:top]
    summary = {
        "n_candidates": n,
        "n_pairs_total": n_pairs,
        "n_removed_kinship": n_kin,
        "n_removed_sex": n_sex,
        "n_removed_clone": n_clone,
        "n_reported": len(rows),
        "parent": parent or "",
        "intensity": intensity,
    }
    return rows, summary


def load_sex_map(annot_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not annot_path.exists():
        return out
    import csv

    with annot_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            out[row["ID"]] = row.get("vivc_flower_sex") or ""
    return out


def write_cross_tsv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("p1\tp2\tindex\n", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(keys) + "\n")
        for r in rows:
            fh.write("\t".join(str(r.get(k, "")) for k in keys) + "\n")


def parent_ranking(
    ids: list[str],
    gebv: dict[str, dict[str, float]],
    targets: list[tuple[str, float]],
    scale_range: dict[str, tuple[float, float]],
    top: int = 20,
) -> list[dict]:
    """Hazel-style desirability index on parents themselves."""
    rows = []
    for sid in ids:
        des = []
        for trait, tgt in targets:
            v = gebv.get(sid, {}).get(trait)
            if v is None:
                des.append(0.0)
                continue
            lo, hi = scale_range.get(trait, (0.0, 1.0))
            des.append(desirability(v, tgt, lo, hi))
        rows.append({"ID": sid, "index": float(np.mean(des) if des else 0.0)})
    rows.sort(key=lambda r: r["index"], reverse=True)
    return rows[:top]


def run_cross_recommend(
    *,
    cache_path: Path,
    gs_root: Path,
    target: str,
    out_tsv: Path,
    annot_path: Path | None = None,
    parent: str | None = None,
    parent_vcf: Path | None = None,
    top: int = 50,
    kin_filter: bool = True,
    max_parents: int = 80,
) -> dict:
    """Load rrBLUP models + panel dosages and write a mate table."""
    from grapeancestry.breeding.gs import load_model
    from grapeancestry.core.dosage import load_cache, load_sample_dosage

    targets = parse_target(target)
    mat, ref_ids, sites = load_cache(cache_path)
    site_index = {s: i for i, s in enumerate(sites)}
    models = {}
    for npz in sorted(gs_root.glob("*/*/model.npz")):
        mdl = load_model(npz)
        key = mdl.trait if not str(npz.parent.name).endswith("_bin") else mdl.trait
        slug = npz.parent.name
        models[slug] = mdl
        models[mdl.trait] = mdl

    beta_by_trait: dict[str, np.ndarray] = {}
    gebv: dict[str, dict[str, float]] = {i: {} for i in ref_ids}
    scale_range: dict[str, tuple[float, float]] = {}
    used_sites: list[str] | None = None
    for trait, _tgt in targets:
        slug_bin = trait.replace(" ", "_") + "_bin"
        slug = trait.replace(" ", "_")
        mdl = models.get(slug_bin) or models.get(slug) or models.get(trait)
        if mdl is None or mdl.beta is None:
            continue
        key = trait
        beta_by_trait[key] = mdl.beta
        used_sites = mdl.sites
        idx = [site_index[s] for s in mdl.sites if s in site_index]
        X = mat[:, idx] if len(idx) == len(mdl.sites) else mat
        # predict all panel
        from grapeancestry.breeding.gs import predict_sample

        for i, sid in enumerate(ref_ids):
            pred, _cov = predict_sample(mdl, mat[i, idx] if len(idx) == mdl.beta.size else mat[i])
            gebv[sid][key] = pred
        lo, hi = (0.0, 1.0) if slug_bin in models or mdl.scale == "binary" else (1.0, 9.0)
        scale_range[key] = (lo, hi)

    if used_sites is None:
        raise FileNotFoundError("no GS model.npz matching --target traits; run gs-train first")

    idx = [site_index[s] for s in used_sites if s in site_index]
    dosages = mat[:, idx]
    # subsample candidates: top parents by first trait GEBV to keep pair count tractable
    trait0 = targets[0][0]
    ranked = sorted(ref_ids, key=lambda s: gebv.get(s, {}).get(trait0, -1e9), reverse=True)
    keep_ids = ranked[:max_parents]
    if parent and parent in ref_ids and parent not in keep_ids:
        keep_ids = [parent] + keep_ids[:-1]
    keep_idx = [ref_ids.index(s) for s in keep_ids]
    dosages_k = dosages[keep_idx]
    parent_dos = None
    if parent and parent not in ref_ids and parent_vcf:
        q = load_sample_dosage(parent_vcf, parent, used_sites)
        parent_dos = q

    sex = load_sex_map(annot_path) if annot_path else {}
    rows, summary = recommend_crosses(
        ids=keep_ids,
        dosages=dosages_k,
        gebv=gebv,
        beta_by_trait=beta_by_trait,
        targets=targets,
        sex=sex,
        kin_filter=kin_filter,
        top=top,
        parent=parent if parent else None,
        parent_dosage=parent_dos,
        scale_range=scale_range,
    )
    write_cross_tsv(rows, out_tsv)
    summary_path = out_tsv.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    rank = parent_ranking(keep_ids, gebv, targets, scale_range)
    rank_path = out_tsv.parent / (out_tsv.stem + "_parents.tsv")
    write_cross_tsv(rank, rank_path)
    summary["out_tsv"] = str(out_tsv)
    return summary

