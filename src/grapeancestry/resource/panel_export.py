"""Export a custom capture sub-panel (BED / probe-list TSV)."""

from __future__ import annotations

from pathlib import Path


def sites_to_bed(sites: list[str], out_bed: Path, flank: int = 0) -> Path:
    out_bed.parent.mkdir(parents=True, exist_ok=True)
    with out_bed.open("w") as fh:
        for s in sites:
            chrom, _, pos = s.partition(":")
            p = int(pos)
            fh.write(f"{chrom}\t{max(0, p - 1 - flank)}\t{p + flank}\t{s}\n")
    return out_bed


def sites_to_probe_tsv(sites: list[str], out_tsv: Path) -> Path:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w") as fh:
        fh.write("site\tchrom\tpos\n")
        for s in sites:
            chrom, _, pos = s.partition(":")
            fh.write(f"{s}\t{chrom}\t{pos}\n")
    return out_tsv
