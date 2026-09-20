"""mapDamage2 reader + BAM fallback for 5′ C→T / 3′ G→A.

mapDamage2 (Ginolhac et al. 2011 Bioinformatics 27:2153–2155,
doi:10.1093/bioinformatics/btr347; Jónsson et al. 2013 Bioinformatics
29:1682–1684, doi:10.1093/bioinformatics/btt193;
https://ginolhac.github.io/mapDamage/).
Lite fallback does not require the mapDamage binary.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import pysam

# mapDamage misincorporation.txt substitution columns (ref>read).
_SUBS = (
    "C>T",
    "G>A",
    "A>G",
    "T>C",
    "A>C",
    "A>T",
    "C>G",
    "C>A",
    "T>G",
    "T>A",
    "G>C",
    "G>T",
)
_BASE_FOR = {s: s[0] for s in _SUBS}


def lite_damage_profile(
    bam: Path,
    ref_fa: Path,
    max_reads: int = 200_000,
    window: int = 25,
) -> dict:
    """5′ C→T and 3′ G→A from BAM (mapDamage-style strand rule).

    BAM query[0] = 5′ of the sequenced read. +strand: 5′ C→T, 3′ G→A.
    −strand: 5′ G→A, 3′ C→T (do not reverse/complement again).
    ``ref_fa`` is unused; pysam uses the BAM MD/reference sequence.
    """
    del ref_fa
    ct = [0] * window
    c_tot = [0] * window
    ga = [0] * window
    g_tot = [0] * window
    n = 0
    with pysam.AlignmentFile(str(bam), "rb") as af:
        for read in af.fetch(until_eof=True):
            if read.is_unmapped or read.is_secondary or read.is_supplementary:
                continue
            if read.is_duplicate:
                continue
            try:
                refseq = read.get_reference_sequence().upper()
            except ValueError:
                continue
            qseq = (read.query_sequence or "").upper()
            L = min(len(qseq), len(refseq))
            if L < 1:
                continue
            n5 = min(L, window)
            if read.is_reverse:
                for i in range(n5):
                    rb, qb = refseq[i], qseq[i]
                    if rb == "G":
                        c_tot[i] += 1
                        if qb == "A":
                            ct[i] += 1
            else:
                for i in range(n5):
                    rb, qb = refseq[i], qseq[i]
                    if rb == "C":
                        c_tot[i] += 1
                        if qb == "T":
                            ct[i] += 1
            n3 = min(L, window)
            if read.is_reverse:
                for i in range(n3):
                    j = L - 1 - i
                    rb, qb = refseq[j], qseq[j]
                    if rb == "C":
                        g_tot[i] += 1
                        if qb == "T":
                            ga[i] += 1
            else:
                for i in range(n3):
                    j = L - 1 - i
                    rb, qb = refseq[j], qseq[j]
                    if rb == "G":
                        g_tot[i] += 1
                        if qb == "A":
                            ga[i] += 1
            n += 1
            if n >= max_reads:
                break
    return {
        "source": "damage_lite",
        "version": "",
        "ct5": [ct[i] / c_tot[i] if c_tot[i] else 0.0 for i in range(window)],
        "ga3": [ga[i] / g_tot[i] if g_tot[i] else 0.0 for i in range(window)],
        "subs5": {},
        "subs3": {},
        "length": [],
    }


def c_to_t_profile(
    bam: Path,
    ref_fa: Path,
    max_reads: int = 200_000,
    window: int = 25,
) -> list[float]:
    """Return 5′ C→T frequencies (backward-compatible wrapper)."""
    return lite_damage_profile(bam, ref_fa, max_reads=max_reads, window=window)["ct5"]


def write_damage_tsv(
    freqs: list[float],
    out_tsv: Path,
    ga3: list[float] | None = None,
) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w") as fh:
        if ga3:
            n = max(len(freqs), len(ga3))
            fh.write("pos\tfreq_CtoT_5p\tfreq_GtoA_3p\n")
            for i in range(n):
                ct = freqs[i] if i < len(freqs) else float("nan")
                ga = ga3[i] if i < len(ga3) else float("nan")
                fh.write(f"{i + 1}\t{ct:.6f}\t{ga:.6f}\n")
        else:
            fh.write("pos5p\tfreq_CtoT\n")
            for i, f in enumerate(freqs, 1):
                fh.write(f"{i}\t{f:.6f}\n")


def read_damage_tsv(path: Path) -> dict | None:
    """Read lite or mapDamage-exported TSV (2 or 3 columns)."""
    if not path.exists():
        return None
    ct5: list[float] = []
    ga3: list[float] = []
    with path.open() as fh:
        header = fh.readline()
        if not header:
            return None
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                ct5.append(float(parts[1]))
            except ValueError:
                continue
            if len(parts) >= 3:
                try:
                    ga3.append(float(parts[2]))
                except ValueError:
                    ga3.append(0.0)
    if not ct5:
        return None
    return {
        "source": "tsv",
        "version": "",
        "ct5": ct5,
        "ga3": ga3,
        "subs5": {},
        "subs3": {},
        "length": [],
    }


def run_mapdamage(bam: Path, ref_fa: Path, out_dir: Path) -> Path:
    """Run mapDamage2 on markdup BAM; return output directory.

    Requires `mapDamage` on PATH (conda: mapdamage2).
    Source: https://ginolhac.github.io/mapDamage/
    Skips if out_dir already has misincorporation.txt / 5pCtoT_freq.txt.
    """
    import shutil
    import subprocess

    out_dir = Path(out_dir)
    if (
        (out_dir / "misincorporation.txt").exists()
        or (out_dir / "5pCtoT_freq.txt").exists()
        or any(out_dir.rglob("misincorporation.txt")) if out_dir.exists() else False
    ):
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = shutil.which("mapDamage") or shutil.which("mapDamage2")
    if not exe:
        raise FileNotFoundError("mapDamage not found on PATH")
    cmd = [
        exe,
        "-i",
        str(bam),
        "-r",
        str(ref_fa),
        "-d",
        str(out_dir),
        "--no-stats",
    ]
    subprocess.check_call(cmd)
    return out_dir


def _read_freq_file(path: Path, window: int) -> list[float]:
    freqs: list[float] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("pos"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                freqs.append(float(parts[1]))
            except ValueError:
                continue
            if len(freqs) >= window:
                break
    return freqs


def _mapdamage_version(root: Path) -> str:
    for name in ("Runtime_log.txt", "misincorporation.txt", "5pCtoT_freq.txt"):
        p = root / name
        if not p.exists():
            hits = list(root.rglob(name))
            p = hits[0] if hits else p
        if not p.exists():
            continue
        try:
            head = p.read_text(errors="replace")[:800]
        except OSError:
            continue
        m = re.search(r"mapDamage version\s+([0-9.]+)", head, re.I)
        if m:
            return m.group(1)
    return ""


def _parse_misincorporation(path: Path, window: int) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    """Aggregate mapDamage misincorporation.txt to per-position frequencies.

    Frequency of X>Y = count(X>Y) / count(base X), summed over chromosomes and strands.
    """
    acc5: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    acc3: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with path.open() as fh:
        header = None
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            header = line.rstrip("\n").split("\t")
            break
        if not header:
            return {}, {}
        col = {h: i for i, h in enumerate(header)}
        need = ["End", "Pos", "A", "C", "G", "T"]
        if any(k not in col for k in need):
            return {}, {}
        sub_i = {s: col[s] for s in _SUBS if s in col}
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            mx = max(col["End"], col["Pos"], col["A"], col["C"], col["G"], col["T"])
            if len(parts) <= mx:
                continue
            try:
                pos = int(parts[col["Pos"]])
            except ValueError:
                continue
            if pos < 1 or pos > window:
                continue
            end = parts[col["End"]]
            bucket = acc5 if end.startswith("5") else acc3 if end.startswith("3") else None
            if bucket is None:
                continue
            row = bucket[pos]
            for b in ("A", "C", "G", "T"):
                try:
                    row[b] += int(float(parts[col[b]]))
                except ValueError:
                    pass
            for s, i in sub_i.items():
                if i >= len(parts):
                    continue
                try:
                    row[s] += int(float(parts[i]))
                except ValueError:
                    pass

    def _freqs(acc: dict[int, dict[str, int]]) -> dict[str, list[float]]:
        out = {s: [] for s in _SUBS}
        for pos in range(1, window + 1):
            row = acc.get(pos, {})
            for s in _SUBS:
                den = float(row.get(_BASE_FOR[s], 0))
                num = float(row.get(s, 0))
                out[s].append(num / den if den else 0.0)
        return out

    return _freqs(acc5), _freqs(acc3)


def _parse_length(path: Path) -> list[dict]:
    by_len: dict[int, int] = defaultdict(int)
    with path.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith("#") or line.lower().startswith("std"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                length = int(parts[1])
                n = int(float(parts[2]))
            except ValueError:
                continue
            by_len[length] += n
    return [{"len": k, "n": by_len[k]} for k in sorted(by_len)]


def read_mapdamage_profile(mapdmg_dir: Path, window: int = 25) -> dict | None:
    """Full mapDamage2 profile: 5′ C→T, 3′ G→A, other substitutions, length.

    Prefers ``5pCtoT_freq.txt`` / ``3pGtoA_freq.txt``; fills the remaining
    substitution lines from ``misincorporation.txt`` when present.
    """
    root = Path(mapdmg_dir)
    if not root.exists():
        return None
    ct_files = list(root.rglob("5pCtoT_freq.txt"))
    ga_files = list(root.rglob("3pGtoA_freq.txt"))
    ct5 = _read_freq_file(ct_files[0], window) if ct_files else []
    ga3 = _read_freq_file(ga_files[0], window) if ga_files else []
    subs5: dict[str, list[float]] = {}
    subs3: dict[str, list[float]] = {}
    misc = list(root.rglob("misincorporation.txt"))
    if misc:
        subs5, subs3 = _parse_misincorporation(misc[0], window)
        if not ct5 and subs5.get("C>T"):
            ct5 = list(subs5["C>T"])
        if not ga3 and subs3.get("G>A"):
            ga3 = list(subs3["G>A"])
    if not ct5 and not ga3:
        return None
    length: list[dict] = []
    lg = list(root.rglob("lgdistribution.txt"))
    if lg:
        length = _parse_length(lg[0])
    if ct5 and "C>T" not in subs5:
        subs5["C>T"] = list(ct5)
    if ga3 and "G>A" not in subs3:
        subs3["G>A"] = list(ga3)
    ver = _mapdamage_version(root)
    return {
        "source": "mapDamage2",
        "version": ver,
        "ct5": ct5[:window],
        "ga3": ga3[:window],
        "subs5": subs5,
        "subs3": subs3,
        "length": length,
    }


def read_mapdamage_freqs(mapdmg_dir: Path, window: int = 25) -> list[float] | None:
    """Parse mapDamage 5p C→T freqs (backward-compatible)."""
    prof = read_mapdamage_profile(mapdmg_dir, window=window)
    if not prof or not prof.get("ct5"):
        return None
    return list(prof["ct5"])


def load_sample_damage(
    root: Path,
    sample: str,
    *,
    tsv: Path | None = None,
    window: int = 25,
) -> dict | None:
    """Prefer ``results/{sample}.mapDamage/``, else ``{sample}.damage.tsv``."""
    mapdir = root / "results" / f"{sample}.mapDamage"
    tsv_path = Path(tsv) if tsv else root / "results" / f"{sample}.damage.tsv"
    if mapdir.exists():
        prof = read_mapdamage_profile(mapdir, window=window)
        if prof and (prof.get("ct5") or prof.get("ga3")):
            return prof
    if tsv_path.exists():
        return read_damage_tsv(tsv_path)
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bam", type=Path, required=True)
    p.add_argument("--ref", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-reads", type=int, default=100_000)
    p.add_argument("--window", type=int, default=25)
    args = p.parse_args(argv)
    prof = lite_damage_profile(args.bam, args.ref, max_reads=args.max_reads, window=args.window)
    write_damage_tsv(prof["ct5"], args.out, ga3=prof.get("ga3"))
    ga = prof.get("ga3") or [0.0]
    print(f"wrote {args.out} 5pC>T={prof['ct5'][0]:.4f} 3pG>A={ga[0]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
