"""Nearest-gene lookup from GFF3 (panel locus portal enrichment)."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Gene:
    chrom: str
    start: int  # 1-based inclusive
    end: int
    gene_id: str
    strand: str = "."
    biotype: str = ""


def _attr_map(attrs: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in attrs.split(";"):
        if "=" not in tok:
            continue
        key, val = tok.split("=", 1)
        out[key] = val
    return out


def _gene_id_from_parent(parent: str) -> str:
    p = parent.split(",")[0].strip()
    if ".t" in p:
        return p.rsplit(".t", 1)[0]
    return p


def load_genes(gff: Path, feature: str = "gene") -> dict[str, list[Gene]]:
    """Parse GFF3 gene features → chrom → sorted by start."""
    genes, _features = load_gene_annotation(gff, gene_feature=feature)
    return genes


def load_gene_annotation(
    gff: Path,
    gene_feature: str = "gene",
) -> tuple[dict[str, list[Gene]], dict[str, dict[str, list[tuple[int, int]]]]]:
    """One-pass GFF3: genes plus CDS / UTR intervals keyed by gene ID.

    VS1.final.gff3 gene ``Name=`` is the biotype (protein_coding), not a
    product name (Dong VS-1 GFF; no Note/GO/Alias in that file).
    """
    by_chrom: dict[str, list[Gene]] = {}
    features: dict[str, dict[str, list[tuple[int, int]]]] = {}
    kind_map = {
        "CDS": "cds",
        "five_prime_UTR": "utr5",
        "three_prime_UTR": "utr3",
    }
    with gff.open() as fh:
        for line in fh:
            if not line or line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 9:
                continue
            ftype = p[2]
            chrom, start, end, attrs = p[0], int(p[3]), int(p[4]), p[8]
            amap = _attr_map(attrs)
            if ftype == gene_feature:
                gid = amap.get("ID") or ""
                if not gid:
                    continue
                by_chrom.setdefault(chrom, []).append(
                    Gene(
                        chrom,
                        start,
                        end,
                        gid,
                        strand=p[6] or ".",
                        biotype=amap.get("Name") or "",
                    )
                )
                continue
            kind = kind_map.get(ftype)
            if not kind:
                continue
            parent = amap.get("Parent") or ""
            gid = _gene_id_from_parent(parent) if parent else ""
            if not gid:
                continue
            bucket = features.setdefault(gid, {"cds": [], "utr5": [], "utr3": []})
            bucket[kind].append((start, end))
    for chrom in by_chrom:
        by_chrom[chrom].sort(key=lambda g: g.start)
    return by_chrom, features


def classify_region(
    pos: int,
    gene: Gene,
    feats: dict[str, list[tuple[int, int]]] | None,
) -> str:
    """CDS / UTR / intron / flanking. Empty feats inside a gene → ``gene``."""
    if not (gene.start <= pos <= gene.end):
        return "flanking"
    if not feats:
        return "gene"
    for s, e in feats.get("cds") or ():
        if s <= pos <= e:
            return "CDS"
    for s, e in feats.get("utr5") or ():
        if s <= pos <= e:
            return "UTR5"
    for s, e in feats.get("utr3") or ():
        if s <= pos <= e:
            return "UTR3"
    return "intron"


def nearest_gene_obj(
    chrom: str,
    pos: int,
    genes: dict[str, list[Gene]],
    max_dist: int = 50_000,
) -> tuple[Gene, int] | None:
    """Return (Gene, signed_distance) or None if farther than max_dist.

    Distance 0 = within gene; negative = gene upstream of pos; positive = downstream.
    """
    lst = genes.get(chrom) or genes.get(chrom.lstrip("chr"))
    if not lst:
        return None
    starts = [g.start for g in lst]
    i = bisect_right(starts, pos) - 1
    best: tuple[Gene, int] | None = None
    best_abs = max_dist + 1
    for j in (i, i + 1):
        if j < 0 or j >= len(lst):
            continue
        g = lst[j]
        if g.start <= pos <= g.end:
            return g, 0
        if pos < g.start:
            d = g.start - pos
            signed = d
        else:
            d = pos - g.end
            signed = -d
        if d < best_abs:
            best_abs = d
            best = (g, signed)
    if best is None or best_abs > max_dist:
        return None
    return best


def nearest_gene(
    chrom: str,
    pos: int,
    genes: dict[str, list[Gene]],
    max_dist: int = 50_000,
) -> tuple[str, int] | None:
    """Return (gene_id, signed_distance) or None if farther than max_dist.

    Distance 0 = within gene; negative = gene upstream of pos; positive = downstream.
    """
    hit = nearest_gene_obj(chrom, pos, genes, max_dist=max_dist)
    if hit is None:
        return None
    return hit[0].gene_id, hit[1]


def annotate_site(
    chrom: str,
    pos: int,
    genes: dict[str, list[Gene]] | None,
    features: dict[str, dict[str, list[tuple[int, int]]]] | None = None,
    *,
    max_dist: int = 50_000,
    mas_by_site: dict[str, dict] | None = None,
    mas_by_gene: dict[str, dict] | None = None,
    sprot_by_gene: dict[str, dict] | None = None,
) -> dict[str, str]:
    """Structural annotation + optional Dong 2023 MAS alias/note + func xrefs."""
    from grapeancestry.resource.sprot import FUNC_KEYS, apply_swissprot

    site = f"{chrom}:{pos}"
    out = {
        "gene": "",
        "dist": "",
        "strand": "",
        "biotype": "",
        "span": "",
        "region": "",
        "n_cds": "",
        "alias": "",
        "science_note": "",
        "product": "",
        "uniprot": "",
        "sprot_gn": "",
        "sprot_pident": "",
        "sprot_organism": "",
    }
    for k in FUNC_KEYS:
        out[k] = ""
    if genes:
        hit = nearest_gene_obj(chrom, pos, genes, max_dist=max_dist)
        if hit:
            g, dist = hit
            feats = (features or {}).get(g.gene_id) or {}
            out["gene"] = g.gene_id
            out["dist"] = str(dist)
            out["strand"] = g.strand
            out["biotype"] = g.biotype
            out["span"] = f"{g.chrom}:{g.start}-{g.end}"
            out["n_cds"] = str(len(feats.get("cds") or []))
            out["region"] = classify_region(pos, g, feats)
        else:
            out["region"] = "intergenic"
    mas = (mas_by_site or {}).get(site)
    if mas is None and out["gene"]:
        mas = (mas_by_gene or {}).get(out["gene"])
    if mas:
        alias = str(mas.get("gene") or "")
        if alias and alias != out["gene"]:
            out["alias"] = alias
        out["science_note"] = str(mas.get("note") or "")
    if out["gene"] and sprot_by_gene:
        apply_swissprot(out, sprot_by_gene.get(out["gene"]))
    return out
