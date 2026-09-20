"""Panel k-NN dosage imputation (local). GLIMPSE2 remains an HPC haplotype option."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def glimpse_plan(
    bam_or_vcf: Path,
    ref_panel: Path,
    out_dir: Path,
    *,
    chroms: list[str] | None = None,
) -> str:
    """HPC checklist only — haplotype imputation is not run on the laptop."""
    chroms = chroms or [str(i) for i in range(1, 20)]
    lines = [
        "# GLIMPSE2 plan (run on HPC, not MBP 16GB)",
        f"# input: {bam_or_vcf}",
        f"# ref:   {ref_panel}",
        f"# out:   {out_dir}",
        "module load glimpse2  # or conda glimpse-bio",
        "for chr in " + " ".join(chroms) + "; do",
        "  GLIMPSE2_phase --bam-file $bam --reference $ref --output $out/chr$chr",
        "done",
        "GLIMPSE2_ligate --input ligate.list --output $out/merged",
    ]
    return "\n".join(lines)


def knn_impute(
    query: np.ndarray,
    panel: np.ndarray,
    *,
    k: int = 5,
    min_called: int = 30,
    ref_ids: list[str] | None = None,
) -> tuple[np.ndarray, dict]:
    """Fill missing dosages (−1) from k nearest panel rows (IBS on called sites).

    Not GLIMPSE2 / Beagle haplotype imputation. Weighted rounded mean of
    neighbour genotypes at each missing site.
    """
    q = np.asarray(query, dtype=np.int16).reshape(-1)
    g = np.asarray(panel, dtype=np.int8)
    if g.ndim != 2 or g.shape[1] != q.shape[0]:
        raise ValueError("query/panel site length mismatch")
    out = q.copy()
    called = q >= 0
    n_miss = int((~called).sum())
    if n_miss == 0 or g.shape[0] == 0:
        return out.astype(np.int8), {
            "n_imputed": 0,
            "n_missing": n_miss,
            "k": k,
            "neighbors": [],
            "method": "panel_knn",
        }
    from grapeancestry.popgen.tree_nj import ibs_distance_to_rows

    dist = ibs_distance_to_rows(q, g)
    called_q = q >= 0
    n_ok = ((g >= 0) & called_q).sum(axis=1).astype(np.int32)
    sims = np.where(n_ok >= min_called, 1.0 - dist, np.nan)
    order = np.argsort(np.where(np.isfinite(sims), sims, -1.0))[::-1]
    k_idx = [int(i) for i in order if sims[i] == sims[i]][:k]
    miss = np.where(~called)[0]
    n_imp = 0
    for j in miss:
        votes: list[int] = []
        w: list[float] = []
        for i in k_idx:
            v = int(g[i, j])
            if v >= 0:
                votes.append(v)
                w.append(max(float(sims[i]), 1e-6))
        if not votes:
            continue
        out[j] = int(np.clip(round(float(np.average(votes, weights=w))), 0, 2))
        n_imp += 1
    neighbors = []
    for i in k_idx:
        rid = ref_ids[i] if ref_ids and i < len(ref_ids) else str(i)
        neighbors.append({"ref_id": rid, "ibs": float(sims[i]), "n_comparable": int(n_ok[i])})
    return out.astype(np.int8), {
        "n_imputed": n_imp,
        "n_missing": n_miss,
        "k": k,
        "neighbors": neighbors,
        "method": "panel_knn",
        "note": "k-NN from 2449 panel dosages; not GLIMPSE2 haplotypes.",
    }


def site_map_impute(
    site_map: dict[str, int],
    panel: np.ndarray,
    sites: list[str],
    *,
    k: int = 5,
    ref_ids: list[str] | None = None,
) -> tuple[dict[str, int], dict]:
    from grapeancestry.cloud.vcf_py import align_dosage

    q = np.asarray(align_dosage(site_map, sites), np.int8)
    filled, meta = knn_impute(q, panel, k=k, ref_ids=ref_ids)
    out = dict(site_map)
    for i, s in enumerate(sites):
        if int(site_map.get(s, -1)) < 0 and int(filled[i]) >= 0:
            out[s] = int(filled[i])
    return out, meta
