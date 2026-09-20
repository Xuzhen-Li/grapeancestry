"""PCA projection CLI — smartPCA (EIGENSOFT), Italy ``smartPCA.md`` style."""

from __future__ import annotations

import argparse
from pathlib import Path

from grapeancestry.adna.smartpca_project import run_smartpca_project, write_pca_tsvs
from grapeancestry.core.dosage import load_cache, load_sample_dosage

SUITE_ROOT = Path(__file__).resolve().parents[3]


def run_project(
    query_vcf: Path,
    sample: str,
    cache_npz: Path,
    info_tsv: Path,
    out_sample_tsv: Path,
    out_ref_tsv: Path,
    *,
    n_components: int = 2,
    workdir: Path | None = None,
    allele_annot: Path | None = None,
) -> None:
    mat, ref_ids, sites = load_cache(cache_npz)
    ok = (mat >= 0).sum(axis=0) > mat.shape[0] * 0.5
    mat = mat[:, ok]
    sites = [s for s, keep in zip(sites, ok) if keep]
    q = load_sample_dosage(query_vcf, sample, sites)

    meta: dict[str, dict[str, str]] = {}
    if info_tsv.exists():
        with info_tsv.open() as fh:
            header = fh.readline().rstrip("\n").split("\t")
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                row = dict(zip(header, parts))
                meta[row.get("ID", parts[0])] = row

    pops = [meta.get(s, {}).get("Grp", "REF") or "REF" for s in ref_ids]
    annot = allele_annot or (SUITE_ROOT / "data" / "panel" / "locus_annot.tsv")
    wd = workdir or (SUITE_ROOT / "results" / "smartpca" / sample)

    result = run_smartpca_project(
        ref_ids,
        mat,
        [sample],
        q,
        sites,
        annot,
        wd,
        n_pcs=n_components,
        pop_labels=pops,
    )
    write_pca_tsvs(result, out_sample_tsv, out_ref_tsv, meta)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query-vcf", type=Path, required=True)
    p.add_argument("--sample", required=True)
    p.add_argument("--cache", type=Path, default=Path("results/cache/panel_dosage_5k.npz"))
    p.add_argument("--info", type=Path, default=Path("data/panel/2449.info"))
    p.add_argument("--out-sample", type=Path, required=True)
    p.add_argument("--out-ref", type=Path, default=Path("results/ref_pca.tsv"))
    args = p.parse_args(argv)
    run_project(args.query_vcf, args.sample, args.cache, args.info, args.out_sample, args.out_ref)
    print(f"wrote {args.out_sample} and {args.out_ref} (smartpca)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
