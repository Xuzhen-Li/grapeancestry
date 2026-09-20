"""CLI entry point for grapeancestry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import click

from grapeancestry import __version__

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AnalysisPaths:
    """Report paths plus source-sample inputs used during analysis."""

    vcf: Path
    bam: Path
    source_damage_tsv: Path
    source_mapdamage_dir: Path
    report_qc_tsv: Path


def analysis_paths(
    root: Path,
    report_sample: str,
    source_sample: str | None = None,
) -> AnalysisPaths:
    """Resolve report outputs separately from source-sample analysis inputs."""
    source = source_sample or report_sample
    results = Path(root) / "results"
    return AnalysisPaths(
        vcf=results / f"{report_sample}.vcf.gz",
        bam=results / "bam" / f"{source}.markdup.bam",
        source_damage_tsv=results / f"{source}.damage.tsv",
        source_mapdamage_dir=results / f"{source}.mapDamage",
        report_qc_tsv=results / f"{report_sample}.qc.tsv",
    )


def query_output_collisions(
    targets: list[str],
    source_ids: list[str] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return generated query IDs reserved by source IDs."""
    reserved_ids = set(source_ids if source_ids is not None else targets)
    return tuple(
        (source, f"{source}_query")
        for source in targets
        if not source.endswith("_query") and f"{source}_query" in reserved_ids
    )


@click.group()
@click.version_option(__version__, prog_name="grapeancestry")
def main() -> None:
    """GrapeAncestry Suite — 167K capture panel analysis."""


def _post_analyze(
    sample: str,
    root: Path = ROOT,
    pca_color: str = "Grp",
    *,
    source_sample: str | None = None,
    admix_mode: str = "auto",
    admix_all_k: bool = True,
) -> None:
    """Full multi-domain report (Italy-style figures + tables)."""
    from grapeancestry.adna.damage_lite import (
        lite_damage_profile,
        load_sample_damage,
        run_mapdamage,
        write_damage_tsv,
    )
    from grapeancestry.core.merge_ref import merge_ref
    from grapeancestry.core.qc import qc_sample, write_tsv
    from grapeancestry.identity.run_ibs import kinship_top, run_identity
    from grapeancestry.report.build_report import build_bundle, render_full_html

    paths = analysis_paths(root, sample, source_sample=source_sample)
    vcf = paths.vcf
    bam = paths.bam
    bed = root / "data" / "panel" / "panel167k.sites.bed"
    from grapeancestry.core.dosage import resolve_cache

    cache = resolve_cache(root)
    ref = root / "data" / "ref" / "VS1.final.fa"
    panel_vcf = root / "data" / "panel" / "panel167k_2449.vcf.gz"
    admix_dir = root / "data" / "panel" / "admixture"

    # Merged VCF artifact (2449 + query); analysis still uses npz cache
    if vcf.exists() and panel_vcf.exists():
        merged = root / "results" / f"{sample}.merged.vcf.gz"
        if not Path(str(merged) + ".tbi").exists() and not Path(str(merged) + ".csi").exists():
            try:
                merge_ref([vcf], panel_vcf, merged)
                click.echo(f"merged → {merged}")
            except Exception as exc:  # noqa: BLE001
                click.echo(f"[warn] merge_ref failed: {exc}")

    if bam.exists() and bed.exists():
        metrics = qc_sample(
            bam,
            bed,
            vcf=vcf if vcf.exists() else None,
            sample=sample,
        )
        write_tsv(metrics, paths.report_qc_tsv, sample)

    if vcf.exists() and cache.exists():
        run_identity(vcf, sample, cache, root / "results" / f"{sample}.ibs.tsv", top_n=10)
        kinship_top(vcf, sample, cache, root / "results" / f"{sample}.kinship_top.tsv", top_n=20)

    damage_tsv = root / "results" / f"{sample}.damage.tsv"
    mapdmg_dir = root / "results" / f"{sample}.mapDamage"
    source_damage = None
    if paths.source_mapdamage_dir.exists() or paths.source_damage_tsv.exists():
        source_id = source_sample or sample
        source_damage = load_sample_damage(
            root,
            source_id,
            tsv=paths.source_damage_tsv,
        )
    prof = source_damage
    if prof is None and bam.exists() and ref.exists():
        try:
            run_mapdamage(bam, ref, mapdmg_dir)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"[warn] mapDamage failed: {exc}")
        prof = load_sample_damage(root, sample, tsv=damage_tsv)
        if prof is None:
            try:
                prof = lite_damage_profile(bam, ref, max_reads=80_000)
            except Exception as exc:  # noqa: BLE001
                click.echo(f"[warn] damage_lite failed: {exc}")
                prof = None
    if prof is not None:
        write_damage_tsv(prof.get("ct5") or [], damage_tsv, ga3=prof.get("ga3") or None)
    if prof is None and not damage_tsv.exists():
        damage_tsv = None

    bundle = build_bundle(
        sample,
        root,
        admix_dir=admix_dir if admix_dir.exists() else None,
        damage_tsv=damage_tsv if damage_tsv and Path(damage_tsv).exists() else None,
        pca_color=pca_color,
        merged_vcf=root / "results" / f"{sample}.merged.vcf.gz",
        admix_mode=admix_mode,
        admix_all_k=admix_all_k,
        source_sample_id=source_sample,
    )
    pca_path = root / "results" / f"{sample}.pca.tsv"
    pcs = list(bundle.pca_coords.get(sample) or bundle.pca_sample)
    while len(pcs) < 3:
        pcs.append(float("nan"))
    with pca_path.open("w") as fh:
        fh.write("sample\tPC1\tPC2\tPC3\tmethod\n")
        vals = [
            f"{x:.6f}" if math.isfinite(float(x)) else "NA"
            for x in pcs[:3]
        ]
        fh.write(f"{sample}\t" + "\t".join(vals) + f"\t{bundle.pca_method}\n")

    html_path = root / "results" / f"{sample}.report.html"
    render_full_html(bundle, html_path)
    click.echo(f"report → {html_path}")


def _sample_ids_from_yaml(samples_file: Path) -> list[str]:
    import yaml

    data = yaml.safe_load(samples_file.read_text()) or {}
    samples = data.get("samples") or {}
    return list(samples.keys())


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=True), default="config/mbp_demo.yaml")
@click.option("--samples", "samples_file", type=click.Path(exists=True), default="config/samples_demo.yaml")
@click.option("--mapping", type=click.Choice(["subref", "full"]), default=None)
@click.option("--sample", default=None, help="Target sample id (default: all in samples file)")
@click.option("-j", "--jobs", default=4, show_default=True)
@click.option("--analyze/--no-analyze", default=True, help="Run QC+IBS+PCA+HTML after VCF")
@click.option(
    "--as-query/--in-panel",
    default=False,
    help="Treat each called sample as a stranger and analyze it as {id}_query",
)
@click.option(
    "--force-query-vcf",
    is_flag=True,
    default=False,
    help="Replace an existing derived query VCF",
)
@click.option(
    "--pca-color",
    type=click.Choice(["Grp", "CON", "GEO", "Uti"]),
    default="Grp",
    show_default=True,
    help="Reference panel PCA point color column from 2449.info",
)
@click.option(
    "--admix-mode",
    type=click.Choice(["auto", "lookup", "nnls", "official"]),
    default="auto",
    show_default=True,
    help="auto=in-panel lookup; new samples on panel167k_nogwas use admixture -P for K=2–8; "
    "Science archive has no matching P; nnls/official force projection onto the selected family P",
)
@click.option(
    "--admix-all-k/--admix-k8-only",
    default=True,
    show_default=True,
    help="Project every K in 2–8 (default on for customer reports)",
)
def run(
    config_path: str,
    samples_file: str,
    mapping: str | None,
    sample: str | None,
    jobs: int,
    analyze: bool,
    as_query: bool,
    force_query_vcf: bool,
    pca_color: str,
    admix_mode: str,
    admix_all_k: bool,
) -> None:
    """End-to-end: fastq → panel VCF (+ default analyses)."""
    import subprocess

    root = ROOT
    cfg = Path(config_path)
    if not cfg.is_absolute():
        cfg = root / cfg
    samp = Path(samples_file)
    if not samp.is_absolute():
        samp = root / samp
    cmd = [
        "snakemake",
        "-s",
        str(root / "workflow" / "Snakefile"),
        "--configfile",
        str(cfg),
        "--config",
        f"samples_file={samp}",
    ]
    # snakemake: multiple --config flags replace (not merge); put all KEY=VALUE in one --config
    if mapping:
        cmd.append(f"mapping={mapping}")
    cmd.extend(["-j", str(jobs)])
    if sample:
        cmd.append(f"results/{sample}.vcf.gz")
    manifest_ids = _sample_ids_from_yaml(samp)
    targets = [sample] if sample else manifest_ids
    click.echo(" ".join(cmd))
    if analyze and as_query:
        collisions = query_output_collisions(targets, source_ids=manifest_ids)
        if collisions:
            details = ", ".join(f"{source} → {query}" for source, query in collisions)
            raise click.UsageError(
                "--as-query would overwrite source VCF target(s): "
                f"{details}"
            )
        for source in targets:
            if source.endswith("_query"):
                continue
            query_vcf = root / "results" / f"{source}_query.vcf.gz"
            if query_vcf.exists() and not force_query_vcf:
                raise click.UsageError(
                    f"query VCF already exists: {query_vcf}; "
                    "use --force-query-vcf to replace it"
                )
    subprocess.check_call(cmd, cwd=root)
    if analyze:
        if as_query:
            from grapeancestry.core.merge_ref import write_query_vcf

        for source in targets:
            source_vcf = root / "results" / f"{source}.vcf.gz"
            if not source_vcf.exists():
                click.echo(f"[warn] skip analyze {source}: no VCF")
                continue
            report_sample = source
            source_sample = None
            if as_query:
                source_sample = source
                if source.endswith("_query"):
                    report_sample = source
                else:
                    report_sample = f"{source}_query"
                    query_vcf = root / "results" / f"{report_sample}.vcf.gz"
                    if query_vcf.exists() and not force_query_vcf:
                        raise click.UsageError(
                            f"query VCF already exists: {query_vcf}; "
                            "use --force-query-vcf to replace it"
                        )
                    wrote = write_query_vcf(source_vcf, query_vcf, new_id=report_sample)
                    click.echo(f"stranger VCF → {query_vcf} sample={wrote}")
            _post_analyze(
                report_sample,
                root,
                pca_color=pca_color,
                source_sample=source_sample,
                admix_mode=admix_mode,
                admix_all_k=admix_all_k,
            )


@main.command()
@click.option("--bam", type=click.Path(exists=True), required=True)
@click.option("--bed", type=click.Path(exists=True), default="data/panel/panel167k.sites.bed")
@click.option("--vcf", type=click.Path(exists=True), default=None)
@click.option("--sample", default=None)
@click.option("--out-tsv", type=click.Path(), default=None)
def qc(
    bam: str,
    bed: str,
    vcf: str | None,
    sample: str | None,
    out_tsv: str | None,
) -> None:
    """Enrichment / panel coverage / calling-rate QC metrics."""
    from grapeancestry.core.qc import qc_sample, write_tsv

    root = ROOT
    bed_p = Path(bed) if Path(bed).is_absolute() else root / bed
    vcf_p = None
    if vcf:
        vcf_p = Path(vcf) if Path(vcf).is_absolute() else root / vcf
    if sample is not None:
        output_sample = sample
    elif vcf_p is not None:
        output_sample = vcf_p.name
        for suffix in (".vcf.gz", ".vcf"):
            if output_sample.endswith(suffix):
                output_sample = output_sample[: -len(suffix)]
                break
    else:
        output_sample = Path(bam).name
        for suffix in (".markdup.bam", ".bam"):
            if output_sample.endswith(suffix):
                output_sample = output_sample[: -len(suffix)]
                break
    out = (
        Path(out_tsv)
        if out_tsv
        else root / "results" / f"{output_sample}.qc.tsv"
    )
    metrics = qc_sample(Path(bam), bed_p, vcf=vcf_p, sample=sample)
    write_tsv(metrics, out, output_sample)
    for k, v in metrics.items():
        click.echo(f"{k}\t{v}")


@main.command()
@click.option("--vcf", type=click.Path(exists=True), required=True)
@click.option("--sample", required=True)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--out-tsv", type=click.Path(), default=None)
def identity(vcf: str, sample: str, cache: str | None, out_tsv: str | None) -> None:
    """IBS nearest-neighbor identity / clone matching."""
    from grapeancestry.core.dosage import resolve_cache
    from grapeancestry.identity.run_ibs import run_identity

    root = ROOT
    cache_p = Path(cache) if cache else resolve_cache(root)
    if cache and not cache_p.is_absolute():
        cache_p = root / cache
    out = Path(out_tsv) if out_tsv else root / "results" / f"{sample}.ibs.tsv"
    run_identity(Path(vcf), sample, cache_p, out)
    click.echo(f"wrote {out}")


@main.command()
@click.option("--vcf", type=click.Path(exists=True), required=True)
@click.option("--sample", required=True)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--info", type=click.Path(exists=True), default="data/panel/2449.info")
@click.option("--out-tsv", type=click.Path(), default=None)
def project(vcf: str, sample: str, cache: str | None, info: str, out_tsv: str | None) -> None:
    """PCA projection onto reference panel."""
    from grapeancestry.adna.run_project import run_project
    from grapeancestry.core.dosage import resolve_cache

    root = ROOT
    cache_p = Path(cache) if cache else resolve_cache(root)
    if cache and not cache_p.is_absolute():
        cache_p = root / cache
    info_p = Path(info) if Path(info).is_absolute() else root / info
    out = Path(out_tsv) if out_tsv else root / "results" / f"{sample}.pca.tsv"
    run_project(Path(vcf), sample, cache_p, info_p, out, root / "results" / "ref_pca.tsv")
    click.echo(f"wrote {out}")

@main.command()
@click.option("--pheno", type=click.Path(exists=True), required=True)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--out-tsv", type=click.Path(), default=None)
@click.option("--trait", default=None)
@click.option("--source", default="euvitis")
@click.option("--all-traits", is_flag=True, default=False)
@click.option("--curated", is_flag=True, default=False)
@click.option("--binary", is_flag=True, default=False)
@click.option("--pcs", default=3, show_default=True)
@click.option("--maf", default=0.05, show_default=True)
@click.option("--min-n", default=50, show_default=True)
@click.option("--max-sites", type=int, default=None)
def gwas(
    pheno: str,
    cache: str | None,
    out_tsv: str | None,
    trait: str | None,
    source: str,
    all_traits: bool,
    curated: bool,
    binary: bool,
    pcs: int,
    maf: float,
    min_n: int,
    max_sites: int | None,
) -> None:
    """EMMAX/P3D GWAS on phenotype.tsv (requires ≥50 IDs overlapping the panel)."""
    from grapeancestry.breeding.gwas import (
        gwas_from_phenotype,
        load_phenotype,
        phenotype_is_usable,
        run_gwas_all,
        run_gwas_trait,
    )
    from grapeancestry.breeding.provenance import file_ref, write_provenance
    from grapeancestry.core.dosage import load_cache, resolve_cache

    cache_p = Path(cache) if cache else resolve_cache(ROOT)
    pheno_p = Path(pheno)
    out_dir = ROOT / "results" / "gwas"
    if all_traits or curated:
        idx = run_gwas_all(
            cache_p,
            pheno_p,
            ROOT / "results" / "phenotype" / "coverage.tsv",
            out_dir,
            min_n=min_n,
            curated_only=curated or not all_traits,
            root=ROOT,
            pcs=pcs,
            maf=maf,
            max_sites=max_sites,
        )
        click.echo(f"wrote {idx}")
        write_provenance(
            ROOT / "results" / "provenance",
            step="gwas",
            inputs=[file_ref(pheno_p), file_ref(cache_p)],
            parameters={
                "all_traits": all_traits,
                "curated": curated,
                "pcs": pcs,
                "maf": maf,
                "min_n": min_n,
            },
            counts={"index": str(idx)},
            methods=[
                {"name": "EMMAX/P3D", "ref_keys": ["kang2008", "kang2010", "zhang2010", "vanraden2008"]},
                {"name": "genomic_control", "ref_keys": ["devlin1999", "benjamini1995"]},
            ],
            outputs=[file_ref(idx)],
            caveats=[
                "167K panel includes 13,950 design-time GWAS sites; in-panel association only.",
                "Binary 0/1 traits use the same LMM as Kang 2010 WTCCC (doi:10.1038/ng.548 Online Methods: linear model on binary phenotypes). P-values can be unreliable when cases are highly imbalanced.",
            ],
            git_cwd=ROOT,
        )
        return
    if trait:
        sm = run_gwas_trait(
            cache_p,
            pheno_p,
            trait,
            source,
            out_dir,
            pcs=pcs,
            maf=maf,
            binary=binary,
            root=ROOT,
            max_sites=max_sites,
        )
        click.echo(f"GWAS {sm}")
        write_provenance(
            ROOT / "results" / "provenance",
            step="gwas",
            inputs=[file_ref(pheno_p), file_ref(cache_p)],
            parameters={"trait": trait, "source": source, "binary": binary, "pcs": pcs, "maf": maf},
            counts={k: sm.get(k) for k in (
                "n", "n_after_dedup", "m_sites_before", "m_after_maf",
                "m_after_missing", "n_pcs", "lambda_gc", "n_bonf", "n_fdr", "n_clumps",
            )},
            methods=[
                {"name": "EMMAX/P3D", "ref_keys": ["kang2008", "kang2010", "zhang2010", "vanraden2008"]},
            ],
            outputs=[file_ref(Path(sm["out_dir"]) / "assoc.tsv")] if sm.get("ok") else [],
            caveats=["167K panel is not a random-genome SNP set."],
            git_cwd=ROOT,
        )
        return
    mat, ref_ids, sites = load_cache(cache_p)
    phenomap = load_phenotype(pheno_p)
    ok, n = phenotype_is_usable(phenomap, ref_ids)
    if not ok:
        click.echo(f"GWAS skipped: {n} overlapping IDs < 50. Fill data/phenotype.tsv.")
        return
    res = gwas_from_phenotype(mat, ref_ids, sites, phenomap)
    out = Path(out_tsv) if out_tsv else ROOT / "results" / "gwas.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    nlp = res.get("nlp")
    with out.open("w") as fh:
        fh.write("site\tneglog10p\n")
        if nlp is not None:
            for s, v in zip(res.get("sites") or sites[: len(nlp)], nlp):
                fh.write(f"{s}\t{float(v):.4f}\n")
    click.echo(f"wrote {out} n={res.get('n')}")


@main.command("gs-train")
@click.option("--pheno", type=click.Path(exists=True), required=True)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--trait", default=None)
@click.option("--source", default="euvitis")
@click.option("--all-traits", is_flag=True, default=False)
@click.option("--curated", is_flag=True, default=False)
@click.option("--binary", is_flag=True, default=False)
@click.option("--with-bayes", is_flag=True, default=False)
@click.option("--min-n", default=50, show_default=True)
@click.option("--max-sites", type=int, default=3000, show_default=True)
@click.option("--k-folds", default=3, show_default=True)
@click.option("--repeats", default=1, show_default=True)
def gs_train(
    pheno: str,
    cache: str | None,
    trait: str | None,
    source: str,
    all_traits: bool,
    curated: bool,
    binary: bool,
    with_bayes: bool,
    min_n: int,
    max_sites: int | None,
    k_folds: int,
    repeats: int,
) -> None:
    """k-fold CV genomic selection; writes results/gs/{source}/{slug}/model.npz."""
    import csv

    from grapeancestry.breeding.gwas import CURATED_GWAS
    from grapeancestry.breeding.gs import run_gs_train
    from grapeancestry.breeding.provenance import file_ref, write_provenance
    from grapeancestry.core.dosage import resolve_cache

    cache_p = Path(cache) if cache else resolve_cache(ROOT)
    jobs: list[tuple[str, str, bool]] = []
    if curated or (all_traits and not trait):
        if curated or not all_traits:
            jobs = list(CURATED_GWAS)
        else:
            cov = ROOT / "results" / "phenotype" / "coverage.tsv"
            with cov.open() as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    if int(float(row["n_nonmissing"])) < min_n:
                        continue
                    jobs.append((row["source"], row["trait"], False))
    elif trait:
        jobs = [(source, trait, binary)]
    else:
        raise click.UsageError("provide --trait, --curated, or --all-traits")
    index_rows = []
    gs_root = ROOT / "results" / "gs"
    last = {}
    for src, tr, binv in jobs:
        sm = run_gs_train(
            cache_p,
            Path(pheno),
            tr,
            src,
            gs_root,
            binary=binv,
            min_n=min_n,
            with_bayes=with_bayes and binv,
            max_sites=max_sites,
            k_folds=k_folds,
            repeats=repeats,
        )
        if not sm.get("ok"):
            click.echo(f"skip {src} {tr} n={sm.get('n')}")
            continue
        last = sm
        index_rows.append(sm)
        click.echo(f"GS {src} {tr} best={sm['best_model']} r={sm['cv_r']:.3f} n={sm['n']}")
    idx = gs_root / "index.tsv"
    idx.parent.mkdir(parents=True, exist_ok=True)
    with idx.open("w") as fh:
        fh.write("source\ttrait\tscale\tn\tbest_model\tcv_r\tcv_r_sd\n")
        for sm in index_rows:
            fh.write(
                f"{sm['source']}\t{sm['trait']}\t{'binary' if sm['binary'] else 'ordinal'}\t"
                f"{sm['n']}\t{sm['best_model']}\t{sm['cv_r']}\t{sm['cv_r_sd']}\n"
            )
    write_provenance(
        ROOT / "results" / "provenance",
        step="gs_train",
        inputs=[file_ref(Path(pheno)), file_ref(cache_p)],
        parameters={
            "jobs": len(jobs),
            "with_bayes": with_bayes,
            "min_n": min_n,
            "max_sites": max_sites,
            "k_folds": k_folds,
            "repeats": repeats,
        },
        counts={
            "n_jobs": len(jobs),
            "n_ok": len(index_rows),
            "per_trait": [
                {
                    "trait": sm["trait"],
                    "source": sm["source"],
                    "best_model": sm["best_model"],
                    "cv_r": sm["cv_r"],
                    "n": sm["n"],
                }
                for sm in index_rows
            ],
        },
        methods=[
            {"name": "GBLUP-REML", "ref_keys": ["vanraden2008", "habier2007"]},
            {"name": "rrBLUP", "ref_keys": ["meuwissen2001", "endelman2011"]},
            {"name": "RKHS", "ref_keys": ["gianola2008", "delosCampos2010", "perez2014"]},
            {"name": "elastic_net", "ref_keys": ["zou2005", "beck2009", "ogutu2012"]},
        ],
        outputs=[file_ref(idx)],
        caveats=["CNN/MLP are not DeepGS/DNNGP reimplementations (ma2018, wang2023 background only)."],
        git_cwd=ROOT,
    )
    click.echo(f"wrote {idx}")


@main.command("gs-predict")
@click.option("--sample", required=True)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--min-cv-r", default=0.3, show_default=True)
@click.option("--vcf", type=click.Path(exists=True), default=None)
def gs_predict(sample: str, cache: str | None, min_cv_r: float, vcf: str | None) -> None:
    """Predict GEBVs for a sample from saved GS models."""
    from grapeancestry.breeding.gs import run_gs_predict
    from grapeancestry.breeding.provenance import file_ref, write_provenance
    from grapeancestry.core.dosage import resolve_cache

    cache_p = Path(cache) if cache else resolve_cache(ROOT)
    out = ROOT / "results" / f"{sample}.gs_pred.tsv"
    path = run_gs_predict(
        sample,
        cache_p,
        ROOT / "results" / "gs",
        out,
        min_cv_r=min_cv_r,
        query_vcf=Path(vcf) if vcf else None,
    )
    write_provenance(
        ROOT / "results" / "provenance",
        step="gs_predict",
        inputs=[file_ref(cache_p)],
        parameters={"sample": sample, "min_cv_r": min_cv_r},
        counts={"out": str(path)},
        methods=[{"name": "rrBLUP_predict", "ref_keys": ["meuwissen2001"]}],
        outputs=[file_ref(path)],
        caveats=[],
        git_cwd=ROOT,
    )
    click.echo(f"wrote {path}")


@main.command("cross-recommend")
@click.option("--target", required=True, help='e.g. "OIV 225=1,OIV 241=1"')
@click.option("--parent", default=None)
@click.option("--top", default=50, show_default=True)
@click.option("--no-kin-filter", is_flag=True, default=False)
@click.option("--cache", type=click.Path(exists=True), default=None)
@click.option("--vcf", type=click.Path(exists=True), default=None)
def cross_recommend(
    target: str,
    parent: str | None,
    top: int,
    no_kin_filter: bool,
    cache: str | None,
    vcf: str | None,
) -> None:
    """Rank crosses by usefulness / desirability index."""
    from grapeancestry.breeding.cross import run_cross_recommend
    from grapeancestry.breeding.provenance import file_ref, write_provenance
    from grapeancestry.core.dosage import resolve_cache

    cache_p = Path(cache) if cache else resolve_cache(ROOT)
    name = f"{parent or 'panel'}_mates"
    out = ROOT / "results" / "cross" / f"{name}.tsv"
    sm = run_cross_recommend(
        cache_path=cache_p,
        gs_root=ROOT / "results" / "gs",
        target=target,
        out_tsv=out,
        annot_path=ROOT / "data" / "panel" / "sample_annot.tsv",
        parent=parent,
        parent_vcf=Path(vcf) if vcf else None,
        top=top,
        kin_filter=not no_kin_filter,
    )
    write_provenance(
        ROOT / "results" / "provenance",
        step="cross_recommend",
        inputs=[file_ref(cache_p)],
        parameters={"target": target, "parent": parent, "top": top, "kin_filter": not no_kin_filter},
        counts=sm,
        methods=[
            {"name": "usefulness_criterion", "ref_keys": ["zhong2007", "lehermeier2017"]},
            {"name": "KING_filter", "ref_keys": ["manichaikul2010"]},
        ],
        outputs=[file_ref(out)],
        caveats=[
            "Progeny variance ignores LD (no genetic map).",
            "Genomic mating optimiser (akdemir2016) not implemented.",
        ],
        git_cwd=ROOT,
    )
    click.echo(f"wrote {out} {sm}")



@main.command()
@click.option("--sample", required=True, help="Accession / VCF sample id (e.g. HUN89)")
@click.option(
    "--source-sample",
    default=None,
    help="Original sample id for source BAM/mapDamage lineage",
)
@click.option(
    "--force-query-vcf",
    is_flag=True,
    default=False,
    help="Replace an existing derived query VCF",
)
@click.option(
    "--as-query/--in-panel",
    default=False,
    help="Treat an independently called VCF as a stranger: rename to {id}_query, "
    "do not lookup the 2449 row; project onto frozen P (chip P until panel167k ingest)",
)
@click.option(
    "--admix-mode",
    type=click.Choice(["auto", "lookup", "nnls", "official"]),
    default="auto",
    show_default=True,
)
@click.option(
    "--admix-all-k/--admix-k8-only",
    default=True,
    show_default=True,
)
@click.option(
    "--pca-color",
    type=click.Choice(["Grp", "CON", "GEO", "Uti"]),
    default="Grp",
    show_default=True,
)
def analyze(
    sample: str,
    source_sample: str | None,
    force_query_vcf: bool,
    as_query: bool,
    admix_mode: str,
    admix_all_k: bool,
    pca_color: str,
) -> None:
    """QC + IBS + PCA + ADMIXTURE HTML from an existing results/{sample}.vcf.gz."""
    from grapeancestry.adna.panel167k_nogwas import panel167k_assets_complete
    from grapeancestry.core.merge_ref import write_query_vcf

    root = ROOT
    src = root / "results" / f"{sample}.vcf.gz"
    if as_query:
        original_id = sample
        if sample.endswith("_query"):
            qid = sample
            qvcf = src
            if not qvcf.exists():
                raise click.UsageError(f"missing {qvcf}")
            source_sample = source_sample or original_id
        else:
            if not src.exists():
                raise click.UsageError(f"missing {src}")
            qid = f"{sample}_query"
            qvcf = root / "results" / f"{qid}.vcf.gz"
            if qvcf.exists() and not force_query_vcf:
                raise click.UsageError(
                    f"query VCF already exists: {qvcf}; "
                    "use --force-query-vcf to replace it"
                )
            wrote = write_query_vcf(src, qvcf, new_id=qid)
            click.echo(f"stranger VCF → {qvcf} sample={wrote}")
            source_sample = source_sample or original_id
        sample = qid
        if admix_mode == "auto" and not panel167k_assets_complete(root / "data" / "panel" / "admixture"):
            admix_mode = "official"
            click.echo(
                "[note] panel167k_nogwas P not ingested; stranger sample uses "
                "chip-P projection (official -P, NNLS fallback), not Science lookup"
            )
    elif not src.exists():
        raise click.UsageError(f"missing {src}")
    _post_analyze(
        sample,
        root,
        pca_color=pca_color,
        source_sample=source_sample,
        admix_mode=admix_mode,
        admix_all_k=admix_all_k,
    )


@main.command("admix-project")
@click.option(
    "--vcf",
    "vcfs",
    multiple=True,
    type=click.Path(exists=True),
    help="Query VCF (repeat). Missing sites vs panel167k_nogwas.sites.txt → ./.",
)
@click.option(
    "--sample-list",
    type=click.Path(exists=True),
    default=None,
    help="Text file: one VCF path per line (comments with #)",
)
@click.option("--out-dir", type=click.Path(), default=None)
@click.option(
    "--admix-mode",
    type=click.Choice(["auto", "nnls", "official"]),
    default="auto",
    show_default=True,
)
@click.option("--html/--no-html", default=True, help="Write K=2–8 interactive HTML per sample")
def admix_project(
    vcfs: tuple[str, ...],
    sample_list: str | None,
    out_dir: str | None,
    admix_mode: str,
    html: bool,
) -> None:
    """Project N query VCFs onto frozen panel167k_nogwas P (K=2–8)."""
    from grapeancestry.adna.admix_project import project_query_vcfs
    from grapeancestry.adna.admixture import load_admixture_k_range
    from grapeancestry.adna.panel167k_nogwas import PANEL167K_NOGWAS_FAMILY, panel167k_assets_complete
    from grapeancestry.report.build_report import write_admix_k28_report

    root = ROOT
    paths: list[Path] = [Path(v) for v in vcfs]
    if sample_list:
        for line in Path(sample_list).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line)
            if not p.is_absolute():
                p = root / p
            paths.append(p)
    if not paths:
        raise click.UsageError("pass --vcf and/or --sample-list")
    admix_dir = root / "data" / "panel" / "admixture"
    if not panel167k_assets_complete(admix_dir):
        click.echo(
            "[warn] panel167k_nogwas Q+P not ingested yet; cannot freeze-then -P. "
            "Run HPC fit + scripts/ingest_admixture_qp.py first."
        )
        raise SystemExit(2)
    dest = Path(out_dir) if out_dir else root / "results" / "admix_project"
    dest.mkdir(parents=True, exist_ok=True)
    projected = project_query_vcfs(
        paths,
        admix_dir,
        out_dir=dest,
        method=admix_mode,
        run_family=PANEL167K_NOGWAS_FAMILY,
        workdir=dest / "work",
    )
    for sid, by_k in projected.items():
        click.echo(f"{sid} Ks={sorted(by_k)}")
        if not html:
            continue
        contrast = load_admixture_k_range(
            sid,
            admix_dir,
            info_path=root / "data" / "panel" / "2449.info",
            mode="lookup",
            run_family=PANEL167K_NOGWAS_FAMILY,
        )
        if contrast is None:
            continue
        contrast.projected_by_k = by_k
        if not contrast.q_by_k:
            contrast.source = "projected_panel167k_p"
            contrast.projection_status = "panel167k_P_projection"
        write_admix_k28_report(sid, root, dest / f"{sid}.report.html", contrast)
        click.echo(f"report → {dest / sid}.report.html")
    click.echo(f"wrote {dest}")


@main.command("chip-report")
@click.option("--vcf", type=click.Path(exists=True), required=True)
@click.option("--sample", default=None)
@click.option("--out", type=click.Path(), default=None)
def chip_report(vcf: str, sample: str | None, out: str | None) -> None:
    """Python-only chip companion JSON (no bcftools). Cloud/Docker same path."""
    import json

    from grapeancestry.cloud.analyze import analyze_parsed, reports_as_dicts
    from grapeancestry.cloud.sites import load_panel_sites
    from grapeancestry.cloud.vcf_py import parse_vcf_path

    panel = set(load_panel_sites(ROOT))
    parsed = parse_vcf_path(Path(vcf), panel_sites=panel or None)
    payload = reports_as_dicts(analyze_parsed(parsed, ROOT, sample=sample))
    text = json.dumps(payload, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        click.echo(out)
    else:
        click.echo(text)


@main.command()
@click.option("--vcf", type=click.Path(exists=True), required=True)
@click.option("--out", type=click.Path(), default=None)
@click.option("--k", default=5, show_default=True)
def impute(vcf: str, out: str | None, k: int) -> None:
    """k-NN impute missing dosages from the 2449 fingerprint (not GLIMPSE2)."""
    import csv

    from grapeancestry.cloud.pack import load_fingerprint
    from grapeancestry.cloud.sites import load_panel_sites
    from grapeancestry.cloud.vcf_py import parse_vcf_path
    from grapeancestry.resource.impute import site_map_impute

    packed = load_fingerprint(ROOT)
    if packed is None:
        raise click.UsageError("need data/cloud/fingerprint.npz (python -m grapeancestry.cloud)")
    mat, ids, sites = packed
    panel = set(load_panel_sites(ROOT))
    parsed = parse_vcf_path(Path(vcf), panel_sites=panel or None)
    dest = Path(out) if out else ROOT / "results" / f"{parsed.samples[0]}.imputed.tsv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["sample", "site", "observed", "imputed", "k"])
        for sid, smap in parsed.dosages.items():
            filled, meta = site_map_impute(smap, mat, sites, k=k, ref_ids=ids)
            click.echo(f"{sid} n_imputed={meta['n_imputed']} / missing={meta['n_missing']}")
            for s in sites:
                obs = int(smap.get(s, -1))
                imp = int(filled.get(s, -1))
                if obs < 0 or obs != imp:
                    w.writerow([sid, s, obs, imp, k])
    click.echo(dest)
    click.echo("# haplotype GLIMPSE2 remains HPC-only; this command is panel k-NN.")


@main.command("catalog")
@click.option("--id", "sample_id", required=True)
def catalog_cmd(sample_id: str) -> None:
    """VIVC / passport / OIV row for a panel ID."""
    import json

    from grapeancestry.cloud.catalog import record_for
    from grapeancestry.identity.catalog import catalog_row

    payload = {"passport": catalog_row(sample_id, ROOT), "oiv": record_for(sample_id, ROOT)}
    click.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@main.command("gea")
@click.option("--out-dir", type=click.Path(), default=None)
def gea_cmd(out_dir: str | None) -> None:
    """Fst by GEO + dosage~origin-longitude Spearman on the fingerprint pack."""
    from grapeancestry.cloud.pack import load_fingerprint
    from grapeancestry.identity.catalog import load_info, load_passport, passport_path
    from grapeancestry.popgen.gea import gea_panel, load_lonlat, write_gea_tables

    packed = load_fingerprint(ROOT)
    if packed is None:
        raise click.UsageError("need data/cloud/fingerprint.npz")
    mat, ids, sites = packed
    info = load_info(ROOT / "data" / "panel" / "2449.info")
    passp = load_passport(str(passport_path(ROOT)))
    groups = [info.get(i, {}).get("GEO", "") for i in ids]
    origins = [passp.get(i, {}).get("Origin", "") for i in ids]
    lonlat = load_lonlat(ROOT / "data" / "panel" / "country_lonlat.tsv")
    payload = gea_panel(mat, sites, origins, groups, lonlat)
    dest = Path(out_dir) if out_dir else ROOT / "results" / "gea"
    write_gea_tables(payload, dest)
    click.echo(f"n_origin={payload['n_with_origin_lon']} mean_|r|={payload['mean_abs_spearman']}")
    click.echo(dest)


@main.command("locus-search")
@click.option("--query", required=True)
@click.option("--limit", default=20, show_default=True)
def locus_search(query: str, limit: int) -> None:
    """Search MAS + trait_locus + 167K site list (no bcftools)."""
    import json

    from grapeancestry.resource.portal import search_panel

    click.echo(json.dumps(search_panel(ROOT, query, limit=limit), indent=2))


@main.command("seq-score")
@click.option("--out", type=click.Path(), default=None)
@click.option("--lm/--no-lm", default=False, show_default=True, help="Try DNA LM (PlantCaduceus or HyenaDNA)")
def seq_score(out: str | None, lm: bool) -> None:
    """Score MAS SNP flanks: VS-1 sequence + Markov; optional DNA LM."""
    from grapeancestry.resource.seqscore import score_mas, write_tsv

    dest = Path(out) if out else ROOT / "results" / "seqscore" / "mas.tsv"
    rows = score_mas(ROOT, use_lm=lm)
    write_tsv(rows, dest)
    cloud = ROOT / "data" / "cloud" / "seqscore_mas.tsv"
    cloud.parent.mkdir(parents=True, exist_ok=True)
    cloud.write_text(dest.read_text())
    for r in rows:
        click.echo(
            f"{r['site']}\t{r['gene']}\t{r['vcf_ref']}/{r['vcf_alt']}\t"
            f"{r['center_snippet']}\tmarkov_delta={r.get('markov_delta')}\t"
            f"lm={r.get('lm_status', '')}"
        )
    click.echo(dest)


@main.command("selection")
@click.option("--half-bp", default=50_000, show_default=True, type=int)
@click.option("--top", default=40, show_default=True, type=int)
def selection_cmd(half_bp: int, top: int) -> None:
    """Unphased 167K windowed het + Fst by Grp; per-Grp het and Fst vs rest."""
    from grapeancestry.popgen.selscan import run_from_root

    scan = run_from_root(ROOT, half_bp=half_bp, top_n=top)
    dest = ROOT / "results" / "selection" / "named_windows.tsv"
    for r in scan["named"]:
        click.echo(
            f"{r['name']}\t{r['chrom']}:{r['start']}-{r['end']}\t"
            f"n={r['n_sites']}\thet={r['mean_het']:.4f}\tfst={r['mean_fst']:.4f}"
        )
    click.echo(dest)
    by = scan.get("by_grp") or {}
    used = by.get("groups_used") or []
    if used:
        click.echo(
            "by_grp\t"
            + ",".join(f"{r['grp']}(n={r['n']})" for r in used)
        )
        click.echo(ROOT / "results" / "selection" / "by_grp_named.tsv")
    sm = scan.get("vs_summary") or {}
    if sm:
        click.echo(
            "vs_science\t"
            f"bins={sm.get('n_s29_bins')}\t"
            f"chip={sm.get('n_s29_with_chip')}\t"
            f"fst_top_in_s29={sm.get('n_fst_top_in_s29')}/{sm.get('n_fst_top')}\t"
            f"het_dips_in_s29={sm.get('n_het_dips_in_s29')}/{sm.get('n_het_dips')}"
        )
        click.echo(ROOT / "results" / "selection" / "vs_science_s29.tsv")
    lz = ROOT / "results" / "selection" / "locuszoom.json"
    if lz.exists():
        click.echo(lz)


if __name__ == "__main__":
    main()
