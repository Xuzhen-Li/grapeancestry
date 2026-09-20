"""Read VS-1 FASTA windows via the .fai index (no pysam)."""

from __future__ import annotations

from pathlib import Path

_COMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def load_fai(fai: Path) -> dict[str, tuple[int, int, int, int]]:
    """chrom → (length, byte_offset, linebases, linewidth)."""
    out: dict[str, tuple[int, int, int, int]] = {}
    with fai.open() as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 5:
                continue
            out[p[0]] = (int(p[1]), int(p[2]), int(p[3]), int(p[4]))
    return out


def fetch_fa(fa: Path, chrom: str, start: int, end: int, index: dict[str, tuple[int, int, int, int]] | None = None) -> str:
    """1-based inclusive fetch. ``start``/``end`` clipped to chromosome."""
    index = index or load_fai(Path(str(fa) + ".fai"))
    if chrom not in index:
        raise KeyError(f"chrom {chrom} not in {fa}.fai")
    length, offset, linebases, linewidth = index[chrom]
    start = max(1, start)
    end = min(length, end)
    if end < start:
        return ""
    # byte of first base (0-based coordinate start-1)
    def byte_of(pos0: int) -> int:
        row, col = divmod(pos0, linebases)
        return offset + row * linewidth + col

    a = byte_of(start - 1)
    b = byte_of(end - 1)
    with fa.open("rb") as fh:
        fh.seek(a)
        raw = fh.read(b - a + 1)
    seq = raw.replace(b"\n", b"").decode("ascii")
    return seq.upper()


def revcomp(seq: str) -> str:
    return seq.translate(_COMP)[::-1]


def window_with_alt(
    ref_seq: str,
    *,
    offset: int,
    ref: str,
    alt: str,
) -> tuple[str, str]:
    """Replace the SNP base at ``offset`` (0-based in ref_seq)."""
    if offset < 0 or offset >= len(ref_seq):
        raise ValueError("SNP offset outside window")
    observed = ref_seq[offset]
    if observed != ref.upper() and observed != "N":
        # still build alt from observed if REF in VCF disagrees — keep both strings
        pass
    alt_seq = ref_seq[:offset] + alt.upper() + ref_seq[offset + 1 :]
    return ref_seq, alt_seq
