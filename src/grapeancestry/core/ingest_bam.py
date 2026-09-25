"""Ingest a user BAM already claimed to be on VS-1."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def load_fai_contigs(fai: Path) -> list[str]:
    names: list[str] = []
    for line in fai.read_text().splitlines():
        if line.strip():
            names.append(line.split()[0])
    return names


def bam_sq_names(bam: Path) -> list[str]:
    header = subprocess.check_output(["samtools", "view", "-H", str(bam)], text=True)
    names: list[str] = []
    for line in header.splitlines():
        if not line.startswith("@SQ"):
            continue
        for field in line.split("\t"):
            if field.startswith("SN:"):
                names.append(field[3:])
    return names


def contig_mismatch_message(fa_names: list[str], sq_names: list[str]) -> str | None:
    fa = set(fa_names)
    sq = set(sq_names)
    if not fa:
        return "empty FASTA index"
    if not sq:
        return "BAM has no @SQ header. Index it or provide FASTQ."
    if fa & sq:
        return None
    bam_ex = ", ".join(sorted(sq)[:8])
    vs1_ex = ", ".join(sorted(fa)[:8])
    return (
        "BAM @SQ does not match VS-1. "
        f"BAM examples: {bam_ex}. VS-1 examples: {vs1_ex}. "
        "This usually means 12X / PN40024 / chr-prefixed contigs. "
        "Re-align to VS-1 or start from FASTQ."
    )


def assert_vs1_compatible(bam: Path, fai: Path) -> None:
    """Fail if BAM @SQ does not overlap VS-1 contig names."""
    msg = contig_mismatch_message(load_fai_contigs(fai), bam_sq_names(bam))
    if msg:
        raise ValueError(msg)


def stage_bam(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check VS-1 contigs and copy a BAM.")
    parser.add_argument("--in-bam", required=True)
    parser.add_argument("--out-bam", required=True)
    parser.add_argument("--ref-fai", required=True)
    args = parser.parse_args(argv)
    src = Path(args.in_bam)
    dest = Path(args.out_bam)
    fai = Path(args.ref_fai)
    assert_vs1_compatible(src, fai)
    stage_bam(src, dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
