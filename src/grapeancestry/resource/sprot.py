"""Functional homology table for VS-1 ``Vvsyl*`` genes.

SwissProt hits: DIAMOND blastp of NGDC ``GWHBQCW00000000.Protein.faa.gz`` vs
UniProt SwissProt (https://www.uniprot.org/help/uniprotkb). GO / Pfam / KEGG /
InterPro / EC are UniProt xrefs of that hit (homology, not Dong GFF).

Grape IDs: Ensembl Plants ``Vitis_vinifera.ASM3070453v1`` pep
(https://plants.ensembl.org/Vitis_vinifera/Info/Index) plus Entrez / RefSeq
TSV and KEGG ``vvi`` (https://www.kegg.jp/kegg/rest/keggapi.html).
"""

from __future__ import annotations

from pathlib import Path

FUNC_KEYS = (
    "go",
    "pfam",
    "kegg",
    "interpro",
    "ec",
    "vitis_id",
    "vitis_symbol",
    "vitis_desc",
    "ensembl_pident",
    "ncbi_geneid",
    "ncbi_symbol",
    "ncbi_desc",
    "kegg_vvi",
    "refseq",
)

_SPROT_KEYS = (
    "uniprot",
    "gn",
    "product",
    "organism",
    "pident",
    "evalue",
    "bitscore",
)


def load_swissprot_table(
    path: Path,
    *,
    min_bits: float = 100.0,
) -> dict[str, dict[str, str]]:
    """``gene_id → SwissProt + optional GO/Pfam/Ensembl/NCBI/KEGG fields``."""
    table: dict[str, dict[str, str]] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            row = dict(zip(hdr, parts))
            gid = row.get("gene_id") or ""
            if not gid:
                continue
            uniprot = row.get("uniprot") or ""
            try:
                bits = float(row.get("bitscore") or 0)
            except ValueError:
                bits = 0.0
            if uniprot and bits < min_bits:
                continue
            if not uniprot and not (row.get("vitis_id") or row.get("ncbi_geneid")):
                continue
            rec = {k: row.get(k) or "" for k in _SPROT_KEYS}
            rec["uniprot"] = uniprot
            for k in FUNC_KEYS:
                rec[k] = row.get(k) or ""
            table[gid] = rec
    return table


def load_gene_func(root: Path, *, min_bits: float = 100.0) -> dict[str, dict[str, str]]:
    """Prefer merged ``vs1_func.tsv``; else SwissProt-only table."""
    root = Path(root)
    func = root / "data" / "ref" / "vs1_func.tsv"
    sprot = root / "data" / "ref" / "vs1_swissprot.tsv"
    return load_swissprot_table(func if func.exists() else sprot, min_bits=min_bits)


def apply_swissprot(out: dict[str, str], hit: dict[str, str] | None) -> dict[str, str]:
    """Fill product + DB xrefs; Vitis GN / Ensembl / NCBI may fill empty alias."""
    out.setdefault("product", "")
    out.setdefault("uniprot", "")
    out.setdefault("sprot_gn", "")
    out.setdefault("sprot_pident", "")
    out.setdefault("sprot_organism", "")
    for k in FUNC_KEYS:
        out.setdefault(k, "")
    if not hit:
        return out
    out["uniprot"] = hit.get("uniprot") or ""
    out["sprot_gn"] = hit.get("gn") or ""
    out["sprot_pident"] = hit.get("pident") or ""
    out["sprot_organism"] = hit.get("organism") or ""
    out["product"] = (
        hit.get("product")
        or hit.get("vitis_desc")
        or hit.get("ncbi_desc")
        or ""
    )
    for k in FUNC_KEYS:
        out[k] = hit.get(k) or ""
    gn = hit.get("gn") or ""
    org = (hit.get("organism") or "").lower()
    if not out.get("alias"):
        if gn and "vitis vinifera" in org:
            out["alias"] = gn
        elif hit.get("vitis_symbol"):
            out["alias"] = hit["vitis_symbol"]
        else:
            ns = hit.get("ncbi_symbol") or ""
            if ns and not ns.startswith("LOC"):
                out["alias"] = ns
    return out


def attach_func_fields(row: dict, ann: dict, *, prefix: str = "") -> dict:
    """Copy product / xref keys onto a report row (``prefix='top_'`` for GWAS)."""
    for k in ("product", "uniprot", "sprot_gn", "sprot_pident", "sprot_organism") + FUNC_KEYS:
        row[f"{prefix}{k}"] = ann.get(k) or ""
    return row
