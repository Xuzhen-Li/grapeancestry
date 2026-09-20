"""Lift alignments from sub-reference contigs back to VS1 coordinates.

Subref contig naming: {chrom}_{start1}_{end1} (1-based inclusive ends),
matching grapeancestry.core.subref output / map TSV.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pysam

_CONTIG_RE = re.compile(r"^(.+)_(\d+)_(\d+)$")


def parse_contig(name: str) -> tuple[str, int, int] | None:
    """Return (chrom, start0, end0_half_open) or None if not a subref contig."""
    m = _CONTIG_RE.match(name)
    if not m:
        return None
    chrom, start1_s, end1_s = m.group(1), m.group(2), m.group(3)
    start1, end1 = int(start1_s), int(end1_s)
    return chrom, start1 - 1, end1


def resolve(name: str, map_table: dict[str, tuple[str, int, int]]) -> tuple[str, int, int]:
    info = map_table.get(name) or parse_contig(name)
    if info is None:
        raise ValueError(f"unknown subref contig: {name}")
    return info


def load_map(map_tsv: Path) -> dict[str, tuple[str, int, int]]:
    """contig -> (chrom, start0, end0)."""
    out: dict[str, tuple[str, int, int]] = {}
    with map_tsv.open() as fh:
        header = fh.readline()
        if not header.startswith("subref_contig"):
            fh.seek(0)
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            contig, chrom, s0, e0 = parts[0], parts[1], int(parts[2]), int(parts[3])
            out[contig] = (chrom, s0, e0)
    return out


def build_header(src: pysam.AlignmentFile, ref_fai: Path) -> pysam.AlignmentHeader:
    """VS1-style header from .fai lengths; keep @PG/@RG from source."""
    lengths: dict[str, int] = {}
    with ref_fai.open() as fh:
        for line in fh:
            name, length, *_ = line.split("\t")
            lengths[name] = int(length)
    sq = [{"SN": n, "LN": lengths[n]} for n in lengths]
    hd = src.header.to_dict()
    hd["SQ"] = sq
    return pysam.AlignmentHeader.from_dict(hd)


def lift_bam(in_bam: Path, out_bam: Path, map_tsv: Path, ref_fai: Path) -> None:
    map_table = load_map(map_tsv)
    with pysam.AlignmentFile(str(in_bam), "rb") as src:
        header = build_header(src, ref_fai)
        with pysam.AlignmentFile(str(out_bam), "wb", header=header) as dst:
            for read in src:
                # Capture source contig names BEFORE mutating the read
                src_contig = (
                    src.get_reference_name(read.reference_id)
                    if read.reference_id >= 0
                    else None
                )
                mate_contig = (
                    src.get_reference_name(read.next_reference_id)
                    if read.next_reference_id >= 0
                    else None
                )
                local_start = read.reference_start
                local_mate = read.next_reference_start

                if src_contig is not None and not read.is_unmapped:
                    chrom, start0, _ = resolve(src_contig, map_table)
                    tid = header.get_tid(chrom)
                    if tid < 0:
                        raise ValueError(f"chrom not in VS1 header: {chrom}")
                    read.reference_id = tid
                    read.reference_start = start0 + local_start
                else:
                    read.reference_id = -1

                if mate_contig is not None and not read.mate_is_unmapped:
                    chrom, start0, _ = resolve(mate_contig, map_table)
                    tid = header.get_tid(chrom)
                    if tid < 0:
                        raise ValueError(f"mate chrom not in VS1 header: {chrom}")
                    read.next_reference_id = tid
                    read.next_reference_start = start0 + local_mate
                else:
                    read.next_reference_id = -1

                dst.write(read)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in-bam", type=Path, required=True)
    p.add_argument("--out-bam", type=Path, required=True)
    p.add_argument("--map", type=Path, required=True)
    p.add_argument("--ref-fai", type=Path, required=True)
    args = p.parse_args(argv)
    lift_bam(args.in_bam, args.out_bam, args.map, args.ref_fai)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
