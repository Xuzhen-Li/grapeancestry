"""Build sub-reference FASTA from VS1 panel loci ±flank.

Merges overlapping windows so the FASTA stays compact (<50MB target),
then extracts with samtools faidx.

Coordinate map written alongside for lifting subref → VS1 coords.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def load_loci(panel_vcf: Path) -> list[tuple[str, int]]:
    """Return (chrom, pos 1-based) from panel VCF via bcftools query."""
    cmd = ["bcftools", "query", "-f", "%CHROM\t%POS\n", str(panel_vcf)]
    out = subprocess.check_output(cmd, text=True)
    loci: list[tuple[str, int]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        chrom, pos_s = line.split("\t")
        loci.append((chrom, int(pos_s)))
    return loci


def windows_to_merged(
    loci: list[tuple[str, int]],
    flank: int,
    chrom_lengths: dict[str, int],
    merge_gap: int = 100,
) -> list[tuple[str, int, int]]:
    """Build ±flank windows (0-based half-open), merge overlaps/near gaps per chrom.

    merge_gap: merge intervals if the gap between them is <= this many bp
    (default 100 keeps FASTA under ~50MB while still covering all loci).
    """
    by_chrom: dict[str, list[tuple[int, int]]] = {}
    for chrom, pos in loci:
        length = chrom_lengths.get(chrom)
        if length is None:
            raise KeyError(f"chrom {chrom} missing from FASTA index")
        start = max(0, pos - 1 - flank)  # 0-based
        end = min(length, pos + flank)  # half-open end
        by_chrom.setdefault(chrom, []).append((start, end))

    merged: list[tuple[str, int, int]] = []
    for chrom, intervals in by_chrom.items():
        intervals.sort()
        cur_s, cur_e = intervals[0]
        for s, e in intervals[1:]:
            if s <= cur_e + merge_gap:
                cur_e = max(cur_e, e)
            else:
                merged.append((chrom, cur_s, cur_e))
                cur_s, cur_e = s, e
        merged.append((chrom, cur_s, cur_e))
    # stable order: numeric chroms first then lexical
    def _key(item: tuple[str, int, int]) -> tuple:
        c, s, _ = item
        return (0, int(c), s) if c.isdigit() else (1, c, s)

    merged.sort(key=_key)
    return merged


def read_fai(fai: Path) -> dict[str, int]:
    lengths: dict[str, int] = {}
    with fai.open() as fh:
        for line in fh:
            parts = line.split("\t")
            lengths[parts[0]] = int(parts[1])
    return lengths


def extract_fasta(
    ref_fa: Path,
    regions: list[tuple[str, int, int]],
    out_fa: Path,
    map_tsv: Path,
) -> None:
    """Extract merged regions via samtools faidx -r; rename headers to chrom_start_end."""
    out_fa.parent.mkdir(parents=True, exist_ok=True)
    regions_txt = out_fa.with_suffix(".regions.txt")
    contig_order: list[tuple[str, str, int, int]] = []  # contig, chrom, start0, end0
    with regions_txt.open("w") as rfh, map_tsv.open("w") as fmap:
        fmap.write("subref_contig\tchrom\tstart0\tend0\tlength\n")
        for chrom, start0, end0 in regions:
            start1 = start0 + 1
            end1 = end0
            contig = f"{chrom}_{start1}_{end1}"
            rfh.write(f"{chrom}:{start1}-{end1}\n")
            contig_order.append((contig, chrom, start0, end0))
            fmap.write(f"{contig}\t{chrom}\t{start0}\t{end0}\t{end0 - start0}\n")

    raw = subprocess.check_output(
        ["samtools", "faidx", str(ref_fa), "-r", str(regions_txt)],
        text=True,
    )
    # Rewrite headers to contig names (order matches regions file)
    with out_fa.open("w") as fout:
        idx = -1
        for line in raw.splitlines():
            if line.startswith(">"):
                idx += 1
                fout.write(f">{contig_order[idx][0]}\n")
            else:
                fout.write(line + "\n")
    regions_txt.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel-vcf", type=Path, required=True)
    p.add_argument("--ref-fa", type=Path, required=True)
    p.add_argument("--out-fa", type=Path, required=True)
    p.add_argument("--out-map", type=Path, required=True)
    p.add_argument("--flank", type=int, default=200)
    p.add_argument("--merge-gap", type=int, default=100)
    args = p.parse_args(argv)

    fai = Path(str(args.ref_fa) + ".fai")
    if not fai.exists():
        subprocess.check_call(["samtools", "faidx", str(args.ref_fa)])

    loci = load_loci(args.panel_vcf)
    lengths = read_fai(fai)
    regions = windows_to_merged(loci, args.flank, lengths, merge_gap=args.merge_gap)
    extract_fasta(args.ref_fa, regions, args.out_fa, args.out_map)

    size_mb = args.out_fa.stat().st_size / (1024 * 1024)
    print(
        f"loci={len(loci)} merged_regions={len(regions)} "
        f"out={args.out_fa} size_mb={size_mb:.2f}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
