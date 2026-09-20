"""Panel locus portal: annotation TSV + simple search (Python-only default)."""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


def build_locus_annot_from_sites(sites: list[str], out_tsv: Path) -> Path:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["chrom", "pos", "ref", "alt", "site"])
        for s in sites:
            chrom, _, pos = s.partition(":")
            w.writerow([chrom, pos, "", "", s])
    return out_tsv


def build_locus_annot(panel_vcf: Path, out_tsv: Path) -> Path:
    """Prefer bcftools REF/ALT; fall back to the 167K site list."""
    try:
        raw = subprocess.check_output(
            ["bcftools", "query", "-f", "%CHROM\t%POS\t%REF\t%ALT\n", str(panel_vcf)],
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        from grapeancestry.cloud.sites import load_panel_sites

        root = panel_vcf.resolve()
        for p in [root, *panel_vcf.parents]:
            if (p / "app.py").exists():
                return build_locus_annot_from_sites(load_panel_sites(p), out_tsv)
        raise
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["chrom", "pos", "ref", "alt", "site"])
        for line in raw.splitlines():
            chrom, pos, ref, alt = line.split("\t")
            w.writerow([chrom, pos, ref, alt, f"{chrom}:{pos}"])
    return out_tsv


def search_loci(annot_tsv: Path, query: str, limit: int = 20) -> list[dict]:
    q = query.lower()
    hits: list[dict] = []
    if not annot_tsv.exists():
        return hits
    with annot_tsv.open() as fh:
        r = csv.DictReader(fh, delimiter="\t")
        for row in r:
            blob = "\t".join(row.values()).lower()
            if q in blob:
                hits.append(row)
                if len(hits) >= limit:
                    break
    return hits


def search_panel(root: Path, query: str, limit: int = 20) -> list[dict]:
    """Python-only locus search: MAS + trait_locus + 167K site list."""
    q = query.lower().strip()
    if not q:
        return []
    hits: list[dict] = []
    from grapeancestry.cloud.mas import MAS_LOCI
    from grapeancestry.cloud.sites import load_panel_sites

    for loc in MAS_LOCI:
        blob = " ".join(str(v) for v in loc.values()).lower()
        if q in blob or q in loc["site"].lower():
            hits.append({"source": "MAS", **loc})
            if len(hits) >= limit:
                return hits
    trait = root / "data" / "trait_locus.tsv"
    if trait.exists():
        with trait.open(encoding="utf-8") as fh:
            hdr = fh.readline().rstrip("\n").split("\t")
            for line in fh:
                if q not in line.lower():
                    continue
                parts = line.rstrip("\n").split("\t")
                row = {hdr[i]: parts[i] if i < len(parts) else "" for i in range(len(hdr))}
                chrom, pos = row.get("chrom", ""), row.get("pos", "")
                hits.append({"source": "trait_locus", "site": f"{chrom}:{pos}", **row})
                if len(hits) >= limit:
                    return hits
    for site in load_panel_sites(root):
        if q in site.lower():
            chrom, _, pos = site.partition(":")
            hits.append({"source": "panel", "site": site, "chrom": chrom, "pos": pos})
            if len(hits) >= limit:
                return hits
    return hits


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--panel-vcf", type=Path, default=None)
    b.add_argument("--out", type=Path, default=Path("data/panel/locus_annot.tsv"))
    s = sub.add_parser("search")
    s.add_argument("--root", type=Path, default=Path("."))
    s.add_argument("--annot", type=Path, default=None)
    s.add_argument("--query", required=True)
    args = p.parse_args(argv)
    if args.cmd == "build":
        if args.panel_vcf and args.panel_vcf.exists():
            path = build_locus_annot(args.panel_vcf, args.out)
        else:
            from grapeancestry.cloud.sites import load_panel_sites

            path = build_locus_annot_from_sites(load_panel_sites(Path(".")), args.out)
        print(f"wrote {path}")
    else:
        if args.annot:
            rows = search_loci(args.annot, args.query)
        else:
            rows = search_panel(args.root, args.query)
        for row in rows:
            print("\t".join(str(v) for v in row.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
