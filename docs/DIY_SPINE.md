# DIY spine (`00a`→`13b`)

One-page map. Detail pages: [`steps/`](steps/). You must supply **VS-1 + 2449** assets (not in public git).

| Step | Goal | Entry |
|------|------|-------|
| 00a | Panel sites + sample metadata | [`steps/00a`](steps/00a-panel-sites-and-metadata.md) |
| 00b | Reference genome (VS-1) | [`steps/00b`](steps/00b-reference-genome.md) |
| 00c | Panel VCF + dosage cache | [`steps/00c`](steps/00c-panel-vcf-and-dosage-cache.md) · `python -m grapeancestry.core.dosage` |
| 00d | Freeze PCA axes | [`steps/00d`](steps/00d-frozen-pca-axes.md) · suite `gcta64` |
| 00e | Freeze ADMIXTURE Q/P (K=2–8) | [`steps/00e`](steps/00e-frozen-admixture-qp.md) · ADMIXTURE 1.3.0 |
| 00f–00g | Phenotypes / optional cloud pack | skip if ancestry-only |
| 01a | Trim + map to VS-1 | `grapeancestry run` · Snakefile `fastp` / AdapterRemoval3 → `bwa` |
| 01b | Markdup + call at 167K BED | same · `samtools markdup` → `bcftools … -T` BED |
| 02a–02b | Capture QC + method coverage | `grapeancestry qc` · inside `analyze` |
| 03a–03b | Clone/PO + IBS/kinship | `grapeancestry identity` |
| 04a–04b | Load frozen PCA + project | `grapeancestry project` |
| 05a–05b | ADMIXTURE family + project Q | `grapeancestry admix-project` |
| 06a–06b | IBS distance + NJ | report-path only (`src/grapeancestry/popgen/tree_nj.py`) |
| 07a–07b | Optional aDNA damage | report-path / damage lite |
| 08–10 | f3/f4 · selection · GWAS | `grapeancestry selection` · `gwas` · f-stats report-path |
| 11a–11b | GS train/predict | `grapeancestry gs-train` · `gs-predict` (OIV 225 decision-grade) |
| 12a–12b | LocusZoom | report-path |
| 13a–13b | Sample-first V2 HTML | `grapeancestry analyze` / `run` → `*.sample-first-v2.report.html` |
| 14a–14b | Optional Cloud JSON | `grapeancestry chip-report` → `chip.json` (**not** v1 product) |

v1 product file remains **`*.sample-first-v2.report.html`**.
