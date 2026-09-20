"""Enrichment / on-target QC + panel-site & VCF calling metrics.

BAM/BED via samtools bedcov; VCF via bcftools query (GT + DP).
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import subprocess
from pathlib import Path


def bed_total_bases(bed: Path) -> int:
    total = 0
    with bed.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            _c, start, end, *_ = line.split("\t")
            total += int(end) - int(start)
    return total


def bed_n_intervals(bed: Path) -> int:
    n = 0
    with bed.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            n += 1
    return n


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def summarize_bedcov(bedcov_text: str) -> dict[str, float]:
    """Aggregate samtools bedcov lines into panel coverage / depth stats.

    For 1 bp panel sites, interval length=1 and depth_sum == site depth.
    """
    depths: list[float] = []
    covered_1 = covered_5 = covered_10 = 0
    target_bases = 0
    depth_sum_all = 0.0
    for line in bedcov_text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        start, end = int(parts[1]), int(parts[2])
        length = end - start
        d_sum = float(parts[3])
        target_bases += length
        mean_d = d_sum / length if length else 0.0
        depths.append(mean_d)
        depth_sum_all += d_sum
        if mean_d >= 1:
            covered_1 += 1
        if mean_d >= 5:
            covered_5 += 1
        if mean_d >= 10:
            covered_10 += 1

    n_sites = float(len(depths))
    mean_depth = depth_sum_all / target_bases if target_bases else 0.0
    median_depth = float(statistics.median(depths)) if depths else 0.0
    covered_depths = [d for d in depths if d >= 1]
    mean_depth_covered = (
        float(sum(covered_depths) / len(covered_depths)) if covered_depths else 0.0
    )
    return {
        "n_panel_sites": n_sites,
        "target_bases": float(target_bases),
        "n_covered_1x": float(covered_1),
        "n_covered_5x": float(covered_5),
        "n_covered_10x": float(covered_10),
        "pct_covered_1x": 100.0 * covered_1 / n_sites if n_sites else 0.0,
        "pct_covered_5x": 100.0 * covered_5 / n_sites if n_sites else 0.0,
        "pct_covered_10x": 100.0 * covered_10 / n_sites if n_sites else 0.0,
        "mean_depth": mean_depth,
        "median_depth": median_depth,
        "mean_depth_covered": mean_depth_covered,
        # legacy fraction (same as pct/100 for 1bp BED)
        "breadth_1x": covered_1 / n_sites if n_sites else 0.0,
        "breadth_5x": covered_5 / n_sites if n_sites else 0.0,
    }


def qc_bam(bam: Path, bed: Path, genome_size: int = 486_000_000) -> dict[str, float]:
    flagstat = _run(["samtools", "flagstat", str(bam)])
    mapped = 0
    total_reads = 0
    dup = 0
    for line in flagstat.splitlines():
        if "in total" in line and "primary" not in line:
            total_reads = int(line.split()[0])
        elif "primary mapped" in line:
            mapped = int(line.split()[0])
        elif line.endswith("duplicates") and "primary" not in line:
            dup = int(line.split()[0])
    if mapped == 0:
        for line in flagstat.splitlines():
            if "mapped (" in line and "primary" not in line:
                mapped = int(line.split()[0])
                break

    on_target_s = _run(
        ["samtools", "view", "-c", "-F", "0x904", "-L", str(bed), str(bam)]
    ).strip()
    on_target = int(on_target_s) if on_target_s else 0

    bedcov = _run(["samtools", "bedcov", str(bed), str(bam)])
    cov = summarize_bedcov(bedcov)

    unique = max(0, mapped - dup)
    on_target_pct = 100.0 * on_target / mapped if mapped else 0.0
    expected = cov["target_bases"] / genome_size if genome_size else 0.0
    fold = (on_target / mapped) / expected if mapped and expected else float("nan")

    return {
        "total_reads": float(total_reads),
        "mapped_reads": float(mapped),
        "unique_reads": float(unique),
        "on_target_reads": float(on_target),
        "on_target_pct": on_target_pct,
        "fold_enrichment": fold,
        **cov,
    }


def qc_vcf(
    vcf: Path,
    sample: str | None = None,
    *,
    n_panel_sites: int | None = None,
) -> dict[str, float]:
    """Variant / calling-rate metrics from panel-targeted VCF.

    calling_rate = n_called / n_sites_vcf
    calling_rate_panel = n_called / n_panel_sites (if provided)
    """
    samples = _run(["bcftools", "query", "-l", str(vcf)]).splitlines()
    if not samples:
        return {}
    if sample is None:
        sid = samples[0]
    elif sample not in samples:
        raise ValueError(f"sample {sample!r} not found in {vcf}")
    else:
        sid = sample
    # GT, DP (DP may be missing → ".")
    fmt = "%CHROM\\t%POS\\t[%GT]\\t[%DP]\\n"
    out = _run(["bcftools", "query", "-s", sid, "-f", fmt, str(vcf)])

    n_sites = 0
    n_called = 0
    n_missing = 0
    n_hom_ref = 0
    n_het = 0
    n_hom_alt = 0
    dps: list[float] = []

    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        n_sites += 1
        gt = parts[2].replace("|", "/")
        dp_s = parts[3] if len(parts) > 3 else "."
        alleles = gt.split("/")
        if len(alleles) != 2 or not all(
            allele.isascii() and allele.isdigit() for allele in alleles
        ):
            n_missing += 1
            continue
        n_called += 1
        a, b = alleles[0], alleles[1]
        if a == "0" and b == "0":
            n_hom_ref += 1
        elif a != b:
            n_het += 1
        else:
            # 1/1, 2/2, …
            n_hom_alt += 1
        if dp_s not in {".", ""}:
            try:
                dps.append(float(dp_s))
            except ValueError:
                pass

    n_variant = n_het + n_hom_alt
    calling_rate = n_called / n_sites if n_sites else 0.0
    metrics: dict[str, float] = {
        "n_sites_vcf": float(n_sites),
        "n_called": float(n_called),
        "n_missing": float(n_missing),
        "calling_rate": calling_rate,
        "calling_rate_pct": 100.0 * calling_rate,
        "n_hom_ref": float(n_hom_ref),
        "n_het": float(n_het),
        "n_hom_alt": float(n_hom_alt),
        "n_variant": float(n_variant),
        "variant_rate": n_variant / n_called if n_called else 0.0,
        "het_rate": n_het / n_called if n_called else 0.0,
        "mean_dp_called": float(sum(dps) / len(dps)) if dps else float("nan"),
        "median_dp_called": float(statistics.median(dps)) if dps else float("nan"),
    }
    if n_panel_sites and n_panel_sites > 0:
        metrics["n_panel_sites_ref"] = float(n_panel_sites)
        metrics["calling_rate_panel"] = n_called / n_panel_sites
        metrics["calling_rate_panel_pct"] = 100.0 * n_called / n_panel_sites
        metrics["sites_recovered_pct"] = 100.0 * n_sites / n_panel_sites
    return metrics


def qc_sample(
    bam: Path,
    bed: Path,
    vcf: Path | None = None,
    sample: str | None = None,
    genome_size: int = 486_000_000,
) -> dict[str, float]:
    """Combine BAM enrichment QC with VCF calling / variant stats."""
    metrics = qc_bam(bam, bed, genome_size=genome_size)
    if vcf and Path(vcf).exists():
        n_panel = int(metrics.get("n_panel_sites") or bed_n_intervals(bed))
        metrics.update(qc_vcf(vcf, sample=sample, n_panel_sites=n_panel))
    return metrics


def write_tsv(metrics: dict[str, float], out_tsv: Path, sample: str) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)

    def _fmt(v: float) -> str:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return "NA"
        if isinstance(v, float) and v == int(v) and abs(v) < 1e12:
            return str(int(v))
        return f"{v:.6g}" if isinstance(v, float) else str(v)

    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample", *metrics.keys()])
        w.writerow([sample, *[_fmt(metrics[k]) for k in metrics]])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bam", type=Path, required=True)
    p.add_argument("--bed", type=Path, required=True)
    p.add_argument("--vcf", type=Path, default=None)
    p.add_argument("--out-tsv", type=Path, required=True)
    p.add_argument("--sample", default="sample")
    p.add_argument("--genome-size", type=int, default=486_000_000)
    args = p.parse_args(argv)
    metrics = qc_sample(
        args.bam,
        args.bed,
        vcf=args.vcf,
        sample=args.sample,
        genome_size=args.genome_size,
    )
    write_tsv(metrics, args.out_tsv, args.sample)
    for k, v in metrics.items():
        print(f"{k}\t{v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
