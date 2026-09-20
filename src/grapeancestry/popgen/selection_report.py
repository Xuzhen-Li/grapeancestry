"""Selection scan helpers for report (G12-like het dip + gene annotation)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from grapeancestry.adna.selection import g12_like, window_het
from grapeancestry.resource.genes import annotate_site, load_gene_annotation
from grapeancestry.resource.sprot import attach_func_fields


def selection_scan(
    mat: np.ndarray,
    sites: list[str],
    *,
    window: int = 25,
    q: float = 0.05,
    gff: Path | None = None,
    genes=None,
    features=None,
    sprot=None,
    top_n: int = 30,
) -> dict:
    """Return windowed het track + lowest-q outlier sites (optional gene)."""
    het = window_het(mat, window=window)
    idxs = g12_like(het, q=q)
    # rank by het ascending
    idxs = sorted(idxs, key=lambda i: het[i] if het[i] == het[i] else 1.0)
    if genes is None and gff and Path(gff).exists():
        genes, features = load_gene_annotation(gff)
    from grapeancestry.cloud.mas import MAS_LOCI

    mas_site = {r["site"]: r for r in MAS_LOCI}
    mas_gene = {
        r["gene"]: r for r in MAS_LOCI if str(r.get("gene") or "").startswith("Vvsyl")
    }
    outliers: list[dict] = []
    for i in idxs[:top_n]:
        chrom, pos = sites[i].split(":") if ":" in sites[i] else ("?", sites[i])
        ann = annotate_site(
            chrom,
            int(pos) if str(pos).isdigit() else 0,
            genes,
            features,
            mas_by_site=mas_site,
            mas_by_gene=mas_gene,
            sprot_by_gene=sprot,
        )
        outliers.append(
            {
                "site": sites[i],
                "chrom": chrom,
                "pos": pos,
                "het": float(het[i]),
                "gene": ann.get("gene") or "",
                "dist": ann.get("dist") or "",
                "strand": ann.get("strand") or "",
                "region": ann.get("region") or "",
                "span": ann.get("span") or "",
                "alias": ann.get("alias") or "",
                "biotype": ann.get("biotype") or "",
                "science_note": ann.get("science_note") or "",
            }
        )
        attach_func_fields(outliers[-1], ann)
    return {
        "het": het,
        "sites": sites,
        "outliers": outliers,
        "n_outlier": len(idxs),
        "q": q,
        "window": window,
    }
