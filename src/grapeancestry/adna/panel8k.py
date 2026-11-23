"""8,044-site GrapeReseq ∩ 167K panel analysis.

PCA uses the frozen GCTA loadings (``project_query_pcs``). ADMIXTURE Q uses
fixed-P NNLS (``estimate_q_fixed_p`` → ``project_q_nnls``). Sites outside the
8,044-site set are treated as missing and do not contribute.

Intermediates stay under ``results/_panel8k/{target}/`` so a 167K report in
``results/`` is left in place. Report HTML is written to ``results/`` (or
``out_dir``) with the v1.2 filenames.
"""

from __future__ import annotations

import csv
import gzip
import inspect
import os
from pathlib import Path

import numpy as np

from grapeancestry.adna.pca_lock import METHOD_GCTA
from grapeancestry.adna.project import SVDCacheResult
from grapeancestry.identity.ibs import (
    RELATIONSHIPS,
    PairStats,
    classify_relationship,
    ibs2_star_percent_of_informative,
    king_robust,
    r0_r1,
)

N_SITES = 8044
FROZEN_MODEL_SITES = 153_483

_IBS_HEADER = [
    "ref",
    "IBS0",
    "IBS1",
    "IBS2*",
    "IBS2*_pct",
    "R0",
    "R1",
    "KING_Robust",
    "kinship",
    "relationship",
]

SITE_NOTE_HTML = (
    '<div id="site-set-note" class="ga-site-note"><p>'
    '<span class="en">GrapeReseq (8K) report. Genotypes use the 8,044 sites shared '
    "with the 167K capture panel. PCA and ADMIXTURE are a projection onto the frozen "
    "167K model, using only these sites.</span>"
    '<span class="cn">GrapeReseq（8K）报告。基因型用的是与 167K 捕获面板共有的 8,044 个位点。'
    "PCA 和 ADMIXTURE 是投到冻结 167K 模型上的投影，只用这些位点。</span>"
    "</p></div>\n"
)


class GctaWeights:
    """SNP weights that reconstruct the frozen GCTA sample PCs."""

    def __init__(
        self,
        mu: np.ndarray,
        sd: np.ndarray,
        ok_snp: np.ndarray,
        w: np.ndarray,
        alpha: np.ndarray,
        sites: list[str],
        ref_ids: list[str],
        ref_xy: np.ndarray,
        evals: list[float],
    ) -> None:
        self.mu = np.asarray(mu, float)
        self.sd = np.asarray(sd, float)
        self.ok_snp = np.asarray(ok_snp, bool)
        self.w = np.asarray(w, float)
        self.alpha = np.asarray(alpha, float)
        self.sites = [str(s) for s in sites]
        self.ref_ids = [str(s) for s in ref_ids]
        self.ref_xy = np.asarray(ref_xy, float)
        self.evals = [float(x) for x in evals]


def sites_bed_path(root: Path) -> Path:
    return Path(root) / "data" / "panel" / "sites_8044.bed"


def panel_cache_path(root: Path) -> Path:
    return Path(root) / "results" / "cache" / "panel_dosage_8044.npz"


def weights_path(root: Path) -> Path:
    return Path(root) / "results" / "cache" / "gcta_weights.npz"


def load_site_keys(path: Path) -> list[str]:
    """Read a BED or two-column site list. BED keys use the end coordinate."""
    keys: list[str] = []
    seen: set[str] = set()
    with Path(path).open() as handle:
        for line in handle:
            if not line.strip() or line.startswith(("#", "track", "browser", "CHROM")):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                parts = line.split()
            if len(parts) >= 3:
                key = f"{parts[0]}:{int(parts[2])}"
            else:
                key = f"{parts[0]}:{int(parts[1])}"
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def _zchunk(block: np.ndarray, mu: np.ndarray, sd: np.ndarray, ok_snp: np.ndarray) -> np.ndarray:
    # Same standardisation as pca_lock.lsq_project_onto_gcta.
    sl = np.asarray(block, float)
    sl = np.where(sl < 0, np.nan, sl)
    z = (sl - mu) / sd
    return np.where(np.isfinite(z) & ok_snp, z, 0.0)


def fit_gcta_weights_from_arrays(
    dosage: np.ndarray,
    ref_ids: list[str],
    sites: list[str],
    freeze_ids: list[str],
    freeze_xy: np.ndarray,
    evals: list[float],
    *,
    chunk: int = 128,
) -> GctaWeights:
    """Least-squares SNP weights of frozen sample PCs. Missing dosages are skipped."""
    x = np.asarray(dosage)
    idx = {sid: i for i, sid in enumerate(ref_ids)}
    keep = [i for i, sid in enumerate(freeze_ids) if sid in idx]
    if len(keep) < 10:
        raise ValueError("too few reference IDs overlap the GCTA freeze")
    rows = [idx[freeze_ids[i]] for i in keep]
    v = np.asarray(freeze_xy, float)[keep]
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
    return GctaWeights(
        mu=mu,
        sd=sd,
        ok_snp=ok_snp,
        w=w,
        alpha=alpha,
        sites=list(sites),
        ref_ids=list(freeze_ids),
        ref_xy=np.asarray(freeze_xy, float),
        evals=list(evals),
    )


def fit_panel_gcta_weights(root: Path, chunk: int = 128) -> GctaWeights:
    """Loadings of the frozen GCTA axes on every nogwas site."""
    from grapeancestry.adna.panel167k_nogwas import load_family_sites
    from grapeancestry.adna.pca_lock import load_gcta_freeze
    from grapeancestry.core.dosage import load_cache

    root = Path(root)
    freeze = load_gcta_freeze(root)
    if freeze is None:
        raise RuntimeError("GCTA freeze is missing")
    mat, ref_ids, cache_sites = load_cache(root / "results" / "cache" / "panel_dosage_167k.npz")
    ref_ids = [str(s) for s in ref_ids]
    cache_sites = [str(s) for s in cache_sites]
    nogwas = load_family_sites(root / "data" / "panel" / "admixture")
    site_i = {s: i for i, s in enumerate(cache_sites)}
    cols = [site_i[s] for s in nogwas if s in site_i]
    sites = [s for s in nogwas if s in site_i]
    if len(cols) < 1000:
        raise RuntimeError(f"nogwas overlap is {len(cols)}")
    weights = fit_gcta_weights_from_arrays(
        np.asarray(mat)[:, cols],
        ref_ids,
        sites,
        list(freeze.ids),
        np.asarray(freeze.xy, float),
        list(freeze.evals),
        chunk=chunk,
    )
    del mat
    return weights


def project_query_pcs(
    query: np.ndarray,
    weights: GctaWeights,
    site_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Project one dosage vector. Sites outside ``site_mask`` are treated as missing."""
    q = np.asarray(query, float).reshape(-1).copy()
    if q.shape[0] != weights.w.shape[0]:
        raise ValueError(f"query length {q.shape[0]} != loadings {weights.w.shape[0]}")
    if site_mask is not None:
        mask = np.asarray(site_mask, bool).reshape(-1)
        if mask.shape[0] != q.shape[0]:
            raise ValueError("site_mask length does not match the query")
        q[~mask] = -1.0
    qmiss = (q < 0) | ~np.isfinite(q) | ~weights.ok_snp
    zq = np.where(qmiss, 0.0, (q - weights.mu) / weights.sd)
    zq = np.where(np.isfinite(zq), zq, 0.0)
    return (zq @ weights.w) * weights.alpha


def estimate_q_fixed_p(
    dosage: np.ndarray,
    P: np.ndarray,
    *,
    counted_allele: str = "REF",
) -> np.ndarray:
    """Q with P fixed. Same NNLS and allele coding as ``project_q_nnls``."""
    from grapeancestry.adna.admixture import project_q_nnls

    return project_q_nnls(
        np.asarray(dosage, float),
        np.asarray(P, float),
        counted_allele=counted_allele,
    )


def dosage_on_weights(dosage: np.ndarray, keys: list[str], weights: GctaWeights) -> np.ndarray:
    pos = {site: i for i, site in enumerate(weights.sites)}
    out = np.full(len(weights.sites), -1.0)
    dose = np.asarray(dosage, float).reshape(-1)
    for j, site in enumerate(keys):
        i = pos.get(site)
        if i is not None and j < dose.shape[0]:
            out[i] = float(dose[j])
    return out


def project_locked_query(
    weights: GctaWeights,
    sample: str,
    query_dosage: np.ndarray,
    cache_sites: list[str],
) -> SVDCacheResult:
    aligned = dosage_on_weights(np.asarray(query_dosage), [str(s) for s in cache_sites], weights)
    xy = project_query_pcs(aligned, weights)
    if not np.isfinite(xy).all():
        raise RuntimeError(f"PCA projection is not finite for {sample}")
    weight_sites = set(weights.sites)
    used = int(sum(1 for site in cache_sites if site in weight_sites))
    return SVDCacheResult(
        ref_ids=list(weights.ref_ids),
        ref_coords=np.asarray(weights.ref_xy, float),
        query_ids=[sample],
        query_coords=np.asarray(xy, float).reshape(1, -1),
        evals=list(weights.evals),
        method=METHOD_GCTA,
        cache_name="gcta_nogwas",
        n_sites=used,
    )


def save_gcta_weights(path: Path, weights: GctaWeights) -> None:
    path = Path(path)
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        mu=weights.mu,
        sd=weights.sd,
        ok_snp=weights.ok_snp,
        w=weights.w,
        alpha=weights.alpha,
        sites=np.asarray(weights.sites, dtype=object),
        ref_ids=np.asarray(weights.ref_ids, dtype=object),
        ref_xy=weights.ref_xy,
        evals=np.asarray(weights.evals, dtype=float),
    )
    os.chmod(path, 0o644)


def load_gcta_weights(path: Path) -> GctaWeights:
    with np.load(path, allow_pickle=True) as z:
        return GctaWeights(
            mu=np.asarray(z["mu"], float),
            sd=np.asarray(z["sd"], float),
            ok_snp=np.asarray(z["ok_snp"], bool),
            w=np.asarray(z["w"], float),
            alpha=np.asarray(z["alpha"], float),
            sites=[str(s) for s in z["sites"].tolist()],
            ref_ids=[str(s) for s in z["ref_ids"].tolist()],
            ref_xy=np.asarray(z["ref_xy"], float),
            evals=[float(x) for x in np.asarray(z["evals"], float).tolist()],
        )


def ensure_gcta_weights(root: Path) -> GctaWeights:
    path = weights_path(root)
    if path.is_file():
        return load_gcta_weights(path)
    weights = fit_panel_gcta_weights(root)
    save_gcta_weights(path, weights)
    return weights


def subset_panel_dosage(root: Path, keys: list[str]) -> tuple[list[str], np.ndarray, list[str]]:
    """Columns of the 167K dosage cache that sit on ``keys``."""
    from grapeancestry.core.dosage import load_cache

    mat, samples, sites = load_cache(Path(root) / "results" / "cache" / "panel_dosage_167k.npz")
    sites = [str(s) for s in sites]
    index = {site: i for i, site in enumerate(sites)}
    kept = [key for key in keys if key in index]
    if len(kept) != N_SITES or len(set(kept)) != N_SITES:
        raise RuntimeError(f"8K ∩ panel dosage is {len(set(kept))}, expected {N_SITES}")
    cols = [index[key] for key in kept]
    return kept, np.asarray(mat)[:, cols], [str(s) for s in samples]


def ensure_panel_dosage(root: Path) -> tuple[list[str], np.ndarray, list[str]]:
    """Load ``panel_dosage_8044.npz``, rebuilding it from the 167K cache if needed."""
    from grapeancestry.core.dosage import load_cache, save_cache

    root = Path(root)
    bed_keys = load_site_keys(sites_bed_path(root))
    if len(bed_keys) != N_SITES or len(set(bed_keys)) != N_SITES:
        raise RuntimeError(f"sites_8044.bed has {len(set(bed_keys))} unique sites, expected {N_SITES}")
    path = panel_cache_path(root)
    if path.is_file():
        mat, samples, sites = load_cache(path)
        sites = [str(s) for s in sites]
        if len(sites) != N_SITES or set(sites) != set(bed_keys):
            raise RuntimeError("panel_dosage_8044.npz does not match sites_8044.bed")
        return sites, np.asarray(mat), [str(s) for s in samples]
    keys, mat, samples = subset_panel_dosage(root, bed_keys)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_cache(path, mat, samples, keys)
    os.chmod(path, 0o644)
    return keys, mat, samples


def read_query_dosage(vcf: Path, sample: str, keys: list[str]) -> tuple[np.ndarray, int]:
    """ALT dosage on ``keys`` for ``sample`` (first column if the name is absent)."""
    from grapeancestry.core.dosage import _gt_to_dose

    vcf = Path(vcf)
    want = {key: i for i, key in enumerate(keys)}
    out = np.full(len(keys), -1, dtype=np.int8)
    seen = 0
    opener = gzip.open if str(vcf).endswith(".gz") else open
    sample_col = 9
    with opener(vcf, "rt") as handle:
        for line in handle:
            if not line or line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                header = line.rstrip("\n").split("\t")
                if sample in header:
                    sample_col = header.index(sample)
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) <= sample_col:
                continue
            key = f"{parts[0]}:{int(parts[1])}"
            slot = want.get(key)
            if slot is None:
                continue
            seen += 1
            fmt = parts[8].split(":") if len(parts) > 8 else ["GT"]
            values = parts[sample_col].split(":")
            gt = values[fmt.index("GT")] if "GT" in fmt and fmt.index("GT") < len(values) else values[0]
            out[slot] = _gt_to_dose(gt)
    return out, seen


def _fmt_stat(value: float, *, inf_ok: bool = False) -> str:
    if value != value:
        return "NA"
    if value == float("inf"):
        return "inf" if inf_ok else "NA"
    if value == float("-inf"):
        return "NA"
    return f"{value:.6f}"


def _pair_from_counts(ref_id: str, ibs0: int, ibs1: int, ibs2: int, ibs2_star: int, n: int) -> PairStats:
    pct = ibs2_star_percent_of_informative(ibs0, ibs2_star)
    r0, r1 = r0_r1(ibs0, ibs1, ibs2_star)
    king = king_robust(ibs0, ibs1, ibs2_star)
    ibs = (ibs2 / n) if n else float("nan")
    rel = classify_relationship(r0, r1, pct, king, king)
    return PairStats(
        ref_id=ref_id,
        ibs0=int(ibs0),
        ibs1=int(ibs1),
        ibs2=int(ibs2),
        ibs2_star=int(ibs2_star),
        n_comparable=int(n),
        ibs2_star_pct=pct,
        r0=r0 if r0 != float("inf") else float("nan"),
        r1=r1,
        king_robust=king,
        kinship=king,
        relationship=rel,
        ibs=ibs,
    )


def panel_pair_stats(query: np.ndarray, panel: np.ndarray, ref_ids: list[str]) -> list[PairStats]:
    """Vectorised 4K IBS/KING. Same counts as ``pair_stats``; thresholds stay in ``ibs.py``."""
    q = np.asarray(query).reshape(1, -1)
    panel = np.asarray(panel)
    mask = (panel >= 0) & (q >= 0)
    n = mask.sum(axis=1).astype(np.int64)
    both_het = ((panel == 1) & (q == 1) & mask).sum(axis=1)
    opposite = ((((panel == 0) & (q == 2)) | ((panel == 2) & (q == 0))) & mask).sum(axis=1)
    same = ((panel == q) & mask).sum(axis=1)
    ibs1 = n - same - opposite
    rows = [
        _pair_from_counts(ref_ids[i], int(opposite[i]), int(ibs1[i]), int(same[i]), int(both_het[i]), int(n[i]))
        for i in range(len(ref_ids))
    ]
    rank = {name: i for i, name in enumerate(RELATIONSHIPS)}

    def sort_key(row: PairStats) -> tuple:
        king = row.king_robust if row.king_robust == row.king_robust else -999.0
        ibs = row.ibs if row.ibs == row.ibs else -1.0
        return (rank.get(row.relationship, 99), -king, -ibs)

    rows.sort(key=sort_key)
    return rows


def _write_ibs(path: Path, rows: list[PairStats]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(_IBS_HEADER)
        for row in rows:
            writer.writerow(
                [
                    row.ref_id,
                    row.ibs0,
                    row.ibs1,
                    row.ibs2_star,
                    _fmt_stat(row.ibs2_star_pct),
                    _fmt_stat(row.r0),
                    _fmt_stat(row.r1, inf_ok=True),
                    _fmt_stat(row.king_robust),
                    _fmt_stat(row.kinship),
                    row.relationship,
                ]
            )


def write_identity(sample: str, rows: list[PairStats], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _write_ibs(dest / f"{sample}.ibs.tsv", rows)
    counts = {name: 0 for name in RELATIONSHIPS}
    for row in rows:
        if row.ref_id == sample:
            continue
        counts[row.relationship] = counts.get(row.relationship, 0) + 1
    with (dest / f"{sample}.ibs_summary.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["relationship", "count"])
        for name in RELATIONSHIPS:
            writer.writerow([name, counts.get(name, 0)])
    hits = [row for row in rows if row.relationship in {"Identical", "Parent-Offspring"} and row.ref_id != sample]
    _write_ibs(dest / f"{sample}.ibs_clone_hits.tsv", hits)
    ranked = sorted(
        (row for row in rows if row.ref_id != sample),
        key=lambda row: (
            -(row.king_robust if row.king_robust == row.king_robust else -999.0),
            -(row.ibs if row.ibs == row.ibs else -1.0),
        ),
    )
    with (dest / f"{sample}.kinship_top.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["rank", "ref_id", "KING_Robust", "kinship", "relationship", "ibs", "n_comparable"])
        for rank, row in enumerate(ranked[:20], 1):
            writer.writerow(
                [
                    rank,
                    row.ref_id,
                    _fmt_stat(row.king_robust),
                    _fmt_stat(row.kinship),
                    row.relationship,
                    _fmt_stat(row.ibs),
                    row.n_comparable,
                ]
            )


def write_genotype_qc(
    sample: str,
    dosage: np.ndarray,
    n_in_vcf: int,
    dest: Path,
    bam_metrics: dict | None = None,
) -> None:
    from grapeancestry.core.qc import write_tsv

    dose = np.asarray(dosage)
    n_panel = int(dose.shape[0])
    n_called = int((dose >= 0).sum())
    n_hom_ref = int((dose == 0).sum())
    n_het = int((dose == 1).sum())
    n_hom_alt = int((dose == 2).sum())
    calling_rate = (n_called / n_in_vcf) if n_in_vcf else 0.0
    metrics = dict(bam_metrics or {})
    metrics.update(
        {
            "n_panel_sites": float(n_panel),
            "n_sites_vcf": float(n_in_vcf),
            "n_called": float(n_called),
            "n_missing": float(n_panel - n_called),
            "calling_rate": calling_rate,
            "calling_rate_pct": 100.0 * calling_rate,
            "n_hom_ref": float(n_hom_ref),
            "n_het": float(n_het),
            "n_hom_alt": float(n_hom_alt),
            "n_variant": float(n_het + n_hom_alt),
            "variant_rate": ((n_het + n_hom_alt) / n_called) if n_called else 0.0,
            "het_rate": (n_het / n_called) if n_called else 0.0,
            "n_panel_sites_ref": float(n_panel),
            "calling_rate_panel": (n_called / n_panel) if n_panel else 0.0,
            "calling_rate_panel_pct": (100.0 * n_called / n_panel) if n_panel else 0.0,
            "sites_recovered_pct": (100.0 * n_in_vcf / n_panel) if n_panel else 0.0,
        }
    )
    write_tsv(metrics, dest / f"{sample}.qc.tsv", sample)


def _nnls_mode(admix_mode: str) -> str:
    mode = str(admix_mode or "nnls").lower()
    if mode == "official":
        return "official"
    return "nnls"


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name))
    return cleaned or "sample"


def _isolated_root(root: Path, target: str) -> tuple[Path, Path]:
    work = Path(root) / "results" / "_panel8k" / _safe_name(target) / "work"
    results = work / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "cache").mkdir(parents=True, exist_ok=True)
    return work, results


def _link_new(src: Path, dest: Path) -> None:
    if dest.exists() or dest.is_symlink():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.symlink_to(src)


def _prepare_workspace(root: Path, target: str) -> tuple[Path, Path]:
    root = Path(root)
    work, results = _isolated_root(root, target)
    for name in ("data", "assets", "docs", "config", "bin"):
        src = root / name
        if src.exists():
            _link_new(src, work / name)
    dosage = panel_cache_path(root)
    _link_new(dosage, results / "cache" / "panel_dosage_167k.npz")
    gwas_index = root / "results" / "gwas" / "index.tsv"
    dest_index = results / "gwas" / "index.tsv"
    if gwas_index.is_file() and not dest_index.exists():
        dest_index.parent.mkdir(parents=True, exist_ok=True)
        dest_index.write_bytes(gwas_index.read_bytes())
        os.chmod(dest_index, 0o644)
    _filter_gwas(root, results, set(load_site_keys(sites_bed_path(root))))
    return work, results


def _filter_gwas(root: Path, results: Path, keep: set[str]) -> None:
    src = Path(root) / "results" / "gwas" / "locuszoom.json"
    dest = results / "gwas" / "locuszoom.json"
    if not src.is_file() or dest.exists():
        return
    import json

    records = json.loads(src.read_text())
    filtered = []
    for rec in records if isinstance(records, list) else []:
        snps = dict(rec.get("snps") or {})
        sites = [str(site) for site in (snps.get("site") or [])]
        n = len(sites)
        keep_i = [i for i, site in enumerate(sites) if site in keep]
        for key, value in list(snps.items()):
            if isinstance(value, list) and len(value) == n:
                snps[key] = [value[i] for i in keep_i]
        lead_i = rec.get("lead_i")
        lead_site = sites[lead_i] if isinstance(lead_i, int) and 0 <= lead_i < n else ""
        if lead_site in keep and keep_i:
            new_lead = [sites[i] for i in keep_i].index(lead_site)
        else:
            new_lead = 0 if keep_i else None
        row = dict(rec)
        row["snps"] = snps
        row["n_snps"] = len(keep_i)
        row["lead_i"] = new_lead
        filtered.append(row)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(filtered, ensure_ascii=False) + "\n")
    os.chmod(dest, 0o644)


def _link_vcf(vcf: Path, dest: Path) -> None:
    vcf = Path(vcf)
    if dest.exists() or dest.is_symlink():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if vcf.resolve() != dest.resolve():
            dest.symlink_to(vcf)
    except OSError:
        if not dest.exists():
            dest.symlink_to(vcf)
    tbi = Path(str(vcf) + ".tbi")
    dest_tbi = Path(str(dest) + ".tbi")
    if tbi.is_file() and not dest_tbi.exists():
        dest_tbi.symlink_to(tbi)


def _retarget_downloads(payload: dict, prefix: str) -> None:
    prefix = prefix.strip("/")

    def fix(rows: object) -> None:
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            href = str(row.get("href") or "")
            if not href or href.startswith(("/", "http", prefix + "/")):
                continue
            row["href"] = f"{prefix}/{href}"

    fix(payload.get("downloads"))
    per = payload.get("per_query") or {}
    if isinstance(per, dict):
        for sl in per.values():
            if isinstance(sl, dict):
                fix(sl.get("downloads"))


def _write_dashboard(sample: str, payload: dict, out_html: Path, root: Path, *, nav_html: str) -> None:
    from grapeancestry.report.compare import inject_after_body
    from grapeancestry.report.interactive_dashboard import write_dashboard_html
    from grapeancestry.report.interactive_data import payload_to_json

    data_json = payload_to_json(payload)
    optional = {
        "nav_html": nav_html or "",
        "site_note_html": SITE_NOTE_HTML,
        "panel_sites_count": N_SITES,
    }
    sig = inspect.signature(write_dashboard_html)
    kwargs = {key: value for key, value in optional.items() if key in sig.parameters}
    write_dashboard_html(sample, data_json, out_html, root, **kwargs)
    # Step 2 inserts these kwargs itself. Inject only if that signature is absent.
    if "nav_html" not in sig.parameters:
        inject_after_body(out_html, nav_html or "", "ga-report-nav")
    if "site_note_html" not in sig.parameters:
        inject_after_body(out_html, SITE_NOTE_HTML, "site-set-note")


def _publish(root: Path, html_path: Path) -> None:
    from grapeancestry.release_io import publish_v2_report

    publish_v2_report(root, html_path)


class _GctaHook:
    def __init__(self, weights: GctaWeights) -> None:
        self.weights = weights
        self._saved = None

    def __enter__(self) -> "_GctaHook":
        import grapeancestry.adna.pca_lock as pca_lock

        self._saved = pca_lock.locked_pca_for_sample

        def locked(root, sample, ref_ids, ref_dosage, query_dosage, cache_sites, nogwas_sites):
            del root, ref_ids, ref_dosage, nogwas_sites
            return project_locked_query(self.weights, sample, query_dosage, list(cache_sites))

        pca_lock.locked_pca_for_sample = locked
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        import grapeancestry.adna.pca_lock as pca_lock

        if self._saved is not None:
            pca_lock.locked_pca_for_sample = self._saved


def _bam_metrics(bam: Path | None, bed: Path, vcf: Path, sample: str) -> dict:
    if bam is None or not Path(bam).is_file():
        return {}
    try:
        from grapeancestry.core.qc import qc_sample

        return dict(qc_sample(Path(bam), bed, vcf=vcf if vcf.is_file() else None, sample=sample))
    except Exception:
        return {}


def _stage_sample(
    sample: str,
    vcf: Path,
    results: Path,
    keys: list[str],
    mat: np.ndarray,
    ref_ids: list[str],
    *,
    bam: Path | None,
    bed: Path,
) -> np.ndarray:
    _link_vcf(Path(vcf), results / f"{sample}.vcf.gz")
    dosage, n_in_vcf = read_query_dosage(Path(vcf), sample, keys)
    write_identity(sample, panel_pair_stats(dosage, mat, ref_ids), results)
    write_genotype_qc(sample, dosage, n_in_vcf, results, _bam_metrics(bam, bed, Path(vcf), sample))
    return dosage


def _finish_html(
    root: Path,
    payload: dict,
    out_html: Path,
    fake_results: Path,
    *,
    nav_html: str,
    title: str,
) -> dict:
    prefix = os.path.relpath(fake_results, out_html.parent)
    _retarget_downloads(payload, Path(prefix).as_posix())
    out_html.parent.mkdir(parents=True, exist_ok=True)
    _write_dashboard(title, payload, out_html, root, nav_html=nav_html)
    _publish(root, out_html)
    return payload


def run_8k_single(
    root,
    sample: str,
    vcf,
    *,
    bam=None,
    damage_tsv=None,
    pca_color: str = "Grp",
    admix_mode: str = "nnls",
    out_dir=None,
    nav_html: str = "",
    render_html: bool = True,
    source_sample: str | None = None,
    admix_all_k: bool = True,
) -> dict:
    """One-sample 8K report. Returns the dashboard payload."""
    from grapeancestry.report.build_report import build_bundle
    from grapeancestry.report.interactive_data import build_interactive_payload

    root = Path(root)
    sample = str(sample)
    keys, mat, ref_ids = ensure_panel_dosage(root)
    weights = ensure_gcta_weights(root)
    work, results = _prepare_workspace(root, sample)
    _stage_sample(
        sample,
        Path(vcf),
        results,
        keys,
        mat,
        ref_ids,
        bam=Path(bam) if bam else None,
        bed=sites_bed_path(root),
    )
    damage = Path(damage_tsv) if damage_tsv else None
    with _GctaHook(weights):
        bundle = build_bundle(
            sample,
            work,
            admix_dir=work / "data" / "panel" / "admixture",
            damage_tsv=damage if damage and damage.is_file() else None,
            pca_color=pca_color,
            merged_vcf=None,
            admix_mode=_nnls_mode(admix_mode),
            admix_all_k=bool(admix_all_k),
            source_sample_id=source_sample,
        )
    payload = build_interactive_payload(bundle, work)
    if not render_html:
        return payload
    dest = Path(out_dir) if out_dir else root / "results"
    html_path = dest / f"{sample}.8k.sample-first-v2.report.html"
    return _finish_html(root, payload, html_path, results, nav_html=nav_html, title=sample)


def run_8k_batch(
    root,
    batch_name: str,
    sample_specs: list[dict],
    *,
    out_dir=None,
    nav_html: str = "",
    render_html: bool = True,
    admix_all_k: bool = True,
) -> dict:
    """Batch 8K report. ``sample_specs`` items need ``sample`` and ``vcf``."""
    from grapeancestry.report.batch_payload import build_batch_payload, stamp_library_type
    from grapeancestry.report.build_report import build_bundle

    root = Path(root)
    batch_name = str(batch_name)
    if not sample_specs:
        raise ValueError("run_8k_batch needs at least one sample")
    keys, mat, ref_ids = ensure_panel_dosage(root)
    weights = ensure_gcta_weights(root)
    work, results = _prepare_workspace(root, batch_name)
    bed = sites_bed_path(root)
    bundles = []
    report_ids: list[str] = []
    with _GctaHook(weights):
        for spec in sample_specs:
            sample = str(spec["sample"])
            vcf = Path(spec["vcf"])
            if not vcf.is_file():
                continue
            bam = spec.get("bam")
            _stage_sample(
                sample,
                vcf,
                results,
                keys,
                mat,
                ref_ids,
                bam=Path(bam) if bam else None,
                bed=bed,
            )
            damage = spec.get("damage_tsv")
            damage_path = Path(damage) if damage else None
            bundle = build_bundle(
                sample,
                work,
                admix_dir=work / "data" / "panel" / "admixture",
                damage_tsv=damage_path if damage_path and damage_path.is_file() else None,
                pca_color=str(spec.get("pca_color") or "Grp"),
                merged_vcf=None,
                admix_mode=_nnls_mode(str(spec.get("admix_mode") or "nnls")),
                admix_all_k=bool(spec.get("admix_all_k", admix_all_k)),
                source_sample_id=spec.get("source_sample"),
            )
            library = str(spec.get("library_type") or "").strip()
            if library:
                stamp_library_type(bundle, library)
            bundles.append(bundle)
            report_ids.append(sample)
    if not report_ids:
        raise ValueError("run_8k_batch found no readable VCFs")
    payload = build_batch_payload(work, report_ids, bundles=bundles)
    if not render_html:
        return payload
    dest = Path(out_dir) if out_dir else root / "results"
    html_path = dest / f"{batch_name}.8k.batch.report.html"
    return _finish_html(root, payload, html_path, results, nav_html=nav_html, title=batch_name)
