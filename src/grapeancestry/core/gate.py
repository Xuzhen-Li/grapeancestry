"""Genotype concordance for subref vs full mapping gate (Batch 1.5).

Compares two call sets at shared sites (CHROM:POS), normalizing GT to
unordered allele dosage strings (0/0, 0/1, 1/1, ./.).
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


def _norm_gt(gt: str) -> str:
    """Normalize GT to unordered diploid code."""
    if not gt or gt in {".", "./.", ".|."}:
        return "./."
    gt = gt.split(":")[0].replace("|", "/")
    parts = gt.split("/")
    if len(parts) != 2 or any(p == "." for p in parts):
        return "./."
    try:
        a, b = sorted(int(p) for p in parts)
    except ValueError:
        return "./."
    return f"{a}/{b}"


def load_vcf_gt(vcf: Path, sample: str | None = None) -> dict[str, str]:
    """Return {chrom:pos -> norm_gt} for first (or named) sample."""
    samples = subprocess.check_output(["bcftools", "query", "-l", str(vcf)], text=True).splitlines()
    if not samples:
        raise ValueError(f"no samples in {vcf}")
    if sample is None:
        sample = samples[0]
    elif sample not in samples:
        # allow _query suffix
        alt = f"{sample}_query"
        if alt in samples:
            sample = alt
        else:
            raise ValueError(f"sample {sample} not in {vcf}: {samples}")
    fmt = f"%CHROM:%POS[\t%GT]\\n"
    # restrict to one sample
    out = subprocess.check_output(
        ["bcftools", "query", "-s", sample, "-f", fmt, str(vcf)],
        text=True,
    )
    gts: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        key, gt = line.split("\t", 1)
        gts[key] = _norm_gt(gt)
    return gts


def load_matrix_gt(matrix: Path, sample: str) -> dict[str, str]:
    """Load hunage5-style matrix: CHROM POS REF ALT SAMPLE=GT ..."""
    gts: dict[str, str] = {}
    prefix = f"{sample}="
    with matrix.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            chrom, pos = parts[0], parts[1]
            key = f"{chrom}:{pos}"
            gt = "./."
            for cell in parts[4:]:
                if cell.startswith(prefix):
                    gt = _norm_gt(cell.split("=", 1)[1])
                    break
            gts[key] = gt
    return gts


@dataclass
class Concordance:
    n_shared: int
    n_both_called: int
    n_match: int
    n_mismatch: int
    n_missing_a: int
    n_missing_b: int
    concordance: float  # match / both_called
    match_incl_missing: float  # match_or_both_missing / shared

    def as_dict(self) -> dict[str, float | int]:
        return {
            "n_shared": self.n_shared,
            "n_both_called": self.n_both_called,
            "n_match": self.n_match,
            "n_mismatch": self.n_mismatch,
            "n_missing_a": self.n_missing_a,
            "n_missing_b": self.n_missing_b,
            "concordance": self.concordance,
            "match_incl_missing": self.match_incl_missing,
        }


def compare_gts(a: dict[str, str], b: dict[str, str]) -> Concordance:
    keys = sorted(set(a) & set(b))
    n_match = n_mismatch = n_miss_a = n_miss_b = n_both = 0
    n_both_miss_or_match = 0
    for k in keys:
        ga, gb = _norm_gt(a[k]), _norm_gt(b[k])
        a_miss = ga == "./."
        b_miss = gb == "./."
        if a_miss:
            n_miss_a += 1
        if b_miss:
            n_miss_b += 1
        if a_miss or b_miss:
            if a_miss and b_miss:
                n_both_miss_or_match += 1
            continue
        n_both += 1
        if ga == gb:
            n_match += 1
            n_both_miss_or_match += 1
        else:
            n_mismatch += 1
    conc = n_match / n_both if n_both else float("nan")
    incl = n_both_miss_or_match / len(keys) if keys else float("nan")
    return Concordance(
        n_shared=len(keys),
        n_both_called=n_both,
        n_match=n_match,
        n_mismatch=n_mismatch,
        n_missing_a=n_miss_a,
        n_missing_b=n_miss_b,
        concordance=conc,
        match_incl_missing=incl,
    )


def mismatch_table(
    a: dict[str, str], b: dict[str, str], limit: int = 50
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for k in sorted(set(a) & set(b)):
        ga, gb = a[k], b[k]
        if ga == "./." or gb == "./.":
            continue
        if ga != gb:
            rows.append((k, ga, gb))
            if len(rows) >= limit:
                break
    return rows


def decide(concordance: float, threshold: float = 0.99) -> str:
    if concordance != concordance:  # NaN
        return "full"
    return "subref" if concordance >= threshold else "full"


def write_report(
    out_dir: Path,
    rows: list[dict],
    decision: str,
    threshold: float,
    mismatches: list[tuple[str, str, str]] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = out_dir / "concordance.tsv"
    with tsv.open("w", newline="") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t")
            w.writeheader()
            w.writerows(rows)
    summary = out_dir / "gate_decision.txt"
    summary.write_text(
        f"threshold={threshold}\n"
        f"decision={decision}\n"
        f"# decision=subref means enable accelerated subref mapping by default\n"
        f"# decision=full means fall back to full-genome mapping\n"
    )
    if mismatches:
        mm = out_dir / "mismatches_head.tsv"
        with mm.open("w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["site", "gt_a", "gt_b"])
            w.writerows(mismatches)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subref-vcf", type=Path, required=True)
    p.add_argument("--full-vcf", type=Path, required=True)
    p.add_argument("--truth-matrix", type=Path, default=None, help="Optional hunage5 matrix")
    p.add_argument("--sample", default="HUN89")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--threshold", type=float, default=0.99)
    args = p.parse_args(argv)

    sub = load_vcf_gt(args.subref_vcf, args.sample)
    full = load_vcf_gt(args.full_vcf, args.sample)
    c_sf = compare_gts(sub, full)
    rows = [{"comparison": "subref_vs_full", **c_sf.as_dict()}]
    mismatches = mismatch_table(sub, full)

    if args.truth_matrix and args.truth_matrix.exists():
        truth = load_matrix_gt(args.truth_matrix, args.sample)
        rows.append({"comparison": "subref_vs_truth", **compare_gts(sub, truth).as_dict()})
        rows.append({"comparison": "full_vs_truth", **compare_gts(full, truth).as_dict()})

    decision = decide(c_sf.concordance, args.threshold)
    path = write_report(args.out_dir, rows, decision, args.threshold, mismatches)
    print(f"subref_vs_full concordance={c_sf.concordance:.6f} both_called={c_sf.n_both_called}")
    print(f"decision={decision} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
