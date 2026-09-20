"""Outbound database URLs for gene annotation IDs.

Templates follow each database’s public record pages (not search boxes):
- UniProtKB https://www.uniprot.org/help/uniprotkb
- QuickGO https://www.ebi.ac.uk/QuickGO/
- InterPro (Pfam + InterPro) https://www.ebi.ac.uk/interpro/
- KEGG entry https://www.kegg.jp/kegg/kegg1.html
- Ensembl Plants search https://plants.ensembl.org/Vitis_vinifera/Info/Index
  (``Gene/Summary?g=`` returns HTTP 422 for ASM3070453v1 pep IDs like ``Vitis19g01394``;
  ``Psychic?q=`` resolves the same IDs)
- NCBI Gene https://www.ncbi.nlm.nih.gov/gene
- NCBI Protein https://www.ncbi.nlm.nih.gov/protein
- Expasy ENZYME https://enzyme.expasy.org/
- EU-Vitis OIV descriptor PDFs http://www.eu-vitis.de/docs/descriptors/oivdesc/
- OIV Descriptor List 2nd ed. https://www.oiv.int/node/2830
"""

from __future__ import annotations

import re

_OK = re.compile(r"^[A-Za-z0-9_.:-]+$")

# Dashboard JS ``dbHref`` must keep these prefixes in sync.
URLS = {
    "uniprot": "https://www.uniprot.org/uniprotkb/{id}",
    "go": "https://www.ebi.ac.uk/QuickGO/term/{id}",
    "pfam": "https://www.ebi.ac.uk/interpro/entry/pfam/{id}",
    "interpro": "https://www.ebi.ac.uk/interpro/entry/InterPro/{id}",
    "kegg": "https://www.kegg.jp/entry/{id}",
    "ensembl": "https://plants.ensembl.org/Vitis_vinifera/Psychic?q={id}",
    "ncbi": "https://www.ncbi.nlm.nih.gov/gene/{id}",
    "refseq": "https://www.ncbi.nlm.nih.gov/protein/{id}",
    "ec": "https://enzyme.expasy.org/EC/{id}",
    "oiv": "http://www.eu-vitis.de/docs/descriptors/oivdesc/OIV%20{id}.pdf",
    "oiv_list": "https://www.oiv.int/node/2830",
}


def db_url(kind: str, identifier: str) -> str:
    """Return the record URL, or empty if the ID is not a safe token."""
    ident = (identifier or "").strip()
    tmpl = URLS.get(kind or "")
    if not tmpl:
        return ""
    if "{id}" not in tmpl:
        return tmpl
    if not ident or not _OK.match(ident):
        return ""
    if kind == "ensembl" and ident.lower().startswith("vvsyl"):
        return ""
    return tmpl.format(id=ident)
