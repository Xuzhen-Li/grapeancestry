#!/usr/bin/env python3
"""Build 167k-minus-GWAS site list (+ optional VCF/BED) for ADMIXTURE.

Writes:
  data/panel/admixture/gwas_exclude.tsv
  data/panel/admixture/gwas_exclude.bed
  data/panel/admixture/panel167k_nogwas.sites.txt
Optional (if --vcf / bcftools / plink):
  data/panel/admixture/bed/panel167k_nogwas.vcf.gz
  data/panel/admixture/bed/panel167k_nogwas.{bed,bim,fam}
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grapeancestry.adna.panel167k_nogwas import (  # noqa: E402
    EXPECTED_GWAS_IN_PANEL,
    EXPECTED_KEEP_SITES,
    EXPECTED_PANEL_SITES,
    count_summary,
    gwas_panel_split,
    load_panel_sites_bed,
    load_trait_locus_chrpos,
    write_exclude_and_sites,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--panel-bed", type=Path, default=None)
    p.add_argument("--trait-locus", type=Path, default=None)
    p.add_argument("--panel-vcf", type=Path, default=None)
    p.add_argument("--make-vcf", action="store_true", help="bcftools view -T ^exclude")
    p.add_argument("--make-bed", action="store_true", help="plink --make-bed (needs plink)")
    args = p.parse_args()
    root = args.root
    panel_bed = args.panel_bed or (root / "data" / "panel" / "panel167k.sites.bed")
    trait = args.trait_locus or (root / "data" / "trait_locus.tsv")
    panel_vcf = args.panel_vcf or (root / "data" / "panel" / "panel167k_2449.vcf.gz")
    admix = root / "data" / "panel" / "admixture"

    panel_sites = load_panel_sites_bed(panel_bed)
    gwas = load_trait_locus_chrpos(trait)
    keep, exclude = gwas_panel_split(panel_sites, gwas)
    summary = count_summary(len(panel_sites), len(exclude), len(keep))
    print(summary)
    if len(panel_sites) != EXPECTED_PANEL_SITES:
        raise SystemExit(f"panel sites {len(panel_sites)} != {EXPECTED_PANEL_SITES}")
    if len(exclude) != EXPECTED_GWAS_IN_PANEL:
        raise SystemExit(f"gwas-in-panel {len(exclude)} != {EXPECTED_GWAS_IN_PANEL}")
    if len(keep) != EXPECTED_KEEP_SITES:
        raise SystemExit(f"keep {len(keep)} != {EXPECTED_KEEP_SITES}")

    paths = write_exclude_and_sites(keep, exclude, admix)
    print("wrote", {k: str(v) for k, v in paths.items()})

    bed_dir = admix / "bed"
    if args.make_vcf or args.make_bed:
        if not shutil.which("bcftools"):
            raise SystemExit("bcftools not on PATH")
        if not panel_vcf.exists():
            raise SystemExit(f"missing {panel_vcf}")
        bed_dir.mkdir(parents=True, exist_ok=True)
        out_vcf = bed_dir / "panel167k_nogwas.vcf.gz"
        subprocess.check_call(
            [
                "bcftools",
                "view",
                "-T",
                f"^{paths['exclude_bed']}",
                "-Oz",
                "-o",
                str(out_vcf),
                str(panel_vcf),
            ]
        )
        subprocess.check_call(["bcftools", "index", "-t", str(out_vcf)])
        n_sites = subprocess.check_output(
            ["bcftools", "view", "-H", str(out_vcf)],
            text=True,
        ).count("\n")
        print(f"vcf sites {n_sites}")
        if n_sites != EXPECTED_KEEP_SITES:
            raise SystemExit(f"vcf sites {n_sites} != {EXPECTED_KEEP_SITES}")

    if args.make_bed:
        plink = shutil.which("plink")
        if not plink:
            print("plink not on PATH; skip --make-bed (run on HPC via admixture_k.sbatch)")
            return
        vcf = bed_dir / "panel167k_nogwas.vcf.gz"
        if not vcf.exists():
            raise SystemExit("run --make-vcf first or together with --make-bed")
        prefix = bed_dir / "panel167k_nogwas"
        subprocess.check_call(
            [
                plink,
                "--vcf",
                str(vcf),
                "--make-bed",
                "--out",
                str(prefix),
                "--allow-extra-chr",
                "--keep-allele-order",
            ]
        )
        print("wrote", prefix.with_suffix(".bed"))


if __name__ == "__main__":
    main()
